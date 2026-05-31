"""Client Quality Scorer — evaluates whether a brand is worth reaching out to.

Unlike listing-quality scoring (which measures Rufus gaps), client-quality scoring
measures: Do they have budget? Can we reach the decision-maker? Are they growing?
Do they have urgency? Are they the right size (not too small, not mega-brand)?

Output: client_quality_score (0-100) where higher = better client.
Combined with listing_quality_score to produce a "reachability index".
"""
from typing import Optional

import config
import db
from models import Brand, Prospect


# ---------------------------------------------------------------------------
# Sub-scorers (each returns 0-100 for that dimension, higher = better)
# ---------------------------------------------------------------------------

def score_revenue_potential(anchor: Prospect) -> tuple[int, list[str]]:
    """Estimate monthly revenue from price × reviews (proxy for volume).

    Returns (score 0-25, [positive/negative signals]).
    """
    signals = []
    price = anchor.listing_price or 0
    reviews = anchor.listing_review_count or 0

    # Very rough monthly revenue proxy: price * (reviews / 30) * conversion guess
    # This is intentionally crude — we just need tiers.
    estimated_monthly = price * (reviews / 25)  # heuristic

    if estimated_monthly >= 20_000:
        score = 25
        signals.append("HIGH_REVENUE_POTENTIAL")
    elif estimated_monthly >= 8_000:
        score = 20
        signals.append("SOLID_REVENUE_POTENTIAL")
    elif estimated_monthly >= 3_000:
        score = 14
        signals.append("MODERATE_REVENUE_POTENTIAL")
    elif estimated_monthly >= 1_000:
        score = 8
        signals.append("LOW_REVENUE_POTENTIAL")
    else:
        score = 3
        signals.append("MINIMAL_REVENUE_POTENTIAL")

    # Price-point signals
    if price >= 35:
        signals.append("PREMIUM_PRICE_POINT")
    elif price < 15:
        score = max(0, score - 5)
        signals.append("LOW_PRICE_NO_BUDGET")

    # Review count = market validation
    if reviews >= 200:
        signals.append("PROVEN_MARKET")
    elif reviews < 30:
        score = max(0, score - 8)
        signals.append("UNPROVEN_PRODUCT")

    return max(0, min(25, score)), signals


def score_decision_maker_access(brand: Brand) -> tuple[int, list[str]]:
    """Score how well we can reach and influence the decision maker.

    Returns (score 0-25, [signals]).
    """
    signals = []
    score = 0

    email = (brand.contact_email or "").strip()
    title = (brand.contact_title or "").lower()
    first = (brand.contact_first_name or "").strip()
    linkedin = (brand.contact_linkedin or "").strip()

    # Email quality
    if not email:
        score = 0
        signals.append("NO_EMAIL")
        return score, signals

    score += 10
    signals.append("HAS_EMAIL")

    if first:
        score += 5
        signals.append("HAS_FIRST_NAME")

    # Title quality
    founder_titles = ["founder", "co-founder", "cofounder", "owner", "ceo",
                      "chief executive", "president", "managing director", "managing partner"]
    if any(ft in title for ft in founder_titles):
        score += 8
        signals.append("FOUNDER_TITLE")
    elif "head" in title and "ecommerce" in title:
        score += 5
        signals.append("HEAD_OF_ECOME")
    elif any(bad in title for bad in ["manager", "director", "coordinator", "analyst", "specialist", "assistant"]):
        score -= 4
        signals.append("MID_LEVEL_TITLE")

    # LinkedIn presence = more reachable
    if linkedin:
        score += 2
        signals.append("HAS_LINKEDIN")

    # Apollo score if available
    if brand.apollo_score and brand.apollo_score >= 80:
        score += 2
        signals.append("HIGH_APOLLO_SCORE")

    return max(0, min(25, score)), signals


def score_market_maturity(anchor: Prospect) -> tuple[int, list[str]]:
    """Score whether the brand is in the sweet spot (past validation, pre-agency).

    Returns (score 0-25, [signals]).
    """
    signals = []
    reviews = anchor.listing_review_count or 0
    rating = anchor.listing_rating or 0.0

    # Sweet spot: 50-1500 reviews, 3.8-4.6 rating
    score = 15  # baseline

    if 100 <= reviews <= 1500:
        score += 6
        signals.append("SWEET_SPOT_REVIEWS")
    elif reviews < 50:
        score -= 8
        signals.append("TOO_EARLY")
    elif reviews > 3000:
        score -= 5
        signals.append("LIKELY_HAS_AGENCY")

    if 3.8 <= rating <= 4.7:
        score += 4
        signals.append("HEALTHY_RATING")
    elif rating < 3.5:
        score -= 5
        signals.append("POOR_RATING_SIGNAL")
    elif rating > 4.8 and reviews > 1000:
        score -= 3
        signals.append("ALREADY_OPTIMIZED")

    # Brand blocklist check (already filtered upstream, but double-check)
    brand_norm = (anchor.brand or "").lower().strip()
    if brand_norm in config.AMAZON_BRAND_BLOCKLIST:
        score = 0
        signals.append("BLOCKLISTED_BRAND")

    return max(0, min(25, score)), signals


