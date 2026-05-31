import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Prompt loading helpers
# ---------------------------------------------------------------------------

_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(path: str | None = None) -> str:
    """Load a prompt file from disk. Caches in memory so repeated reads are free.
    Falls back to env var resolution for convenience."""
    if path is None:
        path = RUFUS_PROMPT_PATH
    if path in _PROMPT_CACHE:
        return _PROMPT_CACHE[path]
    full = Path(path)
    if not full.is_absolute():
        # Resolve relative to this config file's directory
        full = Path(__file__).parent.resolve() / path
    text = full.read_text(encoding="utf-8")
    _PROMPT_CACHE[path] = text
    return text


def reload_prompt(path: str | None = None) -> str:
    """Force a re-read of a prompt file from disk (bypass cache)."""
    if path is None:
        path = RUFUS_PROMPT_PATH
    if path in _PROMPT_CACHE:
        del _PROMPT_CACHE[path]
    return load_prompt(path)


# ---------------------------------------------------------------------------
# Secrets / required env vars
# ---------------------------------------------------------------------------

def _require_env(var_name: str, *, default: str | None = None) -> str:
    val = os.getenv(var_name, default)
    if val is None or val == "":
        raise ValueError(
            f"Missing required environment variable: {var_name}. "
            "See .env.example for all required variables."
        )
    return val


# ---------------------------------------------------------------------------
# Apify — Amazon search + detail
# ---------------------------------------------------------------------------
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")


# Search actor (page-level harvest; cheap, returns price/reviews/brand for pre-filter)
APIFY_AMAZON_SEARCH_ACTOR_ID = os.getenv(
    "APIFY_AMAZON_SEARCH_ACTOR_ID",
    "axesso_data/amazon-search-scraper",
)

# Detail actor (per-ASIN; returns full bullets, A+, Q&A, images — needed for Rufus scoring)
# Default: axesso_data/amazon-product-details-extractor (same provider as search; consistent output keys).
# Override via APIFY_AMAZON_DETAIL_ACTOR_ID env var if you want a different actor.
APIFY_AMAZON_DETAIL_ACTOR_ID = os.getenv(
    "APIFY_AMAZON_DETAIL_ACTOR_ID",
    "axesso_data/amazon-product-details-scraper",
)

# ---------------------------------------------------------------------------
# LLM — Rufus scorer + cold email teardown
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")  # optional — only needed for Claude email
OPENROUTER_API_KEY = _require_env("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324")
OPENROUTER_DRAFT_MODEL = os.getenv("OPENROUTER_DRAFT_MODEL", "deepseek/deepseek-chat-v3-0324")
EMAIL_MINI_BATCH_SIZE = int(os.getenv("EMAIL_MINI_BATCH_SIZE", "5"))

# Lead magnet calculator URL — embedded in cold email CTAs
CALCULATOR_BASE_URL = os.getenv("CALCULATOR_BASE_URL", "https://calc.optimusrufus.com")
PITCH_PAGE_BASE_URL = os.getenv("PITCH_PAGE_BASE_URL", "https://audit.optimusrufus.com")

# ---------------------------------------------------------------------------
# Backend Rufus/COSMO Optimization Engine
# ---------------------------------------------------------------------------
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
USE_BACKEND_SCORING = os.getenv("USE_BACKEND_SCORING", "false").lower() == "true"

# Toggle Claude API for email drafting (vs OpenRouter/deepseek)
USE_CLAUDE_EMAIL = os.getenv("USE_CLAUDE_EMAIL", "false").lower() == "true"
CLAUDE_EMAIL_MODEL = os.getenv("CLAUDE_EMAIL_MODEL", "claude-haiku-4-5-20251001")

# Supabase — cloud PostgreSQL primary store
SUPABASE_URL = _require_env("SUPABASE_URL")
SUPABASE_KEY = _require_env("SUPABASE_KEY")

