# Phase 2: Core Subsystem Specifications
# Prospect & Communication Engine

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Overview

The Prospect & Communication Engine is the CRM backbone of the Omni-Dashboard MAS. It tracks every entity from raw Amazon listing scrape through closed-won customer, manages personalized 5-step email sequences, handles inbound reply classification, and maintains a complete audit trail of all human and agent actions.

**Key Design Principle:** The `Brand` is the unit of outreach. One `Brand` rolls up many `Prospects` (ASINs). One `Brand` has one `Email Sequence` (5 steps). One `Brand` has many `Email Conversations` (inbound/outbound replies).

---

## 2. Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    prospects    │       │     brands      │       │brand_step_emails│
│   (ASIN-level)  │◄──────┤  (unit of       │◄──────┤ (5-step seq)    │
│                 │  N:1  │   outreach)     │  1:5  │                 │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
                                   │ 1:N
                                   ▼
                          ┌─────────────────┐
                          │email_conversations
                          │ (inbound/outbound)
                          └─────────────────┘
                                   │
                                   │ N:1
                                   ▼
                          ┌─────────────────┐
                          │    meetings     │
                          │ (Calendly booked)
                          └─────────────────┘
```

---

## 3. Pipeline Stages

### 3.1 Canonical Stage List

```python
# acquisition-tool/models.py
STAGES = [
    # Discovery
    "LISTING_FOUND",
    "WEAK_LISTING",
    "WEAK_BRAND",
    
    # Enrichment
    "BRAND_RESOLVED",      # No valid email found
    "CONTACT_ENRICHED",    # Valid contact acquired
    
    # Scoring & Drafting
    "EMAIL_DRAFTED",       # 5-step sequence generated
    
    # Outreach
    "SEQUENCED",           # Enrolled in Apollo sequence
    
    # Engagement
    "CALCULATOR_USED",     # Clicked calculator link
    "CALCULATOR_SUBMITTED", # Completed calculator
    "REPLIED",             # Replied to email
    
    # Conversion
    "DEMO_SCHEDULED",      # Booked Calendly meeting
    "BETA_ACTIVE",         # In beta engagement
    "REVIEW_REQUESTED",    # Awaiting review/testimonial
    "PAID",                # Closed-won
    
    # Disqualification
    "SKIP_NO_LISTING",
    "SKIP",
    "LOW_FIT",
]
```

### 3.2 Stage Transition Rules

| From | To | Trigger | Actor |
|------|----|---------|-------|
| `LISTING_FOUND` | `WEAK_LISTING` | LQS ≥ 35 | Scoring Agent |
| `WEAK_LISTING` | `WEAK_BRAND` | Brand rollup complete | Brand Rollup Agent |
| `WEAK_BRAND` | `CONTACT_ENRICHED` | Apollo returns valid email | Outreach Agent |
| `WEAK_BRAND` | `BRAND_RESOLVED` | No email found after enrichment | Outreach Agent |
| `CONTACT_ENRICHED` | `EMAIL_DRAFTED` | LLM sequence generation complete | Outreach Agent |
| `EMAIL_DRAFTED` | `SEQUENCED` | Apollo enrollment successful | Outreach Agent |
| `EMAIL_DRAFTED` | `WEAK_BRAND` | Preflight audit failed | Outreach Agent |
| `SEQUENCED` | `REPLIED` | Inbound reply received | Email Agent |
| `SEQUENCED` | `CALCULATOR_USED` | CTA link clicked | Webhook |
| `CALCULATOR_USED` | `CALCULATOR_SUBMITTED` | Form submitted | Webhook |
| `REPLIED` | `DEMO_SCHEDULED` | Classification = BOOKING_READY | Email Agent |
| `REPLIED` | `SKIP` | Classification = UNSUBSCRIBE | Email Agent / Human |
| `REPLIED` | `BRAND_RESOLVED` | Classification = WRONG_PERSON | Email Agent |
| `REPLIED` | `EMAIL_DRAFTED` | Loom recorded; regenerate | Human |
| `DEMO_SCHEDULED` | `BETA_ACTIVE` | Post-demo engagement | Human |
| `BETA_ACTIVE` | `PAID` | Contract signed | Human |

### 3.3 Stage Transition Guards

```python
class StageTransitionGuard:
    """Validates and records all stage transitions."""
    
    ALLOWED_TRANSITIONS = {
        "EMAIL_DRAFTED": ["SEQUENCED", "WEAK_BRAND"],
        "SEQUENCED": ["REPLIED", "CALCULATOR_USED"],
        "REPLIED": ["DEMO_SCHEDULED", "SKIP", "BRAND_RESOLVED", "EMAIL_DRAFTED"],
        # ... etc
    }
    
    @classmethod
    def can_transition(cls, from_stage: str, to_stage: str, actor: str) -> bool:
        if to_stage not in cls.ALLOWED_TRANSITIONS.get(from_stage, []):
            return False
        if cls.is_destructive(to_stage) and not cls.is_human(actor):
            return False  # Agents cannot auto-advance to PAID or SKIP
        return True
    
    @classmethod
    def is_destructive(cls, stage: str) -> bool:
        return stage in ["PAID", "SKIP", "BRAND_RESOLVED"]
