# NexOptimus Growth Calculator
## Product Specification & Strategic Documentation

**Version:** 0.1
**Owner:** Yahya · NexOptimus
**Date:** May 2026
**Status:** Prototype complete · Pre-deployment

---

## 1. Executive Summary

The Growth Calculator is a public-facing, single-page web tool that converts a 60-second Amazon listing self-assessment into a 90-day revenue projection. It serves three functions simultaneously:

1. **Lead generation** — captures email and listing data from sellers actively researching their performance gap.
2. **Audit positioning** — quantifies the dollar value of optimization, making the $297–$497 audit price feel asymmetric to the opportunity it diagnoses.
3. **Demonstration asset** — the output becomes a slide in every prospect-specific Loom audit, and the calculator demo itself becomes content for public LinkedIn / X teardowns.

Built on the existing NexOptimus stack (React + Netlify + Supabase). MVP deployment target: under one week from spec. Operational use begins immediately upon deployment as the top-of-funnel mechanism for the 45-day cash sprint and as the foundational asset for the longer-term Nexarch product.

---

## 2. Strategic Rationale

### 2.1 The Problem It Solves

Two adjacent problems collapse into one asset:

**Prospect side:** Amazon sellers running mid-six-figure businesses generally suspect they're underperforming but have no quantitative model for the gap. They get told "your listing could be better" by every agency on LinkedIn. None give them a number. The calculator gives them a number.

**Operator side:** Selling agency services without case-study proof is a structural disadvantage. The calculator transfers the proof burden — instead of the operator proving competence first, the model proves the opportunity first. The operator then proves they can capture it.

### 2.2 Funnel Position

```
Public content (LinkedIn teardowns, Reddit comments, FB groups)
        │
        ▼
Calculator submission ── email + inputs captured ──► Supabase
        │
        ▼
Personalized Loom audit (delivered within 4 hours)
        │
        ▼
$297 audit close
        │
        ▼
$2–3K/month retainer conversion
```

The calculator is the only conversion point between cold attention and qualified, intent-signaling leads. Everything upstream is content. Everything downstream is sales.

### 2.3 Why This Beats Alternatives

| Alternative | Why It's Worse |
|---|---|
| Direct cold outreach for management retainer | Zero proof → 1-3% conversion, 6-week sales cycle |
| Static PDF lead magnet | No per-prospect value; commodity; doesn't qualify intent |
| Internal-only CRM dashboard | Operator-facing; organizes existing pipeline but doesn't generate demand |
| Custom proposal-per-prospect | Doesn't scale; burns hours on unqualified leads |

The calculator is the only asset that scales, captures qualified intent, and produces a per-prospect artifact (the projection) usable in the next sales touch.

---

## 3. Product Specification

### 3.1 User Flow

Three-step flow, intentionally tight:

1. **Input** — Six fields, approximately 60 seconds to complete.
2. **Email gate** — Email capture before reveal. Single point of friction, intentional.
3. **Results** — Animated revenue-gap reveal, tiered projections, and audit CTA.

### 3.2 Inputs

| # | Field | Type | Purpose |
|---|---|---|---|
| 01 | Current monthly revenue | Numeric ($) | Baseline multiplier for projection |
| 02 | Category | Select | Competitive intensity modifier |
| 03 | Image quality | Scale 1–5 | Conversion rate lift potential |
| 04 | Copy quality (title / bullets / A+) | Scale 1–5 | Traffic + CVR lift potential |
| 05 | PPC structure | Scale 1–5 | Efficient spend lift potential |
| 06 | Review count | Numeric | Social proof bottleneck modifier |

### 3.3 Calculation Model

The model converts subjective quality scores into expected revenue lift using industry-derived uplift benchmarks.

**Step 1 — Per-area lift potential**

For each scored area (image, copy, PPC), the gap-to-perfect is computed as `(5 − score) / 4`, yielding a value 0–1 representing recoverable headroom.

Each area has a maximum lift coefficient derived from industry benchmarks:

- Image fix: max **17%** CVR uplift (operational range 10–25%)
- Copy fix: max **12%** combined traffic + CVR uplift (range 5–15%)
- PPC restructure: max **22%** effective revenue uplift via ACOS reduction and reclaimed spend (range 15–30%)

Per-area lift = `gap × max_coefficient`

**Step 2 — Combined lift with overlap dampening**

```
base_lift = (image_lift + copy_lift + ppc_lift) × 0.85
```

The 0.85 multiplier accounts for non-additive interaction: gains in one area partially overlap gains in others (e.g., better images lift CVR for traffic already arriving from better PPC, double-counting if added naively).

**Step 3 — Category modifier**

| Category | Modifier | Reasoning |
|---|---|---|
| Supplements | 0.85 | High saturation, brand dominance |
| Beauty | 0.90 | High saturation |
| Electronics | 0.95 | High variance, brand-driven |
| Pet, Sports | 1.00 | Baseline |
| Kitchen, Home | 1.05 | Less mature competition |

**Step 4 — Review bottleneck**

| Review count | Modifier | Reasoning |
|---|---|---|
| Under 50 | 0.70 | Social proof gate dampens any optimization |
| 50–199 | 0.85 | Partial bottleneck |
| 200+ | 1.00 | Bottleneck released |

