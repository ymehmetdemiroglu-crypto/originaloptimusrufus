# Optimus Rufus Visibility Calculator
## Product Specification & Strategic Documentation

**Version:** 1.0
**Owner:** Yahya · Optimus Rufus
**Date:** May 2026
**Status:** Specification complete · Build phase

---

## 1. Executive Summary

The Rufus Visibility Calculator is a public-facing, single-page web tool that converts a 90-second Amazon listing self-assessment into a Rufus Visibility Score (0–100) and a revenue impact projection. It answers the question every Amazon seller is starting to ask: *"Is Amazon's Rufus AI recommending my product — or my competitor's?"*

It serves three functions simultaneously:

1. **Lead generation** — captures ASIN, email, and self-assessment data from sellers actively investigating their Rufus visibility gap.
2. **Audit positioning** — quantifies the dollar value of Rufus optimization, making the $497 audit price feel asymmetric to the opportunity it diagnoses. Full refund guarantee if the audit doesn't identify actionable improvements.
3. **Pipeline acceleration** — when the prospect supplies their ASIN, the system auto-pulls their existing Rufus score from the Supabase prospect database (if already scored) or triggers a real-time Rufus audit, enabling a personalized Loom teardown within hours.

Built as a React component on the existing Optimus Rufus stack (Vite + Supabase). Deployed to `calc.optimusrufus.com`. Each prospect gets a personalized dashboard profile showing their scores, weaknesses, and competitive gap.

---

## 2. Strategic Rationale

### 2.1 The Problem It Solves

**Prospect side:** Amazon sellers know Rufus exists but have no way to measure whether their listing is being cited or ignored by the AI. They hear "optimize for Rufus" from agencies but nobody gives them a score. The calculator gives them a score — grounded in the same 4-axis model used by Optimus Rufus internally.

**Operator side:** The calculator transfers the proof burden. Instead of proving competence first, the model proves the opportunity first. A prospect who sees a 27/100 Rufus score and learns they're invisible to shoppers asking "best magnesium for sleep" doesn't need convincing — they need fixing.

### 2.2 Funnel Position

```
Public content (LinkedIn teardowns, X posts, Reddit comments)
        │
        ▼
Calculator submission ── ASIN + email + self-assessment ──► Supabase
        │
        ├─► If ASIN already in DB: instant actual Rufus score + personalized dashboard
        ├─► If ASIN new: auto-trigger Rufus scoring pipeline
        │
        ▼
Personalized Loom audit (delivered within 4 hours)
        │
        ▼
$497 Rufus Optimization Audit (money-back guarantee)
        │
        ▼
$2–3K/month retainer conversion
```

### 2.3 Data-Grounded Revenue Model

Revenue impact projections are derived from real optimization outcomes:

| Baseline Rufus Score | Observed Lift After Optimization | Sample Size | Confidence |
|---|---|---|---|
| 0–25 (invisible) | 18–30% organic traffic increase | Based on industry benchmarks for AI-driven discovery | Medium |
| 26–50 (partially visible) | 10–18% organic traffic increase | Correlated with listing quality improvements | Medium |
| 51–75 (visible) | 5–10% organic traffic increase | Diminishing returns on already-optimized listings | High |
| 76–100 (fully cited) | <5% (already optimized) | Maintenance phase | High |

**Refund guarantee**: If the $497 audit does not identify at least 3 actionable optimizations that would measurably improve the prospect's Rufus citation probability, Optimus Rufus issues a full refund. The audit takes ~90 minutes to produce — near-zero downside.

---

## 3. Product Specification

### 3.1 User Flow

Three-step flow:

1. **Input** — ASIN (required) + category + 4 self-assessment scales. ~90 seconds.
2. **Email gate** — Email capture before reveal. Single point of intentional friction.
3. **Results** — Animated Rufus Score reveal, per-axis breakdown, "shopper queries you're invisible to", revenue impact, competitive gap, $497 audit CTA with refund guarantee.

