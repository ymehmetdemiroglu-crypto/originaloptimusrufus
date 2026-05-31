# Omni-Dashboard MAS — Agent Specifications

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Agent Overview

| Agent | Role | Graph Type | LLM | Existing Code Wrapped |
|-------|------|------------|-----|----------------------|
| **OrchestratorAgent** | Intent parsing, planning, delegation, synthesis | Supervisor | OpenRouter `deepseek/deepseek-chat-v3-0324` | `backend/agent/orchestrator.py` (concept) |
| **ListingAgent** | COSMO analysis + agentic copy optimization | Cyclic Subgraph | OpenRouter `deepseek/deepseek-chat-v3-0324` | `analysis/cosmo_mapper.py`, `acquisition-tool/agentic_optimizer.py` |
| **CompetitorAgent** | Competitor landscape + gap clustering | DAG Subgraph | Gemini Embeddings (no generative LLM) | `analysis/competitor_analyzer.py` |
| **AttributionAgent** | Causal lift + revenue projection | DAG Subgraph | None (statistical) | `analysis/attribution.py` |
| **OutreachAgent** | Prospect enrichment + email drafting + sequencing | DAG Subgraph + HITL | OpenRouter `deepseek/deepseek-chat-v3-0324` | `acquisition-tool/pipeline.py`, `cold_email.py`, `apollo_api.py` |
| **EmailAgent** | Inbound reply classification + response drafting | DAG Subgraph | OpenRouter `deepseek/deepseek-chat-v3-0324` | `email_integration/conversation_drafter.py` |
| **AdminCopilotAgent** | Dashboard control + telemetry queries | Tool-Use Loop | OpenRouter `deepseek/deepseek-chat-v3-0324` | `backend/main.py` admin endpoints |

---

## 2. OrchestratorAgent

### 2.1 System Prompt

```text
You are the Orchestrator for the Optimus Rufus Omni-Dashboard. Your job is to interpret user intent, create a plan, delegate to specialized agents, and synthesize their outputs into a clear, action-oriented response.

RULES:
1. ALWAYS produce a structured plan before delegating.
2. Agents can run in parallel if they have no data dependencies.
3. If a step requires human approval (e.g., sending emails), insert a HITL checkpoint.
4. Synthesize outputs with specific numbers, scores, and next actions — never vague summaries.
5. If the user asks a simple question, answer directly without spawning subgraphs.

AVAILABLE AGENTS:
- listing: Analyzes ASIN semantic coverage and optimizes copy for Amazon Rufus/COSMO.
- competitor: Generates competitor landscape and gap opportunities.
- attribution: Runs DiD/SCM causal analysis and projects revenue impact.
- outreach: Enriches contacts, drafts cold email sequences, and enrolls in Apollo.
- email: Classifies inbound replies and drafts responses.
- admin: Queries dashboard telemetry and triggers pipeline stages.

WORKSPACE:
You have access to the active workspace (asin, brand_key, client_id). If missing, ask the user before planning.
```

### 2.2 Node: `plan`

**Input:** `OmniState.messages` (latest HumanMessage)  
**Output:** `OmniState.plan` (list of `PlanStep`)  
**Implementation:** LLM call with structured output (`PlanStep[]`).

```python
class PlanStep(BaseModel):
    agent: Literal["listing", "competitor", "attribution", "outreach", "email", "admin"]
    task: str
    depends_on: List[int] = []  # indices of prior steps
    requires_human_approval: bool = False
```

### 2.3 Node: `delegate`

**Logic:**
- For each step with satisfied dependencies, invoke the corresponding subgraph with a forked state.
- Parallel steps are gathered via `asyncio.gather()`.
- Results are written back to `OmniState.agent_outputs[step.agent]`.

### 2.4 Node: `synthesize`

**Input:** `OmniState.agent_outputs`  
**Output:** `AIMessage` + optional `OmniState.workspace_updates`  
**Implementation:** LLM call with all agent outputs as context.

---

## 3. ListingAgent

### 3.1 System Prompt (COSMO Catalyst)

```text
You are the COSMO Catalyst. Rewrite Amazon listings to maximize semantic relation coverage across 15 COSMO relation types (Function, Audience, Context, Classification, Complementary).

RULES:
1. Maintain conversational, shopper-question-answering tone.
2. Do NOT drop high-value indexing keywords.
3. Return structured JSON: { title, bullets[], description, relation_coverage }.
```

### 3.2 System Prompt (SEO Guardian)

```text
You are the SEO Guardian. Audit listing copy for keyword safety and semantic drift.

RULES:
1. Compute WLPI (Weighted Lexical Preservation Index) across title (1.0), bullets (0.5), description (0.1).
2. If WLPI < 0.85 or semantic drift > 15%, flag as UNSAFE and specify missing keywords.
3. If unsafe, surgically re-insert missing keywords without destroying conversational flow.
```

### 3.3 Node: `agentic_optimize`

**Type:** Cyclic (up to 5 rounds)  
**Termination:** `wlpi_status == "SAFE"` AND `semantic_drift <= 0.15`  
**Fallback:** If max rounds exceeded, return best intermediate draft + warning.

---

## 4. CompetitorAgent

### 4.1 Nodes

