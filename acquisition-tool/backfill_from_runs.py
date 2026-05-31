"""Re-process existing Apify run datasets without triggering new actor runs.

Usage:
    py backfill_from_runs.py <search_run_id> <detail_run_id>

Example:
    py backfill_from_runs.py 78tBoKh5oGdu4cMuh DxnanN45m8DivV0Dh
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from difflib import SequenceMatcher
from apify_client import ApifyClient

import config
import db
from amazon_scraper import _to_prospect

BRAND_MATCH_THRESHOLD = 0.55


def _sim(a: str, b: str) -> float:
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def main(search_run_id: str, detail_run_id: str):
    db.init_db()
    client = ApifyClient(config.APIFY_TOKEN)

    # Load all brands that still need an ASIN
    with db._conn() as rc:
        rows = rc.execute("SELECT * FROM brands WHERE anchor_asin = 'apollo_direct'").fetchall()
    brands = [dict(b) for b in rows]
    if not brands:
        print("No apollo_direct brands remain — nothing to do.")
        return
    print(f"Brands needing ASIN: {len(brands)}")

    # ── Step 1: download search dataset ──────────────────────────────────────
    print(f"Downloading search dataset {search_run_id}…")
    run_info = client.run(search_run_id).get()
    search_dataset_id = run_info["defaultDatasetId"]
    search_items = list(client.dataset(search_dataset_id).iterate_items())
    print(f"  {len(search_items)} search result items")

    # ── Step 2: fuzzy-match search results → best ASIN per brand ─────────────
    best_per_brand: dict[str, tuple[float, str, str]] = {}
    for item in search_items:
        asin = item.get("asin") or item.get("ASIN")
        if not asin:
            continue
        item_brand = item.get("brand") or item.get("manufacturer") or ""
        kw = (item.get("keyword") or item.get("searchQuery") or "").lower()

        # try keyword-exact match first
        matched_b = None
        for b in brands:
            expected_kw = f"{b['brand_name']} {b.get('category') or ''}".strip().lower()
            if kw == expected_kw:
                matched_b = b
                break

        # fall back to fuzzy brand name match
        if matched_b is None:
            best_s, best_b = 0.0, None
            for b in brands:
                s = _sim(b["brand_name"], item_brand)
                if s > best_s:
                    best_s, best_b = s, b
            if best_b and best_s >= BRAND_MATCH_THRESHOLD:
                matched_b = best_b

        if matched_b is None:
            continue

        score = _sim(matched_b["brand_name"], item_brand)
        if score < BRAND_MATCH_THRESHOLD:
            continue

        prev = best_per_brand.get(matched_b["brand_key"])
        if prev is None or score > prev[0]:
            best_per_brand[matched_b["brand_key"]] = (score, asin, item_brand)

    print(f"  Confident matches: {len(best_per_brand)}")
    for bk, (sc, asin, ab) in best_per_brand.items():
        b = next(x for x in brands if x["brand_key"] == bk)
        print(f"    {b['brand_name']} → {asin} ({sc:.0%})")

    if not best_per_brand:
        print("No confident brand matches found in search dataset.")
        return

    # ── Step 3: download detail dataset ──────────────────────────────────────
    print(f"\nDownloading detail dataset {detail_run_id}…")
    detail_run_info = client.run(detail_run_id).get()
    detail_dataset_id = detail_run_info["defaultDatasetId"]
    detail_items = list(client.dataset(detail_dataset_id).iterate_items())
    print(f"  {len(detail_items)} detail items")

    detail_by_asin = {}
    for item in detail_items:
        a = item.get("asin") or item.get("ASIN")
        if a:
            detail_by_asin[a] = item

    # ── Step 4: persist matches ───────────────────────────────────────────────
    updated, missing_detail, errors = 0, 0, 0
    brand_by_key = {b["brand_key"]: b for b in brands}

    for brand_key, (score, asin, amazon_brand) in best_per_brand.items():
        b = brand_by_key.get(brand_key)
        if not b:
            continue
        item = detail_by_asin.get(asin)
        if not item:
            print(f"  WARN {b['brand_name']}: detail missing for {asin}")
            missing_detail += 1
            continue
        p = _to_prospect(item, b.get("category") or "")
        if not p:
            errors += 1
            continue
        try:
            db.upsert_listing(p)
            with db._conn() as wc:
                wc.execute("UPDATE brands SET anchor_asin = ? WHERE brand_key = ?", (asin, brand_key))
            updated += 1
            print(f"  ✓ {b['brand_name']} → {asin} ({score:.0%})")
        except Exception as e:
            print(f"  ERROR {b['brand_name']}: {e}")
            errors += 1

    print(f"\nDone: {updated} updated, {missing_detail} missing detail, {errors} errors.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: py backfill_from_runs.py <search_run_id> <detail_run_id>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
