"""Rule-based weakness scoring for Amazon listings — no LLM, runs in milliseconds.

Score = count of triggered rules. Listings with score >= WEAKNESS_THRESHOLD become WEAK_LISTING;
others are marked SKIP. Each triggered rule contributes a tag to weakness_signals.
"""
import config
import db
from models import Prospect


STRUCTURAL_SIGNALS = {"TITLE", "BULLETS", "ATTRIBUTES", "QA_GAP"}


def score_listing(p: Prospect) -> tuple[int, list[str]]:
    """Return (weakness_score, [signals]).

    Signals are split into structural (listing-quality) and demand (popularity).
    Demand-only weakness means a young brand, not a weak listing — we filter those
    upstream of the gate so we don't burn early-stage founders.
    """
    rules = config.WEAKNESS_RULES
    score = 0
    signals = []

    if p.post_title and len(p.post_title) < rules["thin_title"]:
        score += 1
        signals.append("TITLE")

    if p.bullet_count is not None and p.bullet_count < rules["few_bullets"]:
        score += 1
        signals.append("BULLETS")

    if rules["no_a_plus"] and p.has_a_plus is False:
        score += 1
        signals.append("ATTRIBUTES")

    if p.qa_count is not None and p.qa_count < rules["low_qa"]:
        score += 1
        signals.append("QA_GAP")

    if p.image_count is not None and p.image_count < rules["few_images"]:
        score += 1
        signals.append("ATTRIBUTES")

    if p.listing_rating is not None and p.listing_rating < rules["low_rating"]:
        score += 1
        signals.append("CONVERSION")

    # Review count is informational only — do not gate WEAK_LISTING on it.
    # Young brands with <50 reviews are often the most receptive prospects.
    if p.listing_review_count is not None and p.listing_review_count < rules["low_review_count"]:
        signals.append("EARLY_STAGE")

    seen = set()
    unique_signals = []
    for s in signals:
        if s not in seen:
            seen.add(s)
            unique_signals.append(s)
    return score, unique_signals


def score_all(listings: list[Prospect]) -> int:
    """Score and persist. Returns count flagged WEAK_LISTING.

    Gate requires (a) score >= threshold AND (b) at least one structural signal.
    A demand-only listing (CONVERSION/EARLY_STAGE) is SKIP — the listing isn't
    weak, the brand is just young.
    """
    weak_count = 0
    for p in listings:
        score, signals = score_listing(p)
        has_structural = any(s in STRUCTURAL_SIGNALS for s in signals)
        is_weak = score >= config.WEAKNESS_THRESHOLD and has_structural
        stage = "WEAK_LISTING" if is_weak else "SKIP"
        db.set_weakness_score(p.id, score, signals, stage)
        if stage == "WEAK_LISTING":
            weak_count += 1
    return weak_count
