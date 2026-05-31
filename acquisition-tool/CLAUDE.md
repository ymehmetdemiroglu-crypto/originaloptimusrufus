# Optimus Rufus — Amazon listing audit → Apollo outreach

Outbound prospecting tool for Optimus Rufus (Amazon Rufus AI listing visibility auditor). Scrapes weak Amazon listings, scores them on the 4 Rufus citation axes, enriches the brand decision-maker via Apollo, drafts a personalized teardown grounded in the per-axis scores, and enrolls the contact in an Apollo sequence.

## One funnel, two entry points

Every outbound email is now ASIN-grounded and fully AI-generated per recipient (no shared template, no category-generic copy). The two entry points feed the same drafting pipeline:

**Entry A — Amazon-first:** `/rufus-audit` — scrapes Amazon listings, scores them, enriches via Apollo, sends ASIN-specific teardown.

**Entry B — Apollo-first:** `/prospect` — searches Apollo directly for decision-makers at supplement/skincare brands, then **mandatorily backfills their ASINs via Apify** before drafting. If no ASIN can be found, the brand is moved to `SKIP_NO_LISTING` rather than receiving generic copy.

## Funnel A: Amazon listing → Apollo outreach

```
/rufus-audit [category1] [category2] ... [--limit=N] [--no-llm]
```

```
Apify Amazon search (axesso_data/amazon-search-scraper)
    ↓  pages 2–6, niche subcategory seeds
    ↓
Cheap pre-filter on search-stage data         ← drops ~60–70% of junk before paying detail cost
    ↓  (price band, review band, brand blocklist, brand cap, ASIN-already-in-DB cache)
    ↓
Apify detail (axesso_data/amazon-product-details-extractor)
    ↓  full bullets, A+ content, Q&A, images, BSR
    ↓
BSR filter (post-detail, only field not in search results)
    ↓
data/prospects.db prospects table  (source='amazon_listing', stage='LISTING_FOUND')
    ↓
Rule-based weakness score (weakness_scorer.py — 7 rules, runs in ms)
    ↓
LISTING_FOUND → WEAK_LISTING / SKIP
    ↓
brand_rollup.consolidate() — group ASINs by brand_key, pick worst as anchor
    ↓
data/prospects.db brands table (one row per brand, source='amazon_scrape')  →  WEAK_BRAND
    ↓
auto-enrich (calls Apollo REST API directly)    ← ENRICHMENT BEFORE LLM SCORING
    ↓    searches by brand_name/domain
    ↓    matches target_titles → email + name
WEAK_BRAND → BRAND_RESOLVED → CONTACT_ENRICHED
    ↓
LLM Rufus 4-axis score (rufus_scorer.py — ONLY anchor ASINs of CONTACT_ENRICHED brands)
    ↓  0–25 per axis → 0–100 total + low/medium/high citation probability + top weaknesses + summary
    ↓  command: rufus-score-enriched   ← pays per reachable contact, not per listing
    ↓
LLM teardown (cold_email.py) — anchored on per-axis Rufus scores + top weaknesses
    ↓
EMAIL_DRAFTED  →  SEQUENCED (APOLLO_SEQUENCE_ID — personalized)
    ↓
REPLIED → DEMO_SCHEDULED → BETA_ACTIVE → PAID
```

## Funnel B: Apollo-first → generic audit offer

```
/prospect <category>
# (Claude will execute: python main.py auto-prospect <category>)
```

```
auto-prospect (calls Apollo REST API directly)
    ↓    searches target_titles, employees=1-50, US, verified
    ↓    Search 1: python main.py auto-prospect "supplements"
    ↓    Search 2: python main.py auto-prospect "skincare"
    ↓
Filter (skip agencies, mega-brands, no-email, marketplace domains)
    ↓
save-apollo-prospect → brands table (anchor_asin='apollo_direct', source='apollo_search')
                                                CONTACT_ENRICHED
    ↓
Mandatory ASIN backfill (backfill_asins.py — auto-chained after auto-prospect)
    ↓    Apify fuzzy-match brand → anchor ASIN
    ↓    no ASIN found → SKIP_NO_LISTING (no generic copy ever sent)
    ↓
LLM Rufus 4-axis score on the backfilled anchor ASIN
    ↓
LLM teardown — same draft_teardown as Funnel A (per-recipient unique copy)
    ↓
EMAIL_DRAFTED  →  SEQUENCED (APOLLO_SEQUENCE_ID)
    ↓
REPLIED → DEMO_SCHEDULED → BETA_ACTIVE → PAID
```