**Step 5 — Outcome bands**

- Conservative = `realistic × 0.6`
- Realistic = computed lift
- Aggressive = `realistic × 1.3`

**Step 6 — Time-decay projection**

- 30-day: `current_revenue × (1 + realistic × 0.35)`
- 60-day: `current_revenue × (1 + realistic × 0.70)`
- 90-day: `current_revenue × (1 + realistic × 1.00)`

Reflects compounding nature of organic ranking improvements and ad relevance scoring — gains accumulate non-linearly across the optimization window.

### 3.4 Outputs

- **Headline metric:** annual revenue gap (`monthly_gap × 12`), animated count-up over 1.4s for emotional impact at reveal
- 30 / 60 / 90-day revenue projections, side-by-side
- Conservative / Realistic / Aggressive bands at 90 days
- Identified weak areas with per-area lift percentages
- Audit offer ($297 founding rate / $497 standard) with money-back guarantee

---

## 4. Technical Architecture

### 4.1 Stack

- **Frontend:** React, single-file component, Tailwind utility classes, lucide-react icons
- **Hosting:** Netlify (existing deployment pipeline, proposed subdomain `calc.nexoptimus.com`)
- **Backend:** Supabase
- **Booking:** Cal.com or Calendly link, UTM-tagged
- **Typography:** Instrument Serif (display) / IBM Plex Sans (body) / IBM Plex Mono (numeric)
- **Analytics:** Plausible or PostHog (lightweight, privacy-respecting)

### 4.2 Supabase Schema

```sql
create table growth_calc_submissions (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  inputs jsonb not null,
  results jsonb not null,
  referrer text,
  utm_source text,
  utm_campaign text,
  user_agent text,
  created_at timestamptz not null default now()
);

-- RLS: anon role can insert only, authenticated role can read
alter table growth_calc_submissions enable row level security;

create policy "anon_insert" on growth_calc_submissions
  for insert to anon with check (true);

create policy "service_read" on growth_calc_submissions
  for select to authenticated using (true);
```

### 4.3 Data Flow

1. User submits inputs → client-side calculation runs (no API call required for math)
2. Email gate triggered → on submit, insert row into `growth_calc_submissions`
3. Results revealed client-side with animated reveal
4. CTA click → external redirect to booking page with UTM attribution

### 4.4 Deployment Checklist

- [ ] Create Supabase table with RLS policies as specified above
- [ ] Wire email submit handler to Supabase client `insert()`
- [ ] Configure Cal.com / Calendly booking link with UTM source = `calc`
- [ ] Deploy to subdomain `calc.nexoptimus.com`
- [ ] Configure DNS + SSL via Netlify
- [ ] Add Plausible script to track page views and submission conversion
- [ ] Add UTM parameters to all outbound campaign links pointing to calculator
- [ ] End-to-end test with throwaway email and a real ASIN profile
- [ ] Verify mobile responsiveness (60%+ of traffic will be mobile from LinkedIn)

---

## 5. Funnel Integration

### 5.1 Content Engine Pairing

Every public Loom teardown ends with a soft CTA pointing to the calculator. The calculator demo itself becomes a content format: a 90-second LinkedIn or X video showing the operator using the calculator on a real, publicly visible listing builds brand surface area while driving direct traffic to the tool.

Three content formats fed by the calculator:

1. **Public teardown Loom** — listing teardown, ends with "I built a calculator that quantifies this — link below"
2. **Calculator demo Loom** — 90 seconds of using the tool on a real listing, narrating the projection
3. **Static carousel post** — five-slide LinkedIn carousel of "before / after / projected" using calculator outputs

### 5.2 Calculator → Audit Conversion Path

1. Submission captured in Supabase with email, inputs, and computed results
2. Within 4 hours: personalized Loom recorded using the prospect's own data, opening with their specific gap number
3. Loom delivered via email; subject line references the dollar gap ("$47K/yr you're not capturing on [brand]")
4. Follow-up 48 hours later if no response, referencing Loom view analytics (who watched, how far)
5. Booking link in follow-up → discovery call → $297 audit close

Target conversion rates:
- Submission → Loom delivered: 100% (manual queue, no exceptions)
- Loom open rate: 60%+
- Loom-to-booking: 15-25%
- Booking-to-audit-purchase: 50-70%

### 5.3 Audit → Retainer Path

The audit Loom is structured to end with a one-slide "what month 1 of management would look like" preview. Every audit is an audition for the $2–3K/month retainer. Target audit-to-retainer conversion: 25-40% within 30 days of audit delivery.

---

## 6. Calibration & Maintenance

### 6.1 Benchmark Sources

Uplift coefficients are calibrated against publicly available case studies and NexOptimus operational experience. They should be reviewed every 60 days against actual client outcomes:

- After every completed audit-to-management engagement, log actual revenue lift achieved at days 30, 60, 90.
- Compare against the initial calculator projection for that listing.
- If observed lift deviates more than 20% from projection in either direction across 3+ engagements, adjust coefficients.

### 6.2 Known Limitations of v0