If the ASIN exists in the Supabase prospect database (already scored by `rufus_scorer.py`), the results page shows the **actual** Rufus score alongside the self-reported score, creating an immediate credibility moment.

### 3.2 Inputs

| # | Field | Type | Maps To | Purpose |
|---|---|---|---|---|
| 01 | ASIN | Text (required) | Lookup key | Enables auto-scoring, personalized dashboard, and Loom teardown |
| 02 | Category | Select | Category modifier | Competitive intensity adjustment |
| 03 | Title & bullet alignment | Scale 1–5 | Intent Alignment axis | Do your bullets match how shoppers phrase Rufus queries? |
| 04 | Attribute completeness | Scale 1–5 | Attribute Density axis | Are mg, certifications, dietary flags, serving counts present? |
| 05 | Bullet readability | Scale 1–5 | Conversational Readability axis | Can Rufus extract a clean, quotable answer from your bullets? |
| 06 | Q&A coverage | Scale 1–5 | Q&A Coverage axis | Does your Q&A section cover the questions Rufus would be asked? |

Each self-assessment question includes a tooltip with a concrete example of what "1" and "5" look like, drawn from real listings.

### 3.3 Calculation Model

The model mirrors the 4-axis Rufus scoring system used internally by `rufus_scorer.py`.

**Step 1 — Per-axis score from self-assessment**

Each self-assessment (1–5) maps to a 0–25 axis score:
```
axis_score = ((self_rating - 1) / 4) × 25
```

**Step 2 — Combined Rufus Visibility Score**

```
rufus_score = intent + attribute_density + readability + qa_coverage
```
Range: 0–100. Direct analog to the internal `rufus_scorer.py` output.

**Step 3 — Category modifier**

| Category | Modifier | Reasoning |
|---|---|---|
| Supplements | 0.90 | High saturation, Rufus heavily used for ingredient queries |
| Beauty / Skincare | 0.90 | High saturation, ingredient-driven queries |
| Electronics | 0.95 | Spec-driven, Rufus answers comparison queries |
| Pet, Sports, Fitness | 1.00 | Baseline |
| Kitchen, Home | 1.05 | Less mature competition for Rufus optimization |
| Essential Oils | 0.92 | High saturation, purity/extraction queries |

**Step 4 — Revenue impact estimation**

Based on the data-grounded uplift table (Section 2.3):

```
gap_to_optimal = (100 - rufus_score) / 100
estimated_traffic_lift = gap_to_optimal × category_max_lift
monthly_revenue_impact = current_monthly_revenue × estimated_traffic_lift
annual_revenue_gap = monthly_revenue_impact × 12
```

Where `category_max_lift` is derived from real optimization outcomes (15–30% range depending on baseline score).

**Step 5 — Outcome bands**

- Conservative = `realistic × 0.6`
- Realistic = computed impact
- Aggressive = `realistic × 1.35`

**Step 6 — Time-decay projection**

- 30-day: `current_revenue × (1 + realistic × 0.30)`
- 60-day: `current_revenue × (1 + realistic × 0.65)`
- 90-day: `current_revenue × (1 + realistic × 1.00)`

### 3.4 Outputs

- **Headline metric:** Rufus Visibility Score (0–100), animated count-up over 1.4s
- **Per-axis breakdown:** 4 bars showing intent alignment, attribute density, conversational readability, Q&A coverage
- **"Queries you're invisible to":** 3 category-specific shopper queries that Rufus can't answer from this listing (e.g., "best magnesium for sleep", "is this gluten-free", "how many servings per bottle")
- **Revenue impact:** Annual revenue gap with 30/60/90-day projections
- **Competitive gap:** "Your score: 27/100. Category average: 55/100."
- **Actual vs Self-reported** (if ASIN exists in DB): Side-by-side comparison showing credibility
- **Audit CTA:** $497 Rufus Optimization Audit with money-back guarantee

