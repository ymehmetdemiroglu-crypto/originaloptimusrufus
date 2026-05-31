from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


STAGES = [
    # Outbound (Amazon listing → brand rollup → Apollo) — primary funnel
    "LISTING_FOUND",
    "WEAK_LISTING",
    "WEAK_BRAND",       # brand-level rollup of one or more WEAK_LISTING ASINs
    "BRAND_RESOLVED",
    "CONTACT_ENRICHED",
    "EMAIL_DRAFTED",
    "SEQUENCED",
    "SKIP_NO_LISTING",  # Apollo-sourced brand with no ASIN found by backfill
    "CALCULATOR_USED",  # Prospect clicked through from cold email to calculator
    "CALCULATOR_SUBMITTED",  # Prospect submitted email on calculator
    "LINKEDIN_CONNECTED",  # Accepted LinkedIn connection request
    # Shared mid/late stages
    "REPLIED",
    "DEMO_SCHEDULED",
    "BETA_ACTIVE",
    "REVIEW_REQUESTED",
    "PAID",
    # Legacy social funnel
    "FOUND",
    "QUALIFIED",
    "LOW_FIT",
    "SKIP",
    "MESSAGED",
]


@dataclass
class RawPost:
    id: str
    username: str
    subreddit: str
    post_title: str
    post_body: str
    post_url: str
    created_at: datetime
    score: int
    num_comments: int


@dataclass
class Prospect:
    id: str
    username: str
    subreddit: str
    post_title: str
    post_body: str
    post_url: str
    pain_summary: Optional[str] = None
    rank_score: Optional[int] = None
    pain_intensity: Optional[int] = None
    fit_score: Optional[int] = None
    urgency: Optional[int] = None
    stage: str = "FOUND"
    outreach_msg: Optional[str] = None
    notes: Optional[str] = None
    messaged_at: Optional[datetime] = None
    last_followup: Optional[datetime] = None
    next_followup: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    post_score: int = 0
    num_comments: int = 0
    platform: Optional[str] = None
    followup_count: int = 0
    source: str = "reddit"

    # Amazon listing fields (source='amazon_listing')
    asin: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    listing_price: Optional[float] = None
    listing_rating: Optional[float] = None
    listing_review_count: Optional[int] = None
    bullet_count: Optional[int] = None
    image_count: Optional[int] = None
    has_a_plus: Optional[bool] = None
    qa_count: Optional[int] = None
    weakness_score: Optional[int] = None
    weakness_signals: Optional[str] = None  # comma-joined: TITLE,BULLETS,…
    brand_key: Optional[str] = None         # normalized brand slug for rollup

    # Apollo enrichment fields
    domain: Optional[str] = None
    contact_email: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_linkedin: Optional[str] = None
    apollo_person_id: Optional[str] = None
    apollo_organization_id: Optional[str] = None
    apollo_contact_id: Optional[str] = None

    # Cold email
    email_teardown: Optional[str] = None

    # Enhanced Listing Quality Score (weighted, predictive, category-aware)
    quality_score: Optional[int] = None                      # 0–100, higher = more gaps
    quality_signals: Optional[str] = None                    # comma-joined signal tags
    quality_breakdown: Optional[str] = None                  # JSON of per-dimension scores

    # Rufus Optimization Score (LLM-powered 6-axis analysis)
    rufus_score: Optional[int] = None                        # 0–120 total (v2) or 0–100 (v1)
    intent_alignment_score: Optional[int] = None             # 0–20 (v2) or 0–25 (v1)
    attribute_density_score: Optional[int] = None            # 0–20 (v2) or 0–25 (v1)
    conversational_readability_score: Optional[int] = None   # 0–20 (v2) or 0–25 (v1)
    qa_coverage_score: Optional[int] = None                  # 0–20 (v2) or 0–25 (v1)
    visual_structured_content_score: Optional[int] = None    # 0–20 (v2 only)
    competitive_relativity_score: Optional[int] = None       # 0–20 (v2 only)
    rufus_citation_probability: str = ""                     # low / medium / high
    rufus_top_weaknesses: str = ""                           # JSON array of {axis, issue, fix, severity}
    rufus_summary: str = ""                                  # one-sentence explanation
    competitive_summary: Optional[str] = None                # v2 only: how they compare to rivals

    # Seller info (from seller profile scrape)
    seller_id: Optional[str] = None
    seller_domain: Optional[str] = None
    seller_business_name: Optional[str] = None
    seller_country: Optional[str] = None
    seller_feedback_pct: Optional[float] = None



@dataclass
class Brand:
    """Brand-level rollup of one or more weak Amazon listings — the unit of email outreach."""
    brand_key: str
    brand_name: str
    anchor_asin: str
    asin_count: int = 1
    max_weakness_score: Optional[int] = None
    weakness_signals: Optional[str] = None  # comma-joined union across ASINs
    category: Optional[str] = None
    stage: str = "WEAK_BRAND"

    # Apollo enrichment
    domain: Optional[str] = None
    contact_email: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_linkedin: Optional[str] = None
    apollo_person_id: Optional[str] = None
    apollo_organization_id: Optional[str] = None
    apollo_contact_id: Optional[str] = None

    email_teardown: Optional[str] = None
    notes: Optional[str] = None
    source: str = "amazon_scrape"   # 'amazon_scrape' | 'apollo_search'
    apollo_score: Optional[int] = None  # pre-enrichment quality score 0-100

    # Brand-level Rufus score (aggregated from all ASINs)
    brand_rufus_score: Optional[int] = None

    # Per-recipient generated copy (no shared template across sends)
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None
    worst_axis_at_send: Optional[str] = None  # intent | attribute | conversational | qa
    replied_at: Optional[datetime] = None
    calculator_url: Optional[str] = None
    calculator_used_at: Optional[datetime] = None
    calculator_submitted_at: Optional[datetime] = None
    loom_url: Optional[str] = None
    loom_recorded_at: Optional[datetime] = None

    # Intent signals
    intent_score: Optional[int] = None
    intent_signals: Optional[str] = None
    intent_summary: Optional[str] = None

    # Client Quality Score (0-100, higher = better client)
    client_quality_score: Optional[int] = None
    client_quality_signals: Optional[str] = None
    client_quality_breakdown: Optional[str] = None

    # Reachability Index (0-100, geometric mean of listing need × client quality)
    reachability_index: Optional[int] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