- Self-reported quality scores are inherently biased (sellers consistently underestimate their listing weakness)
- Category modifiers are coarse; no sub-niche granularity yet
- No accounting for seasonality (current model assumes steady-state)
- No competitive moat scoring (BSR rank, Buy Box share, brand strength)
- No factor for inventory health or out-of-stock history

These are acceptable for v0 because the calculator is designed as a conversation-starter, not a contractual projection. v1 addresses all of them.

---

## 7. Roadmap

### v0 — Current (Prototype Complete)
Single-page calculator with manual inputs. Email gate. Static audit CTA. Manual Loom follow-up by operator.

### v1 — Target: 60 days post-launch
- ASIN auto-fetch via Keepa or SP-API integration to pre-populate inputs
- Automated listing quality scoring (eliminates self-report bias)
- Real-time BSR, price history, and review velocity factored into model
- Automated personalized projection email within 5 minutes of submission

### v2 — Target: 120 days post-launch (becomes Nexarch v0)
- Full prospect CRM with calculator submissions as entry point
- Per-prospect Loom embedding and view tracking
- Pipeline analytics (calculator → audit → retainer conversion funnel)
- Calibration loop: actual client outcomes auto-feed back into coefficient adjustments

### Hard Gate for v1 Development

**Do not begin v1 development until both conditions are met:**
- $3,000 collected from audit sales
- 3 completed audit-to-engagement conversions

This gate ensures v1 is built on validated demand, not anticipation. The temptation to build before selling is the single largest risk to this project.

---

## 8. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Self-reported scores too biased | High | Medium | v1 ASIN auto-fetch eliminates self-report entirely |
| Outputs feel "too good to be true" | Medium | High | Conservative bands prominently shown; methodology link in footer |
| Email gate kills conversion | Medium | High | Track gate drop-off rate; consider revealing partial results pre-gate if drop > 70% |
| Audit close rate underperforms | Medium | High | Loom analytics inform follow-up timing; test $197 floor if needed |
| Supabase email spam / bot submissions | Low | Low | Honeypot field + rate limit per IP |
| Operator burns out doing manual Looms | High | Critical | Cap at 10 Looms/day; automate at v1 |
| Calculator gets cloned by competitor | Low | Low | Network effects of submission data + speed of iteration are the moat |

---

## 9. Success Metrics

### 30-Day Targets (Post-Launch)

| Metric | Target |
|---|---|
| Calculator page views | 500+ |
| Submission rate | 15%+ |
| Submissions | 75+ |
| Loom delivery (of submissions) | 100% |
| Loom open rate | 60%+ |
| Audit close rate (of submitters) | 5-10% |
| Audits closed | 4-7 |
| Revenue | $1,200 – $3,500 |

### 90-Day Targets

| Metric | Target |
|---|---|
| Calculator page views | 3,000+ |
| Submissions | 400+ |
| Audits closed | 25+ |
| Retainer conversions | 8-12 |
| Monthly revenue from this funnel | $20K – $35K |

---

## 10. Decision Log

| Date | Decision | Rationale |
|---|---|---|
| May 2026 | Build public calculator vs internal CRM dashboard | Public tool generates demand; internal dashboard only organizes existing pipeline. Calculator does both. |
| May 2026 | Six inputs vs three | Three felt too thin to support projection credibility; six is the credibility-to-friction floor. |
| May 2026 | Email gate before results | Single point of intentional friction; submission rate hit is worth the qualified lead list. |
| May 2026 | $297 founding rate vs $497 standard | First three audits priced for proof generation; reverts to $497 after first case studies banked. |
| May 2026 | Money-back guarantee on audit | Reverses risk for no-proof phase; near-zero downside (90 min recording). |
| May 2026 | Defer Supabase web-app dashboard to v2 | 45-day cash crunch requires shipping the lead-gen layer first; CRM scaffolding burns days that should burn Looms. |

---

## 11. Open Questions

To be resolved before launch:

1. **Niche concentration** — calculator should launch with one targeted vertical in copy and examples. Which one? (TBD: requires Yahya's niche selection.)
2. **Booking tool** — Cal.com vs Calendly. Probable answer: Cal.com (open source, owned subdomain, better analytics).
3. **Pricing display** — show $297 with $497 strikethrough vs $297 standalone. Test after 30 days of submission data.
4. **Methodology page** — separate `/methodology` page explaining the model in detail? Likely yes by day 14; increases trust for serious prospects.

---

## Appendix A — Glossary

- **ACOS** — Advertising Cost of Sale. Ad spend divided by ad-attributed sales.
- **A+ Content** — Enhanced brand content section on Amazon listings (formerly EBC).
- **BSR** — Best Sellers Rank. Amazon's category-level sales ranking.
- **CVR** — Conversion rate. Sessions divided by orders.
- **Loom** — Async video recording tool used for prospect-specific audit delivery.
- **TACOS** — Total Advertising Cost of Sale. Ad spend divided by total revenue (organic + paid).

---

**Document Status:** Living document. Update after each calibration cycle.
**Next Scheduled Review:** 30 days post-launch.
**Maintained By:** Yahya / NexOptimus
