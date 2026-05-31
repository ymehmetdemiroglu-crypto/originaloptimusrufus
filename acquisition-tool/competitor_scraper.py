"""Competitor intelligence scraper — finds top 3 competitors for an anchor ASIN.

Uses the same Apify actors as amazon_scraper.py but with different filters:
- No price/review/BSR gating (we want ALL competitors, including bestsellers)
- Exclude the target brand
- Pick top 3 by search rank (page 1-2, relevance sort)
- Fetch detail for competitive intel: bullets, title, Q&A, A+, reviews

Stored in Supabase `competitors` table linked to brand_key.
"""
import re
from datetime import datetime
from typing import Optional

import config
import db


def _normalize_brand(brand: str) -> str:
    if not brand:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", brand.lower()).strip()


def _brand_key(brand: str) -> str:
    return re.sub(r"\s+", "", _normalize_brand(brand))


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


def _coerce_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val) if val not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _extract_search_keyword(title: str, category: str) -> str:
    """Derive a search keyword from listing title + category.

    Strategy: use the category if it's a specific niche term
    (e.g., 'magnesium glycinate'); otherwise extract the core
    product phrase from the title (first 3-5 words before any
    separator like '—', '|', '-', or comma).
    """
    if category and len(category.split()) <= 3:
        return category
    # Extract core product phrase from title
    clean = re.split(r"[\-\|\—,]", (title or ""))[0].strip()
    words = clean.split()
    # Keep first 3-5 words that look like a product name
    if len(words) >= 3:
        return " ".join(words[:5])
    return clean or "product"


def _search_competitors(client, keyword: str, target_brand: str, max_results: int = 3, console=None) -> list[dict]:
    """Search Amazon for `keyword`, return top `max_results` competitors excluding target_brand.

    Searches pages 1-2 (bestsellers area) since we want the leaders.
    """
    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")
    search_inputs = [
        {
            "keyword": keyword,
            "domainCode": domain_code,
            "sortBy": "relevanceblender",
            "page": page,
        }
        for page in range(1, 3)
    ]

    run = client.actor(config.APIFY_AMAZON_SEARCH_ACTOR_ID).call(run_input={"input": search_inputs})
    raw = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    target_norm = _normalize_brand(target_brand)
    competitors: list[dict] = []
    seen_brand: set[str] = set()

    for item in raw:
        brand = (item.get("brand") or item.get("manufacturer") or "").strip()
        brand_norm = _normalize_brand(brand)
        if not brand_norm:
            continue
        # Exclude target brand and its variants
        if brand_norm == target_norm or target_norm in brand_norm or brand_norm in target_norm:
            continue
        # Exclude blocklist brands
        if brand_norm in config.AMAZON_BRAND_BLOCKLIST:
            continue
        # Deduplicate by brand
        if brand_norm in seen_brand:
            continue
        seen_brand.add(brand_norm)

        asin = item.get("asin") or item.get("ASIN")
        if not asin:
            continue

        competitors.append({
            "asin": asin,
            "brand": brand,
            "title": (item.get("title") or "").strip(),
            "price": _coerce_float(item.get("price")),
            "rating": _coerce_float(item.get("rating") or item.get("stars")),
            "review_count": _coerce_int(
                item.get("reviewsCount") or item.get("numberOfReviews") or item.get("reviewCount")
            ),
            "search_rank": len(competitors) + 1,
        })

        if len(competitors) >= max_results:
            break

    if console:
        console.print(f"[dim]  → {len(raw)} raw hits → {len(competitors)} competitors for '{keyword}'[/dim]")

    return competitors


