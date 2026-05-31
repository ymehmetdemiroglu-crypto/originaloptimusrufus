# Omni-Dashboard MAS — Action Matrix

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Overview

The Action Matrix defines every user-facing interaction in the Omni-Dashboard and maps it to the precise backend execution command, API endpoint, or webhook that fulfills the intent. It serves as the contract between the React frontend and the FastAPI backend.

**Pattern:** All destructive or state-mutating actions flow through the **Action Gateway** (`/api/omni/*`), which validates permissions, logs the action to the audit trail, and dispatches to the appropriate LangGraph subgraph or legacy pipeline.

---

## 2. Action Gateway Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ACTION GATEWAY                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        FastAPI — /api/omni/*                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │  Validate   │  │   Log to    │  │   Dispatch  │  │   Stream    │ │  │
│  │  │   Auth      │  │   Audit     │  │   to Agent  │  │   Result    │ │  │
│  │  │  (cookie)   │  │   Trail     │  │   / Pipeline│  │   (SSE)     │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Gateway Rules:**
1. All `POST`/`PUT`/`DELETE` actions require `admin_token` cookie
2. Every action is logged to `audit_log` with `before_state` + `after_state`
3. Destructive actions (stage advance, sequence enrollment, bulk delete) require explicit confirmation
4. Actions return SSE streams for real-time progress if they invoke LangGraph
5. Actions return JSON for simple CRUD operations

---

## 3. Omni-Dashboard Action Matrix

### 3.1 Workspace Bar Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **ASIN Input** | Type ASIN + press Enter | Set workspace context | POST | `/api/omni/chat` | `{ message: "Set workspace", workspace: { asin: "B08X" } }` |
| **ASIN Input** | Click "Set Target" button | Set workspace context | POST | `/api/omni/chat` | Same as above |
| **Workspace Badge** | Click to clear | Reset workspace | POST | `/api/omni/chat` | `{ message: "Clear workspace", workspace: {} }` |
| **Streaming Indicator** | — (passive) | Receive SSE events | GET | SSE stream | — |

### 3.2 Agent Status Grid Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **Agent Card (Listing)** | Click "Run" | Trigger Listing subgraph | POST | `/api/omni/chat` | `{ message: "Analyze ASIN", workspace: { asin } }` |
| **Agent Card (Competitor)** | Click "Run" | Trigger Competitor subgraph | POST | `/api/omni/chat` | `{ message: "Show competitors", workspace: { asin } }` |
| **Agent Card (Attribution)** | Click "Run" | Trigger Attribution subgraph | POST | `/api/omni/chat` | `{ message: "Project revenue", workspace: { asin } }` |
| **Agent Card (Outreach)** | Click "Run" | Trigger Outreach subgraph | POST | `/api/omni/chat` | `{ message: "Draft outreach", workspace: { asin } }` |
| **Agent Card (Email)** | Click "Run" | Trigger Email subgraph | POST | `/api/omni/chat` | `{ message: "Check replies", workspace: { brand_key } }` |
| **Agent Card (Admin)** | Click "Run" | Trigger Admin Copilot | POST | `/api/omni/chat` | `{ message: "Show dashboard metrics" }` |
| **Agent Card** | Hover | — | — | — | Tooltip shows last run status |

### 3.3 Contextual Metrics Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **COSMO Score Card** | Click "Details" | Fetch full COSMO analysis | POST | `/api/analyze` | `{ asin }` |
| **Competitor Similarity** | Click "View" | Fetch competitor landscape | POST | `/api/competitors` | `{ asin }` |
| **Gap Alerts** | Click alert badge | Fetch gap opportunities | POST | `/api/competitors` | `{ asin }` |
| **Revenue Projection** | Click "Attribution" | Fetch DiD/SCM analysis | POST | `/api/attribution/analyze` | `{ asin, control_asins: [...] }` |