1. **`scrape_competitors`** — Tool call to `competitor_scraper.scrape_competitors_for_brand()`.
2. **`embed_landscape`** — Async embedding of all competitor listings + client listing.
3. **`cluster_gaps`** — PCA + HDBSCAN on gap vectors (CPU-bound → `to_thread`).
4. **`generate_report`** — Structured output `CompetitorAnalysisResponse`.

### 4.2 No LLM Required

This subgraph is purely embedding + statistical clustering. No generative LLM is invoked.

---

## 5. AttributionAgent

### 5.1 Nodes

1. **`fetch_traffic`** — Read `DataStore.traffic_history[asin]`.
2. **`compute_did`** — `CausalAttributionModel.calculate_did_lift()`.
3. **`compute_scm`** — `CausalAttributionModel.calculate_synthetic_control_lift()`.
4. **`project_revenue`** — `estimate_financial_impact()`.

### 5.2 No LLM Required

Purely statistical. Returns structured `AttributionResponse`.

---

## 6. OutreachAgent

### 6.1 Nodes

1. **`enrich`** — Apollo `mixed_people/api_search` + `bulk_match`.
2. **`score`** — `rufus_scorer.score_all_async()` (v2, 6-axis, 0-120).
3. **`draft`** — `cold_email.draft_batch_async()` with worst-axis spine.
4. **`validate`** — Anti-template checks (banned phrases, 5-gram overlap, word counts).
5. **`human_gate`** — **Interrupt** node. Waits for frontend approval.
6. **`sequence`** — Apollo contact creation + sequence enrollment.

### 6.2 Validation Rules

- Banned phrases loaded dynamically from `acquisition-tool/rules/banned_phrases.json`.
- 5-gram overlap vs. last 50 drafts must be < 25%.
- Word count per step must be within 20% of target.

---

## 7. EmailAgent

### 7.1 Nodes

1. **`classify`** — `ConversationClassifier.classify_reply()` → `INTERESTED | OBJECTION | NOT_NOW | UNSUBSCRIBE | FORWARD`.
2. **`strategy`** — LLM node selecting playbook based on classification + conversation history.
3. **`draft_reply`** — `ConversationDrafter.draft_reply()`.
4. **`compliance`** — Brand voice check + banned phrase scan.

### 7.2 Strategy Playbooks

| Classification | Playbook |
|----------------|----------|
| `INTERESTED` | Ask qualifying questions, push calculator/demo |
| `OBJECTION` | Acknowledge, provide social proof, reframe value |
| `NOT_NOW` | Soft nurture, set 14-day follow-up |
| `UNSUBSCRIBE` | Graceful exit, mark `DO_NOT_CONTACT` |
| `FORWARD` | Thank referrer, offer incentive |

---

## 8. AdminCopilotAgent

### 8.1 Tools

| Tool | Function |
|------|----------|
| `get_dashboard_metrics` | Returns `/api/admin/dashboard` KPIs |
| `trigger_pipeline_stage` | POST to `/api/admin/trigger/{stage}` |
| `list_prospects` | Returns filtered prospects from Supabase |
| `get_prospect_detail` | Returns single prospect with scores |
| `update_prospect_stage` | Advances prospect to next stage |

### 8.2 System Prompt

```text
You are the Admin Copilot. Help operators manage the Optimus Rufus pipeline by querying telemetry and triggering actions.

RULES:
1. ALWAYS confirm destructive actions (stage advances, bulk triggers) before executing.
2. Present metrics in compact tables, not prose.
3. If the user asks for something outside your tools, say so clearly.
```

---

## 9. Tool Interface Specifications

All tools are decorated with `@tool` from `langchain-core` and accept/return Pydantic models.

### 9.1 Example: `cosmo_analysis_tool`

```python
from langchain_core.tools import tool
from backend.analysis.cosmo_mapper import CosmoMapper

@tool(args_schema=CosmoAnalysisInput, return_direct=False)
def cosmo_analysis_tool(asin: str, title: str, bullets: list, description: str) -> CosmoAnalysisResponse:
    """Analyze an Amazon listing for COSMO semantic relation coverage."""
    mapper = CosmoMapper(engine)
    return mapper.analyze(asin=asin, title=title, bullets=bullets, description=description)
```

### 9.2 Async Tool Pattern

All I/O-bound tools are `async def` and wrapped with `RunnableLambda` or `StructuredTool.from_function(coroutine=...)`.

CPU-bound tools (HDBSCAN, scipy optimize) use:

```python
async def cluster_gaps_tool(gap_vectors: list) -> GapClusters:
    return await asyncio.to_thread(_sync_cluster, gap_vectors)
```

---

## 10. Error Handling & Resilience

### 10.1 Node-Level Retry

- LLM calls: 3 retries with exponential backoff (1s, 2s, 4s).
- External APIs (Apollo, Gemini, OpenRouter): 5 retries with jitter.
- JSON parse failures: Re-prompt with schema reminder.

### 10.2 Subgraph Fallback

If a subgraph fails after all retries:
1. Record error in `OmniState.errors`.
2. Supervisor skips dependent steps.
3. Synthesis acknowledges the failure and provides partial results.

### 10.3 Circuit Breaker

- Apollo API: Circuit opens after 10 consecutive 5xx errors; closes after 60s.
- Gemini Embeddings: Circuit opens after 5 consecutive rate-limit errors.
