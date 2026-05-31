"""Agent-specific configuration loaded from environment variables."""

import os
from pathlib import Path

# Resolve acquisition tool path (mirrors backend/main.py pattern)
ACQUISITION_TOOL_DIR = (
    Path(__file__).resolve().parent.parent.parent / "acquisition-tool"
)

# Feature toggles -----------------------------------------------------------
AGENT_ENABLED = os.getenv("AGENT_ENABLED", "false").lower() == "true"
AGENT_AUTO_SCRAPE = os.getenv("AGENT_AUTO_SCRAPE", "false").lower() == "true"
AGENT_AUTO_ENRICH = os.getenv("AGENT_AUTO_ENRICH", "false").lower() == "true"
AGENT_AUTO_SCORE = os.getenv("AGENT_AUTO_SCORE", "false").lower() == "true"
AGENT_AUTO_DRAFT = os.getenv("AGENT_AUTO_DRAFT", "false").lower() == "true"
AGENT_AUTO_SEQUENCE = os.getenv("AGENT_AUTO_SEQUENCE", "false").lower() == "true"
AGENT_AUTO_REPLY = os.getenv("AGENT_AUTO_REPLY", "false").lower() == "true"

# Safety limits -------------------------------------------------------------
AGENT_MAX_DAILY_SEQUENCES = int(os.getenv("AGENT_MAX_DAILY_SEQUENCES", "50"))
AGENT_REPLY_CONFIDENCE_THRESHOLD = float(os.getenv("AGENT_REPLY_CONFIDENCE_THRESHOLD", "0.85"))
AGENT_MAX_AUTO_REPLIES_PER_DAY = int(os.getenv("AGENT_MAX_AUTO_REPLIES_PER_DAY", "20"))

# Schedule times (UTC) — used by the default APScheduler config ------------
AGENT_SCHEDULE_SCRAPE_UTC = os.getenv("AGENT_SCHEDULE_SCRAPE_UTC", "06:00")
AGENT_SCHEDULE_ENRICH_UTC = os.getenv("AGENT_SCHEDULE_ENRICH_UTC", "07:30")
AGENT_SCHEDULE_SCORE_UTC = os.getenv("AGENT_SCHEDULE_SCORE_UTC", "08:00")
AGENT_SCHEDULE_DRAFT_UTC = os.getenv("AGENT_SCHEDULE_DRAFT_UTC", "08:30")
AGENT_SCHEDULE_SEQUENCE_UTC = os.getenv("AGENT_SCHEDULE_SEQUENCE_UTC", "09:00")
AGENT_SCHEDULE_REPLY_UTC = os.getenv("AGENT_SCHEDULE_REPLY_UTC", "09:30")
AGENT_SCHEDULE_SNAPSHOT_UTC = os.getenv("AGENT_SCHEDULE_SNAPSHOT_UTC", "23:00")

# Category rotation for scraping -------------------------------------------
# Tier 1 = highest priority (supplements, skincare)
AGENT_SCRAPE_TIER1_CATEGORIES = [
    "magnesium glycinate",
    "ashwagandha capsules",
    "creatine monohydrate",
    "collagen peptides powder",
    "vitamin c serum",
    "retinol cream",
    "niacinamide serum",
]

AGENT_SCRAPE_TIER2_CATEGORIES = [
    "calming dog treats",
    "joint supplement for dogs",
    "tallow balm skincare",
    "pimple patches acne",
    "rosemary hair oil",
    "shilajit supplement",
]

AGENT_SCRAPE_TIER3_CATEGORIES = [
    "electric milk frother",
    "resistance bands set",
    "baby carrier wrap",
]

AGENT_SCRAPE_CATEGORIES = (
    AGENT_SCRAPE_TIER1_CATEGORIES
    + AGENT_SCRAPE_TIER2_CATEGORIES
    + AGENT_SCRAPE_TIER3_CATEGORIES
)

AGENT_SCRAPE_LIMIT_PER_CATEGORY = int(os.getenv("AGENT_SCRAPE_LIMIT_PER_CATEGORY", "50"))
AGENT_SCRAPE_CATEGORIES_PER_RUN = int(os.getenv("AGENT_SCRAPE_CATEGORIES_PER_RUN", "2"))

# Notifications -------------------------------------------------------------
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

# Subprocess timeouts (seconds) --------------------------------------------
JOB_TIMEOUT_SCRAPE = int(os.getenv("JOB_TIMEOUT_SCRAPE", "900"))   # 15 min
JOB_TIMEOUT_ENRICH = int(os.getenv("JOB_TIMEOUT_ENRICH", "600"))   # 10 min
JOB_TIMEOUT_SCORE = int(os.getenv("JOB_TIMEOUT_SCORE", "1200"))   # 20 min
JOB_TIMEOUT_DRAFT = int(os.getenv("JOB_TIMEOUT_DRAFT", "1200"))   # 20 min
JOB_TIMEOUT_SEQUENCE = int(os.getenv("JOB_TIMEOUT_SEQUENCE", "600"))  # 10 min
JOB_TIMEOUT_REPLY = int(os.getenv("JOB_TIMEOUT_REPLY", "300"))    # 5 min