def score_growth_trajectory(anchor: Prospect) -> tuple[int, list[str]]:
    """Score growth signals from available data.

    Returns (score 0-15, [signals]).
    """
    signals = []
    score = 8  # neutral baseline

    reviews = anchor.listing_review_count or 0
    rating = anchor.listing_rating or 0.0

    # High review count with mediocre rating = growth potential (fixable)
    if reviews > 500 and rating < 4.2:
        score += 5
        signals.append("HIGH_VOLUME_FIXABLE")

    # Low review count but decent rating = just launched, might invest
    if reviews < 200 and rating >= 4.0:
        score += 3
        signals.append("NEW_BUT_PROMISING")

    # Very high rating with few reviews = product is good, needs visibility
    if reviews < 300 and rating >= 4.5:
        score += 4
        signals.append("GREAT_PRODUCT_NEEDS_VISIBILITY")

    # BSR signal if available
    bsr = getattr(anchor, "bsr", None)
    if bsr is not None:
        if bsr <= 5_000:
            score += 3
            signals.append("STRONG_BSR")
        elif bsr > 50_000:
            score -= 4
            signals.append("WEAK_BSR")

    return max(0, min(15, score)), signals


def score_category_attractiveness(category: Optional[str]) -> tuple[int, list[str]]:
    """Score whether this category typically invests in listing optimization.

    Returns (score 0-10, [signals]).
    """
    signals = []
    cat = (category or "").lower()

    # Categories known to invest heavily in content/optimization
    high_invest = ["supplement", "skincare", "beauty", "cosmetic", "serum", "retinol",
                   "collagen", "protein", "vitamin"]
    medium_invest = ["pet", "kitchen", "fitness", "baby", "home office"]
    low_invest = ["automotive", "office supply", "tool", "hardware"]

    if any(h in cat for h in high_invest):
        score = 10
        signals.append("HIGH_INVEST_CATEGORY")
    elif any(m in cat for m in medium_invest):
        score = 7
        signals.append("MEDIUM_INVEST_CATEGORY")
    elif any(l in cat for l in low_invest):
        score = 4
        signals.append("LOW_INVEST_CATEGORY")
    else:
        score = 6
        signals.append("UNKNOWN_CATEGORY")

    return score, signals


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_client(brand: Brand, anchor: Optional[Prospect] = None) -> tuple[int, list[str], dict]:
    """Return (client_quality_score 0-100, [signals], breakdown dict).

    Higher = better client prospect.
    """
    if anchor is None:
        anchor = db.get_anchor_prospect(brand.anchor_asin)

    if anchor is None:
        return 0, ["NO_ANCHOR_DATA"], {}

    rev_score, rev_signals = score_revenue_potential(anchor)
    dm_score, dm_signals = score_decision_maker_access(brand)
    mat_score, mat_signals = score_market_maturity(anchor)
    growth_score, growth_signals = score_growth_trajectory(anchor)
    cat_score, cat_signals = score_category_attractiveness(anchor.category)

    total = rev_score + dm_score + mat_score + growth_score + cat_score
    total = min(100, total)

    all_signals = rev_signals + dm_signals + mat_signals + growth_signals + cat_signals
    all_signals = list(dict.fromkeys(all_signals))

    breakdown = {
        "revenue_potential": {"score": rev_score, "max": 25, "signals": rev_signals},
        "decision_maker_access": {"score": dm_score, "max": 25, "signals": dm_signals},
        "market_maturity": {"score": mat_score, "max": 25, "signals": mat_signals},
        "growth_trajectory": {"score": growth_score, "max": 15, "signals": growth_signals},
        "category_attractiveness": {"score": cat_score, "max": 10, "signals": cat_signals},
    }

    return total, all_signals, breakdown


def compute_reachability_index(listing_quality_score: int, client_quality_score: int) -> int:
    """Compute a 0-100 reachability index.

    Formula: we want high client quality AND high listing need.
    A perfect client with a perfect listing = low priority.
    A terrible client with a terrible listing = low priority (can't convert).
    Sweet spot: client quality > 50 AND listing quality > 40.
    """
    # Normalize both to 0-1
    lq = listing_quality_score / 100.0
    cq = client_quality_score / 100.0

    # Geometric mean-ish: both need to be high
    # But client quality is slightly more important (can't close a bad client)
    raw = (lq ** 0.9) * (cq ** 1.1) * 100
    return min(100, int(raw))


def score_all_brands(stage: str = "WEAK_BRAND", limit: int = 100, console=None) -> int:
    """Compute client quality scores for all brands in a stage. Returns count scored."""
    brands = db.get_brands_by_stage(stage, limit=limit)
    if not brands:
        if console:
            console.print(f"[dim]No brands in stage {stage}.[/dim]")
        return 0

    scored = 0
    for brand in brands:
        anchor = db.get_anchor_prospect(brand.anchor_asin)
        if not anchor:
            continue

        cq_score, cq_signals, cq_breakdown = score_client(brand, anchor)
        lq_score = anchor.weakness_score or 0  # legacy field; new code uses quality_score

        reachability = compute_reachability_index(lq_score, cq_score)

        db.set_client_quality_score(
            brand_key=brand.brand_key,
            client_quality_score=cq_score,
            client_quality_signals=",".join(cq_signals),
            client_quality_breakdown=cq_breakdown,
            reachability_index=reachability,
        )
        scored += 1
        if console:
            console.print(
                f"  [dim]{brand.brand_key}[/dim]  CQ={cq_score}  "
                f"LQ={lq_score}  RI={reachability}  "
                f"{cq_signals[0] if cq_signals else '—'}"
            )

    if console:
        console.print(f"[green]✓[/green] Scored {scored} brand(s) for client quality")
    return scored