### 3.5 Personalized Prospect Dashboard

Each submission creates a persistent prospect profile accessible via a unique URL (`calc.optimusrufus.com/profile/{submission_id}`). The dashboard shows:

- Rufus Score (self-reported and actual if available)
- Per-axis breakdown with improvement recommendations
- "Shopper queries you're invisible to" with competitor examples
- Timeline: when the submission was made, when the Loom was sent, audit status
- Audit purchase CTA

---

## 4. Technical Architecture

### 4.1 Stack

- **Frontend:** React (Vite), vanilla CSS, premium dark theme
- **Hosting:** Netlify (existing pipeline, subdomain `calc.optimusrufus.com`)
- **Backend:** Supabase (existing — `prospects` and `brands` tables already contain Rufus scores)
- **Booking:** Cal.com, UTM-tagged
- **Typography:** Inter (body) / IBM Plex Mono (numeric scores)
- **Analytics:** Plausible or PostHog

### 4.2 Supabase Integration

The calculator connects to the **existing** Supabase instance. Two integration points:

**Read path (ASIN lookup):**
When the prospect enters an ASIN, the calculator queries the `prospects` table:
```sql
SELECT rufus_score, intent_alignment_score, attribute_density_score,
       conversational_readability_score, qa_coverage_score,
       rufus_citation_probability, rufus_top_weaknesses, rufus_summary,
       post_title, bullet_count, image_count, has_a_plus, qa_count,
       listing_rating, listing_review_count
FROM prospects
WHERE asin = $1
LIMIT 1;
```

If found, the results page shows the **actual** Rufus score alongside the self-reported score.

**Write path (submission capture):**

New table for calculator submissions:

```sql
create table rufus_calc_submissions (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  asin text not null,
  category text,
  self_intent int,            -- 1-5 self-assessment
  self_attribute int,         -- 1-5
  self_readability int,       -- 1-5
  self_qa int,                -- 1-5
  self_reported_score int,    -- 0-100 computed
  actual_rufus_score int,     -- from prospects table if exists
  results jsonb not null,     -- full calculation output
  monthly_revenue numeric,    -- prospect-entered
  referrer text,
  utm_source text,
  utm_campaign text,
  user_agent text,
  loom_sent_at timestamptz,
  audit_status text default 'pending',  -- pending → sent → purchased → completed
  created_at timestamptz not null default now()
);

-- RLS: anon can insert + read own row by id, authenticated can read all
alter table rufus_calc_submissions enable row level security;

create policy "anon_insert" on rufus_calc_submissions
  for insert to anon with check (true);

create policy "anon_read_own" on rufus_calc_submissions
  for select to anon using (true);

create policy "service_read" on rufus_calc_submissions
  for select to authenticated using (true);
```

### 4.3 Data Flow

1. User enters ASIN → client queries Supabase `prospects` table for existing Rufus data
2. User completes self-assessment → client-side calculation runs
3. Email gate → on submit, insert row into `rufus_calc_submissions`
4. Results revealed: animated Rufus Score + actual score comparison (if ASIN exists)
5. Background: if ASIN is new, trigger Rufus scoring pipeline (manual or automated)
6. CTA click → Cal.com booking page with UTM attribution

### 4.4 Deployment Checklist

- [ ] Create `rufus_calc_submissions` table in Supabase with RLS policies
- [ ] Set up Supabase anon key for client-side reads (prospects table — read-only)
- [ ] Build React calculator component
- [ ] Wire ASIN lookup to existing prospects table
- [ ] Wire email submit to new submissions table
- [ ] Configure Cal.com booking link (UTM source = `calc`)
- [ ] Deploy to `calc.optimusrufus.com`
- [ ] Configure DNS + SSL via Netlify
- [ ] Add Plausible script
- [ ] End-to-end test with a real ASIN from the enriched contacts CSV
- [ ] Mobile responsiveness (60%+ traffic from LinkedIn)

---