# ---------------------------------------------------------------------------
# Tiered category lists for budget-aware scraping
AMAZON_TIER_1_CATEGORIES = [
    # Supplements — ingredient-led, highest Rufus vulnerability
    "magnesium glycinate", "ashwagandha capsules", "creatine monohydrate",
    "collagen peptides powder", "berberine supplement",
    "sea moss capsules", "lions mane mushroom capsules",
    "beef liver supplement", "turmeric curcumin capsules",
    # Skincare — ingredient-led, high cold-email response rate
    "vitamin c serum", "retinol cream", "niacinamide serum",
    "hyaluronic acid moisturizer", "snail mucin essence",
    "rosehip seed oil", "lash growth serum",
]

AMAZON_TIER_2_CATEGORIES = [
    # Pet — problem-led, founders are passionate about their brand
    "calming dog treats", "joint supplement for dogs", "cat dental treats",
    "dog probiotics", "salmon oil for dogs",
    # Beauty-adjacent — DTC founders, respond well to teardowns
    "tallow balm skincare", "pimple patches acne", "gua sha tool",
    "scalp scrub shampoo", "rosemary hair oil", "castor oil hair",
    # Trending wellness — new category with weak listings
    "shilajit supplement", "elderberry gummies",
    "digestive enzyme supplement",
]

AMAZON_TIER_3_CATEGORIES = [
    # Kitchen — function-led, some DTC brands
    "electric milk frother", "cast iron skillet", "beeswax food wraps",
    # Fitness — item-led, niche DTC
    "resistance bands set", "foam roller muscle", "acupressure mat",
    # Home Office — functional
    "monitor stand riser", "laptop stand adjustable",
    # Baby — safety-conscious parents = good clients
    "baby carrier wrap", "baby sound machine",
]

# Combined
AMAZON_SEED_CATEGORIES = AMAZON_TIER_1_CATEGORIES + AMAZON_TIER_2_CATEGORIES + AMAZON_TIER_3_CATEGORIES

AMAZON_SCRAPE_LIMIT_PER_CATEGORY = 100
AMAZON_DOMAIN = "amazon.com"

# Targeting filters (applied at search stage on cheap data, then again post-detail for BSR).
AMAZON_PRICE_MIN = 20.0           # below = commodity, no SaaS budget
AMAZON_PRICE_MAX = 120.0          # above = enterprise / luxury, different buyer
AMAZON_REVIEW_MIN = 30            # loosened from 50: catch newer founder brands
AMAZON_REVIEW_MAX = 3000          # loosened from 2000: mid-tier brands still lack Rufus-ready listings
AMAZON_BSR_MIN = 5_000            # in subcategory; below = bestseller (already winning)
AMAZON_BSR_MAX = 75000            # loosened from 50000: include seasonal dips
AMAZON_SEARCH_PAGE_START = 2      # skip page 1 (bestsellers + Amazon Basics)
AMAZON_SEARCH_PAGE_END = 6        # stop before pages with no sales

# At most this many ASINs per brand may go to the detail call (rollup picks one anchor anyway).
AMAZON_MAX_ASINS_PER_BRAND = 1

# Brand blocklist — Amazon house brands and mega-brands (already have agencies).
AMAZON_BRAND_BLOCKLIST = {
    # Amazon house brands
    "amazon basics", "amazonbasics", "amazon", "amazon essentials",
    "solimo", "happy belly", "wag", "presto", "pinzon",
    # Mega-brands with agencies
    "anker", "soundcore", "eufy", "bose", "sony", "logitech",
    "oxo", "cuisinart", "kitchenaid", "ninja", "instant pot",
    "nature made", "now foods", "garden of life", "optimum nutrition",
    "neutrogena", "cerave", "cetaphil", "the ordinary",
    # Found in pipeline — too large / corporate to convert via cold email
    "orgain", "cymbiotika", "thorne", "momentous", "bulksupplements",
    "bulk supplements", "naked nutrition", "naked", "hum nutrition",
    "humnutrition", "nativepath", "new chapter", "designs for health",
    "designsforhealth", "jshealth", "rollga", "microingredients",
    "micro ingredients",
}

