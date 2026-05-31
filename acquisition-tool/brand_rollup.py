"""Brand-level rollup — collapse WEAK_LISTING ASINs into one Brand row per brand_key.

The brand becomes the unit of outreach: enrichment, teardown, and Apollo sequence add
all operate on brands, not individual ASINs. The "anchor" ASIN (worst weak listing) is
attached to the brand and used as the case study in the cold-email teardown.
"""
from datetime import datetime

import db
from models import Brand


def _pick_anchor(prospects):
    """Anchor = highest quality_score (new) or weakness_score (legacy), tie-break by listing_review_count desc, then ASIN."""
    def _key(p):
        score = p.quality_score if p.quality_score is not None else (p.weakness_score or 0)
        return (-score, -(p.listing_review_count or 0), p.asin or "")
    return min(prospects, key=_key)


def _union_signals(prospects) -> str:
    seen = []
    for p in prospects:
        signals = p.quality_signals or p.weakness_signals or ""
        if not signals:
            continue
        for sig in signals.split(","):
            sig = sig.strip()
            if sig and sig not in seen:
                seen.append(sig)
    return ",".join(seen)


def _max_quality_score(prospects) -> int:
    return max((p.quality_score or p.weakness_score or 0) for p in prospects)


def consolidate(console=None) -> int:
    """Roll up unprocessed WEAK_LISTING ASINs into the brands table. Returns brand count created."""
    listings = db.get_weak_listings_for_rollup()
    if not listings:
        if console:
            console.print("[dim]No weak listings awaiting rollup.[/dim]")
        return 0

    by_brand: dict[str, list] = {}
    for p in listings:
        by_brand.setdefault(p.brand_key, []).append(p)

    created = 0
    for brand_key, group in by_brand.items():
        existing = db.get_brand(brand_key)
        if existing and existing.stage not in ("WEAK_BRAND", "SKIP_NO_LISTING"):
            continue  # preserve already-enriched/drafted brands
        anchor = _pick_anchor(group)
        now = datetime.utcnow()
        brand = Brand(
            brand_key=brand_key,
            brand_name=anchor.brand or brand_key,
            category=anchor.category,
            anchor_asin=anchor.asin,
            asin_count=len(group),
            max_weakness_score=_max_quality_score(group),
            weakness_signals=_union_signals(group),
            stage="WEAK_BRAND",
            created_at=now,
            updated_at=now,
        )
        if db.upsert_brand(brand):
            created += 1

    if console:
        console.print(f"[green]✓[/green] Rolled up {len(listings)} ASINs → {created} new brand(s)")
    return created