```

---

## 4. Data Models

### 4.1 Prospect (ASIN-Level)

**Table:** `prospects` (Supabase)

```python
class Prospect(BaseModel):
    # Identity
    id: str                           # UUID
    asin: str
    brand: str
    brand_key: str                    # Normalized slug
    category: str
    platform: str = "amazon_listing"
    source: str = "amazon_scrape"     # or "apollo_search"
    
    # Listing Data
    title: str
    bullets: List[str]
    description: str
    listing_price: float
    listing_rating: float
    listing_review_count: int
    bullet_count: int
    image_count: int
    has_a_plus: bool
    qa_count: int
    
    # Quality Scoring (LQS / ALII)
    quality_score: float              # 0-100
    quality_signals: str              # Comma-joined tags
    quality_breakdown: Dict           # JSON
    weakness_score: float
    weakness_signals: str             # e.g., "TITLE,BULLETS,QA"
    
    # Rufus v2 Scoring (0-120)
    rufus_score: Optional[float]
    intent_alignment_score: Optional[float]        # 0-20
    attribute_density_score: Optional[float]        # 0-20
    conversational_readability_score: Optional[float]  # 0-20
    qa_coverage_score: Optional[float]              # 0-20
    visual_structured_content_score: Optional[float]   # 0-20 (v2 only)
    competitive_relativity_score: Optional[float]   # 0-20 (v2 only)
    rufus_citation_probability: Optional[str]       # low/medium/high
    rufus_top_weaknesses: Optional[List[Dict]]     # [{axis, issue, fix, severity}]
    rufus_summary: Optional[str]
    competitive_summary: Optional[str]
    
    # Enrichment
    domain: Optional[str]
    contact_email: Optional[str]
    contact_first_name: Optional[str]
    contact_last_name: Optional[str]
    contact_title: Optional[str]
    contact_linkedin: Optional[str]
    apollo_person_id: Optional[str]
    apollo_organization_id: Optional[str]
    apollo_contact_id: Optional[str]
    
    # Pipeline
    stage: str = "LISTING_FOUND"
    intent_score: Optional[float]     # 0-100
    intent_signals: Optional[str]
    intent_summary: Optional[str]
    
    # Seller Info
    seller_id: Optional[str]
    seller_domain: Optional[str]
    seller_business_name: Optional[str]
    seller_country: Optional[str]
    seller_feedback_pct: Optional[float]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

### 4.2 Brand (Unit of Outreach)

**Table:** `brands` (Supabase)

