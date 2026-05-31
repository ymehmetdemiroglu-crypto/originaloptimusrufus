# Optimus Rufus — Autonomous Prospecting Agent v2.0
## Master Plan, Architecture & Requirements

**Date:** 2026-05-26  
**Status:** Draft — awaiting build approval  
**Scope:** Fully autonomous daily prospecting → enrichment → personalized email drafting → Apollo sequencing → reply handling → dynamic landing pages → call booking → continuous optimization loop.

---

## 1. Executive Summary

Your existing acquisition pipeline is already one of the most sophisticated AI outbound systems I've seen. This plan elevates it from a **manual CLI toolkit** to a **self-improving autonomous agent** that runs 24/7, learns from every interaction, and converts replies into booked calls with minimal human intervention.

### Key Upgrades
| Capability | Current State | Target State |
|-----------|--------------|--------------|
| Execution | Manual CLI commands | Fully cron-scheduled, autonomous daily runs |
| Reply Handling | Classification + pending drafts | Auto-send for low-risk categories, human-in-the-loop for high-value |
| Landing Pages | Static API-served data | Dynamic, persuasion-optimized pages with semantic heatmaps |
| Learning Loop | None | A/B tested email/landing variants, winner propagation, LLM prompt evolution |
| Routing | Basic stage updates | Intent-score-based routing (fast-lane vs nurture) |
| Copy Quality | Excellent cold emails | Hormozi-grade persuasion across emails, landing pages, and replies |

---

## 2. Improved Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Scheduler   │  │ State Machine│  │ A/B Test    │  │ Feedback Loop       │ │
│  │ (APScheduler│  │ (Brand Stage │  │ Engine      │  │ (Winners → Prompt   │ │
│  │  + cron)    │  │  Transitions)│  │             │  │  Tuning)            │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         └─────────────────┴─────────────────┴────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐           ┌─────────────────┐           ┌─────────────────┐
│  PIPELINE A   │           │   PIPELINE B    │           │  REPLY ENGINE   │
│  (Outbound)   │           │  (Inbound/      │           │  (Conversational)│
│               │           │   Nurture)      │           │                 │
│ 1. Scrape     │           │ 1. Reply Poller │           │ 1. Ingest       │
│ 2. Enrich     │           │ 2. Classify     │           │ 2. Classify     │
│ 3. Score      │           │ 3. Auto-Reply   │           │ 3. Route        │
│ 4. Draft      │           │ 4. Landing Hit  │           │ 4. Draft/Send   │
│ 5. Sequence   │           │ 5. Book Call    │           │ 5. Stage Update │
└───────┬───────┘           └────────┬────────┘           └────────┬────────┘
        │                            │                            │
        ▼                            ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PERSISTENCE LAYER                                  │
│  Supabase: prospects | brands | competitors | brand_step_emails |           │
│  email_conversations | landing_analytics | ab_test_variants |               │
│  conversion_events | agent_runs | prompt_performance                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐           ┌─────────────────┐           ┌─────────────────┐
│  LANDING PAGES│           │  ANALYTICS      │           │  LEARNING       │
│  (Next.js)    │           │  (Real-time)    │           │  (Continuous)   │
│               │           │                 │           │                 │
│ /p/{brand_key}│           │ Funnel metrics  │           │ Per-variant CTR │
│ Personalized  │           │ Revenue attrib  │           │ Reply-rate opt  │
│ Persuasion    │           │ Pipeline velocity│          │ Prompt evolution│
│ A/B tested    │           │ CAC by channel  │           │ Auto-prompt     │
└───────────────┘           └─────────────────┘           └─────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Autonomous Orchestrator (`agent/orchestrator.py`)

**What it does:** Runs the entire pipeline on a schedule without human commands.