def _fetch_competitor_details(client, asins: list[str], console=None) -> list[dict]:
    """Fetch detail for competitor ASINs."""
    if not asins:
        return []
    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")
    urls = [f"https://www.{config.AMAZON_DOMAIN}/dp/{a}" for a in asins]
    run = client.actor(config.APIFY_AMAZON_DETAIL_ACTOR_ID).call(
        run_input={"urls": urls, "domainCode": domain_code}
    )
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _extract_competitor_intel(item: dict, search_meta: dict) -> Optional[dict]:
    """Map a detail item to structured competitor intel."""
    asin = item.get("asin") or item.get("ASIN")
    if not asin:
        return None

    brand = (item.get("brand") or item.get("manufacturer") or "").strip() or search_meta.get("brand", "")
    title = (item.get("title") or item.get("productTitle") or "").strip()

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
    bullets_joined = "\n".join(bullets)[:2000] if isinstance(bullets, list) else str(bullets)[:2000]

    images = item.get("images") or item.get("imageUrls") or item.get("highResolutionImages") or []
    image_count = len(images) if isinstance(images, list) else 0

    a_plus = (
        item.get("aPlusContent")
        or item.get("hasAplus")
        or item.get("a_plus")
        or item.get("hasAPlusContent")
    )
    has_a_plus = bool(a_plus) if a_plus not in (None, "", 0, False) else False

    qa_count = _coerce_int(
        item.get("questions")
        or item.get("qaCount")
        or item.get("questionsAnswered")
        or item.get("questionCount")
    )

    rating = _coerce_float(item.get("rating") or item.get("stars") or item.get("averageRating"))
    review_count = _coerce_int(
        item.get("reviewsCount") or item.get("numberOfReviews") or item.get("reviewCount")
    )

    return {
        "asin": asin,
        "brand": brand,
        "title": title,
        "bullet_count": bullet_count,
        "bullets": bullets_joined,
        "image_count": image_count,
        "has_a_plus": has_a_plus,
        "qa_count": qa_count,
        "rating": rating,
        "review_count": review_count,
        "search_rank": search_meta.get("search_rank", 0),
        "price": _coerce_float(item.get("price")),
    }


def scrape_competitors_for_brand(brand_key: str, console=None) -> list[dict]:
    """Find and store top 3 competitors for a brand's anchor ASIN.

    Returns list of competitor dicts (empty if no anchor or no Apify token).
    """
    if not config.APIFY_TOKEN:
        if console:
            console.print("[yellow]APIFY_TOKEN missing — skipping competitor scrape.[/yellow]")
        return []

    brand = db.get_brand(brand_key)
    if not brand or not brand.anchor_asin or brand.anchor_asin == "apollo_direct":
        if console:
            console.print(f"[dim]{brand_key}: no anchor ASIN, skipping competitor scrape[/dim]")
        return []

    anchor = db.get_anchor_prospect(brand.anchor_asin)
    if not anchor:
        if console:
            console.print(f"[dim]{brand_key}: anchor prospect not found, skipping[/dim]")
        return []

    try:
        from apify_client import ApifyClient
    except ImportError:
        if console:
            console.print("[yellow]apify-client not installed — skipping competitor scrape.[/yellow]")
        return []

    if console:
        console.print(
            f"[dim]Competitor scrape for {brand.brand_name} ({brand.anchor_asin}) — "
            f"keyword: {anchor.category or anchor.post_title[:40]}…[/dim]"
        )

    client = ApifyClient(config.APIFY_TOKEN)
    keyword = _extract_search_keyword(anchor.post_title or "", anchor.category or "")

    # Step 1: search
    search_results = _search_competitors(client, keyword, anchor.brand or brand.brand_name, max_results=3, console=console)
    if not search_results:
        return []

    # Step 2: detail
    asins = [c["asin"] for c in search_results]
    detail_items = _fetch_competitor_details(client, asins, console=console)

    # Map detail to search meta
    asin_to_search = {c["asin"]: c for c in search_results}
    competitors: list[dict] = []
    for item in detail_items:
        asin = item.get("asin") or item.get("ASIN")
        intel = _extract_competitor_intel(item, asin_to_search.get(asin, {}))
        if intel:
            competitors.append(intel)

    # Sort by search rank
    competitors.sort(key=lambda c: c.get("search_rank", 99))

    # Persist to DB
    for rank, comp in enumerate(competitors, start=1):
        db.save_competitor(
            brand_key=brand_key,
            competitor_asin=comp["asin"],
            competitor_brand=comp["brand"],
            search_rank=rank,
            title=comp["title"],
            bullet_count=comp["bullet_count"],
            bullets=comp["bullets"],
            image_count=comp["image_count"],
            has_a_plus=comp["has_a_plus"],
            qa_count=comp["qa_count"],
            rating=comp["rating"],
            review_count=comp["review_count"],
            price=comp["price"],
        )

    if console:
        console.print(
            f"[green]✓[/green] {brand_key}: saved {len(competitors)} competitor(s)"
        )

    return competitors


def scrape_competitors_for_batch(brand_keys: list[str], console=None) -> dict[str, list[dict]]:
    """Scrape competitors for multiple brands. Returns {brand_key: [competitors]}."""
    results: dict[str, list[dict]] = {}
    for bk in brand_keys:
        comps = scrape_competitors_for_brand(bk, console=console)
        results[bk] = comps
    return results
