# Optimus Rufus — Listing Assessment Strategy v2

## The Problem with v1

Your old strategy had three fundamental flaws that burned leads and wasted LLM tokens:

1. **Crude pre-filter.** The rule-based weakness scorer used binary thresholds (`title < 80 chars = +1`). It treated a 20-char title the same as a 75-char title. It couldn't detect attribute density, caps spam, or vague copy without paying for an LLM call.

2. **No client quality gate.** The system scored *listing weakness* but never scored *client quality*. You were burning email credits on:
   - Mega-brands that already have agencies
   - Early-stage brands with 12 reviews and no budget
   - Brands where we only have a "Marketing Manager" contact
   - Low-price-point products (<$15) with no SaaS budget

3. **Static Rufus scoring.** The 4-axis LLM prompt scored listings in isolation. It didn't benchmark against competitors, didn't consider visual/A+ content, and gave the same weight to supplements as kitchenware.

---

## v2 Architecture: Three-Layer Assessment

```
Layer 1: Listing Quality Scorer  (cheap, weighted, predictive)
    ↓
Layer 2: Client Quality Scorer   (filters time-wasters before enrichment)
    ↓
Layer 3: Rufus v2 LLM Scoring    (6-axis, competitor-aware, category-aware)
    ↓
Reachability Index × Intent Score  →  send-queue priority
```

---

## Layer 1 — Enhanced Listing Quality Scorer

**Replaces:** `weakness_scorer.py`  
**New file:** `listing_quality_scorer.py`

### What changed
- **Severity-weighted penalties:** A 20-char title hurts more than a 75-char title. Missing ALL 6 attribute types hurts more than missing 2.
- **Regex-based attribute detection per category:** Detects mg/IU/count for supplements, oz/%/actives for skincare, protein/health-goal for pet — all without LLM cost.
- **Bullet quality analysis:** Detects ALL CAPS spam, emoji/symbol spam, vague phrases ("premium", "best in class"), and missing question-answering structure.
- **Competitive position signals:** High volume + low rating = urgent fixable gap. Low price = no budget.

### Score breakdown (0–100, higher = more gaps)
| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Title Quality | 0–20 | Length, structure, measurement info, caps spam |
| Bullet Quality | 0–25 | Count, length, readability, vagueness, QA structure |
| Attribute Density | 0–20 | Category-specific structured attributes present |
| Q&A Coverage | 0–15 | Count + coverage breadth |
| Visual/Structured | 0–15 | Images, A+ content, infographics |
| Competitive Position | 0–10 | Revenue proxy, rating, BSR, price point |

### Gate
```
WEAK_LISTING if quality_score >= 35 AND at least one structural signal
SKIP otherwise
```

---

## Layer 2 — Client Quality Scorer

**New file:** `client_quality_scorer.py`

This is the layer v1 was missing entirely. It answers: *"If we fix this listing, will they actually pay us?"*

### Score breakdown (0–100, higher = better client)
| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Revenue Potential | 0–25 | Price × review proxy = estimated monthly revenue |
| Decision-Maker Access | 0–25 | Do we have founder/CEO email? First name? LinkedIn? |
| Market Maturity | 0–25 | Sweet spot: 100–1500 reviews, 3.8–4.7 rating |
| Growth Trajectory | 0–15 | High volume + fixable rating, new but promising, strong BSR |
| Category Attractiveness | 0–10 | Supplements/skincare invest heavily; automotive/tools less so |

### Key filters
| Signal | Action |
|--------|--------|
| `BLOCKLISTED_BRAND` | Score = 0, never reach out |
| `NO_EMAIL` | Score = 0, never reach out |
| `TOO_EARLY` (<50 reviews) | -8 points, usually skips |
| `LIKELY_HAS_AGENCY` (>3000 reviews) | -5 points |
| `LOW_PRICE_NO_BUDGET` (<$15) | -5 to -7 points |
| `FOUNDER_TITLE` | +8 points, priority boost |
| `PREMIUM_PRICE_POINT` (>$35) | +points, higher LTV |