**Daily Schedule:**
| Time (UTC) | Job | Description |
|-----------|-----|-------------|
| 06:00 | `scrape_job` | Scrape 2-3 categories from Tier-1/2 seeds, insert LISTING_FOUND |
| 06:30 | `score_job` | Run Listing Quality Scorer + Rufus v2 scorer on new listings |
| 07:00 | `rollup_job` | Brand-level rollup of WEAK_LISTING → WEAK_BRAND |
| 07:30 | `enrich_job` | Apollo enrichment for top 50 brands by reachability_index |
| 08:00 | `draft_job` | Generate 5-step sequences for CONTACT_ENRICHED + scored anchors |
| 08:30 | `sequence_job` | Pre-flight checks + Apollo enrollment for EMAIL_DRAFTED |
| 09:00 | `reply_poll_job` | Poll Apollo/inbox for replies, classify, auto-respond |
| 09:30 | `landing_sync_job` | Regenerate landing page copy for REPLIED/CALCULATOR_USED brands |
| 10:00 | `loom_job` | Record personalized Looms for CALCULATOR_USED brands |
| 18:00 | `nurture_job` | Re-enqueue NOT_NOW brands whose snooze expired |
| 23:00 | `learning_job` | Compute A/B winners, update prompt weights, log agent_run |

**State Machine Enforcement:**
```
LISTING_FOUND → WEAK_LISTING  (quality_score >= threshold)
WEAK_LISTING  → WEAK_BRAND     (rollup complete)
WEAK_BRAND    → CONTACT_ENRICHED (Apollo found email + founder title)
CONTACT_ENRICHED → EMAIL_DRAFTED (Rufus scored + sequence drafted)
EMAIL_DRAFTED → SEQUENCED      (Apollo enrollment confirmed)
SEQUENCED     → REPLIED        (inbound reply detected)
REPLIED       → DEMO_SCHEDULED (BOOKING_READY or INTERESTED)
REPLIED       → SKIP           (UNSUBSCRIBE/COMPETITOR)
REPLIED       → BRAND_RESOLVED (WRONG_PERSON)
NOT_NOW       → EMAIL_DRAFTED  (snooze expired + 90 days)
```

### 3.2 Reply Intelligence Engine v2 (`agent/reply_engine.py`)

**Current gap:** Replies are classified and drafted but never auto-sent. They sit in `pending` state.

**Improved behavior:**

```python
class ReplyRouter:
    """Route inbound replies based on classification + confidence."""
    
    ROUTING_TABLE = {
        "NOISE":        Action(auto_send=False, stage=None, alert=False),
        "UNSUBSCRIBE":  Action(auto_send=True,  stage="SKIP", alert=False, 
                               reply_template="unsubscribe_ack"),
        "COMPETITOR":   Action(auto_send=True,  stage="SKIP", alert=False,
                               reply_template="competitor_ack"),
        "WRONG_PERSON": Action(auto_send=False, stage="BRAND_RESOLVED", alert=True,
                               note="Manual: find correct contact"),
        "NOT_NOW":      Action(auto_send=True,  stage="REPLIED", alert=False,
                               reply_template="not_now_nurture", snooze_days=90),
        "OBJECTION":    Action(auto_send=True,  stage="REPLIED", alert=True,  # Human review
                               reply_template="objection_handler", 
                               condition="confidence > 0.85 and not pricing_objection"),
        "INTERESTED":   Action(auto_send=False, stage="DEMO_SCHEDULED", alert=True,
                               note="High-value: human sends booking link"),
        "BOOKING_READY":Action(auto_send=True,  stage="DEMO_SCHEDULED", alert=True,
                               reply_template="booking_confirm",
                               attach_calendly=True),
    }
```

**Auto-send safety gates:**
1. Confidence > 0.85 for auto-send
2. Reply length < 2000 chars (anti-noise)
3. Brand stage must be `SEQUENCED` or `REPLIED` (no re-sends to DEMO_SCHEDULED)
4. Maximum 1 auto-reply per 24h per brand
5. Pricing objections always route to human review

### 3.3 Dynamic Landing Page Engine (`rufus-dashboard/src/app/p/[brand_key]/page.tsx`)

**Current gap:** Landing page exists at backend `/api/landing/{brand_key}` but the frontend page (`prospect-pitch`) is generic. No per-prospect dynamic rendering with persuasion copy.

**Improved behavior:**

Each prospect gets a unique URL: `https://audit.optimusrufus.com/p/{brand_key}`