### 3.4 Quick Intent Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **"Analyze ASIN"** | Click | Full listing analysis | POST | `/api/omni/chat` | `{ message: "Analyze this ASIN", workspace: { asin } }` |
| **"Compare Competitors"** | Click | Competitor intelligence | POST | `/api/omni/chat` | `{ message: "Compare competitors", workspace: { asin } }` |
| **"Project Revenue"** | Click | DiD + revenue projection | POST | `/api/omni/chat` | `{ message: "Estimate revenue impact", workspace: { asin } }` |
| **"Draft Outreach"** | Click | Enrich + draft sequence | POST | `/api/omni/chat` | `{ message: "Draft outreach email", workspace: { asin } }` |
| **"Run Full Optimization"** | Click | Listing + Competitor + Attribution + Outreach | POST | `/api/omni/chat` | `{ message: "Run full optimization", workspace: { asin } }` |
| **"Show Pipeline Status"** | Click | Fetch pipeline metrics | GET | `/api/pipeline` | — |

### 3.5 Agent Chat Panel Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **Message Input** | Type + Enter | Send message to Supervisor | POST | `/api/omni/chat` | `{ thread_id, message, workspace }` |
| **Send Button** | Click | Send message to Supervisor | POST | `/api/omni/chat` | Same as above |
| **Approve Button** | Click (HITL) | Resume with approval | POST | `/api/omni/resume` | `{ thread_id, human_response: { action: "approve" } }` |
| **Reject Button** | Click (HITL) | Resume with rejection | POST | `/api/omni/resume` | `{ thread_id, human_response: { action: "reject" } }` |
| **Message Bubble** | Click JSON payload | Expand/collapse metadata | — | — | Local React state toggle |
| **Scroll Area** | Scroll up | Load older messages | — | — | Virtual scroll (future) |

### 3.6 Canvas Output Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **COSMO Report Card** | Click "Optimize" | Trigger Listing subgraph | POST | `/api/omni/chat` | `{ message: "Optimize this listing", workspace: { asin } }` |
| **Competitor Gap Table** | Click "Export" | Download gap CSV | GET | `/api/csv/job/{id}/download` | — |
| **Revenue Chart** | Click time range | Fetch attribution by date | POST | `/api/attribution/analyze` | `{ asin, start_date, end_date }` |
| **Email Draft Card** | Click "Edit" | Open draft editor | — | — | Local state (no backend) |
| **Email Draft Card** | Click "Send" | Trigger sequence enrollment | POST | `/api/omni/resume` | `{ thread_id, human_response: { action: "approve" } }` |
| **Report Card** | Click "Download" | Generate PDF | — | — | Client-side PDF (future) |

---

## 4. Admin Panel Action Matrix

### 4.1 Admin Dashboard Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **Pipeline Trigger: Scrape** | Click | Trigger scrape stage | POST | `/api/admin/trigger/scrape` | `{ limit: 20 }` |
| **Pipeline Trigger: Enrich** | Click | Trigger enrich stage | POST | `/api/admin/trigger/enrich` | `{ limit: 20 }` |
| **Pipeline Trigger: Score** | Click | Trigger score stage | POST | `/api/admin/trigger/score` | `{ limit: 20 }` |
| **Pipeline Trigger: Draft** | Click | Trigger draft stage | POST | `/api/admin/trigger/draft` | `{ limit: 20 }` |
| **Pipeline Trigger: Sequence** | Click | Trigger sequence stage | POST | `/api/admin/trigger/sequence` | `{ limit: 20 }` |
| **Funnel Stats Refresh** | Click | Fetch latest funnel | GET | `/api/admin/dashboard` | — |
| **Stage Filter** | Select stage | Filter prospects | GET | `/api/admin/prospects` | `?stage=REPLIED` |

