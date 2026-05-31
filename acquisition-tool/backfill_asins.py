"""Batched Apify ASIN backfill for Apollo-direct brands.

For every brand row with anchor_asin = 'apollo_direct':
  1. Build one search input (brand_name + category) and add to a single batched
     search-actor call. Submit ALL brands in ONE actor run.
  2. Fuzzy-match results to brands; collect one ASIN per brand.
  3. Submit ALL ASIN URLs in ONE detail-actor call.
  4. Persist + update brands.anchor_asin.

This replaces the previous threaded one-actor-run-per-brand pattern.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from difflib import SequenceMatcher

from apify_client import ApifyClient

import config
import db
from amazon_scraper import _to_prospect


BRAND_MATCH_THRESHOLD = 0.72      # raised from 0.55 — prevents cross-brand fuzzy hits
DETAIL_MATCH_THRESHOLD = 0.65    # post-detail re-check (listing brand vs Apollo name)


def _brand_similarity(apollo_name: str, amazon_brand: str) -> float:
    a = (apollo_name or "").lower().strip()
    b = (amazon_brand or "").lower().strip()
    if not a or not b:
        return 0.0
    # Substring match is only reliable when both strings are reasonably long;
    # short common words (e.g. "one", "pure") produce false positives.
    if len(a) >= 5 and len(b) >= 5 and (a in b or b in a):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _domain_brand_match(apollo_domain: str, amazon_brand: str) -> bool:
    """True if the Apollo brand's domain root appears in the Amazon brand string."""
    if not apollo_domain or not amazon_brand:
        return False
    # strip TLD: "flybirdfitness.com" → "flybirdfitness"
    root = apollo_domain.lower().split(".")[0].replace("-", "").replace("_", "")
    brand = amazon_brand.lower().replace(" ", "").replace("-", "").replace("_", "")
    return root in brand or brand in root


def _print(msg, console=None):
    if console:
        console.print(msg)
    else:
        print(msg)