**Page sections (dynamically generated):**
1. **Hero** — "Hey {first_name}, I audited {brand_name}'s Amazon listing" + live ASIN snapshot
2. **Score Card** — Animated Rufus score ring + 6-axis breakdown with semantic color coding
3. **Gap Analysis** — Exact weaknesses extracted from `rufus_top_weaknesses`, phrased as money-lost
4. **Competitor Proof** — Side-by-side comparison with top 3 competitors (visual, not tabular)
5. **Calculator CTA** — Embedded mini-calculator showing revenue impact of Rufus optimization
6. **Social Proof** — Rotating testimonials from same category
7. **Booking CTA** — Calendly embed + "Reserve your slot — 3 audits left this week" scarcity

**Persuasion Copy Layer:**
The backend adds a new table `landing_copy_variants`:
```sql
CREATE TABLE landing_copy_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_key text REFERENCES brands(brand_key),
    variant_name text, -- 'control', 'hormozi_v1', 'scarcity_v2'
    headline text,
    subheadline text,
    cta_text text,
    objection_handler text,
    generated_at timestamptz DEFAULT now(),
    impressions int DEFAULT 0,
    clicks int DEFAULT 0,
    bookings int DEFAULT 0
);
```

An LLM prompt generates 3 copy variants per landing page. The variant is selected via URL param (`?v=hormozi_v1`). The tracking job increments counters and computes winners.

### 3.4 Semantic Analysis Layer (`agent/semantic_analyzer.py`)

**New component.** Analyzes every prospect's digital footprint to enrich personalization beyond Amazon listings.

**Data sources:**
1. **Amazon listing semantics** — Entity extraction from title/bullets (ingredients, use-cases, demographics)
2. **Competitor semantic diff** — What concepts do competitors mention that this brand doesn't?
3. **Shopper intent graph** — What queries should this ASIN rank for? What's the query → attribute mapping?
4. **Brand voice analysis** — Tone of current copy (clinical, playful, luxury, etc.)

**Output:** A `semantic_profile` JSON stored on the brand row, consumed by:
- Email drafter (reference their voice, mention missing ingredients)
- Landing page generator (speak their language)
- Reply drafter (mirror their tone in responses)

### 3.5 Continuous Learning Loop (`agent/learning_loop.py`)

**New component.** Closes the feedback loop so the agent improves itself.

**Metrics tracked per variant:**
| Metric | Source | Use |
|--------|--------|-----|
| Open rate | Apollo webhook | Subject line quality |
| Reply rate | Reply classifier | Body + subject quality |
| Landing visit | Landing analytics | Email CTA effectiveness |
| Time on page | Landing analytics | Landing page engagement |
| Calculator use | DB stage transition | Landing persuasion |
| Booking rate | Calendly webhook | End-to-end conversion |
| Loom watch % | Loom analytics | Video effectiveness |

**Winner propagation:**
```python
weekly_winners = {
    "subject_lines": top_open_rate_subject_variant,
    "body_openers": top_reply_rate_opener_variant,
    "landing_headlines": top_booking_headline_variant,
    "cta_frames": top_click_cta_variant,
}
# Winners are injected into the prompt corpus as "high-performing examples"
# for the next week's generation cycle.
```

---

## 4. Database Schema Additions

