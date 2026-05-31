# Phase 2: Core Subsystem Specifications
# Omni-Dashboard Multi-Agent System (MAS)

**Version:** 1.0  
**Date:** 2026-05-30

---

## Table of Contents

1. [Supervisor Subsystem](#1-supervisor-subsystem)
2. [Listing Agent Subgraph](#2-listing-agent-subgraph)
3. [Competitor Agent Subgraph](#3-competitor-agent-subgraph)
4. [Attribution Agent Subgraph](#4-attribution-agent-subgraph)
5. [Outreach Agent Subgraph](#5-outreach-agent-subgraph)
6. [Email Agent Subgraph](#6-email-agent-subgraph)
7. [Admin Copilot Agent](#7-admin-copilot-agent)
8. [API Gateway Subsystem](#8-api-gateway-subsystem)
9. [Frontend Omni-Dashboard](#9-frontend-omni-dashboard)
10. [Tool Layer](#10-tool-layer)

---

## 1. Supervisor Subsystem

### 1.1 Purpose
The Supervisor is the single entry point and orchestrator for all Omni-Dashboard operations. It receives natural language intent, generates a structured execution plan, delegates to specialized subgraphs in parallel where dependencies allow, synthesizes outputs, and manages human-in-the-loop interrupts.

### 1.2 Interface

**Input:** `OmniState` (see `backend/agent/graph/state.py`)

```python
class SupervisorInput(BaseModel):
    message: str                          # Latest human message
    workspace: WorkspaceSnapshot          # Active ASIN/brand/client
    thread_id: Optional[str] = None       # Existing thread or new
```

**Output:** `OmniState` (terminal)

```python
class SupervisorOutput(BaseModel):
    synthesis: Optional[str]              # Final markdown report
    agent_outputs: Dict[str, AgentOutput] # Results from all subgraphs
    pending_human_input: Optional[HumanInterrupt]  # HITL gate (if blocked)
    completed: bool                       # Terminal flag
    errors: List[str]                     # Non-fatal failures
```

### 1.3 State Machine

```
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐
│  START  │───▶│ plan    │───▶│ delegate    │───▶│ synthesize  │───▶│  END    │
└─────────┘    └─────────┘    └─────────────┘    └─────────────┘    └─────────┘
                    │                │                   │
                    │                │ (loop if pending) │
                    │                └───────────────────┘
                    │                │
                    │                ▼
                    │          ┌─────────────┐
                    │          │ human_gate  │
                    │          │ (interrupt) │
                    │          └─────────────┘
                    │
                    ▼
              ┌─────────────┐
              │ direct_answer│  (no subgraphs needed)
              └─────────────┘
```

**Transitions:**

| From | To | Condition |
|------|----|-----------|
| `START` | `plan` | Always |
| `plan` | `direct_answer` | Intent is a simple Q&A (no agents matched) |
| `plan` | `delegate` | Plan has pending steps |
| `delegate` | `delegate` | More pending steps after completing current batch |
| `delegate` | `synthesize` | All plan steps completed |
| `delegate` | `human_gate` | A step has `requires_human_approval=True` and just finished |
| `human_gate` | `delegate` | Human response received via `/api/omni/resume` |
| `synthesize` | `END` | Always |

### 1.4 Node Specifications

#### Node: `plan_node`

**Type:** LLM node (Phase 3) / Rule-based (Phase 1-2)

**Logic (Phase 1-2):**
```python
def _plan_node(state: OmniState) -> Dict[str, Any]:
    message = state.get_last_human_message().lower()
    plan = []
    
    if any(k in message for k in ["optimize", "listing", "cosmo", "fix"]):
        plan.append(PlanStep(agent="listing", task="COSMO analysis + optimization"))
    
    if any(k in message for k in ["competitor", "gap", "landscape"]):
        plan.append(PlanStep(agent="competitor", task="Competitor intelligence"))
    
    if any(k in message for k in ["revenue", "impact", "lift", "attribution"]):
        plan.append(PlanStep(
            agent="attribution", 
            task="DiD/SCM + revenue projection",
            depends_on=[0] if any listing step else []
        ))
    
    if any(k in message for k in ["outreach", "email", "draft", "sequence"]):
        plan.append(PlanStep(
            agent="outreach",
            task="Enrich + draft + sequence",
            requires_human_approval=True
        ))
    
    if not plan:
        plan.append(PlanStep(agent="synthesize", task="Direct answer"))
    
    return {"plan": plan, "current_step_index": 0}
```

**Latency Target:** <200ms

#### Node: `delegate_node`

**Type:** Control node (no LLM)

**Logic:**
1. Identify all plan steps with status `"pending"` and satisfied dependencies
2. Group ready steps by agent type
3. Execute ready subgraphs in parallel via `asyncio.gather()`
4. Merge outputs back into `OmniState.agent_outputs`
5. Update step statuses to `"completed"` or `"failed"`

**Parallelization Rules:**
- `listing` + `competitor` → **Parallel** (no dependencies)
- `attribution` → **Sequential** (depends on `listing` output)
- `outreach` → **Sequential** (depends on `listing` + `attribution`)
- `email` → **Independent** (triggered by external events, not user intent)

**Latency Target:** Depends on slowest subgraph in batch; streaming hides latency

#### Node: `synthesize_node`

**Type:** LLM node (Phase 3) / Template-based (Phase 1-2)

**Logic (Phase 1-2):**
```python
def _synthesize_node(state: OmniState) -> Dict[str, Any]:
    parts = ["## Omni-Dashboard Report\n"]
    
    if "listing" in state.agent_outputs:
        lo = state.agent_outputs["listing"]
        if lo.success:
            parts.append(f"**Listing** — COSMO Score: {lo.data.get('overall_score', 'N/A')}\n")
        else:
            parts.append(f"**Listing** — Error: {lo.error}\n")
    
    if "competitor" in state.agent_outputs:
        co = state.agent_outputs["competitor"]
        if co.success:
            parts.append(f"**Competitor** — {len(co.data.get('profiles', []))} competitors\n")
    
    if "attribution" in state.agent_outputs:
        ao = state.agent_outputs["attribution"]
        if ao.success:
            did = ao.data.get("did", {})
            parts.append(f"**Attribution** — DiD Lift: {did.get('lift_percent', 'N/A')}%\n")
    
    if "outreach" in state.agent_outputs:
        oo = state.agent_outputs["outreach"]
        parts.append(f"**Outreach** — Enrichment: {oo.success}\n")
        if oo.data.get("draft_result"):
            parts.append("- Email draft generated\n")
    
    return {"synthesis": "\n".join(parts), "completed": True}
```

**Latency Target:** <500ms

### 1.5 Error Handling

| Error Type | Handling | Fallback |
|------------|----------|----------|
| Subgraph failure | Mark step `"failed"`; skip dependent steps; include error in synthesis | Partial results delivered |
| LLM timeout | 3 retries with exponential backoff; if all fail, return `"LLM unavailable"` | Direct answer without agent invocation |
| Tool timeout | 5 retries with jitter; mark step failed | Skip step; continue with remaining plan |
| Invalid plan | Return `"I don't understand. Please rephrase."` | Direct answer mode |
| Max recursion | Hard limit 50; return `"Workflow too complex. Please break into smaller requests."` | Error state |

### 1.6 Checkpointing

**Table:** `langgraph_checkpoint` (Supabase Postgres)

**Key:** `thread_id` (UUID)

**Saved After Each Node:**
- `plan` → saves `plan`, `messages`
- `delegate` → saves `agent_outputs`, `plan` (status updates)
- `synthesize` → saves `synthesis`, `completed`
- `human_gate` → saves `pending_human_input`

**Resume Behavior:**
```python
# On POST /api/omni/resume
checkpoint = checkpointer.get_tuple(config)
state = OmniState(**checkpoint.checkpoint)
state.pending_human_input = None
state.messages.append(HumanMessage(content=human_response))
graph.invoke(state, config)  # Continues from human_gate
```

---

## 2. Listing Agent Subgraph

### 2.1 Purpose
Analyze a single ASIN for COSMO semantic relation coverage, optimize copy via the dual-agent loop (COSMO Catalyst ↔ SEO Guardian), validate safety, and persist results.

### 2.2 Interface

**Input:**
```python
class ListingInput(BaseModel):
    asin: str
    title: str
    bullets: List[str]
    description: str
```

**Output:**
```python
class ListingOutput(BaseModel):
    overall_score: float          # 0-100
    keyword_safety: str           # "SAFE" | "WARNING" | "UNSAFE"
    embedding_dimensions: int     # 768
    relation_coverage: Dict[str, float]  # 15 relation scores
    optimized_copy: Optional[Dict] = None  # {title, bullets[], description}
    wlpi_score: Optional[float] = None   # Weighted Lexical Preservation Index
    semantic_drift: Optional[float] = None  # Cosine distance vs. original
    rounds: int = 0               # Optimization rounds executed
```

### 2.3 Graph Topology

```
┌─────────────┐
│    START    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ cosmo_analysis  │──▶ Tool: cosmo_analysis_tool
│    (node)       │     Input: {asin, title, bullets, description}
└────────┬────────┘     Output: {overall_score, relation_coverage, gaps}
         │
         ▼
┌─────────────────┐
│ agentic_optimize│──▶ Dual-agent loop (max 5 rounds)
│    (node)       │     Agent A: COSMO Catalyst (rewrite for relations)
└────────┬────────┘     Agent B: SEO Guardian (audit + re-insert keywords)
         │
         ▼
┌─────────────────┐
│  safety_gate    │──▶ Validate WLPI >= 0.85 AND drift <= 0.15
│    (node)       │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 SAFE      UNSAFE
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ persist│ │ loop   │──▶ Back to agentic_optimize (if rounds < 5)
│        │ │ back   │     else: error node
└───┬────┘ └────────┘
    │
    ▼
┌─────────┐
│   END   │
└─────────┘
```

### 2.4 Node Specifications

#### Node: `cosmo_analysis`

**Tool:** `cosmo_analysis_tool`

**Implementation:**
```python
def _listing_analysis_node(state: OmniState) -> Dict[str, Any]:
    store_result = store_read_tool.invoke({"key": "listings", "id": state.workspace.asin})
    listing = store_result.get("data", {})
    
    if not listing:
        return {
            "agent_outputs": {
                "listing": {
                    "agent": "listing",
                    "success": False,
                    "error": "ASIN not found in store"
                }
            }
        }
    
    cosmo_result = cosmo_analysis_tool.invoke({
        "asin": state.workspace.asin,
        "title": listing.get("title", ""),
        "bullets": listing.get("bullets", []),
        "description": listing.get("description", ""),
    })
    
    return {
        "agent_outputs": {
            "listing": {
                "agent": "listing",
                "success": True,
                "data": cosmo_result
            }
        }
    }
```

**Latency:** ~2-5s (embedding computation)

#### Node: `agentic_optimize` (Cyclic)

**Agents:**
- **COSMO Catalyst:** Rewrites title, bullets, description to maximize 15-relation coverage
- **SEO Guardian:** Audits draft with WLPI formula; re-inserts missing keywords surgically

**Termination Conditions:**
1. `wlpi_status == "SAFE"` AND `semantic_drift <= 0.15`
2. `rounds >= 5` (max)
3. `cosmo_score` stops improving (plateau detection)

**WLPI Formula:**
```python
wlpi = (
    title_score * 1.0 +
    bullets_score * 0.5 +
    description_score * 0.1
) / 1.6
```

**Latency:** ~5-15s per round (2 LLM calls)

#### Node: `safety_gate`

**Validation:**
1. Compute cosine similarity between original embedding and optimized embedding
2. If `drift > 0.15`: return `"UNSAFE"` → loop back
3. If `wlpi < 0.85`: return `"UNSAFE"` → loop back
4. If max rounds exceeded: return `"FAILED"` → error node

**Latency:** <100ms

#### Node: `persist`

**Action:** Write optimized listing to `DataStore` and Supabase

```python
store.set_listing(asin, {
    **original,
    "optimized_title": optimized["title"],
    "optimized_bullets": optimized["bullets"],
    "optimized_description": optimized["description"],
    "cosmo_score": cosmo_result["overall_score"],
    "wlpi": wlpi_score,
    "semantic_drift": drift,
    "optimized_at": datetime.utcnow().isoformat()
})
```

### 2.5 Error Handling

| Error | Cause | Handling |
|-------|-------|----------|
| ASIN not found | Store miss | Return error; skip optimization |
| Embedding timeout | Gemini rate limit | Retry 3x; if fail, return partial analysis |
| LLM parse failure | Invalid JSON from Catalyst | Reprompt with schema reminder |
| Max rounds exceeded | WLPI never reaches threshold | Return best intermediate draft + warning |
| Drift > 15% | Over-optimization | Rollback to original copy |

---

## 3. Competitor Agent Subgraph

### 3.1 Purpose
Generate a competitor landscape for a given ASIN, compute embedding similarity, cluster gap vectors with PCA + HDBSCAN, and output structured gap opportunities.

### 3.2 Interface

**Input:**
```python
class CompetitorInput(BaseModel):
    asin: str
    competitor_asins: Optional[List[str]] = None  # Auto-discover if omitted
```

**Output:**
```python
class CompetitorOutput(BaseModel):
    competitor_profiles: List[CompetitorProfile]
    gap_opportunities: List[GapOpportunity]
    positioning_summary: str
    similarity_matrix: Dict[str, float]
    cluster_labels: Dict[str, int]
```

### 3.3 Graph Topology

```
START ──▶ scrape_competitors ──▶ embed_landscape ──▶ cluster_gaps ──▶ generate_report ──▶ END
```

**Type:** Pure DAG (no cycles, no LLM)

### 3.4 Node Specifications

#### Node: `scrape_competitors`

**Tool:** `competitor_intel_tool`

**Logic:**
1. Read existing competitors from `DataStore`
2. If `competitor_asins` provided, validate they exist
3. If missing, auto-discover via `competitor_scraper`
4. Return competitor listing objects

**Latency:** ~1-3s (DB read + optional scrape)

#### Node: `embed_landscape`

**Implementation:**
```python
async def _embed_landscape(state: OmniState):
    analyzer = _get_competitor_analyzer()
    result = await asyncio.to_thread(
        analyzer.analyze,
        state.workspace.asin,
        state.workspace.competitor_asins or []
    )
    return {"agent_outputs": {"competitor": {"success": True, "data": result}}}
```

**Process:**
1. Embed client listing (3072-dim)
2. Embed all competitor listings (3072-dim each)
3. Compute cosine similarity matrix
4. Persist embeddings to `embedding_cache.db`

**Latency:** ~3-10s (depends on competitor count)

#### Node: `cluster_gaps`

**Algorithm:** PCA (50 components) → HDBSCAN

**Input:** Gap vectors (client_embedding - competitor_embedding)

**Output:** Cluster labels + noise points

**Latency:** ~2-5s (CPU-bound → `asyncio.to_thread`)

#### Node: `generate_report`

**Output Schema:** `CompetitorAnalysisResponse` (existing Pydantic model)

**Fields:**
- `competitor_profiles`: ASIN, title, similarity score, key strengths
- `gap_opportunities`: Clustered gaps with severity (HIGH/MEDIUM/LOW)
- `positioning_summary`: 1-paragraph narrative

**Latency:** <100ms (JSON serialization)

### 3.5 Error Handling

| Error | Handling |
|-------|----------|
| No competitors found | Return empty landscape with message |
| HDBSCAN fails (too few samples) | Fallback to K-Means (k=3) |
| Embedding cache miss | Compute synchronously; write to cache |

---

## 4. Attribution Agent Subgraph

### 4.1 Purpose
Estimate causal lift from listing optimization using Difference-in-Differences (DiD) and Synthetic Control Method (SCM), then project financial impact.

### 4.2 Interface

**Input:**
```python
class AttributionInput(BaseModel):
    asin: str
    control_asins: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
```

**Output:**
```python
class AttributionOutput(BaseModel):
    did: DiDResult
    scm: SCMResult
    financial_projection: FinancialProjection
```

### 4.3 Graph Topology

```
START ──▶ fetch_traffic ──▶ compute_did ──▶ compute_scm ──▶ project_revenue ──▶ END
```

### 4.4 Node Specifications

#### Node: `fetch_traffic`

**Source:** `DataStore.traffic_history[asin]`

**Schema:**
```python
TrafficRecord = {
    "date": "2024-01-01",
    "sessions": 1500,
    "orders": 45,
    "conversion_rate": 0.03
}
```

**Validation:** Minimum 30 days of data required

#### Node: `compute_did`

**Tool:** `attribution_tool`

**Implementation:**
```python
model = CausalAttributionModel()
did_result = model.calculate_did_lift(
    treatment_history=store.traffic_history[asin],
    control_histories={c: store.traffic_history[c] for c in control_asins}
)
```

**Output:**
```python
{
    "lift_percent": 12.5,
    "p_value": 0.03,
    "z_score": 2.15,
    "confidence_interval": [3.2, 21.8],
    "significant": True
}
```

**Latency:** ~1-3s (statistical computation)

#### Node: `compute_scm`

**Algorithm:** `scipy.optimize.minimize` (SLSQP)

**Process:**
1. Construct donor pool from control ASINs
2. Optimize weights to minimize pre-treatment MSE
3. Project counterfactual
4. Compute lift vs. synthetic control

**Latency:** ~2-5s (optimization)

#### Node: `project_revenue`

**Formula:**
```python
projected_monthly_revenue = (
    current_monthly_sessions *
    current_conversion_rate *
    (1 + did_lift_percent) *
    average_order_value
)

impact = projected_monthly_revenue - current_monthly_revenue
```

**Latency:** <10ms

### 4.5 Error Handling

| Error | Handling |
|-------|----------|
| Insufficient traffic data (<30 days) | Return `"Need at least 30 days of traffic history"` |
| No control ASINs | Return `"Add competitor ASINs as controls"` |
| DiD not significant (p > 0.05) | Return results with `"Not statistically significant"` warning |
| SCM optimization fails | Fallback to simple mean difference |

---

## 5. Outreach Agent Subgraph

### 5.1 Purpose
Execute the end-to-end prospecting pipeline: enrich contact via Apollo, score with Rufus LLM, draft cold email sequence, wait for human approval, then enroll in Apollo sequence.

### 5.2 Interface

**Input:**
```python
class OutreachInput(BaseModel):
    brand_key: str
    anchor_asin: Optional[str] = None
    category: Optional[str] = None
```

**Output:**
```python
class OutreachOutput(BaseModel):
    enrichment_success: bool
    rufus_score: Optional[RufusScore]
    email_draft: Optional[EmailSequence]
    sequence_status: Optional[str]  # "SEQUENCED" | "APPROVED_PENDING" | "REJECTED"
    apollo_contact_id: Optional[str]
```

### 5.3 Graph Topology

```
START ──▶ enrich ──▶ score ──▶ draft ──▶ validate ──▶ human_gate ──▶ sequence ──▶ END
                                              │
                                              │ (interrupt)
                                              ▼
                                         WAIT_FOR_RESUME
```

### 5.4 Node Specifications

#### Node: `enrich`

**Tool:** `pipeline_trigger_tool(stage="enrich", limit=1)`

**Process:**
1. Apollo `mixed_people/api_search` for brand domain
2. `bulk_match` for missing emails
3. Filter by target titles (CEO, Founder, Owner)
4. Update Supabase `brands` table

**Latency:** ~3-8s (Apollo API)

#### Node: `score`

**Tool:** `rufus_scorer.score_all_async()`

**Process:**
1. Fetch anchor ASIN details
2. Inject competitor context into prompt
3. LLM call (OpenRouter, deepseek-v3)
4. Parse 6-axis JSON response (0-120 scale)

**Latency:** ~2-5s (LLM)

#### Node: `draft`

**Tool:** `cold_email.draft_batch_async()`

**Process:**
1. Identify "worst Rufus axis" (lowest sub-score)
2. Generate 5-step sequence with worst axis as narrative spine
3. Inject personalized landing page URL (Step 1)
4. Inject competitor data (Step 3)

**Latency:** ~3-6s (LLM)

#### Node: `validate`

**Checks:**
1. Banned phrase scan (`banned_phrases.json`)
2. 5-gram overlap vs. last 50 drafts (<25%)
3. Word count per step (within 20% tolerance)

**If validation fails:** Loop to `draft` (max 2 retries)

#### Node: `human_gate`

**Type:** `interrupt` node

**Behavior:**
```python
return {
    "pending_human_input": {
        "prompt": "Approve email draft before Apollo sequence enrollment?",
        "payload": {
            "email_sequence": draft,
            "rufus_score": score,
            "brand_key": brand_key
        },
        "step_index": state.current_step_index
    }
}
```

**UI Action:** Renders approval/rejection card in Agent Chat Panel

#### Node: `sequence`

**Tool:** `pipeline_trigger_tool(stage="sequence", limit=1)`

**Process:**
1. Create Apollo contact with custom fields
2. Enroll in sequence via REST API
3. Update Supabase brand stage to `"SEQUENCED"`

**Latency:** ~2-4s (Apollo API)

### 5.5 Error Handling

| Error | Handling |
|-------|----------|
| No email found | Mark `"BRAND_RESOLVED"`; skip drafting |
| Apollo rate limit | Circuit breaker; retry in 60s |
| LLM draft parse failure | Retry with stricter JSON schema prompt |
| Validation fail (max retries) | Return draft with `"WARNING: template overlap"` |
| Human rejection | Log reason; mark `"DO_NOT_CONTACT"` |

---

## 6. Email Agent Subgraph

### 6.1 Purpose
Handle inbound email replies: classify tone, select strategy, draft response, validate compliance.

### 6.2 Interface

**Input:**
```python
class EmailInput(BaseModel):
    brand_key: str
    reply_body: str
    conversation_history: List[Message]
    brand_stage: str
```

**Output:**
```python
class EmailOutput(BaseModel):
    classification: str  # INTERESTED | OBJECTION | NOT_NOW | UNSUBSCRIBE | FORWARD
    strategy: str        # Playbook name
    draft_reply: str
    compliance_status: str  # "PASS" | "WARNING" | "FAIL"
    suggested_next_stage: str
```

### 6.3 Graph Topology

```
START ──▶ classify ──▶ strategy ──▶ draft_reply ──▶ compliance ──▶ END
```

### 6.4 Node Specifications

#### Node: `classify`

**Tool:** `ConversationClassifier`

**Classes:**
| Class | Action |
|-------|--------|
| `INTERESTED` | Push calculator/demo |
| `OBJECTION` | Reframe with social proof |
| `NOT_NOW` | Soft nurture; 14-day follow-up |
| `UNSUBSCRIBE` | Graceful exit |
| `FORWARD` | Thank referrer |

**Latency:** ~1-2s (LLM)

#### Node: `strategy`

**Rule-based mapping:**
```python
PLAYBOOKS = {
    "INTERESTED": "qualify_and_demo",
    "OBJECTION": "acknowledge_reframe",
    "NOT_NOW": "nurture_14_day",
    "UNSUBSCRIBE": "graceful_exit",
    "FORWARD": "referrer_thank"
}
```

**Latency:** <10ms

#### Node: `draft_reply`

**Tool:** `ConversationDrafter`

**Context injection:**
- Last 5 messages in thread
- Brand stage history
- Rufus score (if available)
- Competitor intel (if relevant)

**Latency:** ~2-4s (LLM)

#### Node: `compliance`

**Checks:**
1. Banned phrase scan
2. Brand voice consistency (tone match)
3. Legal compliance (no medical claims for supplements)

**Latency:** <100ms

### 6.5 Error Handling

| Error | Handling |
|-------|----------|
| Classification ambiguous (confidence <0.7) | Default to `NOT_NOW` + human review flag |
| Draft too long (>500 words) | Truncate + `"[continued in next message]"` |
| Compliance fail | Re-draft with stricter prompt |

---

## 7. Admin Copilot Agent

### 7.1 Purpose
Natural language interface for dashboard operators to query telemetry and trigger pipeline stages without memorizing API endpoints.

### 7.2 Interface

**Input:** Natural language command (e.g., *"Show me all prospects in REPLIED stage"*)

**Output:** Structured response + optional action confirmation

### 7.3 Tools

| Tool | Function | Parameters |
|------|----------|------------|
| `get_dashboard_metrics` | Returns admin KPIs | `period: "today" | "week" | "month"` |
| `list_prospects` | Filtered prospect list | `stage, limit, sort_by` |
| `get_prospect_detail` | Single prospect view | `brand_key` |
| `trigger_pipeline_stage` | Manual stage trigger | `stage, limit` |
| `update_prospect_stage` | Advance/reject prospect | `brand_key, new_stage, note` |

### 7.4 System Prompt

```text
You are the Admin Copilot for Optimus Rufus. Help operators manage the pipeline.

RULES:
1. ALWAYS confirm destructive actions (stage advances, bulk triggers) before executing.
2. Present metrics in compact tables, not prose.
3. If the user asks for something outside your tools, say so clearly.
4. Do NOT make up data. Query the tools.
```

### 7.5 Example Interactions

**User:** *"How many prospects replied this week?"*
**Copilot:**
```
Replied Prospects (Week of 2024-01-15)
┌─────────┬─────────────┬────────────┐
│ Count   │ Avg Score   │ Top Stage  │
├─────────┼─────────────┼────────────┤
│ 12      │ 78.4        │ LOOM_SENT  │
└─────────┴─────────────┴────────────┘
```

**User:** *"Advance all REPLIED prospects to LOOM_SENT"*
**Copilot:** *"This will affect 12 prospects. Confirm? (yes/no)"*

---

## 8. API Gateway Subsystem

### 8.1 Router: `/api/omni/*`

| Endpoint | Method | Auth | Request Body | Response |
|----------|--------|------|--------------|----------|
| `/api/omni/chat` | POST | Admin cookie | `{ thread_id, message, workspace }` | `text/event-stream` |
| `/api/omni/resume` | POST | Admin cookie | `{ thread_id, human_response, prior_state }` | `application/json` (Phase 1-2) |
| `/api/omni/threads/{id}` | GET | Admin cookie | — | `OmniState` JSON |
| `/api/omni/agents` | GET | Admin cookie | — | Agent health list |

### 8.2 SSE Event Schema

```typescript
interface OmniEvent {
    event: "tool_start" | "tool_end" | "agent_complete" | 
           "synthesis" | "human_input_required" | "error" | "final";
    data: {
        agent?: string;
        tool?: string;
        input?: Record<string, any>;
        output?: Record<string, any>;
        content?: string;           // synthesis text
        prompt?: string;            // HITL prompt
        payload?: Record<string, any>;  // HITL payload
        message?: string;           // error text
    }
}
```

### 8.3 Middleware Stack

```
Request ──▶ CORSMiddleware ──▶ TrustedHostMiddleware ──▶ HTTPSRedirectMiddleware
    │
    ▼
SecurityHeadersMiddleware (CSP, HSTS, X-Frame-Options)
    │
    ▼
RateLimitMiddleware (Redis-backed, 10 req/min per IP)
    │
    ▼
AdminAuthMiddleware (validates admin_token cookie)
    │
    ▼
OmniRouter handler
    │
    ▼
LangGraph Runtime
```

### 8.4 Error Responses

| Status | Code | Body |
|--------|------|------|
| 400 | `INVALID_MESSAGE` | `{ "detail": "message is required" }` |
| 400 | `MISSING_THREAD` | `{ "detail": "thread_id is required for resume" }` |
| 400 | `MISSING_STATE` | `{ "detail": "prior_state is required for resume in partial implementation" }` |
| 403 | `UNAUTHORIZED` | `{ "detail": "Invalid admin token" }` |
| 429 | `RATE_LIMITED` | `{ "detail": "Too many requests. Try again in 60s." }` |
| 503 | `LANGGRAPH_UNAVAILABLE` | `{ "detail": "LangGraph not installed" }` |
| 501 | `NOT_IMPLEMENTED` | `{ "detail": "Checkpoint retrieval not yet implemented" }` |

---

## 9. Frontend Omni-Dashboard

### 9.1 Page: `/omni`

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ Sidebar (256px) │ Main Canvas (flex) │ Agent Chat (380px)  │
└─────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | File | Responsibility |
|-----------|------|----------------|
| `OmniDashboardInner` | `page.tsx` | Layout orchestration, workspace bar, metric cards |
| `WorkspaceBar` | `page.tsx` | ASIN input, thread status, streaming indicator |
| `AgentStatusGrid` | `page.tsx` | 6 agent cards with health + running status |
| `MetricCards` | `page.tsx` | COSMO score, active listings, similarity, gap alerts |
| `QuickIntents` | `page.tsx` | Pre-canned prompts (Analyze, Competitors, Revenue, etc.) |
| `AgentChatPanel` | `agent-chat.tsx` | SSE consumer, message history, HITL approval UI |
| `OmniWorkspaceProvider` | `workspace-context.tsx` | Shared React Context for workspace state |

### 9.2 State Management

```typescript
// OmniWorkspace (React Context)
interface OmniWorkspace {
    asin: string | null;
    brandKey: string | null;
    clientId: string | null;
    threadId: string | null;
    activeAgents: string[];   // Agents currently running
    isStreaming: boolean;      // SSE connection active
}
```

**State Flow:**
```
User sets ASIN ──▶ setAsin() ──▶ OmniWorkspaceContext ──▶ WorkspaceBar renders badge
User sends msg ──▶ handleSend() ──▶ POST /api/omni/chat ──▶ setStreaming(true)
SSE event ──▶ eventSource.onmessage ──▶ addActiveAgent() / appendMessage()
HITL event ──▶ setPendingHuman() ──▶ Renders approval card
Approval click ──▶ handleHumanResponse() ──▶ POST /api/omni/resume
```

### 9.3 API Integration

```typescript
// lib/api.ts (existing) ── extended with:
export const api = {
    // ... existing methods
    omniChat: (message: string, workspace: object, threadId?: string) => {
        return fetch(`${API_BASE}/api/omni/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ thread_id: threadId, message, workspace })
        });
    },
    omniResume: (threadId: string, action: string, modifications?: string) => {
        return fetch(`${API_BASE}/api/omni/resume`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ thread_id: threadId, human_response: { action, modifications } })
        });
    },
    omniAgents: () => fetchApi("/api/omni/agents")
};
```

---

## 10. Tool Layer

### 10.1 Tool Registry

| Tool | Input Schema | Output Schema | Source Module | Async |
|------|-------------|--------------|---------------|-------|
| `cosmo_analysis_tool` | `CosmoAnalysisInput` | `CosmoAnalysisResponse` | `analysis.cosmo_mapper` | Yes (to_thread) |
| `competitor_intel_tool` | `CompetitorIntelInput` | `CompetitorAnalysisResponse` | `analysis.competitor_analyzer` | Yes (to_thread) |
| `attribution_tool` | `AttributionInput` | `AttributionResponse` | `analysis.attribution` | Yes (to_thread) |
| `store_read_tool` | `StoreReadInput` | `Dict` | `data.store.DataStore` | Yes |
| `pipeline_trigger_tool` | `PipelineTriggerInput` | `Dict` | `agent.jobs.JobRegistry` | Yes |

### 10.2 Tool Execution Model

```
LangGraph Node
    │
    ▼
Tool.invoke(state)
    │
    ├──▶ I/O-bound (HTTP API, DB query)
    │       └──▶ await directly (asyncio)
    │
    ├──▶ CPU-bound (embeddings, HDBSCAN, scipy)
    │       └──▶ asyncio.to_thread() (ThreadPoolExecutor)
    │
    └──▶ Subprocess (CLI invocation)
            └──▶ asyncio.create_subprocess_exec()
    │
    ▼
JSON-serializable result
    │
    ▼
OmniState.agent_outputs["tool_name"] = result
```

### 10.3 Error Handling

| Tool Error | Retry | Backoff | Fallback |
|------------|-------|---------|----------|
| Gemini embedding timeout | 3 | 2s exponential | Return cached embedding |
| Apollo rate limit (429) | 5 | 1s + jitter | Circuit breaker; queue for later |
| OpenRouter timeout | 3 | 3s exponential | Offline mode (skip LLM step) |
| DB connection lost | 3 | 1s linear | Read from DataStore fallback |
| Subprocess failure | 1 | — | Log error; skip step |

---

## 11. Integration Matrix

| Subsystem | Depends On | Provides To | Shared State |
|-----------|-----------|-------------|--------------|
| Supervisor | All subgraphs | Frontend (SSE) | `OmniState` |
| Listing | DataStore, Gemini | Supervisor | `agent_outputs["listing"]` |
| Competitor | DataStore, Gemini | Supervisor, Listing | `agent_outputs["competitor"]` |
| Attribution | DataStore, Listing output | Supervisor | `agent_outputs["attribution"]` |
| Outreach | Apollo, OpenRouter, DataStore | Supervisor | `agent_outputs["outreach"]` |
| Email | Supabase, OpenRouter | Admin UI | Supabase `brand_step_emails` |
| Admin Copilot | Supabase, DataStore | Admin UI | Read-only queries |
| API Gateway | LangGraph Runtime | Frontend | HTTP + SSE |
| Frontend | API Gateway | User | React Context |
| Tool Layer | All backend modules | All subgraphs | In-memory + SQLite + Supabase |

---

## 12. Performance Budgets

| Operation | Target Latency | Max Latency | Throughput |
|-----------|---------------|-------------|------------|
| Supervisor planning | <200ms | 500ms | 100/min |
| Listing analysis | <5s | 15s | 20/min |
| Competitor intel | <10s | 30s | 10/min |
| Attribution (DiD+SCM) | <8s | 20s | 15/min |
| Outreach (enrich+draft) | <15s | 45s | 10/min |
| Email classification | <2s | 5s | 60/min |
| Synthesis | <500ms | 2s | 100/min |
| End-to-end simple intent | <3s | 10s | — |
| End-to-end full workflow | <30s | 90s | — |
| SSE first byte | <100ms | 500ms | — |
| HITL resume | <2s | 5s | — |

---

## 13. Files & Implementation Status

| Component | File | Status |
|-----------|------|--------|
| State Schemas | `backend/agent/graph/state.py` | ✅ Implemented |
| Tool Wrappers | `backend/agent/graph/tools.py` | ✅ Implemented |
| Listing Subgraph | `backend/agent/graph/subgraphs.py` | ✅ Partial (cosmo analysis + safety gate) |
| Competitor Subgraph | `backend/agent/graph/subgraphs.py` | ✅ Implemented |
| Attribution Subgraph | `backend/agent/graph/subgraphs.py` | ✅ Implemented |
| Outreach Subgraph | `backend/agent/graph/subgraphs.py` | ✅ Partial (enrich + draft + HITL gate) |
| Supervisor Graph | `backend/agent/graph/supervisor.py` | ✅ Implemented (rule-based planner) |
| API Router | `backend/routers/omni.py` | ✅ Implemented |
| Frontend Page | `rufus-dashboard/src/app/omni/page.tsx` | ✅ Implemented |
| Workspace Context | `rufus-dashboard/src/components/omni/workspace-context.tsx` | ✅ Implemented |
| Agent Chat | `rufus-dashboard/src/components/omni/agent-chat.tsx` | ✅ Implemented |
| Sidebar Link | `rufus-dashboard/src/components/dashboard/sidebar.tsx` | ✅ Updated |
| Dependencies | `backend/requirements.txt` | ✅ Updated |
| FastAPI Wiring | `backend/main.py` | ✅ Updated |