### Funnel B Upgrade Path (Apollo → Amazon)
If you source leads via Funnel B but want to send them the highly personalized Funnel A copy, you can "upgrade" them by backfilling their ASINs:
```bash
# 1. High-speed batch Apify scrape to find & link ASINs for Apollo-direct leads
python backfill_asins.py

# 2. Score the newly found ASINs using the LLM
python main.py rufus-score-enriched

# 3. Draft the personalized teardown emails
python main.py draft-emails
```

## Hybrid execution model

- **Python CLI** does scrape, score, Apollo API calls, draft, and DB I/O.
- **Claude (in this conversation)** listens for commands like `/rufus-audit`, `/prospect`, or "enrich the queue" and translates them into the equivalent `python main.py` CLI executions.
- The pipeline uses direct `requests` calls to the Apollo REST API (`apollo_api.py`), avoiding LLM context bloating.
- DB is the source of truth.

## One-time Apollo setup

See [APOLLO_SEQUENCE_SETUP.md](APOLLO_SEQUENCE_SETUP.md). The Apollo sequence has **5 steps** acting as transport shells. Each step's subject/body is generated per recipient by `cold_email.draft_sequence` (10 LLM calls per brand: 5 subjects + 5 bodies, drafted with `deepseek/deepseek-v4-flash` via `OPENROUTER_DRAFT_MODEL`). Each step is uniqueness-checked against (a) the last 50 same-step bodies in the DB and (b) the prior steps in the same recipient's sequence, so no two emails — across recipients or within a sequence — share template phrasing.

5-step structure (see `STEP_SPECS` in [cold_email.py](cold_email.py)):
| Step | Label | Intent |
|---|---|---|
| 1 | Opening teardown | Name the worst Rufus axis + the specific listing flaw |
| 2 | Concrete fix | Show one fix grounded in the listing |
| 3 | Shopper-query proof | Two "when a shopper asks Rufus 'X'…" constructions |
| 4 | Soft nudge | Short check-in tied to step 1's observation |
| 5 | Final breakaway | One-line sign-off that opens a future thread |

Per-step copy is stored in the `brand_step_emails` table (one row per `(brand_key, step_num)`). For backward compatibility, step 1's subject/body is also mirrored onto `brands.custom_subject` / `brands.custom_body`.

Custom contact fields pushed to Apollo: `custom_subject_1..5`, `custom_body_1..5` (one per step), plus `asin` and `custom_category`. The legacy `custom_subject` / `custom_body` / `weakness_teardown` fields still receive step 1 for back-compat.

## Workflow

### Funnel A — Amazon-first (run as needed, ~weekly)

```bash
# 1. Scrape + rule-score + rollup (NO LLM — free)
python main.py rufus-audit
# OR with specific categories
python main.py rufus-audit "magnesium glycinate" "vitamin c serum" --limit=50

# 2. Enrich the queue automatically via Apollo API
python main.py auto-enrich

# 3. LLM Rufus-score ONLY the enriched brands' anchor ASINs (pay per reachable contact, not per listing)
python main.py rufus-score-enriched

# 4. Draft cold-email teardowns (grounded in per-axis Rufus scores)
python main.py draft-emails

# 5. Show send queue — personalized brands will show APOLLO_SEQUENCE_ID
python main.py send-queue

# 6. In Claude: "send the queue" → Claude creates Apollo contacts + adds to sequence → mark-sequenced
```

### Funnel B — Apollo-first (run 2× per week, Mon + Thu)

### Funnel B — Apollo-first (run 2× per week, Mon + Thu)

```bash
# In Claude, simply type:
/prospect "supplements"
/prospect "skincare"

# Claude will automatically run:
# python main.py auto-prospect "supplements"
# python main.py draft-emails
# ...and then help you enroll them in sequences.
```

### Both funnels

```bash
# Check pipeline health
python main.py dashboard

# When replies come in
python main.py replied <id> "their reply text"
```

## All commands