### 4.2 Prospect Management Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **Prospect Row** | Click "Advance" | Update stage | POST | `/api/admin/prospects/{bk}/action` | `{ action: "advance" }` |
| **Prospect Row** | Click "Skip" | Mark skipped | POST | `/api/admin/prospects/{bk}/action` | `{ action: "skip" }` |
| **Prospect Row** | Click "Set Stage" | Manual stage override | POST | `/api/admin/prospects/{bk}/action` | `{ action: "set_stage", stage: "EMAIL_DRAFTED" }` |
| **Prospect Row** | Click "Add Note" | Append note | POST | `/api/admin/prospects/{bk}/action` | `{ action: "add_note", note: "..." }` |
| **Prospect Row** | Click "Regenerate Email" | Re-draft sequence | POST | `/api/admin/prospects/{bk}/action` | `{ action: "regenerate_email" }` |
| **Bulk Select** | Checkbox + "Bulk Advance" | Batch stage update | POST | `/api/admin/prospects/bulk` | `{ brand_keys: [...], action: "advance" }` |

### 4.3 Email Queue Actions

| UI Component | User Action | Backend Command | Method | Endpoint | Payload |
|-------------|-------------|-----------------|--------|----------|---------|
| **Email Draft** | Click "Approve" | Approve + mark SEQUENCED | POST | `/api/admin/emails/{bk}/approve` | `{ action: "approve" }` |
| **Email Draft** | Click "Reject" | Reject + mark SKIP | POST | `/api/admin/emails/{bk}/approve` | `{ action: "reject" }` |
| **Email Draft** | Click "Edit" | Save modified draft | POST | `/api/admin/emails/{bk}/approve` | `{ action: "edit", subject: "...", body: "..." }` |
| **Conversation Thread** | Click "Send Reply" | Send AI draft | POST | `/api/email-engine/send-reply` | `{ conversation_id, draft_id }` |
| **Conversation Thread** | Click "Regenerate" | Re-draft reply | POST | `/api/email-engine/draft-reply` | `{ brand_key, classification: "OBJECTION" }` |

---

## 5. Webhook Action Matrix

### 5.1 Apollo Webhooks

| Apollo Event | Backend Handler | Resulting Action | Table Updates |
|-------------|-----------------|------------------|---------------|
| `email.opened` | `/api/webhooks/apollo` | Log open event | `landing_analytics` |
| `email.clicked` | `/api/webhooks/apollo` | Log click event | `landing_analytics` |
| `email.replied` | `/api/webhooks/apollo` | Trigger EmailAgent | `email_conversations`, `brands.stage` |
| `sequence.enrolled` | `/api/webhooks/apollo` | Confirm enrollment | `brands.apollo_contact_id` |
| `contact.created` | `/api/webhooks/apollo` | Link contact to brand | `brands.apollo_contact_id` |

### 5.2 Calendly Webhooks

| Calendly Event | Backend Handler | Resulting Action | Table Updates |
|---------------|-----------------|------------------|---------------|
| `invitee.created` | `/api/webhooks/calendly` | Create meeting | `meetings` |
| `invitee.canceled` | `/api/webhooks/calendly` | Cancel meeting | `meetings.status` |
| `invitee.created` | `/api/webhooks/calendly` | Advance brand stage | `brands.stage = DEMO_SCHEDULED` |

### 5.3 Calculator Webhooks

| Event | Backend Handler | Resulting Action | Table Updates |
|-------|-----------------|------------------|---------------|
| `calculator.viewed` | `/api/landing` | Log CTA click | `landing_analytics` |
| `calculator.submitted` | `/api/landing` | Log form submit | `landing_analytics`, `brands.calculator_submitted_at` |
| `calculator.submitted` | `/api/landing` | Advance stage | `brands.stage = CALCULATOR_SUBMITTED` |

---

## 6. Action Sequence Diagrams

### 6.1 "Run Full Optimization" Action Flow

