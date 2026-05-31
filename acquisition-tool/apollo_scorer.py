"""Apollo prospect pre-enrichment scorer.

Scores a raw Apollo search result (person dict) before committing enrichment credits.
Run this on search results to prioritize who is worth enriching.

Score breakdown (0-100):
  Decision-maker title    0-30
  Amazon brand signal     0-25
  Company data richness   0-20
  Data freshness          0-15
  Reachability            0-10
"""

_PRODUCT_KEYWORDS = [
    "supplement", "vitamin", "nutrition", "nutritional", "skincare", "skin care",
    "beauty", "cosmetic", "personal care", "wellness", "protein", "collagen",
    "probiotic", "organic", "natural", "herbal", "health", "nutraceutical",
    "mineral", "botanical", "apothecary",
]

_SERVICE_KEYWORDS = [
    "consulting", "solutions", "services", "group", "international", "holdings",
    "smoothie", "bar", "cafe", "spa", "salon", "clinic", "institute", "center",
    "centre", "agency", "media", "logistics", "wholesale", "distributor",
]


def score_apollo_result(person: dict) -> int:
    """Score a raw Apollo people-search result. Returns 0-100."""
    score = 0
    title = (person.get("title") or "").lower()
    org = person.get("organization") or {}
    org_name = (org.get("name") or "").lower()
    refreshed = person.get("last_refreshed_at") or ""
    direct_phone = person.get("has_direct_phone") or ""

    # --- Decision-maker title (0-30) ---
    if any(t in title for t in ("founder", "owner", "co-founder", "cofounder")):
        score += 30
    elif "ceo" in title:
        score += 25
    elif any(t in title for t in ("head of", "director", "vp ", "vice president", "president")):
        score += 15
    elif any(t in title for t in ("manager", "lead", "specialist")):
        score += 8

    # --- Amazon product brand signal (0-25) ---
    if any(kw in org_name for kw in _PRODUCT_KEYWORDS):
        score += 25
    elif not any(kw in org_name for kw in _SERVICE_KEYWORDS):
        score += 10
    # service/distribution signal = 0

    # --- Company data richness (0-20) ---
    if org.get("has_revenue"):
        score += 10
    if org.get("has_employee_count"):
        score += 5
    if org.get("has_city"):
        score += 5

    # --- Data freshness (0-15) ---
    if refreshed.startswith("2026"):
        score += 15
    elif refreshed.startswith("2025"):
        score += 8

    # --- Reachability (0-10) ---
    if direct_phone == "Yes":
        score += 10
    elif "Maybe" in direct_phone:
        score += 5

    return min(score, 100)


def score_batch(people: list[dict]) -> list[dict]:
    """Add 'apollo_score' to each person dict and return sorted descending."""
    for p in people:
        p["apollo_score"] = score_apollo_result(p)
    return sorted(people, key=lambda x: x["apollo_score"], reverse=True)


def grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"