```python
class Brand(BaseModel):
    # Identity
    brand_key: str                    # Primary key (normalized slug)
    brand_name: str
    anchor_asin: str                  # Worst ASIN or "apollo_direct"
    asin_count: int = 1
    category: Optional[str]
    source: str = "amazon_scrape"     # or "apollo_search"
    
    # Pipeline Stage
    stage: str = "WEAK_BRAND"
    
    # Weakness Signals (union across all ASINs)
    max_weakness_score: Optional[float]
    weakness_signals: Optional[str]
    
    # Apollo Enrichment
    domain: Optional[str]
    contact_email: Optional[str]
    contact_first_name: Optional[str]
    contact_last_name: Optional[str]
    contact_title: Optional[str]
    contact_linkedin: Optional[str]
    apollo_person_id: Optional[str]
    apollo_organization_id: Optional[str]
    apollo_contact_id: Optional[str]
    apollo_score: Optional[float]
    
    # Email Copy (current active sequence)
    custom_subject: Optional[str]
    custom_body: Optional[str]
    worst_axis_at_send: Optional[str]  # intent | attribute | conversational | qa | visual | competitive
    email_teardown: Optional[str]
    
    # Engagement Tracking
    calculator_url: Optional[str]
    calculator_used_at: Optional[datetime]
    calculator_submitted_at: Optional[datetime]
    loom_url: Optional[str]
    loom_recorded_at: Optional[datetime]
    replied_at: Optional[datetime]
    
    # Scoring
    intent_score: Optional[float]     # 0-100
    intent_signals: Optional[str]
    intent_summary: Optional[str]
    client_quality_score: Optional[float]   # CQS, 0-100
    client_quality_signals: Optional[str]
    client_quality_breakdown: Optional[Dict]
    reachability_index: Optional[float]     # RI, 0-100
    brand_rufus_score: Optional[float]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

### 4.3 Brand Step Email (5-Step Sequence)

**Table:** `brand_step_emails` (Supabase)

```python
class BrandStepEmail(BaseModel):
    brand_key: str
    step_num: int                     # 1-5
    subject: str
    body: str
    overlap: Optional[float]          # 5-gram uniqueness score
    created_at: datetime
    
    class Config:
        primary_key = ["brand_key", "step_num"]
```

**5-Step Sequence Structure:**

| Step | Label | Timing | Word Count | Shopper Queries | Purpose |
|------|-------|--------|------------|-----------------|---------|
| 1 | `teardown anchor` | Day 0 | 90-140 | ≥2 | Hook with worst-axis teardown + landing page URL |
| 2 | `tactical insight` | Day 3 | 60-90 | ≥1 | Share actionable optimization tip |
| 3 | `competitor proof` | Day 7 | 70-110 | ≥1 | Inject competitor data + social proof |
| 4 | `pattern interrupt` | Day 12 | 25-45 | 0 | Short, blunt break from pattern |
| 5 | `break-up` | Day 18 | 50-80 | 0 | Final attempt; graceful exit |

**Apollo Custom Fields Mapping:**
```python
# Pushed to Apollo as contact custom variables
apollo_fields = {
    "subject_1": step_1.subject, "body_1": step_1.body,
    "subject_2": step_2.subject, "body_2": step_2.body,
    "subject_3": step_3.subject, "body_3": step_3.body,
    "subject_4": step_4.subject, "body_4": step_4.body,
    "subject_5": step_5.subject, "body_5": step_5.body,
}
```

### 4.4 Email Conversation (Inbound/Outbound)

**Table:** `email_conversations` (Supabase)

```python
class EmailConversation(BaseModel):
    id: str                           # UUID
    brand_key: str
    
    # Message Content
    direction: str                    # "outbound" | "inbound"
    subject: str
    body: str
    
    # AI Classification (inbound only)
    classification: Optional[Dict]    # {category, confidence, reason, suggested_action}
    classification_category: Optional[str]
    # INTERESTED | OBJECTION | NOT_NOW | BOOKING_READY | UNSUBSCRIBE 
    # | WRONG_PERSON | COMPETITOR | NOISE
    
    # AI Draft (outbound replies)
    ai_draft: Optional[str]
    ai_draft_strategy: Optional[str]  # qualify_and_demo | acknowledge_reframe | nurture_14_day | graceful_exit | referrer_thank
    
    # Status
    status: str = "pending"           # pending | approved | sent | auto_sent | received
    
    # Metadata
    sent_at: Optional[datetime]
    created_at: datetime
    
    # Apollo tracking
    apollo_message_id: Optional[str]
    apollo_opened_at: Optional[datetime]
    apollo_clicked_at: Optional[datetime]
    apollo_replied_at: Optional[datetime]
```

**Conversation Thread View:**
```sql
-- Fetch full conversation thread for a brand
SELECT * FROM email_conversations
WHERE brand_key = 'hydromax'
ORDER BY created_at ASC;
```

### 4.5 Meeting (Calendly)

**Table:** `meetings` (Supabase)

```python
class Meeting(BaseModel):
    id: str                           # UUID
    brand_key: str
    calendly_event_id: str
    calendly_invitee_id: str
    
    # Meeting Details
    event_type: str
    start_time: datetime
    end_time: datetime
    status: str                       # active | cancelled | rescheduled
    
    # Invitee Info
    invitee_email: str
    invitee_name: Optional[str]
    invitee_questions: Optional[Dict] # Custom Calendly questions
    
    # Tracking
    created_at: datetime
    updated_at: datetime