```sql
-- ============================================
-- Agent Orchestration
-- ============================================
CREATE TABLE agent_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type text NOT NULL, -- 'scrape', 'enrich', 'draft', 'sequence', 'reply', 'learning'
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    status text DEFAULT 'running', -- running, success, partial, failed
    records_processed int DEFAULT 0,
    records_succeeded int DEFAULT 0,
    records_failed int DEFAULT 0,
    error_log jsonb DEFAULT '[]',
    metadata jsonb DEFAULT '{}'
);

-- ============================================
-- Email Conversations (extends existing)
-- ============================================
ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS 
    sent_at timestamptz;
ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS
    auto_sent boolean DEFAULT false; -- was this sent by the agent without approval?
ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS
    ai_draft_reviewed boolean DEFAULT false; -- human reviewed before send

-- ============================================
-- Landing Page Copy A/B Testing
-- ============================================
CREATE TABLE landing_copy_variants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_key text REFERENCES brands(brand_key) ON DELETE CASCADE,
    variant_name text NOT NULL,
    headline text NOT NULL,
    subheadline text,
    hero_body text,
    gap_section_title text,
    gap_section_body text,
    competitor_section_title text,
    cta_text text NOT NULL,
    cta_subtext text,
    objection_handler text,
    semantic_profile jsonb DEFAULT '{}',
    impressions int DEFAULT 0,
    unique_visitors int DEFAULT 0,
    scroll_50 int DEFAULT 0,
    scroll_100 int DEFAULT 0,
    calculator_clicks int DEFAULT 0,
    calendly_clicks int DEFAULT 0,
    bookings int DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

-- ============================================
-- A/B Test Registry
-- ============================================
CREATE TABLE ab_test_experiments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_name text NOT NULL, -- 'subject_line_may_2026', 'landing_hero_v3'
    experiment_type text NOT NULL, -- 'email_subject', 'email_body', 'landing_hero', 'landing_cta'
    started_at timestamptz DEFAULT now(),
    ended_at timestamptz,
    status text DEFAULT 'active', -- active, paused, concluded
    winner_variant text,
    winner_confidence float,
    sample_size int DEFAULT 0
);

-- ============================================
-- Semantic Profiles
-- ============================================
CREATE TABLE semantic_profiles (
    brand_key text PRIMARY KEY REFERENCES brands(brand_key) ON DELETE CASCADE,
    extracted_entities jsonb DEFAULT '[]', -- [{entity, type, confidence}]
    shopper_intent_graph jsonb DEFAULT '{}', -- {query: [attributes]}
    brand_voice jsonb DEFAULT '{}', -- {tone, formality, persona}
    competitor_semantic_diff jsonb DEFAULT '[]',
    generated_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- ============================================
-- Conversion Events (attribution)
-- ============================================
CREATE TABLE conversion_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_key text REFERENCES brands(brand_key),
    event_type text NOT NULL, -- 'email_open', 'email_click', 'landing_view', 'calculator_use', 'calendly_click', 'booking_confirmed', 'demo_completed', 'paid'
    occurred_at timestamptz DEFAULT now(),
    source_variant text, -- which A/B variant drove this
    attribution_chain text[] DEFAULT '{}', -- ['email_step_3', 'landing_page', 'calendly']
    revenue_value float,
    metadata jsonb DEFAULT '{}'
);

-- ============================================
-- Prompt Performance (for LLM prompt evolution)
-- ============================================
CREATE TABLE prompt_performance (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_hash text NOT NULL,
    prompt_type text NOT NULL, -- 'cold_email', 'reply', 'landing_copy', 'semantic_analysis'
    prompt_text text NOT NULL,
    generation_model text,
    usage_count int DEFAULT 0,
    avg_reply_rate float,
    avg_booking_rate float,
    avg_overlap_score float,
    created_at timestamptz DEFAULT now()
);
```

---

## 5. API Additions (Backend)

### 5.1 Webhooks Router (`backend/routers/webhooks.py`)

```python
# Apollo webhooks
@router.post("/apollo/email-event")
async def apollo_email_event(payload: ApolloWebhookPayload):
    """Receive open, click, reply, bounce events from Apollo."""
    # Update conversion_events, trigger reply poller if reply detected

# Calendly webhooks  
@router.post("/calendly/booking")
async def calendly_booking_event(payload: CalendlyWebhookPayload):
    """Mark brand as DEMO_SCHEDULED or PAID based on event type."""

# Loom webhooks
@router.post("/loom/watch-event")
async def loom_watch_event(payload: LoomWebhookPayload):
    """Track video engagement per brand."""
```

### 5.2 Agent Control Router (`backend/routers/agent_control.py`)

```python
@router.post("/agent/run")
async def trigger_agent_run(job_type: str, background_tasks: BackgroundTasks):
    """Manually trigger or schedule a pipeline stage."""

@router.get("/agent/status")
async def agent_status():
    """Real-time agent health, today's pipeline counts, active jobs."""

@router.post("/agent/pause")
async def pause_agent():
    """Emergency stop — pauses all auto-sends but preserves data."""
```

---

## 6. Frontend Additions (Dashboard)

### 6.1 Agent Control Panel (`/agent`)
- Toggle switches for each job type (scrape, draft, sequence, auto-reply)
- Real-time log stream of agent runs
- Kill switch + pause queue
- Today's funnel velocity (brands processed per hour)

