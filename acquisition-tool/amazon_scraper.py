"""Amazon listing scraper — Apify search → cheap pre-filter → detail fetch.

Cost optimisation: most rejected ASINs are killed at the search stage on the data
the search actor already returns (price, reviews, brand). Only survivors are sent
to the per-ASIN detail call, which is the expensive step.

Pipeline:
  1. Search Amazon by category seed across pages 2..6 (skip page 1 bestsellers).
  2. Pre-filter on search-stage data: price band, review band, brand blocklist,
     dedupe by brand_key (1 anchor per brand), drop ASINs already in DB.
  3. Fetch detail for survivors only — full bullets, A+ content, Q&A, images, BSR.
  4. Apply BSR filter post-detail (BSR rarely present on search pages).

Each surviving listing becomes a Prospect row with source='amazon_listing',
stage='LISTING_FOUND', and brand_key (normalised brand) for downstream rollup.
"""
import re
from datetime import datetime
from typing import Optional

import config
import db
from models import Prospect


def _normalize_brand(brand: str) -> str:
    if not brand:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", brand.lower()).strip()


def _brand_key(brand: str) -> str:
    return re.sub(r"\s+", "", _normalize_brand(brand))


def _coerce_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, dict):
        for k in ("value", "price", "amount"):
            if k in val and val[k] is not None:
                try:
                    return float(val[k])
                except (TypeError, ValueError):
                    pass
        return None
    try:
        return float(val) if val not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _coerce_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None


def _extract_bsr(item: dict) -> Optional[int]:
    raw = (
        item.get("bestSellersRank")
        or item.get("bestsellersRank")
        or item.get("salesRank")
        or item.get("bsr")
        or item.get("salesRanks")
    )
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            r = first.get("rank") or first.get("position") or first.get("value")
            try:
                return int(r) if r is not None else None
            except (TypeError, ValueError):
                return None
        if isinstance(first, str):
            raw = first
    if isinstance(raw, str):
        m = re.search(r"#?([\d,]+)", raw)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                return None
    return None


def _get_dataset_id(run) -> str:
    if not run:
        raise ValueError("Apify run failed or returned empty.")
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or ""
    return getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", "")) or ""



# ---------------------------------------------------------------------------
# Step 1 — search-stage harvest with cheap pre-filter
# ---------------------------------------------------------------------------

def _search_passes_prefilter(item: dict) -> tuple[bool, str]:
    """Apply price/review/brand filters on search-stage data (no detail call yet)."""
    brand = (item.get("brand") or item.get("manufacturer") or "").strip()
    norm_brand = _normalize_brand(brand)
    if norm_brand and norm_brand in config.AMAZON_BRAND_BLOCKLIST:
        return False, "blocklist"

    price = _coerce_float(item.get("price"))
    if price is not None and not (config.AMAZON_PRICE_MIN <= price <= config.AMAZON_PRICE_MAX):
        return False, "price"

    reviews = _coerce_int(
        item.get("reviewsCount")
        or item.get("numberOfReviews")
        or item.get("reviewCount")
        or item.get("countReview")
    )
    if reviews is not None and not (config.AMAZON_REVIEW_MIN <= reviews <= config.AMAZON_REVIEW_MAX):
        return False, "reviews"

    return True, ""