```
User clicks "Run Full Optimization"
    │
    ▼
Frontend: POST /api/omni/chat
    { message: "Run full optimization", workspace: { asin: "B08X" } }
    │
    ▼
FastAPI: Validate admin_token cookie
    │
    ▼
FastAPI: Log to audit_log
    { actor: "admin@agency.co", action: "OMNI_REQUEST", resource_type: "thread", ... }
    │
    ▼
FastAPI: Invoke SupervisorGraph.ainvoke(OmniState)
    │
    ▼
LangGraph: plan_node
    PlanStep[listing, competitor, attribution, outreach]
    │
    ▼
LangGraph: delegate_node
    ├──▶ ListingGraph.ainvoke() ──▶ cosmo_analysis_tool ──▶ DataStore + Gemini
    ├──▶ CompetitorGraph.ainvoke() ──▶ competitor_intel_tool ──▶ DataStore + Gemini
    ├──▶ AttributionGraph.ainvoke() ──▶ attribution_tool ──▶ DataStore + scipy
    └──▶ OutreachGraph.ainvoke() ──▶ pipeline_trigger_tool ──▶ Apollo + OpenRouter
    │
    ▼
LangGraph: human_gate (Outreach)
    Sets pending_human_input
    │
    ▼
SSE: event = "human_input_required"
    { prompt: "Approve email draft?", payload: { draft, projected_lift } }
    │
    ▼
Frontend: Renders approval card
    │
    ▼
User clicks "Approve"
    │
    ▼
Frontend: POST /api/omni/resume
    { thread_id, human_response: { action: "approve" } }
    │
    ▼
FastAPI: Resume graph from checkpoint
    │
    ▼
LangGraph: sequence_node ──▶ Apollo enrollment
    │
    ▼
LangGraph: synthesize_node
    │
    ▼
SSE: event = "synthesis"
    { content: "## Omni-Dashboard Report..." }
    │
    ▼
Frontend: Renders report in Canvas
```

### 6.2 "Approve Email Draft" Action Flow

```
User clicks "Approve" on HITL card
    │
    ▼
Frontend: POST /api/omni/resume
    { thread_id, human_response: { action: "approve" } }
    │
    ▼
FastAPI: Validate admin_token
    │
    ▼
FastAPI: Log to audit_log
    { actor: "admin@agency.co", action: "APPROVE_EMAIL", 
      resource_type: "brand", resource_id: "hydromax",
      before_state: { stage: "EMAIL_DRAFTED" },
      after_state: { stage: "SEQUENCED" } }
    │
    ▼
FastAPI: Clear pending_human_input
    │
    ▼
LangGraph: Resume OutreachGraph
    │
    ▼
LangGraph: sequence_node
    ├──▶ Apollo: create_contact()
    ├──▶ Apollo: add_to_sequence()
    └──▶ Supabase: update brands SET stage = 'SEQUENCED'
    │
    ▼
SSE: event = "agent_complete"
    { agent: "outreach", output: { sequence_status: "SEQUENCED" } }
    │
    ▼
Frontend: Updates agent status card + shows success toast
```

### 6.3 "Trigger Pipeline Stage" Action Flow (Admin)

```
User clicks "Trigger: Draft" in /admin/dashboard
    │
    ▼
Frontend: POST /api/admin/trigger/draft
    { limit: 20 }
    │
    ▼
FastAPI: Validate admin_token + admin role
    │
    ▼
FastAPI: Log to audit_log
    { actor: "admin@agency.co", action: "TRIGGER_PIPELINE", 
      resource_type: "pipeline", resource_id: "draft",
      payload: { limit: 20 } }
    │
    ▼
FastAPI: Queue job via AgentOrchestrator
    ├──▶ If auto mode: subprocess main.py draft-emails --limit=20
    └──▶ If omni mode: invoke Outreach subgraph for top 20 brands
    │
    ▼
FastAPI: Return job_id
    │
    ▼
Frontend: Poll /api/admin/dashboard for progress
    │
    ▼
Frontend: Update pipeline stats when complete
```

---

## 7. Action Permission Matrix