def run_backfill(console=None):
    """Batched backfill: 1 search actor run + 1 detail actor run for ALL brands."""
    db.init_db()

    res = db._sb().table("brands").select("*").eq("anchor_asin", "apollo_direct").execute()
    brands = res.data or []

    if not brands:
        _print("[dim]No brands needing ASIN backfill found.[/dim]" if console else "No brands needing ASIN backfill found.", console)
        return

    if not config.APIFY_TOKEN:
        _print("[red]Error: APIFY_TOKEN is not set.[/red]" if console else "Error: APIFY_TOKEN is not set.", console)
        return

    _print(
        f"[dim]Backfilling {len(brands)} brands in 2 batched Apify calls (search + detail)…[/dim]"
        if console else f"Backfilling {len(brands)} brands in 2 batched Apify calls (search + detail)...",
        console,
    )

    client = ApifyClient(config.APIFY_TOKEN)
    domain_code = config.AMAZON_DOMAIN.replace("amazon.", "")

    # Process in shards if total > APIFY_BATCH_SIZE.
    shard = config.APIFY_BATCH_SIZE
    updated = 0
    skipped = 0
    errors = 0

    for shard_start in range(0, len(brands), shard):
        shard_brands = brands[shard_start : shard_start + shard]

        # Stage 1 — single search actor run with all brand keywords.
        search_inputs = []
        keyword_to_brand: dict[str, dict] = {}
        for b in shard_brands:
            kw = f"{b['brand_name']} {b.get('category') or ''}".strip()
            keyword_to_brand[kw.lower()] = b
            search_inputs.append({
                "keyword": kw,
                "domainCode": domain_code,
                "sortBy": "relevanceblender",
                "page": 1,
            })

        try:
            run = client.actor(config.APIFY_AMAZON_SEARCH_ACTOR_ID).call(
                run_input={"input": search_inputs}
            )
            raw_search = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        except Exception as e:
            _print(f"[red]search batch error: {e}[/red]" if console else f"search batch error: {e}", console)
            errors += len(shard_brands)
            continue

        # Map results → best ASIN per brand_key
        best_per_brand: dict[str, tuple[float, str, str]] = {}  # brand_key -> (score, asin, amazon_brand)
        for item in raw_search:
            asin = item.get("asin") or item.get("ASIN")
            if not asin:
                continue
            kw = (item.get("keyword") or item.get("searchQuery") or "").lower()
            matched = keyword_to_brand.get(kw)
            if matched is None:
                # Fall back: fuzzy on item brand vs every brand in this shard
                item_brand = (item.get("brand") or item.get("manufacturer") or "")
                best_b = None
                best_s = 0.0
                for b in shard_brands:
                    s = _brand_similarity(b["brand_name"], item_brand)
                    if s > best_s:
                        best_s, best_b = s, b
                if best_b and best_s >= BRAND_MATCH_THRESHOLD:
                    matched = best_b
            if matched is None:
                continue

            item_brand = (item.get("brand") or item.get("manufacturer") or "")
            score = _brand_similarity(matched["brand_name"], item_brand)
            if score < BRAND_MATCH_THRESHOLD:
                continue

            prev = best_per_brand.get(matched["brand_key"])
            if prev is None or score > prev[0]:
                best_per_brand[matched["brand_key"]] = (score, asin, item_brand)

        if not best_per_brand:
            _print(
                f"[yellow]shard {shard_start//shard + 1}: no confident brand matches[/yellow]"
                if console else f"shard {shard_start//shard + 1}: no confident brand matches",
                console,
            )
            skipped += len(shard_brands)
            continue

        # Stage 2 — single detail actor run for all winning ASINs.
        asins = [v[1] for v in best_per_brand.values()]
        urls = [f"https://www.{config.AMAZON_DOMAIN}/dp/{a}" for a in asins]
        try:
            run2 = client.actor(config.APIFY_AMAZON_DETAIL_ACTOR_ID).call(
                run_input={"urls": urls, "domainCode": domain_code}
            )
            detail_items = list(client.dataset(run2["defaultDatasetId"]).iterate_items())
        except Exception as e:
            _print(f"[red]detail batch error: {e}[/red]" if console else f"detail batch error: {e}", console)
            errors += len(best_per_brand)
            continue

        # Index detail items by ASIN
        detail_by_asin = {}
        for item in detail_items:
            a = item.get("asin") or item.get("ASIN")
            if a:
                detail_by_asin[a] = item

        brand_by_key = {b["brand_key"]: b for b in shard_brands}
        for brand_key, (score, asin, amazon_brand) in best_per_brand.items():
            b = brand_by_key.get(brand_key)
            if not b:
                continue
            item = detail_by_asin.get(asin)
            if not item:
                # Detail call dropped this ASIN; skip instead of pretending we have it.
                _print(
                    f"  [yellow]⚠[/yellow] {b['brand_name']}: ASIN {asin} found but detail missing"
                    if console else f"  WARN {b['brand_name']}: ASIN {asin} found but detail missing",
                    console,
                )
                errors += 1
                continue

            # Post-detail re-validation: re-check the listing's actual brand against
            # the Apollo brand. The search-stage brand string can differ from the
            # detail-stage brand (store name vs manufacturer). Reject if it doesn't
            # pass the stricter threshold AND domain doesn't match.
            detail_brand = (item.get("brand") or item.get("manufacturer") or "").strip()
            detail_score = _brand_similarity(b["brand_name"], detail_brand)
            domain_ok = _domain_brand_match(b.get("domain") or "", detail_brand)
            if detail_score < DETAIL_MATCH_THRESHOLD and not domain_ok:
                _print(
                    f"  [yellow]⚠[/yellow] {b['brand_name']} → {asin} REJECTED post-detail "
                    f"(listing brand='{detail_brand}', score={detail_score:.0%})"
                    if console else
                    f"  SKIP {b['brand_name']} -> {asin}: listing brand '{detail_brand}' mismatch ({detail_score:.0%})",
                    console,
                )
                skipped += 1
                continue

            p = _to_prospect(item, b.get("category") or "")
            if not p:
                errors += 1
                continue
            db.upsert_listing(p)
            db._sb().table("brands").update(
                {"anchor_asin": asin, "updated_at": __import__("datetime").datetime.utcnow().isoformat()}
            ).eq("brand_key", brand_key).execute()
            updated += 1
            _print(
                f"  [green]✓[/green] {b['brand_name']} → {asin} (match {score:.0%})"
                if console else f"  OK {b['brand_name']} -> {asin} (match {score:.0%})",
                console,
            )

        # Anything in this shard without a winning brand match is a skip.
        skipped += len([b for b in shard_brands if b["brand_key"] not in best_per_brand])

    summary = f"Backfill complete: {updated} updated, {skipped} skipped (no match), {errors} errors."
    _print(f"[green]✓[/green] {summary}" if console else summary, console)


def main():
    run_backfill()


if __name__ == "__main__":
    main()
