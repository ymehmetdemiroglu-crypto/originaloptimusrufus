# Omni-Dashboard MAS — System Design

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Next.js — /omni Dashboard                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐ │  │
│  │  │   Sidebar    │  │   Canvas     │  │   Agent Chat Panel          │ │  │
│  │  │  (nav +      │  │  (contextual │  │  (streaming thought +       │ │  │
│  │  │   workspace) │  │   outputs)   │  │   action cards)             │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP/SSE
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                         FastAPI — /api/omni/*                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ POST /chat  │  │ GET /stream │  │ POST /thread│  │ GET /workspace      │ │
│  │             │  │ /{thread_id}│  │             │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ invokes
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH RUNTIME                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    SupervisorGraph (OrchestratorAgent)                 │  │
│  │  • Intent classification (Route to subgraph / direct answer / HITL)   │  │
│  │  • Plan generation (ordered list of tool/subgraph calls)              │  │
│  │  • Delegation (spawn subgraph with forked state)                      │  │
│  │  • Synthesis (merge subgraph outputs into final response)             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│           ┌──────────┬──────────┬────┴────┬──────────┬──────────┐           │
│           ▼          ▼          ▼         ▼          ▼          ▼           │
│  ┌────────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ Listing    │ │Compet- │ │Attrib- │ │Outreach│ │ Email  │ │ Admin  │    │
│  │ Subgraph   │ │itor    │ │ution   │ │Subgraph│ │Subgraph│ │Subgraph│    │
│  │            │ │Subgraph│ │Subgraph│ │        │ │        │ │        │    │
│  └────────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOOL LAYER                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ cosmo_map   │ │ competitor_ │ │ did_analyze │ │ store_read  │           │
│  │ _tool       │ │ _intel_tool │ │ _tool       │ │ /write      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ agentic_    │ │ apollo_     │ │ email_      │ │ pipeline_   │           │
│  │ optimize_   │ │ enrich_     │ │ draft_      │ │ trigger_    │           │
│  │ tool        │ │ tool        │ │ tool        │ │ tool        │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ reads/writes
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ In-Memory   │  │ SQLite      │  │ Supabase    │  │ External    │        │
│  │ DataStore   │  │ embedding_  │  │ Postgres    │  │ APIs        │        │
│  │ (store.py)  │  │ cache.db    │  │ (auth, chat,│  │ (Gemini,    │        │
│  │             │  │             │  │ agent_runs) │  │ Apollo,     │        │
│  │             │  │             │  │             │  │ OpenRouter) │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow: End-to-End Example

**User Intent:** *"Show me what's wrong with ASIN B08X, fix it, estimate revenue impact, and draft an outreach email to the brand owner."*

### Step 1 — Ingestion
- Frontend POSTs to `/api/omni/chat` with `{ message: "...", workspace: { asin: "B08X" } }`.
- FastAPI creates/fetches a LangGraph `thread_id` (UUID) and invokes `SupervisorGraph` with checkpointing.

### Step 2 — Supervisor Planning
- `OrchestratorAgent` (LLM node) classifies intent as `MULTI_SUBGRAPH` requiring:
  1. `listing_graph` (COSMO analysis + optimization)
  2. `competitor_graph` (gap analysis for context)
  3. `attribution_graph` (financial projection)
  4. `outreach_graph` (enrich contact + draft email)

### Step 3 — Parallel Delegation
- Supervisor spawns `listing_graph` and `competitor_graph` **in parallel** (no dependencies).
- Both subgraphs stream `on_tool_start` / `on_tool_end` events via `astream_events`.

### Step 4 — Sequential Dependency
- `attribution_graph` requires outputs from `listing_graph` (optimized vs. baseline metrics). It waits via checkpoint resume.
- `outreach_graph` runs last, using the optimized copy and financial projection as narrative anchors in the email draft.

### Step 5 — Human-in-the-Loop
- Before `outreach_graph` executes the Apollo sequence enrollment, the supervisor hits an `interrupt` node.
- Frontend receives `{"type": "human_input_required", "payload": { draft_email, projected_lift }}`.
- User approves/modifies in the chat panel and POSTs `/api/omni/resume`.

### Step 6 — Synthesis
- Supervisor aggregates all subgraph outputs into a single JSON response:
  - `cosmo_score_before/after`, `competitor_gaps`, `projected_revenue`, `email_draft`, `sequence_status`
- Frontend renders this in the **Canvas** as an interactive report card.

---

## 3. State Schema

### 3.1 Thread State (`OmniState` — Pydantic)

```python
class OmniState(BaseModel):
    messages: List[Union[HumanMessage, AIMessage, ToolMessage]] = []
    workspace: WorkspaceSnapshot = Field(default_factory=WorkspaceSnapshot)
    plan: List[PlanStep] = []
    agent_outputs: Dict[str, Any] = {}
    pending_human_input: Optional[HumanInterrupt] = None
    errors: List[str] = []
    completed: bool = False
```

### 3.2 Workspace Snapshot

```python
class WorkspaceSnapshot(BaseModel):
    asin: Optional[str] = None
    brand_key: Optional[str] = None
    client_id: Optional[str] = None
    category: Optional[str] = None
```

### 3.3 Frontend Context (`OmniWorkspaceContext` — React)

```typescript
interface OmniWorkspace {
  asin: string | null;
  brandKey: string | null;
  clientId: string | null;
  threadId: string | null;
  activeAgents: string[];
  isStreaming: boolean;
}
```

---

## 4. Subgraph Specifications

### 4.1 Listing Subgraph

**Purpose:** Analyze and optimize a single ASIN's semantic coverage.

**Nodes:**
1. `cosmo_analysis` — Calls `cosmo_mapper.analyze()` via tool.
2. `agentic_optimize` — Runs the COSMO Catalyst ↔ SEO Guardian loop (up to 5 rounds).
3. `safety_gate` — Final `verify_semantic_drift()` check; rollback if drift > 15%.
4. `persist` — Writes optimized listing to `DataStore`.

**Edges:**
- `cosmo_analysis` → `agentic_optimize`
- `agentic_optimize` → `safety_gate`
- `safety_gate` → `persist` (if safe)
- `safety_gate` → `agentic_optimize` (if unsafe and rounds < 5)
- `safety_gate` → `error` (if max rounds exceeded)

### 4.2 Competitor Subgraph

**Purpose:** Generate competitor landscape and gap opportunities.

**Nodes:**
1. `scrape_competitors` — `competitor_scraper` tool.
2. `embed_landscape` — 3072-dim embedding + similarity matrix.
3. `cluster_gaps` — PCA + HDBSCAN on gap vectors.
4. `generate_report` — Structured `CompetitorAnalysisResponse`.

### 4.3 Attribution Subgraph

**Purpose:** Estimate causal lift and financial impact.

**Nodes:**
1. `fetch_traffic` — Read `traffic_history` from `DataStore`.
2. `compute_did` — `CausalAttributionModel.calculate_did_lift()`.
3. `compute_scm` — `CausalAttributionModel.calculate_synthetic_control_lift()`.
4. `project_revenue` — `estimate_financial_impact()`.

### 4.4 Outreach Subgraph

**Purpose:** End-to-end prospecting pipeline execution.

**Nodes:**
1. `enrich` — Apollo `mixed_people/api_search` + `bulk_match`.
2. `score` — `rufus_scorer.score_all_async()` (if not already scored).
3. `draft` — `cold_email.draft_batch_async()` with anti-template validation.
4. `human_gate` — **Interrupt** for email approval.
5. `sequence` — Apollo contact creation + sequence enrollment.

### 4.5 Email Subgraph

**Purpose:** Handle inbound reply classification and drafting.

**Nodes:**
1. `classify` — `ConversationClassifier` tool.
2. `strategy` — LLM node selecting objection-handling playbook.
3. `draft_reply` — `ConversationDrafter` tool.
4. `compliance` — Brand voice + banned phrase check.

---

## 5. API Contract

### 5.1 Streaming Chat

```http
POST /api/omni/chat
Content-Type: application/json

{
  "thread_id": "uuid-or-null",
  "message": "Optimize B08X and draft outreach",
  "workspace": { "asin": "B08X" }
}
```

**Response:** `text/event-stream` (Server-Sent Events)

```json
{ "event": "tool_start", "data": { "agent": "listing", "tool": "cosmo_analysis", "input": { "asin": "B08X" } } }
{ "event": "tool_end", "data": { "agent": "listing", "tool": "cosmo_analysis", "output": { "score": 62, ... } } }
{ "event": "human_input_required", "data": { "prompt": "Approve email draft?", "payload": { ... } } }
{ "event": "final", "data": { "synthesis": "...", "workspace_updates": { ... } } }
```

### 5.2 Resume from HITL

```http
POST /api/omni/resume
Content-Type: application/json

{
  "thread_id": "uuid",
  "human_response": { "action": "approve", "modifications": "..." }
}
```

### 5.3 Thread History

```http
GET /api/omni/threads/{thread_id}
```

Returns full checkpoint state for reconstruction.

---

## 6. Persistence & Checkpointing

LangGraph's `PostgresSaver` will be configured to use the existing Supabase Postgres instance.

**Table:** `langgraph_checkpoint` (managed by LangGraph, auto-created)

**Migration Strategy:**
1. Add `langgraph_checkpoint` and `langgraph_checkpoint_writes` tables via Supabase migration.
2. Use `thread_id` = `workspace.asin + "_" + timestamp` for deterministic replay.
3. Retain checkpoints for 30 days; nightly cleanup job.

---

## 7. Security & Safety

1. **Tool Sandboxing:** All tools run in `asyncio.to_thread()` to isolate CPU-heavy work from the graph event loop.
2. **Lexical Safety:** The existing `banned_phrases.json` and WLPI checks are enforced as mandatory nodes in every subgraph that generates copy.
3. **Semantic Drift Guard:** `verify_semantic_drift()` cosine threshold (15%) is a hard gate; subgraph cannot complete without passing.
4. **Rate Limiting:** Per-client token bucket on `/api/omni/chat` to prevent runaway agent loops.
5. **Auth:** Reuse existing admin cookie auth (`admin_token`) for `/api/omni/*`; Supabase JWT for user-scoped threads.

---

## 8. Observability

- **LangSmith:** All graph invocations traced with `project="optimus-rufus-omni"`.
- **Structured Logs:** Python `structlog` integration in every node; `rich` console output in dev.
- **Metrics:** FastAPI `PrometheusMiddleware` (if added later) tracks `/api/omni/chat` latency, error rate, and SSE connection duration.
- **Audit Trail:** Every HITL decision, tool call, and rollback is persisted to Supabase `agent_runs` (existing table).