```

### 4.6 Agent Run (Execution Telemetry)

**Table:** `agent_runs` (Supabase)

```python
class AgentRun(BaseModel):
    id: str                           # UUID
    agent_type: str                   # scrape | enrich | score | draft | sequence | reply | omni
    status: str                       # running | completed | failed
    
    # Scope
    brand_key: Optional[str]
    asin: Optional[str]
    category: Optional[str]
    
    # Metrics
    items_processed: int = 0
    items_failed: int = 0
    duration_ms: Optional[int]
    
    # Error
    error_message: Optional[str]
    error_stack: Optional[str]
    
    # Metadata
    triggered_by: str = "cron"        # cron | manual | webhook | omni
    config_snapshot: Optional[Dict]   # Agent config at time of run
    created_at: datetime
```

---

## 5. Communication Engine Workflows

### 5.1 Outbound Sequence Workflow

```
┌─────────────┐
│ EMAIL_DRAFTED│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Preflight Audit │──▶ Check: title, domain, blocklist, overlap
│   (validate)    │     If FAIL: reset to WEAK_BRAND
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Apollo Create   │──▶ Create contact with custom fields
│   Contact       │     If FAIL: mark BRAND_RESOLVED
└────────┬────────┘
         │ SUCCESS
         ▼
┌─────────────────┐
│ Apollo Enroll   │──▶ Add contact to sequence
│   Sequence      │
└────────┬────────┘
         │ SUCCESS
         ▼
┌─────────────┐
│  SEQUENCED  │──▶ Update brands.stage
└─────────────┘     Log agent_run
```

### 5.2 Inbound Reply Workflow

```
┌─────────────┐
│  SEQUENCED  │──▶ Apollo webhook: reply_received
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Store Inbound   │──▶ Insert into email_conversations
│   Message       │     direction="inbound", status="received"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AI Classify     │──▶ LLM classifies reply
│   (EmailAgent)  │     category + confidence + suggested_action
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AI Draft Reply  │──▶ Select strategy playbook
│   (EmailAgent)  │     Generate response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Compliance Gate │──▶ Banned phrases? Brand voice? Legal?
│   (validate)    │     If FAIL: re-draft (max 2 retries)
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Human Review    │──▶ UI: Admin reviews draft
│   Queue         │     Approve / Reject / Edit
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 APPROVE   REJECT
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ Send   │ │ Log    │
│ Reply  │ │ Skip   │
└───┬────┘ └────────┘
    │
    ▼
┌─────────────────┐
│ Update Stage    │──▶ Based on classification:
│                 │     BOOKING_READY → DEMO_SCHEDULED
│                 │     UNSUBSCRIBE → SKIP
│                 │     WRONG_PERSON → BRAND_RESOLVED
│                 │     Others → REPLIED
└─────────────────┘
```

### 5.3 Loom Override Workflow

```
┌─────────────┐     ┌─────────────┐
│ REPLIED or  │────▶│ Loom Recorded│
│CALCULATOR_  │     │ (human action)
│   USED      │
└──────┬──────┘     └──────┬──────┘
       │                    │
       └────────────────────┘
                          │
                          ▼
               ┌─────────────────┐
               │ Regenerate Email│──▶ Inject loom_url into Step 1
               │  with Loom CTA  │     Update brand_step_emails
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ Stage:          │──▶ brands.stage = "EMAIL_DRAFTED"
               │ EMAIL_DRAFTED   │     (await re-approval)
               └─────────────────┘