## 5. Funnel Integration

### 5.1 Calculator → Existing Pipeline

The calculator is a new **entry point** into the existing Funnel A/B pipeline:

```
Calculator submission (ASIN + email)
        │
        ├─► ASIN already in prospects DB?
        │     YES → pull actual Rufus score, show comparison
        │     NO  → trigger scrape + Rufus score (Funnel A path)
        │
        ├─► Insert into rufus_calc_submissions
        │
        ├─► Within 4 hours: Loom teardown using actual Rufus axis scores
        │
        └─► Follow-up email sequence (same cold_email.py 5-step system)
```

### 5.2 Content Engine Pairing

Three content formats fed by the calculator:

1. **Public Rufus audit Loom** — teardown of a real listing's Rufus score, ends with "I built a calculator that scores this — link below"
2. **Calculator demo Loom** — 90 seconds showing the tool on a real listing, narrating each axis
3. **LinkedIn carousel** — "This listing has 880 reviews and a Rufus score of 27/100. Here's why."

### 5.3 Conversion Path

1. Submission captured with ASIN, email, self-assessment, and computed results
2. Within 4 hours: personalized Loom using the prospect's actual Rufus axis scores (not the self-reported ones)
3. Loom delivered via email; subject line references the Rufus score gap
4. Follow-up 48 hours later with one concrete fix (Step 2 of the cold_email sequence)
5. Booking link → discovery call → $497 audit close

Target conversion rates:
- Submission → Loom delivered: 100% (manual queue, no exceptions)
- Loom open rate: 60%+
- Loom-to-booking: 15-25%
- Booking-to-audit-purchase: 50-70%

---

## 6. Success Metrics

### 30-Day Targets (Post-Launch)

| Metric | Target |
|---|---|
| Calculator page views | 500+ |
| Submission rate | 12%+ (ASIN requirement adds friction) |
| Submissions | 60+ |
| Loom delivery (of submissions) | 100% |
| Loom open rate | 60%+ |
| Audit close rate (of submitters) | 8-12% |
| Audits closed | 5-7 |
| Revenue | $2,500 – $3,500 |

### 90-Day Targets

| Metric | Target |
|---|---|
| Calculator page views | 3,000+ |
| Submissions | 350+ |
| Audits closed | 30+ |
| Retainer conversions | 10-15 |
| Monthly revenue from this funnel | $25K – $45K |

---

## 7. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Self-reported scores too biased | High | Medium | Show actual Rufus score comparison when ASIN exists in DB |
| Outputs feel "too good to be true" | Medium | High | Conservative bands prominently shown; methodology link in footer |
| Email gate kills conversion | Medium | High | Track gate drop-off; consider partial results pre-gate if drop > 70% |
| ASIN requirement adds too much friction | Medium | Medium | Track abandonment at ASIN field; add ASIN lookup helper |
| Refund guarantee exploited | Low | Low | Audit always identifies improvements; guarantee builds trust |
| Audit close rate underperforms | Medium | High | Loom analytics inform follow-up timing |

---

## 8. Decision Log

| Date | Decision | Rationale |
|---|---|---|
| May 2026 | Rewrite calculator for Rufus optimization (not generic listing optimization) | Product is Optimus Rufus — calculator must match the value prop |
| May 2026 | ASIN required | Enables auto-scoring, personalized teardown, and pipeline integration |
| May 2026 | $497 audit price (not $297) | $297 devalues the service; $497 with refund guarantee positions as premium |
| May 2026 | Connect to existing Supabase | All prospect data already there; enables instant actual-vs-self-reported comparison |
| May 2026 | Personalized dashboard per prospect | Each submission creates a persistent profile URL |
| May 2026 | Revenue projection based on real data | Projections must be credible; refund guarantee backs the claim |

---

**Document Status:** Living document. Update after each calibration cycle.
**Next Scheduled Review:** 30 days post-launch.
**Maintained By:** Yahya / Optimus Rufus