def _harvest_asins(client, category: str, limit: int, console=None) -> list[str]:
    """Search Amazon → drop junk ASINs cheaply → return ASIN list capped at `limit`."""
    if console:
        console.print(
            f"[dim]Step 1/3: harvesting ASINs via {config.APIFY_AMAZON_SEARCH_ACTOR_ID} "
            f"(pages {config.AMAZON_SEARCH_PAGE_START}-{config.AMAZON_SEARCH_PAGE_END})…[/dim]"
        )

    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")
    page_inputs = [
        {
            "keyword": category,
            "domainCode": domain_code,
            "sortBy": "relevanceblender",
            "page": page,
        }
        for page in range(config.AMAZON_SEARCH_PAGE_START, config.AMAZON_SEARCH_PAGE_END + 1)
    ]
    run = client.actor(config.APIFY_AMAZON_SEARCH_ACTOR_ID).call(run_input={"input": page_inputs})

    raw = list(client.dataset(_get_dataset_id(run)).iterate_items())

    asins: list[str] = []
    seen_asin: set[str] = set()
    seen_brand: dict[str, int] = {}
    rejects: dict[str, int] = {}
    cached = 0

    seen_asins = {item.get("asin") for item in raw if item.get("asin")}
    cached_asins = db.asins_that_exist(list(seen_asins)) if hasattr(db, 'asins_that_exist') else set()

    for item in raw:
        asin = item.get("asin") or item.get("ASIN")
        if not asin or asin in seen_asin:
            continue
        seen_asin.add(asin)

        # Skip ASINs already in the DB — paying detail cost again is waste.
        if asin in cached_asins:
            cached += 1
            continue

        # Cheap pre-filter on search-stage data.
        ok, reason = _search_passes_prefilter(item)
        if not ok:
            rejects[reason] = rejects.get(reason, 0) + 1
            continue

        # Brand cap — rollup picks one anchor per brand anyway.
        brand_key = _brand_key(item.get("brand") or item.get("manufacturer") or "")
        if brand_key:
            if seen_brand.get(brand_key, 0) >= config.AMAZON_MAX_ASINS_PER_BRAND:
                rejects["brand_cap"] = rejects.get("brand_cap", 0) + 1
                continue
            seen_brand[brand_key] = seen_brand.get(brand_key, 0) + 1

        asins.append(asin)
        if len(asins) >= limit:
            break

    if console:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(rejects.items())) or "(none)"
        console.print(
            f"[dim]  → {len(raw)} raw hits → {len(asins)} ASINs to detail "
            f"(cached={cached}, rejects: {breakdown})[/dim]"
        )

    return asins


# ---------------------------------------------------------------------------
# Step 2 — detail fetch on survivors only
# ---------------------------------------------------------------------------

def _fetch_listing_detail(client, asins: list[str], console=None) -> list[dict]:
    if not asins:
        return []
    if console:
        console.print(
            f"[dim]Step 2/3: fetching detail for {len(asins)} ASINs via "
            f"{config.APIFY_AMAZON_DETAIL_ACTOR_ID}…[/dim]"
        )

    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")
    # axesso amazon-product-details-scraper requires a `urls` list of Amazon product page URLs.
    # Build https://www.amazon.com/dp/<ASIN> for each ASIN.
    urls = [f"https://www.{config.AMAZON_DOMAIN}/dp/{a}" for a in asins]
    run_input = {
        "urls": urls,
        "domainCode": domain_code,
    }
    run = client.actor(config.APIFY_AMAZON_DETAIL_ACTOR_ID).call(run_input=run_input)
    return list(client.dataset(_get_dataset_id(run)).iterate_items())


# ---------------------------------------------------------------------------
# Step 3 — map detail item → Prospect, apply BSR filter, persist
# ---------------------------------------------------------------------------