| Command | Description |
|---|---|
| `rufus-audit [cat …] [--limit=N]` | Scrape → rule-score → rollup → enrich queue (no LLM) |
| `amazon-scrape <category> [--limit=N]` | Scrape one category (search + pre-filter + detail + BSR + rule-score + rollup) |
| `score` | Re-score any unscored listings (rule-based only) |
| `rufus-score-enriched` | **LLM Rufus-score only anchor ASINs of CONTACT_ENRICHED brands** (run after enrichment) |
| `rufus-score [<id>]` | LLM Rufus 4-axis score for one prospect, or all WEAK_LISTING (use sparingly) |
| `consolidate-brands` | Manually roll up WEAK_LISTING ASINs into brand-level rows |
| `auto-enrich` | Iterates over WEAK_BRAND rows, enriches via Apollo API, updates to CONTACT_ENRICHED |
| `auto-prospect <category>` | Searches Apollo API directly and inserts prospects to DB |
| `enrich-queue` | (Legacy) List WEAK_BRAND brands awaiting Apollo enrichment |
| `set-enrichment <brand_key> …` | (Legacy) Write Apollo enrichment back |
| `save-apollo-prospect <brand_key> …` | (Legacy) Insert an Apollo-sourced contact directly |
| `draft-emails` | Generate teardown for CONTACT_ENRICHED brands |
| `send-queue` | List EMAIL_DRAFTED brands ready for sequence add |
| `apollo-sequence` | Automatically enroll EMAIL_DRAFTED brands in Apollo sequences |
| `mark-sequenced <brand_key> <apollo_contact_id>` | Mark brand as enrolled |
| `dashboard` / `stats` / `list` / `show` / `move` / `note` / `export` / `replied` / `open` | Pipeline ops |
| `brand-replied <brand_key>` | Mark brand REPLIED + stamp `replied_at` (drives reply-stats) |
| `reply-stats` | Reply rate broken down by worst Rufus axis at send |
| `uniqueness-report [--limit=N]` | Pairwise 5-gram overlap across recent generated bodies — sanity check the anti-template guard |

### Standalone Tools
| Command | Description |
|---|---|
| `python backfill_asins.py` | Batch Apify scrape to find ASINs for Apollo-sourced leads. Safely handles DB locks. |
| `python export_apollo.py` | Export fully enriched, teardown-ready contacts to a CSV mapped perfectly for Apollo import. |

## Pipeline stages

```
Funnel A (Amazon-first):
LISTING_FOUND → WEAK_LISTING ──(brand_rollup)──→ WEAK_BRAND → CONTACT_ENRICHED ──┐
              ↘ SKIP                                                               │
                                                                                   ↓
Funnel B (Apollo-first):                              save-apollo-prospect → CONTACT_ENRICHED ──┐
                                                                                                 │
                                                                                   ┌─────────────┘
                                                                                   ↓
                                                                            EMAIL_DRAFTED
                                                                                   ↓
                                                      SEQUENCED → REPLIED → DEMO_SCHEDULED → BETA_ACTIVE → PAID
```

`prospects` table: per-ASIN rows (LISTING_FOUND / WEAK_LISTING / SKIP). `brands` table: one row per brand from WEAK_BRAND onward. `brands.source` = `amazon_scrape` (Funnel A) or `apollo_search` (Funnel B).

## Weakness scoring (cheap pre-filter for the LLM)

Rule-based, runs in milliseconds. Each rule contributes 1 point + a signal tag:

| Rule | Threshold (config.WEAKNESS_RULES) | Signal |
|---|---|---|
| Thin title | < 80 chars | TITLE |
| Few bullets | < 5 | BULLETS |
| No A+ content | true | ATTRIBUTES |
| Low Q&A | < 3 | QA_GAP |
| Few images | < 5 | ATTRIBUTES |
| Low review count | < 50 | NEW_LAUNCH_STUCK |
| Low rating | < 4.0 | CONVERSION |

Listings with `weakness_score >= WEAKNESS_THRESHOLD` (default 3) → `WEAK_LISTING`. Others → `SKIP`. Only WEAK_LISTING rows get the (more expensive) LLM Rufus score.

## Rufus optimization scoring (the deliverable)

`rufus_scorer.py` runs an LLM 4-axis evaluation on every WEAK_LISTING. Each axis is scored 0–25 → 0–100 total. Stored on the prospect:

| Axis | What it measures |
|---|---|
| `intent_alignment_score` | Does title/bullet copy use the language shoppers type into Rufus queries? |
| `attribute_density_score` | Are measurable, structured attributes (mg, IU, cert badges, dietary flags) present? |
| `conversational_readability_score` | Can Rufus extract a clean quotable sentence, or is everything passive/marketing fluff? |
| `qa_coverage_score` | Does the Q&A section cover pre-purchase questions Rufus would be asked? |

Plus: `rufus_citation_probability` (low/medium/high), `rufus_top_weaknesses` (JSON of {axis, issue, fix} entries grounded in the actual listing), `rufus_summary` (one sentence).