### Reachability Index
```
reachability = (listing_need ^ 0.9) × (client_quality ^ 1.1) × 100
```
- Both need to be high. A perfect client with a perfect listing = low priority.
- A terrible client with a terrible listing = low priority (can't convert).
- **Sweet spot:** client_quality > 50 AND listing_quality > 40.

---

## Layer 3 — Rufus v2 LLM Scoring (6-Axis)

**Replaces:** `prompts/rufus_system_prompt.txt`  
**New file:** `prompts/rufus_system_prompt_v2.txt`

### What changed
- **6 axes instead of 4** (0–20 each, total 0–120):
  1. Intent Alignment
  2. Attribute Density *(now category-aware)*
  3. Conversational Readability
  4. Q&A Coverage
  5. **Visual & Structured Content** *(new)* — images, A+, infographics, video
  6. **Competitive Relativity** *(new)* — how they stack vs top 3 competitors

- **Competitor benchmarking:** The prompt includes top 3 competitor bullets, Q&A counts, image counts, A+ status, and ratings. The LLM must compare the target listing to competitors on every axis.

- **Category-aware attributes:** The prompt instructs the LLM to score attribute density differently for supplements vs skincare vs pet vs kitchen. No more treating a kitchen tool like a vitamin.

- **Severity ratings:** Every weakness now has a severity (`critical` / `high` / `medium` / `low`) so email copy can calibrate urgency.

- **Competitive summary:** New output field — a one-sentence competitor comparison that feeds directly into Step 3 of the cold email sequence.

### Toggle
```bash
# v2 (default)
export USE_RUFUS_V2=true

# v1 (legacy)
export USE_RUFUS_V2=false
```

Or per-command:
```bash
py main.py rufus-score <asin> --v2
py main.py rufus-score-enriched --v2
```

---

## Enhanced Intent Signals

**Updated file:** `intent_signals.py`

Intent scoring now incorporates:
- **Client quality boost:** `high_reachability` (+12), `premium_client` (+8), `founder_access` (+6)
- **Visual content gap:** `low_images` (+6), `critical_images` (+10)
- **Competitor image dominance:** +5 if competitors have 1.5× more images
- **Reachability penalty:** `low_reachability` (-10), `poor_client_fit` (-8)

Brands are sorted by `intent_score` desc in the send queue. High-intent + high-reachability brands get emailed first.

---

## Pipeline Changes

### `main.py rufus-audit` (end-to-end)
Now runs:
1. Scrape
2. **Enhanced quality scoring** (was: crude weakness scoring)
3. Brand rollup
4. **Client quality scoring** *(new)*
5. Print enrich queue with reachability index

### `main.py client-quality-score`
New command. Run this after rollup and after enrichment to score/re-score brands:
```bash
py main.py client-quality-score WEAK_BRAND --limit=100
py main.py client-quality-score CONTACT_ENRICHED --limit=100
```

### `main.py rufus-score-enriched`
Now supports `--v2` flag for 6-axis competitor-aware scoring.

### Brand rollup
Now picks the anchor ASIN by `quality_score` (new) or falls back to `weakness_score` (legacy).

### Enrichment queue
Now sorted by `reachability_index` desc first, then `max_weakness_score` desc.

---

## DB Schema Additions

### `prospects` table
```sql
quality_score int,
quality_signals text,
quality_breakdown jsonb,
visual_structured_content_score int,
competitive_relativity_score int,
competitive_summary text
```

### `brands` table
```sql
client_quality_score int,
client_quality_signals text,
client_quality_breakdown jsonb,
reachability_index int
```

---

## Quick Start

```bash
# 1. Run the full audit pipeline (now uses enhanced scoring automatically)
py main.py rufus-audit

# 2. After Apollo enrichment, score with v2 (competitor-aware)
py main.py rufus-score-enriched --v2

# 3. Compute client quality + intent for enriched brands
py main.py client-quality-score CONTACT_ENRICHED --limit=100
py main.py intent-score CONTACT_ENRICHED --limit=100

# 4. Draft emails (automatically uses worst axis from v2 if available)
py main.py draft-emails

# 5. View send queue (sorted by intent_score, with reachability visible)
py main.py send-queue
```

---

## Expected Improvements

| Metric | v1 | v2 Target |
|--------|-----|-----------|
| Pre-filter accuracy (% that later score <50 on Rufus) | ~60% | ~85% |
| Email-to-reply rate | ~3-5% | ~8-12% |
| Reply-to-demo rate | ~15% | ~25% |
| LLM tokens wasted on un-mailable brands | ~20% | ~5% |
| Time spent on low-budget / early-stage brands | High | Minimal |

---

## Migration Notes

- **Backward compatible:** The old `weakness_score` and `weakness_signals` fields are still populated. Legacy queries still work.
- **Opt-in v2 Rufus:** Set `USE_RUFUS_V2=true` in your `.env` or pass `--v2` to commands.
- **No DB migration needed** if your Supabase tables already allow dynamic columns (they do via the Python ORM layer). If you have a strict schema, add the columns listed above.
- The old `weakness_scorer.py` still exists and can be imported manually if needed.