# ---------------------------------------------------------------------------
# Weakness scoring (LEGACY — kept for backward compatibility)
# ---------------------------------------------------------------------------
WEAKNESS_THRESHOLD = 3
WEAKNESS_RULES = {
    "thin_title": 80,           # title chars below this = +1
    "few_bullets": 5,           # fewer bullets than this = +1
    "no_a_plus": True,          # listing lacks A+ content = +1
    "low_qa": 3,                # fewer than this many Q&A = +1
    "few_images": 5,            # fewer images than this = +1
    "low_review_count": 50,     # fewer reviews than this = +1
    "low_rating": 4.0,          # rating below this = +1
}

# ---------------------------------------------------------------------------
# Enhanced Listing Quality Scorer (replaces weakness_scorer)
# ---------------------------------------------------------------------------
LISTING_QUALITY_THRESHOLD = 35   # score >= this → WEAK_LISTING (0-100 scale)
LISTING_QUALITY_MAX_SCORE = 100

# Client Quality Scorer thresholds
CLIENT_QUALITY_MIN_FOR_OUTREACH = 40   # CQ score must be >= this to enter email draft queue
REACHABILITY_MIN_FOR_OUTREACH = 30     # reachability index must be >= this

# Rufus v2 prompt path (6-axis with competitor context)
RUFUS_V2_PROMPT_PATH = os.getenv(
    "RUFUS_V2_PROMPT_PATH",
    "prompts/rufus_system_prompt_v2.txt",
)

# ---------------------------------------------------------------------------
# Apollo — sequence + decision-maker targeting
# ---------------------------------------------------------------------------
APOLLO_SEQUENCE_ID = os.getenv("APOLLO_SEQUENCE_ID", "")
APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID = os.getenv("APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID", "")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
APOLLO_TARGET_TITLES = [
    "Founder",
    "Co-Founder",
    "CEO",
    "Owner",
    "President",
    "Head of Ecommerce",
]
# Post-search filter: only keep contacts whose actual title contains one of these keywords.
# Apollo title search is fuzzy — this hard-gates non-owners from reaching the send queue.
APOLLO_FOUNDER_TITLE_KEYWORDS = frozenset({
    "founder", "co-founder", "cofounder", "owner", "ceo",
    "chief executive", "president", "managing director",
    "managing partner", "principal",
})
# Titles containing any of these words are rejected even if a founder keyword also matches.
APOLLO_TITLE_EXCLUDE_KEYWORDS = frozenset({
    "director", "manager", "coordinator", "analyst", "vp",
    "vice president", "specialist", "assistant", "associate",
    "head of", "brand manager", "operations", "supply chain",
    "account manager", "marketing manager", "ecommerce manager",
})
APOLLO_NUM_EMPLOYEES_RANGES = ["1,25"]  # SMB owners only; 26-50 mostly have agencies
APOLLO_PERSON_LOCATIONS = ["United States"]