The cold-email teardown ([cold_email.py](cold_email.py)) is grounded in this data when present — so the email names specific axis scores and quotes specific observations from the listing.

## Cost optimisation built in

- **Search-stage pre-filter** kills ~60–70% of junk ASINs before paying for detail (price/reviews/blocklist applied to free axesso search output).
- **Brand cap** (`AMAZON_MAX_ASINS_PER_BRAND`, default 1) — rollup picks one anchor per brand anyway, so don't pay detail cost on duplicates.
- **ASIN-in-DB cache** (`db.asin_exists`) — never re-fetch detail for an ASIN we've already scored.
- **`--no-llm` flag** on `/rufus-audit` for cost-free dry runs (still does scrape + rule-score + rollup).

## Seed categories (config.AMAZON_SEED_CATEGORIES)

Niche subcategory queries (ingredient-led / function-led / item-led) that index to SMB owner-operated brands rather than bestsellers. Examples: `magnesium glycinate`, `vitamin c serum`, `calming dog treats`, `electric milk frother`, `resistance bands set`, `monitor stand riser`. Generic seeds like "supplements" surface Amazon Basics + mega-brands; niche queries surface our buyer.

## Targeting filters

| Filter | Range | Stage applied | Why |
|---|---|---|---|
| Price | $20–$120 | Search (cheap) | Below = commodity; above = enterprise |
| Reviews | 50–2000 | Search (cheap) | Below = no traction; above = mega-brand |
| Brand blocklist | Amazon house + mega-brands | Search (cheap) | Hard exclude (Amazon Basics, Anker, Bose, Ninja, Nature Made, etc.) |
| Brand cap | 1 ASIN/brand | Search (cheap) | Rollup picks one anchor anyway |
| ASIN already in DB | — | Search (cheap) | Don't re-fetch what we've already paid for |
| BSR | 5,000–50,000 | Detail (post-fetch) | BSR rarely on search pages; below = bestseller, above = no velocity |
| Search pages | 2–6 | Search | Skip page 1 (bestsellers + Amazon Basics) |

## Environment variables (`.env`)

```
OPENROUTER_API_KEY=                    # required — Rufus + teardown LLM
APIFY_TOKEN=                           # required — Amazon search + detail (Funnel A only)
APOLLO_API_KEY=                        # required — Apollo enrichment and prospecting
APOLLO_SEQUENCE_ID=                    # required — personalized sequence (Funnel A)
APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID=     # required — paste from apollo_email_accounts_index
# Optional overrides
APIFY_AMAZON_SEARCH_ACTOR_ID=axesso_data/amazon-search-scraper
APIFY_AMAZON_DETAIL_ACTOR_ID=axesso_data/amazon-product-details-scraper
OPENROUTER_MODEL=deepseek/deepseek-v4-pro        # Rufus scorer
OPENROUTER_DRAFT_MODEL=deepseek/deepseek-v4-flash  # cold email drafting
```

## Key files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point + `cmd_rufus_audit` end-to-end runner |
| `config.py` | Seeds, filter bands, blocklist, Apollo IDs, model, actor IDs |
| `amazon_scraper.py` | Search + cheap pre-filter + detail fetch + BSR filter |
| `apollo_api.py` | Apollo REST API integration for automated enrichment |
| `weakness_scorer.py` | Rule-based listing pre-filter |
| `rufus_scorer.py` | LLM 4-axis Rufus optimization scorer |
| `brand_rollup.py` | Group WEAK_LISTING ASINs by brand_key → brands table |
| `cold_email.py` | LLM teardown generator (grounded in Rufus axis scores when present) |
| `cli.py` | Display + manual stage-move helpers |
| `db.py` / `models.py` | SQLite + Prospect/Brand dataclasses + helpers |
| `backfill_asins.py` | High-speed, batched script to upgrade Funnel B leads to Funnel A by scraping their ASINs. |
| `export_apollo.py` | Export teardown-ready contacts to a structured CSV for direct Apollo import. |
| `APOLLO_SEQUENCE_SETUP.md` | One-time manual setup guide |
| `data/prospects.db` | SQLite database (prospects + brands tables) |

## What was removed

The legacy social funnel (Reddit / Twitter / Facebook / YouTube scraping, ranking, DM generation, follow-ups, daily campaign) has been deleted. The DB schema retains the historical Reddit columns (`subreddit`, `post_score`, etc.) so old rows remain queryable, but the new pipeline is Amazon-listing-only.