def _to_prospect(item: dict, category: str) -> Optional[Prospect]:
    asin = item.get("asin") or item.get("ASIN")
    if not asin:
        return None
    title = (item.get("title") or item.get("productTitle") or "").strip()
    if not title:
        return None
    brand = (item.get("brand") or item.get("manufacturer") or "").strip() or "(unknown)"

    bullets = (
        item.get("features")
        or item.get("bulletPoints")
        or item.get("featureBullets")
        or item.get("productDescription")
        or []
    )
    if isinstance(bullets, str):
        bullets = [b for b in bullets.split("\n") if b.strip()]
    bullet_count = len(bullets) if isinstance(bullets, list) else 0
    bullets_joined = "\n".join(bullets)[:3000] if isinstance(bullets, list) else str(bullets)[:3000]

    images = item.get("images") or item.get("imageUrls") or item.get("highResolutionImages") or []
    image_count = len(images) if isinstance(images, list) else 0

    a_plus = (
        item.get("aPlusContent")
        or item.get("hasAplus")
        or item.get("a_plus")
        or item.get("hasAPlusContent")
    )
    has_a_plus = bool(a_plus) if a_plus not in (None, "", 0, False) else False

    qa = (
        item.get("questions")
        or item.get("qaCount")
        or item.get("questionsAnswered")
        or item.get("answeredQuestions")
    )
    if isinstance(qa, list):
        qa_count = len(qa)
    elif isinstance(qa, (int, float)):
        qa_count = int(qa)
    else:
        qa_count = 0

    rating = _coerce_float(item.get("stars") or item.get("rating") or item.get("productRating"))
    review_count = _coerce_int(
        item.get("reviewsCount")
        or item.get("numberOfReviews")
        or item.get("reviewCount")
        or item.get("countReview")
    ) or 0
    price = _coerce_float(item.get("price"))

    url = item.get("url") or f"https://{config.AMAZON_DOMAIN}/dp/{asin}"

    p = Prospect(
        id=f"asin_{asin}",
        username=brand,
        subreddit=category,
        post_title=title[:500],
        post_body=bullets_joined,
        post_url=url,
        stage="LISTING_FOUND",
        source="amazon_listing",
        asin=asin,
        brand=brand,
        category=category,
        listing_price=price,
        listing_rating=rating,
        listing_review_count=review_count,
        bullet_count=bullet_count,
        image_count=image_count,
        has_a_plus=has_a_plus,
        qa_count=qa_count,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    p.brand_key = _brand_key(brand)
    p._bsr = _extract_bsr(item)
    return p


def _passes_post_detail_filters(p: Prospect) -> tuple[bool, str]:
    """BSR is only reliably available post-detail; everything else was caught at search stage."""
    norm_brand = _normalize_brand(p.brand or "")
    if not norm_brand or norm_brand == "unknown":
        return False, "missing_brand"
    if norm_brand in config.AMAZON_BRAND_BLOCKLIST:
        return False, "blocklist"

    bsr = getattr(p, "_bsr", None)
    if bsr is not None and not (config.AMAZON_BSR_MIN <= bsr <= config.AMAZON_BSR_MAX):
        return False, "bsr"

    return True, ""


def scrape(category: str, limit: int = 100, console=None) -> tuple[int, int]:
    """End-to-end single-category scrape — kept for back-compat. Prefer
    `scrape_many` for multi-category runs to collapse N actor runs into 2."""
    return scrape_many([category], limit_per_category=limit, console=console)


def scrape_many(categories: list[str], limit_per_category: int = 100, console=None) -> tuple[int, int]:
    """Multi-category scrape — single batched search actor run + single batched
    detail actor run, regardless of how many seed categories are provided.

    Returns (kept, new_count) summed across categories.
    """
    if not config.APIFY_TOKEN:
        raise ValueError("APIFY_TOKEN is not set in .env")
    try:
        from apify_client import ApifyClient
    except ImportError:
        raise ImportError("apify-client is not installed. Run: pip install apify-client")

    client = ApifyClient(config.APIFY_TOKEN)
    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")

    # Build one search input list with every (category, page) pair.
    page_range = range(config.AMAZON_SEARCH_PAGE_START, config.AMAZON_SEARCH_PAGE_END + 1)
    search_inputs = []
    keyword_to_category: dict[str, str] = {}
    for cat in categories:
        keyword_to_category[cat.lower()] = cat
        for page in page_range:
            search_inputs.append({
                "keyword": cat,
                "domainCode": domain_code,
                "sortBy": "relevanceblender",
                "page": page,
            })

    if console:
        console.print(
            f"[dim]Batched search: {len(categories)} categories × "
            f"{len(list(page_range))} pages = {len(search_inputs)} inputs in 1 actor run…[/dim]"
        )

    # Apify actors typically accept up to a few hundred inputs in one run; shard if larger.
    raw_search: list[dict] = []
    shard = config.APIFY_BATCH_SIZE
    for i in range(0, len(search_inputs), shard):
        chunk = search_inputs[i : i + shard]
        run = client.actor(config.APIFY_AMAZON_SEARCH_ACTOR_ID).call(run_input={"input": chunk})
        raw_search.extend(client.dataset(_get_dataset_id(run)).iterate_items())

    # Per-category pre-filter, with brand cap and dedupe applied per category.
    category_state: dict[str, dict] = {
        cat: {"asins": [], "seen_asin": set(), "seen_brand": {}, "rejects": {}, "cached": 0, "raw_count": 0}
        for cat in categories
    }
    asin_to_category: dict[str, str] = {}

    # Collect all candidate ASINs first for batched existence check
    candidate_items: list[tuple[str, dict]] = []
    for item in raw_search:
        kw = (item.get("keyword") or item.get("searchQuery") or "").lower()
        cat = keyword_to_category.get(kw)
        if cat is None:
            # Some actors omit the keyword field on returned items — best-effort match
            # to the first category whose name is in the title; otherwise drop.
            title_lower = (item.get("title") or "").lower()
            for c in categories:
                if re.search(r'\b' + re.escape(c.lower()) + r'\b', title_lower):
                    cat = c
                    break
            if cat is None:
                continue
        st = category_state[cat]
        st["raw_count"] += 1

        asin = item.get("asin") or item.get("ASIN")
        if not asin or asin in st["seen_asin"]:
            continue
        st["seen_asin"].add(asin)
        candidate_items.append((cat, item))

    # Batch ASIN existence check
    all_candidate_asins = [item.get("asin") or item.get("ASIN") for _, item in candidate_items]
    existing_asins = db.asins_that_exist(all_candidate_asins) if all_candidate_asins else set()

    for cat, item in candidate_items:
        st = category_state[cat]
        asin = item.get("asin") or item.get("ASIN")

        if asin in existing_asins:
            st["cached"] += 1
            continue

        ok, reason = _search_passes_prefilter(item)
        if not ok:
            st["rejects"][reason] = st["rejects"].get(reason, 0) + 1
            continue

        brand_key = _brand_key(item.get("brand") or item.get("manufacturer") or "")
        if brand_key:
            if st["seen_brand"].get(brand_key, 0) >= config.AMAZON_MAX_ASINS_PER_BRAND:
                st["rejects"]["brand_cap"] = st["rejects"].get("brand_cap", 0) + 1
                continue
            st["seen_brand"][brand_key] = st["seen_brand"].get(brand_key, 0) + 1

        if len(st["asins"]) >= limit_per_category:
            continue
        st["asins"].append(asin)
        asin_to_category[asin] = cat

    if console:
        for cat, st in category_state.items():
            breakdown = ", ".join(f"{k}={v}" for k, v in sorted(st["rejects"].items())) or "(none)"
            console.print(
                f"[dim]  {cat}: {st['raw_count']} raw → {len(st['asins'])} ASINs "
                f"(cached={st['cached']}, rejects: {breakdown})[/dim]"
            )

    all_asins = list(asin_to_category.keys())
    if not all_asins:
        return 0, 0

    # Single batched detail call.
    if console:
        console.print(
            f"[dim]Batched detail: {len(all_asins)} ASINs in 1 actor run "
            f"({config.APIFY_AMAZON_DETAIL_ACTOR_ID})…[/dim]"
        )
    detail_items: list[dict] = []
    for i in range(0, len(all_asins), shard):
        chunk = all_asins[i : i + shard]
        urls = [f"https://www.{config.AMAZON_DOMAIN}/dp/{a}" for a in chunk]
        run = client.actor(config.APIFY_AMAZON_DETAIL_ACTOR_ID).call(
            run_input={"urls": urls, "domainCode": domain_code}
        )
        detail_items.extend(client.dataset(_get_dataset_id(run)).iterate_items())

    rejects: dict[str, int] = {}
    kept = 0
    new_count = 0
    for item in detail_items:
        asin = item.get("asin") or item.get("ASIN")
        cat = asin_to_category.get(asin) or (categories[0] if categories else "")
        prospect = _to_prospect(item, cat)
        if prospect is None:
            rejects["malformed"] = rejects.get("malformed", 0) + 1
            continue
        ok, reason = _passes_post_detail_filters(prospect)
        if not ok:
            rejects[reason] = rejects.get(reason, 0) + 1
            continue
        kept += 1
        if db.upsert_listing(prospect):
            new_count += 1

    if console:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(rejects.items())) or "(none)"
        console.print(f"[dim]  → kept {kept} after BSR filter; rejects: {breakdown}[/dim]")

    return kept, new_count