### 6.2 Conversation Inbox (`/inbox`)
- Unified view of all REPLIED brands
- AI draft preview with one-click send/edit
- Auto-send confidence indicator (green = auto-sent, yellow = drafted, red = needs human)
- Filter by classification category

### 6.3 Landing Page Preview (`/landing-preview/{brand_key}`)
- Side-by-side variant comparison
- Live copy editing with AI regenerate
- Heatmap overlay (scroll depth, click maps)

### 6.4 Learning Dashboard (`/learning`)
- A/B test results with statistical significance
- Prompt performance leaderboard
- Weekly winner summary
- Revenue attribution by variant

---

## 7. Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Get the agent running autonomously on a schedule.

- [ ] Create `agent/` module with `orchestrator.py` (APScheduler-based)
- [ ] Port existing CLI commands into idempotent job functions
- [ ] Add `agent_runs` table + run logging
- [ ] Add environment toggles: `AGENT_AUTO_SCRAPE`, `AGENT_AUTO_ENRICH`, `AGENT_AUTO_DRAFT`, `AGENT_AUTO_SEQUENCE`
- [ ] Dockerize the orchestrator as a background worker
- [ ] Add `/agent/status` and `/agent/run` endpoints

**Deliverable:** `python -m agent.orchestrator --once` runs the full pipeline end-to-end.

### Phase 2: Reply Autonomy (Week 2)
**Goal:** Handle inbound replies without human intervention for low-risk categories.

- [ ] Build `agent/reply_engine.py` with routing table
- [ ] Implement auto-send safety gates
- [ ] Add Apollo webhook ingestion for reply detection
- [ ] Connect `conversation_drafter.py` to actual SMTP/Apollo send API
- [ ] Build Inbox UI (`/inbox`) for human review of high-value replies
- [ ] Add Slack/email alerts for INTERESTED + BOOKING_READY classifications

**Deliverable:** Unsubscribe + competitor + NOT_NOW replies auto-handled. OBJECTION replies drafted and queued for human approval.

### Phase 3: Persuasion Landing Pages (Week 3)
**Goal:** Convert email clicks into Calendly bookings at >15% rate.

- [ ] Build `/p/[brand_key]` Next.js route with server-side data fetch
- [ ] Create `landing_copy_variants` table
- [ ] Build LLM prompt for generating 3 copy variants per brand
- [ ] Add Calendly embed + scarcity messaging ("X audits left this week")
- [ ] Add tracking pixel + scroll depth events
- [ ] Connect landing analytics to `conversion_events`

**Deliverable:** Every SEQUENCED brand gets a personalized landing page URL embedded in Step 1.

### Phase 4: Semantic Intelligence (Week 4)
**Goal:** Emails and landing pages feel like they were written by someone who deeply understands the brand.

- [ ] Build `agent/semantic_analyzer.py`
- [ ] Add `semantic_profiles` table
- [ ] Integrate semantic data into `cold_email.py` prompts
- [ ] Integrate semantic data into `conversation_drafter.py`
- [ ] Integrate semantic data into landing page generator
- [ ] Add brand voice mirroring to reply engine

**Deliverable:** Emails reference missing ingredients, competitor positioning, and shopper queries with high semantic relevance.

### Phase 5: Learning Loop (Week 5-6)
**Goal:** The agent improves its own copy over time.

- [ ] Build `agent/learning_loop.py`
- [ ] Add `ab_test_experiments` + `prompt_performance` tables
- [ ] Implement weekly winner computation (Bayesian or frequentist A/B)
- [ ] Build "high-performing example" injection into prompts
- [ ] Add prompt evolution (auto-tune temperature, system prompt variants)
- [ ] Build Learning Dashboard UI

**Deliverable:** After 4 weeks of data, the agent identifies top-performing subject lines, body structures, and landing CTAs and biases generation toward winners.

---

## 8. Requirements Checklist

### 8.1 Infrastructure
- [ ] Background worker container (Docker) for orchestrator
- [ ] Redis or in-memory queue for job scheduling (APScheduler with SQLAlchemy backend)
- [ ] Webhook endpoints exposed publicly (Ngrok for dev, Caddy for prod)
- [ ] Cron job or systemd timer for orchestrator process health