# Niche → Apollo controlled-vocab mapping for auto-prospect.
# Apollo's q_organization_keyword_tags only matches a small controlled vocabulary
# (skincare, beauty, supplements, etc.) — passing a multi-word niche term like
# "vitamin c serum" returns near-zero matches and Apollo falls back to loose
# matches that drag in food/distribution orgs. We map each niche to the broad
# category tags Apollo actually has tagged, plus an industry hard-filter, plus
# pass the literal niche as q_keywords for free-text relevance ranking.
APOLLO_NICHE_TAG_MAP = {
    # skincare / beauty niches
    "vitamin c serum":         {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "retinol cream":           {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "hyaluronic acid serum":   {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "niacinamide serum":       {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "hyaluronic acid moisturizer": {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "gua sha":                 {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "lash serum":              {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "tallow balm":             {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "pimple patches":          {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]},
    "scalp scrub":             {"tags": ["skincare", "beauty", "cosmetics", "haircare"],     "industries": ["cosmetics", "health, wellness & fitness"]},
    "rosemary hair oil":       {"tags": ["haircare", "beauty", "cosmetics"],                  "industries": ["cosmetics", "health, wellness & fitness"]},
    "castor oil":              {"tags": ["beauty", "cosmetics", "skincare", "haircare"],     "industries": ["cosmetics", "health, wellness & fitness"]},
    # supplements / wellness
    "magnesium glycinate":     {"tags": ["supplements", "nutraceuticals", "health", "wellness"], "industries": ["health, wellness & fitness"]},
    "ashwagandha capsules":    {"tags": ["supplements", "nutraceuticals", "health", "wellness"], "industries": ["health, wellness & fitness"]},
    "creatine monohydrate":    {"tags": ["supplements", "sports nutrition", "fitness"],         "industries": ["health, wellness & fitness"]},
    "collagen peptides powder":{"tags": ["supplements", "nutraceuticals", "wellness"],          "industries": ["health, wellness & fitness"]},
    "berberine supplement":    {"tags": ["supplements", "nutraceuticals", "health"],            "industries": ["health, wellness & fitness"]},
    # pet
    "calming dog treats":      {"tags": ["pet products", "pet care", "pet food"],   "industries": ["consumer goods"]},
    "joint supplement for dogs":{"tags": ["pet products", "pet care"],              "industries": ["consumer goods"]},
    "cat dental treats":       {"tags": ["pet products", "pet care", "pet food"],   "industries": ["consumer goods"]},
    # kitchen / home
    "air fryer accessories":   {"tags": ["kitchenware", "housewares", "consumer goods"], "industries": ["consumer goods"]},
    "cast iron skillet":       {"tags": ["kitchenware", "housewares", "consumer goods"], "industries": ["consumer goods"]},
    "beeswax wraps":           {"tags": ["kitchenware", "housewares", "eco products"],   "industries": ["consumer goods"]},
    "compost bin countertop":  {"tags": ["housewares", "consumer goods", "home"],        "industries": ["consumer goods"]},
    # baby
    "baby carrier wrap":       {"tags": ["baby products", "parenting", "consumer goods"], "industries": ["consumer goods"]},
    "diaper bag backpack":     {"tags": ["baby products", "parenting", "consumer goods"], "industries": ["consumer goods"]},
    "baby sound machine":      {"tags": ["baby products", "parenting", "consumer goods"], "industries": ["consumer goods"]},
    # fitness / outdoor
    "foam roller":             {"tags": ["fitness", "sports", "wellness"],    "industries": ["health, wellness & fitness"]},
    "pull up bar":             {"tags": ["fitness", "sports", "home gym"],    "industries": ["health, wellness & fitness"]},
    "jump rope weighted":      {"tags": ["fitness", "sports", "wellness"],    "industries": ["health, wellness & fitness"]},
    "hiking poles":            {"tags": ["outdoor recreation", "sports", "fitness"], "industries": ["sporting goods"]},
    # home / office
    "acupressure mat":         {"tags": ["wellness", "fitness", "health"],    "industries": ["health, wellness & fitness"]},
    "cord organizer":          {"tags": ["office supplies", "consumer goods", "home"], "industries": ["consumer goods"]},
    "laptop stand adjustable": {"tags": ["office supplies", "consumer goods", "technology"], "industries": ["consumer goods"]},
    # automotive
    "car seat organizer":      {"tags": ["automotive", "consumer goods"],     "industries": ["consumer goods"]},
    "dash cam":                {"tags": ["automotive", "consumer goods", "technology"], "industries": ["consumer goods"]},
}

# Coarse fallback when the exact niche isn't mapped: keyword-substring lookup.
# Order matters — first match wins.
APOLLO_NICHE_FALLBACK_RULES = [
    (("serum", "cream", "skincare", "skin care", "moisturizer", "cleanser", "sunscreen", "balm", "facial", "gua sha", "patches", "exfoliant"),
     {"tags": ["skincare", "beauty", "cosmetics", "personal care"], "industries": ["cosmetics", "health, wellness & fitness"]}),
    (("hair", "shampoo", "conditioner", "scalp"),
     {"tags": ["haircare", "beauty", "cosmetics"], "industries": ["cosmetics", "health, wellness & fitness"]}),
    (("supplement", "capsule", "powder", "vitamin", "nutraceutical", "ashwagandha", "magnesium", "creatine", "collagen", "berberine"),
     {"tags": ["supplements", "nutraceuticals", "health", "wellness"], "industries": ["health, wellness & fitness"]}),
    (("dog", "cat", "pet"),
     {"tags": ["pet products", "pet care"], "industries": ["consumer goods"]}),
    (("beauty", "makeup", "cosmetic", "lipstick", "mascara"),
     {"tags": ["beauty", "cosmetics", "personal care"], "industries": ["cosmetics"]}),
    (("kitchen", "skillet", "fryer", "beeswax", "compost", "cookware", "bakeware", "utensil"),
     {"tags": ["kitchenware", "housewares", "consumer goods"], "industries": ["consumer goods"]}),
    (("baby", "infant", "toddler", "diaper", "stroller", "nursery"),
     {"tags": ["baby products", "parenting", "consumer goods"], "industries": ["consumer goods"]}),
    (("foam roller", "pull up", "jump rope", "hiking", "outdoor", "camping", "trail"),
     {"tags": ["outdoor recreation", "sports", "fitness"], "industries": ["sporting goods"]}),
    (("cord", "organizer", "desk", "office", "laptop stand", "monitor", "ergonomic"),
     {"tags": ["office supplies", "consumer goods", "technology"], "industries": ["consumer goods"]}),
    (("car", "automotive", "dash cam", "seat organizer", "vehicle"),
     {"tags": ["automotive", "consumer goods"], "industries": ["consumer goods"]}),
]


def resolve_apollo_niche(niche: str) -> dict:
    """Return {'tags': [...], 'industries': [...]} for a niche term."""
    n = (niche or "").strip().lower()
    if n in APOLLO_NICHE_TAG_MAP:
        return APOLLO_NICHE_TAG_MAP[n]
    for keywords, mapping in APOLLO_NICHE_FALLBACK_RULES:
        if any(kw in n for kw in keywords):
            return mapping
    # Last-resort: keep behavior loose but at least don't pass the niche string
    # as a literal keyword tag (which is what produced the food results).
    return {"tags": [], "industries": []}

# ---------------------------------------------------------------------------
# Concurrency knobs — drive the async pipeline
# ---------------------------------------------------------------------------
# Max concurrent in-flight requests per provider. OpenRouter accepts ~50 per key;
# Apollo's documented soft limit is ~5 concurrent on /people endpoints.
MAX_LLM_CONCURRENCY = int(os.getenv("MAX_LLM_CONCURRENCY", "25"))
MAX_APOLLO_CONCURRENCY = int(os.getenv("MAX_APOLLO_CONCURRENCY", "5"))
MASS_PROSPECT_PER_NICHE = int(os.getenv("MASS_PROSPECT_PER_NICHE", "25"))

# ---------------------------------------------------------------------------
# Prompt files
# ---------------------------------------------------------------------------
RUFUS_PROMPT_PATH = os.getenv(
    "RUFUS_PROMPT_PATH",
    "prompts/rufus_system_prompt.txt",
)
COLD_EMAIL_RULES_PATH = os.getenv(
    "COLD_EMAIL_RULES_PATH",
    "rules/banned_phrases.json",
)
# Apify caps per-input-batch size. 200 keywords/URLs in one actor run is well under the limit
# and is the natural shard for the orchestrator when category lists exceed this.
APIFY_BATCH_SIZE = int(os.getenv("APIFY_BATCH_SIZE", "200"))
LLM_REQUEST_TIMEOUT_S = float(os.getenv("LLM_REQUEST_TIMEOUT_S", "120"))
APOLLO_REQUEST_TIMEOUT_S = float(os.getenv("APOLLO_REQUEST_TIMEOUT_S", "30"))