| Action | Admin | Operator | Viewer | System |
|--------|-------|----------|--------|--------|
| **Omni Chat** | ✅ | ✅ | ❌ | ❌ |
| **HITL Approve** | ✅ | ✅ | ❌ | ❌ |
| **HITL Reject** | ✅ | ✅ | ❌ | ❌ |
| **View Prospect** | ✅ | ✅ | ✅ | ❌ |
| **Advance Stage** | ✅ | ✅ | ❌ | ❌ |
| **Skip Prospect** | ✅ | ✅ | ❌ | ❌ |
| **Trigger Pipeline** | ✅ | ❌ | ❌ | ✅ (cron) |
| **Regenerate Email** | ✅ | ✅ | ❌ | ❌ |
| **Send Reply** | ✅ | ✅ | ❌ | ❌ |
| **Bulk Operations** | ✅ | ❌ | ❌ | ❌ |
| **View Analytics** | ✅ | ✅ | ✅ | ❌ |
| **Edit Settings** | ✅ | ❌ | ❌ | ❌ |
| **Webhook Ingest** | ❌ | ❌ | ❌ | ✅ |
| **Auto-Sequence** | ❌ | ❌ | ❌ | ✅ |

---

## 8. Error Handling by Action

| Action | Common Error | Frontend Behavior | Backend Fallback |
|--------|-------------|-------------------|------------------|
| **Omni Chat** | LangGraph not installed | Toast: "Agent system unavailable" | Return static error response |
| **Omni Chat** | Rate limit (429) | Toast: "Too many requests. Slow down." | 60s cooldown |
| **HITL Approve** | Thread not found | Toast: "Thread expired. Please retry." | Return 404; user must restart |
| **HITL Approve** | Apollo rate limit | Toast: "Apollo busy. Queued for retry." | Celery task retry in 60s |
| **Trigger Pipeline** | Subprocess fail | Toast: "Pipeline failed. Check logs." | Log error; alert admin |
| **Advance Stage** | Invalid transition | Toast: "Cannot advance from X to Y" | Return 400 with allowed transitions |
| **Send Reply** | Email compliance fail | Toast: "Draft violates policy. Regenerating." | Auto-re-draft (max 2) |
| **Bulk Operation** | Partial failure | Modal: "12/20 succeeded. View failures?" | Return list of failed brand_keys |

---

## 9. Audit Log Event Types

| Action | Event Type | Tables Modified |
|--------|-----------|----------------|
| Omni chat request | `OMNI_REQUEST` | `audit_log` |
| HITL approve | `APPROVE_EMAIL` | `audit_log`, `brands` |
| HITL reject | `REJECT_EMAIL` | `audit_log`, `brands` |
| Stage advance | `STAGE_CHANGE` | `audit_log`, `brands` |
| Pipeline trigger | `TRIGGER_PIPELINE` | `audit_log`, `agent_runs` |
| Email send | `SEND_REPLY` | `audit_log`, `email_conversations` |
| Prospect skip | `SKIP_PROSPECT` | `audit_log`, `brands` |
| Bulk operation | `BULK_ACTION` | `audit_log`, `brands` |
| Webhook received | `WEBHOOK_INGEST` | `audit_log`, `landing_analytics` |
| Settings change | `CONFIG_CHANGE` | `audit_log`, `agent_config` |

---

## 10. Files & Implementation

| Component | File | Status |
|-----------|------|--------|
| Action Gateway | `backend/routers/omni.py` | ✅ Implemented |
| Admin Actions | `backend/routers/admin.py` | ✅ Existing |
| Email Actions | `backend/routers/email_engine.py` | ✅ Existing |
| Webhooks | `backend/routers/webhooks.py` | ✅ Existing |
| Audit Logger | `backend/agent/db_logger.py` | ✅ Existing |
| Stage Guard | `acquisition-tool/models.py` | ✅ Existing |
| Frontend Omni | `rufus-dashboard/src/app/omni/page.tsx` | ✅ Implemented |
| Agent Chat | `rufus-dashboard/src/components/omni/agent-chat.tsx` | ✅ Implemented |
| Admin Dashboard | `rufus-dashboard/src/app/admin/dashboard/page.tsx` | ✅ Existing |