### 8.2 Secrets & Environment
```env
# Agent control
AGENT_ENABLED=true
AGENT_AUTO_SCRAPE=true
AGENT_AUTO_ENRICH=true
AGENT_AUTO_DRAFT=true
AGENT_AUTO_SEQUENCE=true
AGENT_AUTO_REPLY=true
AGENT_REPLY_CONFIDENCE_THRESHOLD=0.85
AGENT_MAX_DAILY_SEQUENCES=50

# Landing pages
LANDING_PAGE_BASE_URL=https://audit.optimusrufus.com
CALENDLY_URL=https://calendly.com/optimusrufus/audit

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ADMIN_EMAIL=yahya@optimusrufus.com

# A/B testing
AB_TEST_MIN_SAMPLES=30
AB_TEST_CONFIDENCE_LEVEL=0.95

# Learning
LEARNING_JOB_ENABLED=true
LEARNING_WEEKLY_DAY=0  # Sunday
```

### 8.3 External API Requirements
| Service | Current Usage | New Usage |
|---------|--------------|-----------|
| Apollo | Search, enrichment, sequencing | + Webhooks for reply/open/click |
| OpenRouter | Rufus scoring, email drafting | + Reply drafting, landing copy, semantic analysis |
| Apify | Amazon scrape | Same — orchestrated by scheduler |
| Supabase | Primary DB | + New tables, + realtime subscriptions for inbox |
| Calendly | Manual link | + Webhook integration for booking confirmation |
| Loom | Manual recording | + API for automated recording + analytics |
| Slack | N/A | Alerts for high-intent replies, daily summary |

### 8.4 Cost Estimates (Daily at 50 prospects/day)
| Component | Calls/Day | Est. Cost/Day |
|-----------|-----------|---------------|
| Apify scrape | 2 actor runs | $3-5 |
| Apollo enrichment | 50 contacts | $0 (included in plan) |
| OpenRouter — Rufus scoring | 50 calls | $2-3 |
| OpenRouter — email drafting | 50 calls (5-step batch) | $4-6 |
| OpenRouter — reply drafting | ~10 replies | $0.50-1 |
| OpenRouter — landing copy | 50 calls | $2-3 |
| OpenRouter — semantic analysis | 50 calls | $2-3 |
| **Total** | | **~$14-21/day** |

At 50 prospects/day → ~$500-650/month. If reply rate is 8% and booking rate is 30% of replies: ~36 bookings/month. CAC via agent = ~$14-18 per booking.

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Auto-reply sounds robotic | Confidence threshold + max 1 auto-reply/day + human review queue |
| Landing page breaks for edge case ASINs | Fallback to generic copy + error telemetry |
| Apollo rate limits | Exponential backoff in `resilience.py` + queue persistence |
| LLM generates inappropriate copy | Banned phrase filters + overlap checks + human review for first 100 |
| Database bloat | Partition `conversion_events` by month; archive old `agent_runs` |
| Competitors find landing pages | Pages are unindexed (`noindex` meta); brand_key is unguessable hash |
| Spam complaints | Pre-flight checks already exist; add unsubscribe link in auto-replies |

---

## 10. Success Metrics (90-Day Targets)

| Metric | Baseline (Current) | 30-Day Target | 90-Day Target |
|--------|-------------------|---------------|---------------|
| Daily prospects processed | Manual (~20/week) | 35/day | 50/day |
| Email reply rate | ~5% | 7% | 10% |
| Landing page visit rate | Unknown | 40% of opens | 50% of opens |
| Landing → booking rate | Unknown | 10% | 15% |
| End-to-end booking rate | ~0.5% | 1.5% | 3% |
| Human hours per booking | ~2 hours | 30 min | 10 min |
| Auto-send accuracy | 0% (manual) | 85% | 92% |

---

## 11. Next Step

**If you approve this plan, I will begin Phase 1 implementation:**

1. Create the `agent/` module with the orchestrator
2. Add all new database tables to Supabase
3. Wire the scheduler to run existing pipeline stages autonomously
4. Add the agent control endpoints to the backend

**Estimated Phase 1 build time:** 2-3 days.

Approve? Or want to adjust scope/priorities?