```

---

## 6. Data Access Patterns

### 6.1 Read Patterns

| Query | Table(s) | Index | Frequency |
|-------|----------|-------|-----------|
| Get brand by stage | `brands` | `stage, updated_at` | High (dashboard) |
| Get brand detail | `brands` + `prospects` + `brand_step_emails` | `brand_key` | High (detail view) |
| Get conversation thread | `email_conversations` | `brand_key, created_at` | Medium |
| Get pipeline snapshot | `pipeline_snapshots` | `date` | Low (daily) |
| Get agent run history | `agent_runs` | `agent_type, created_at` | Medium |
| Search by ASIN | `prospects` | `asin` | Medium |
| Search by email | `brands` | `contact_email` | Low |

### 6.2 Write Patterns

| Operation | Table(s) | Conflict Handling |
|-----------|----------|-------------------|
| Insert scraped listing | `prospects` | Upsert on `asin` |
| Update brand stage | `brands` | Update `stage` + `updated_at` |
| Insert email step | `brand_step_emails` | Upsert on `(brand_key, step_num)` |
| Insert conversation | `email_conversations` | Insert only |
| Insert meeting | `meetings` | Upsert on `calendly_event_id` |
| Log agent run | `agent_runs` | Insert only |

### 6.3 CDC (Change Data Capture)

```sql
-- Trigger: Log every stage change to audit_log
CREATE OR REPLACE FUNCTION log_stage_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.stage IS DISTINCT FROM NEW.stage THEN
        INSERT INTO audit_log (
            actor, action, resource_type, resource_id,
            before_state, after_state
        ) VALUES (
            COALESCE(current_setting('app.current_user', true), 'system'),
            'STAGE_CHANGE',
            'brand',
            NEW.brand_key,
            jsonb_build_object('stage', OLD.stage),
            jsonb_build_object('stage', NEW.stage)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER brands_stage_audit
AFTER UPDATE ON brands
FOR EACH ROW
EXECUTE FUNCTION log_stage_change();
```

---

## 7. Integration with Omni-Dashboard MAS

### 7.1 MAS Read Access

```python
# Omni-Dashboard queries the same tables via tools

@tool
def get_prospect_detail(brand_key: str) -> Brand:
    """Get full brand record with prospects and emails."""
    brand = supabase.table("brands").select("*").eq("brand_key", brand_key).single().execute()
    prospects = supabase.table("prospects").select("*").eq("brand_key", brand_key).execute()
    emails = supabase.table("brand_step_emails").select("*").eq("brand_key", brand_key).execute()
    conversations = supabase.table("email_conversations").select("*").eq("brand_key", brand_key).execute()
    return {
        "brand": brand.data,
        "prospects": prospects.data,
        "emails": emails.data,
        "conversations": conversations.data,
    }

@tool
def list_prospects_by_stage(stage: str, limit: int = 50) -> List[Brand]:
    """Get all brands in a given pipeline stage."""
    return supabase.table("brands").select("*").eq("stage", stage).limit(limit).execute().data

@tool
def update_brand_stage(brand_key: str, new_stage: str, reason: str) -> bool:
    """Advance a brand to a new pipeline stage."""
    # Validate transition
    if not StageTransitionGuard.can_transition(current_stage, new_stage, "omni.admin"):
        return False
    
    supabase.table("brands").update({
        "stage": new_stage,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("brand_key", brand_key).execute()
    
    return True
```

### 7.2 MAS Write Access

| MAS Agent | Writes To | Data |
|-----------|-----------|------|
| **Outreach** | `brands` | `stage`, `apollo_contact_id`, `contact_email` |
| **Outreach** | `brand_step_emails` | 5-step sequence subjects/bodies |
| **Outreach** | `agent_runs` | Execution telemetry |
| **Email** | `email_conversations` | `ai_draft`, `classification`, `status` |
| **Email** | `brands` | `stage` (post-classification) |
| **Admin Copilot** | `brands` | `stage` (on operator command) |
| **Admin Copilot** | `agent_runs` | Manual trigger logs |

### 7.3 Real-Time Sync

```python
# Supabase Realtime subscription for live dashboard updates
from supabase import create_client

supabase = create_client(url, key)

# Subscribe to brand stage changes
channel = supabase.channel("brands-stage")
channel.on(
    "postgres_changes",
    {"event": "UPDATE", "schema": "public", "table": "brands"},
    lambda payload: broadcast_to_sse_clients(payload)
)
channel.subscribe()
```

---

## 8. Files & References

| File | Purpose |
|------|---------|
| `acquisition-tool/models.py` | `STAGES`, `Prospect`, `Brand` dataclasses |
| `acquisition-tool/db.py` | Supabase client wrappers |
| `acquisition-tool/cold_email.py` | 5-step sequence generation |
| `acquisition-tool/pipeline.py` | Async pipeline execution |
| `backend/email_integration/conversation_drafter.py` | Reply drafting |
| `backend/routers/email_engine.py` | Email classification API |
| `backend/routers/webhooks.py` | Apollo + Calendly webhook handlers |
| `backend/agent/db_logger.py` | `agent_runs` persistence |
| `backend/models.py` | FastAPI Pydantic schemas |
