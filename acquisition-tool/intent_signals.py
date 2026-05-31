"""Intent signal scorer — compute an intent_score (0-100) for every brand.

Intent = how urgently the brand needs help RIGHT NOW × how good a client they are.

Signals from EXISTING data (no historical scraping required):
  - Low Rufus score = high pain
  - High review count + low score = has traction but poor visibility
  - Missing Q&A, weak bullets, no A+ = acute structural gaps
  - Competitor gap = we have competitor intel showing they're behind
  - Client quality = do they have budget, can we reach the founder, are they the right size?
  - Reachability index = combined need × client quality score

Signals requiring APPEARS-IN-DATA (future weekly scrape):
  - Review velocity drop (>20% in 30 days)
  - New 1-3 star reviews in last 14 days
  - BSR rank drop (>30% worse)
  - Price undercut by competitor
  - New competitor launched in subcategory

These are stored as JSON in intent_signals.raw_signals and surfaced in
intent_score for send-queue prioritization.
"""
import json
from datetime import datetime
from typing import Optional

import config
import db
from models import Brand, Prospect


def _coerce_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def compute_intent_score(brand: Brand, anchor: Optional[Prospect] = None,
                         competitors: list[dict] | None = None) -> dict:
    """Compute intent score and signal breakdown for a brand.

    Returns dict:
      {
        "intent_score": int (0-100),
        "signals": {signal_name: points, ...},
        "summary": str,
      }
    """
    if anchor is None:
        anchor = db.get_anchor_prospect(brand.anchor_asin)

    if anchor is None:
        return {
            "intent_score": 0,
            "signals": {"no_listing_data": 0},
            "summary": "No anchor ASIN data available.",
        }

    signals: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Rufus pain
    # ------------------------------------------------------------------
    rufus = anchor.rufus_score or 0
    # v2 scores go up to 120; normalize for threshold logic
    rufus_normalized = rufus
    if rufus > 100:
        rufus_normalized = int((rufus / 120) * 100)

    if rufus_normalized < 30:
        signals["rufus_critical"] = 30
    elif rufus_normalized < 50:
        signals["rufus_high_pain"] = 20
    elif rufus_normalized < 65:
        signals["rufus_moderate"] = 10
    elif rufus_normalized > 75:
        signals["already_optimized"] = -20

    # ------------------------------------------------------------------
    # Traction × pain multiplier
    # ------------------------------------------------------------------
    reviews = _coerce_int(anchor.listing_review_count)
    if reviews > 1000 and rufus_normalized < 60:
        signals["high_traction_low_visibility"] = 20
    elif reviews > 500 and rufus_normalized < 60:
        signals["good_traction_low_visibility"] = 15
    elif reviews > 100 and rufus_normalized < 50:
        signals["some_traction_high_pain"] = 10

    # ------------------------------------------------------------------
    # Structural acute gaps
    # ------------------------------------------------------------------
    if _coerce_int(anchor.qa_count) == 0:
        signals["zero_qa"] = 15
    elif _coerce_int(anchor.qa_count) < 3:
        signals["low_qa"] = 8

    if _coerce_int(anchor.bullet_count) < 5:
        signals["weak_bullets"] = 10
    elif _coerce_int(anchor.bullet_count) < 7:
        signals["thin_bullets"] = 5

    if anchor.has_a_plus is False:
        signals["no_a_plus"] = 10

    # New: visual content gap
    if _coerce_int(anchor.image_count) < 5:
        signals["low_images"] = 6
    elif _coerce_int(anchor.image_count) < 3:
        signals["critical_images"] = 10

    # ------------------------------------------------------------------
    # Competitor gap
    # ------------------------------------------------------------------
    if competitors is None:
        competitors = db.get_competitors(brand.brand_key)
    if competitors:
        comp_has_aplus = any(c.get("has_a_plus") for c in competitors)
        if comp_has_aplus and anchor.has_a_plus is False:
            signals["competitor_ahead_aplus"] = 8
        comp_avg_qa = sum(_coerce_int(c.get("qa_count")) for c in competitors) / max(1, len(competitors))
        if comp_avg_qa > _coerce_int(anchor.qa_count) * 2:
            signals["competitor_qa_dominance"] = 8
        comp_avg_bullets = sum(_coerce_int(c.get("bullet_count")) for c in competitors) / max(1, len(competitors))
        if comp_avg_bullets > _coerce_int(anchor.bullet_count) * 1.5:
            signals["competitor_bullet_dominance"] = 5
        # New: competitor image gap
        comp_avg_images = sum(_coerce_int(c.get("image_count")) for c in competitors) / max(1, len(competitors))
        if comp_avg_images > _coerce_int(anchor.image_count) * 1.5:
            signals["competitor_image_dominance"] = 5
    else:
        signals["no_competitor_intel"] = -5

    # ------------------------------------------------------------------
    # Client Quality & Reachability boost
    # ------------------------------------------------------------------
    cq = brand.client_quality_score or 0
    ri = brand.reachability_index or 0

    if ri >= 60:
        signals["high_reachability"] = 12
    elif ri >= 40:
        signals["moderate_reachability"] = 6
    elif ri < 20:
        signals["low_reachability"] = -10

    if cq >= 70:
        signals["premium_client"] = 8
    elif cq >= 50:
        signals["solid_client"] = 4
    elif cq < 30:
        signals["poor_client_fit"] = -8

    # Founder direct access = big bonus
    title = (brand.contact_title or "").lower()
    if any(t in title for t in ["founder", "co-founder", "cofounder", "owner", "ceo"]):
        signals["founder_access"] = 6

    # ------------------------------------------------------------------
    # Compute total
    # ------------------------------------------------------------------
    total = sum(signals.values())
    total = max(0, min(100, total))

    # Generate one-sentence summary
    top_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)[:3]
    if top_signals:
        summary_parts = [f"{name.replace('_', ' ')} (+{val})" for name, val in top_signals if val > 0]
        summary = "Top intent signals: " + ", ".join(summary_parts) + "."
    else:
        summary = "No strong intent signals detected."

    return {
        "intent_score": total,
        "signals": signals,
        "summary": summary,
    }


def score_brand(brand_key: str, save: bool = True) -> dict:
    """Compute and optionally persist intent score for one brand."""
    brand = db.get_brand(brand_key)
    if not brand:
        return {"error": "brand not found"}

    result = compute_intent_score(brand)
    if save:
        db.set_intent_score(
            brand_key=brand_key,
            intent_score=result["intent_score"],
            intent_signals=json.dumps(result["signals"]),
            intent_summary=result["summary"],
        )
    return result


def score_all_brands(stage: str = "CONTACT_ENRICHED", limit: int = 100,
                     console=None) -> int:
    """Compute intent scores for all brands in a stage. Returns count scored."""
    import db as _db

    brands = _db.get_brands_by_stage(stage, limit=limit)
    if not brands:
        if console:
            console.print(f"[dim]No brands in stage {stage}.[/dim]")
        return 0

    scored = 0
    for brand in brands:
        result = compute_intent_score(brand)
        _db.set_intent_score(
            brand_key=brand.brand_key,
            intent_score=result["intent_score"],
            intent_signals=json.dumps(result["signals"]),
            intent_summary=result["summary"],
        )
        scored += 1
        if console:
            console.print(
                f"  [dim]{brand.brand_key}[/dim]  intent={result['intent_score']}  "
                f"{result['summary'][:60]}"
            )

    if console:
        console.print(f"[green]✓[/green] Scored {scored} brand(s)")
    return scored
