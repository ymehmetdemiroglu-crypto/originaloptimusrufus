# Phase 3: AI Copilot Tooling & Agent Spec
# Omni-Dashboard Multi-Agent System (MAS)

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Tool Philosophy

The Omni-Dashboard MAS treats every backend capability as a **tool** — a discrete, composable function with a strict schema. Agents do not directly import modules; they invoke tools through a unified interface. This ensures:

1. **Observability:** Every tool call is logged with input, output, latency, and error.
2. **Reusability:** The same tool can be invoked by any agent or by human operators.
3. **Safety:** Tools enforce their own validation; agents cannot bypass business logic.
4. **Extensibility:** New tools are registered in the Tool Registry; no agent code changes required.

---

## 2. Tool Registry

### 2.1 Registry Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TOOL REGISTRY                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     UnifiedToolRegistry (singleton)                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │  │
│  │  │  Analysis   │  │  Pipeline   │  │    Data     │  │   Admin     │ │  │
│  │  │   Tools     │  │   Tools     │  │   Tools     │  │   Tools     │ │  │
│  │  │             │  │             │  │             │  │             │ │  │
│  │  │ • cosmo_    │  │ • pipeline_ │  │ • store_    │  │ • get_      │ │  │
│  │  │   analysis  │  │   trigger   │  │   read      │  │   dashboard │ │  │
│  │  │ • competitor│  │ • apollo_   │  │ • store_    │  │ • list_     │ │  │
│  │  │   _intel    │  │   enrich    │  │   write     │  │   prospects │ │  │
│  │  │ • attribution│ │ • email_    │  │ • store_    │  │ • trigger_  │ │  │
│  │  │             │  │   draft     │  │   query     │  │   stage     │ │  │
│  │  │             │  │ • apollo_   │  │             │  │ • update_   │ │  │
│  │  │             │  │   sequence  │  │             │  │   stage     │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Tool Schema

Every tool implements:

```python
from pydantic import BaseModel
from typing import Any, Dict, Optional
from enum import Enum

class ToolCategory(str, Enum):
    ANALYSIS = "analysis"
    PIPELINE = "pipeline"
    DATA = "data"
    ADMIN = "admin"
    COMMUNICATION = "communication"

class ToolMetadata(BaseModel):
    name: str
    description: str
    category: ToolCategory
    input_schema: Dict[str, Any]   # JSON Schema
    output_schema: Dict[str, Any]  # JSON Schema
    latency_target_ms: int
    requires_human_approval: bool = False
    destructive: bool = False
    retry_policy: Dict[str, Any] = {
        "max_retries": 3,
        "backoff_strategy": "exponential",
        "base_delay_ms": 1000
    }
    examples: list[Dict[str, Any]] = []

class ToolResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int
    tool_name: str
    input_summary: str  # Truncated input for logging
```

### 2.3 Registry API

```python
class UnifiedToolRegistry:
    _tools: Dict[str, Callable] = {}
    _metadata: Dict[str, ToolMetadata] = {}
    
    @classmethod
    def register(cls, metadata: ToolMetadata, fn: Callable):
        cls._tools[metadata.name] = fn
        cls._metadata[metadata.name] = metadata
    
    @classmethod
    def get(cls, name: str) -> Tuple[Callable, ToolMetadata]:
        return cls._tools[name], cls._metadata[name]
    
    @classmethod
    def list_by_category(cls, category: ToolCategory) -> List[ToolMetadata]:
        return [m for m in cls._metadata.values() if m.category == category]
    
    @classmethod
    def discover(cls, intent: str) -> List[ToolMetadata]:
        """Semantic search over tool descriptions for agent self-selection."""
        # Phase 3: embedding-based search
        # Phase 2: keyword matching
        return [m for m in cls._metadata.values() if intent.lower() in m.description.lower()]
```

---

## 3. Tool Specifications

### 3.1 Analysis Tools

#### Tool: `cosmo_analysis_tool`

```yaml
name: cosmo_analysis_tool
description: Analyze an Amazon listing for COSMO semantic relation coverage across 15 relation types.
category: ANALYSIS
input_schema:
  type: object
  properties:
    asin: { type: string, description: "Amazon ASIN" }
    title: { type: string, description: "Product title" }
    bullets: { type: array, items: { type: string }, description: "Bullet points" }
    description: { type: string, description: "Product description" }
  required: [asin, title]
output_schema:
  type: object
  properties:
    overall_score: { type: number, minimum: 0, maximum: 100 }
    keyword_safety: { type: string, enum: [SAFE, WARNING, UNSAFE] }
    embedding_dimensions: { type: number }
    relation_coverage: { type: object }
    gap_alerts: { type: array }
latency_target_ms: 5000
requires_human_approval: false
retry_policy:
  max_retries: 3
  backoff_strategy: exponential
examples:
  - input: { asin: "B08N5WRWNW", title: "HydroMax Bottle", bullets: [...] }
    output: { overall_score: 62, keyword_safety: "SAFE" }
```

**Implementation:**
```python
@tool(args_schema=CosmoAnalysisInput)
def cosmo_analysis_tool(asin: str, title: str, bullets: list, description: str = "") -> Dict:
    mapper = _get_cosmo_mapper()
    return asyncio.get_event_loop().run_in_executor(
        None, mapper.analyze, asin, title, bullets, description
    )
```

---

#### Tool: `competitor_intel_tool`

```yaml
name: competitor_intel_tool
description: Generate competitor landscape, embedding similarity scores, and clustered gap opportunities.
category: ANALYSIS
input_schema:
  type: object
  properties:
    asin: { type: string }
    competitor_asins: { type: array, items: { type: string } }
  required: [asin]
output_schema:
  type: object
  properties:
    competitor_profiles: { type: array }
    gap_opportunities: { type: array }
    positioning_summary: { type: string }
    similarity_matrix: { type: object }
latency_target_ms: 10000
retry_policy:
  max_retries: 3
```

---

#### Tool: `attribution_tool`

```yaml
name: attribution_tool
description: Run Difference-in-Differences and Synthetic Control causal analysis to estimate optimization lift.
category: ANALYSIS
input_schema:
  type: object
  properties:
    asin: { type: string }
    control_asins: { type: array, items: { type: string } }
    start_date: { type: string, format: date }
    end_date: { type: string, format: date }
  required: [asin]
output_schema:
  type: object
  properties:
    did: { type: object }
    scm: { type: object }
    financial_projection: { type: object }
latency_target_ms: 8000
retry_policy:
  max_retries: 3
```

---

### 3.2 Pipeline Tools

#### Tool: `pipeline_trigger_tool`

```yaml
name: pipeline_trigger_tool
description: Manually trigger an acquisition pipeline stage.
category: PIPELINE
destructive: true
requires_human_approval: true
input_schema:
  type: object
  properties:
    stage:
      type: string
      enum: [scrape, enrich, score, draft, sequence]
    limit: { type: integer, minimum: 1, maximum: 100, default: 10 }
    brand_key: { type: string, description: "Optional single brand target" }
  required: [stage]
output_schema:
  type: object
  properties:
    success: { type: boolean }
    jobs_created: { type: integer }
    stage: { type: string }
latency_target_ms: 2000
```

---

#### Tool: `apollo_enrich_tool`

```yaml
name: apollo_enrich_tool
description: Enrich a brand with Apollo contact data.
category: PIPELINE
input_schema:
  type: object
  properties:
    brand_key: { type: string }
    domain: { type: string }
    force_refresh: { type: boolean, default: false }
  required: [brand_key]
output_schema:
  type: object
  properties:
    success: { type: boolean }
    contact_email: { type: string }
    contact_name: { type: string }
    apollo_contact_id: { type: string }
latency_target_ms: 5000
retry_policy:
  max_retries: 5
  backoff_strategy: jitter
```

---

#### Tool: `email_draft_tool`

```yaml
name: email_draft_tool
description: Generate a personalized 5-step cold email sequence for a brand.
category: PIPELINE
input_schema:
  type: object
  properties:
    brand_key: { type: string }
    anchor_asin: { type: string }
    worst_axis: { type: string }
    competitor_context: { type: string }
  required: [brand_key]
output_schema:
  type: object
  properties:
    steps: { type: array, minItems: 5, maxItems: 5 }
    validation_status: { type: string, enum: [PASS, WARNING, FAIL] }
    banned_phrases_found: { type: array }
latency_target_ms: 8000
retry_policy:
  max_retries: 2
```

---

### 3.3 Data Tools

#### Tool: `store_read_tool`

```yaml
name: store_read_tool
description: Read entities from the shared in-memory data store.
category: DATA
input_schema:
  type: object
  properties:
    key:
      type: string
      enum: [listings, competitors, clients, jobs, traffic_history]
    id: { type: string, description: "Optional entity ID (e.g., ASIN)" }
  required: [key]
output_schema:
  type: object
  properties:
    key: { type: string }
    id: { type: string }
    data: { type: object }
latency_target_ms: 50
```

---

#### Tool: `store_write_tool`

```yaml
name: store_write_tool
description: Write entities to the shared in-memory data store.
category: DATA
destructive: true
requires_human_approval: false
input_schema:
  type: object
  properties:
    key: { type: string }
    id: { type: string }
    data: { type: object }
  required: [key, id, data]
output_schema:
  type: object
  properties:
    success: { type: boolean }
    key: { type: string }
    id: { type: string }
latency_target_ms: 100
```

---

### 3.4 Admin Tools

#### Tool: `get_dashboard_metrics_tool`

```yaml
name: get_dashboard_metrics_tool
description: Fetch aggregate dashboard metrics for a time period.
category: ADMIN
input_schema:
  type: object
  properties:
    period: { type: string, enum: [today, week, month], default: today }
  required: []
output_schema:
  type: object
  properties:
    stage_counts: { type: object }
    funnel_conversion: { type: object }
    avg_cqs: { type: number }
    total_revenue: { type: number }
latency_target_ms: 500
```

---

#### Tool: `list_prospects_tool`

```yaml
name: list_prospects_tool
description: List prospects filtered by stage, score, or date.
category: ADMIN
input_schema:
  type: object
  properties:
    stage: { type: string }
    limit: { type: integer, default: 50 }
    sort_by: { type: string, enum: [created_at, score, reachability], default: created_at }
    order: { type: string, enum: [asc, desc], default: desc }
  required: []
output_schema:
  type: object
  properties:
    prospects: { type: array }
    total: { type: integer }
    page: { type: integer }
latency_target_ms: 1000
```

---

#### Tool: `update_prospect_stage_tool`

```yaml
name: update_prospect_stage_tool
description: Advance or modify a prospect's pipeline stage.
category: ADMIN
destructive: true
requires_human_approval: true
input_schema:
  type: object
  properties:
    brand_key: { type: string }
    new_stage: { type: string }
    reason: { type: string }
  required: [brand_key, new_stage]
output_schema:
  type: object
  properties:
    success: { type: boolean }
    previous_stage: { type: string }
    new_stage: { type: string }
    audit_log_id: { type: string }
latency_target_ms: 500
```

---

#### Tool: `trigger_pipeline_stage_tool`

```yaml
name: trigger_pipeline_stage_tool
description: Manually trigger a pipeline stage for a set of brands.
category: ADMIN
destructive: true
requires_human_approval: true
input_schema:
  type: object
  properties:
    stage: { type: string, enum: [scrape, enrich, score, draft, sequence] }
    brand_keys: { type: array, items: { type: string } }
    limit: { type: integer, default: 10 }
  required: [stage]
output_schema:
  type: object
  properties:
    success: { type: boolean }
    jobs_queued: { type: integer }
    job_ids: { type: array }
latency_target_ms: 1000
```

---

## 4. Agent Specifications

### 4.1 OrchestratorAgent

**Role:** Parse user intent, plan execution, delegate to specialists, synthesize results.

**System Prompt:**
```text
You are the Orchestrator for the Optimus Rufus Omni-Dashboard. Your job is to interpret user intent, create a structured plan, delegate to specialized agents, and synthesize their outputs into a clear, action-oriented response.

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

PLAN FORMAT:
Return a JSON array of PlanStep objects:
[
  { "agent": "listing", "task": "...", "depends_on": [], "requires_human_approval": false },
  { "agent": "competitor", "task": "...", "depends_on": [], "requires_human_approval": false },
  { "agent": "attribution", "task": "...", "depends_on": [0], "requires_human_approval": false },
  { "agent": "outreach", "task": "...", "depends_on": [0, 1, 2], "requires_human_approval": true }
]
```

**Capabilities:**
- Intent classification (simple Q&A vs. multi-agent workflow)
- Dependency graph construction
- Parallel vs. sequential execution planning
- HITL gate insertion
- Synthesis of multi-agent outputs

**Boundaries:**
- Cannot directly execute tools (must delegate to subgraphs)
- Cannot modify pipeline stages (must delegate to Admin Copilot)
- Cannot send emails (must insert HITL gate)

---

### 4.2 ListingAgent (COSMO Catalyst + SEO Guardian)

**Role:** Analyze and optimize Amazon listing copy for semantic relation coverage.

**System Prompt — COSMO Catalyst:**
```text
You are the COSMO Catalyst. Rewrite Amazon listings to maximize semantic relation coverage across 15 COSMO relation types:
- Function (30% weight): "What does it do?"
- Audience (25% weight): "Who is it for?"
- Context (25% weight): "When/where is it used?"
- Classification (10% weight): "What category/type?"
- Complementary (10% weight): "What goes with it?"

RULES:
1. Maintain conversational, shopper-question-answering tone.
2. Do NOT drop high-value indexing keywords.
3. Return structured JSON: { title, bullets[], description, relation_coverage }.
4. Each bullet should anticipate a specific shopper question.
5. Title must include primary keyword + 2-3 semantic modifiers.
```

**System Prompt — SEO Guardian:**
```text
You are the SEO Guardian. Audit listing copy for keyword safety and semantic drift.

RULES:
1. Compute WLPI (Weighted Lexical Preservation Index):
   - Title weight: 1.0
   - Bullets weight: 0.5 each
   - Description weight: 0.1
   - Formula: weighted_sum / total_weight
2. If WLPI < 0.85: flag as UNSAFE, specify missing keywords.
3. If semantic drift > 15% (cosine distance vs. original): flag as UNSAFE.
4. If unsafe, surgically re-insert missing keywords without destroying conversational flow.
5. Return: { wlpi_score, wlpi_status: "SAFE"|"UNSAFE", missing_keywords[], corrected_copy }
```

**Tools Used:**
- `cosmo_analysis_tool` (read current state)
- `store_read_tool` (read listing data)
- `store_write_tool` (persist optimized copy)

**Capabilities:**
- Semantic gap analysis
- Copy rewriting (5-round cyclic)
- WLPI computation
- Semantic drift validation

**Boundaries:**
- Cannot send emails
- Cannot modify competitor data
- Cannot skip safety gate

---

### 4.3 CompetitorAgent

**Role:** Generate competitor landscape, compute embedding similarity, cluster gap opportunities.

**System Prompt:**
```text
You are the Competitor Intelligence Agent. Your job is to map the competitive landscape and identify actionable gaps.

PROCESS:
1. Scrape competitor listings for the target ASIN's category.
2. Embed all listings (client + competitors) at 3072 dimensions.
3. Compute cosine similarity matrix.
4. Run PCA + HDBSCAN on gap vectors to find clustered opportunities.
5. Generate structured report with severity ratings.

OUTPUT FORMAT:
{
  "competitor_profiles": [
    { "asin", "title", "similarity_score", "key_strengths", "key_weaknesses" }
  ],
  "gap_opportunities": [
    { "cluster_id", "severity": "HIGH|MEDIUM|LOW", "description", "affected_competitors" }
  ],
  "positioning_summary": "One-paragraph narrative of where client stands"
}
```

**Tools Used:**
- `competitor_intel_tool`
- `store_read_tool`

**Capabilities:**
- Competitor discovery
- Embedding-based similarity analysis
- Gap clustering (PCA + HDBSCAN)
- Positioning narrative generation

**Boundaries:**
- No LLM generation (purely statistical)
- Cannot modify listings
- Cannot trigger outreach

---

### 4.4 AttributionAgent

**Role:** Estimate causal lift from optimization using DiD and SCM.

**System Prompt:**
```text
You are the Causal Attribution Agent. Your job is to estimate the true revenue impact of listing optimization by subtracting natural market trends.

METHODS:
1. Difference-in-Differences (DiD): Compare treatment vs. control ASINs before/after optimization.
2. Synthetic Control Method (SCM): Build weighted synthetic control from donor competitors.
3. Financial Projection: Multiply lift by sessions and AOV.

OUTPUT FORMAT:
{
  "did": {
    "lift_percent": 12.5,
    "p_value": 0.03,
    "confidence_interval": [3.2, 21.8],
    "significant": true
  },
  "scm": {
    "synthetic_lift": 11.2,
    "donor_weights": { "B08Y": 0.4, "B08Z": 0.6 },
    "mse": 0.003
  },
  "financial_projection": {
    "current_monthly_revenue": 45000,
    "projected_monthly_revenue": 50625,
    "monthly_impact": 5625,
    "annual_impact": 67500
  }
}
```

**Tools Used:**
- `attribution_tool`
- `store_read_tool` (traffic history)

**Capabilities:**
- DiD causal inference
- Synthetic control construction
- Revenue projection
- Statistical significance testing

**Boundaries:**
- Cannot optimize listings
- Cannot send emails
- Requires 30+ days of traffic data

---

### 4.5 OutreachAgent

**Role:** Execute end-to-end prospecting: enrich, score, draft, validate, and sequence.

**System Prompt:**
```text
You are the Outreach Agent. Your job is to find the right person at a weak brand, understand their listing's worst problem, and draft a compelling 5-step email sequence.

PROCESS:
1. ENRICH: Use Apollo to find CEO/Founder contact.
2. SCORE: Run Rufus v2 analysis on anchor ASIN.
3. DRAFT: Generate 5-step sequence using worst axis as narrative spine.
4. VALIDATE: Check banned phrases, 5-gram overlap, word counts.
5. SEQUENCE: Create Apollo contact and enroll in sequence.

ANTI-TEMPLATE RULES:
- No "revolutionize", "leverage", "synergy", "circle back"
- No "I'd love to", "quick note", "free audit"
- No "Hope you're well"
- 5-gram overlap < 25% vs. last 50 drafts
- Step 1 MUST contain "when a shopper asks Rufus '...'"

OUTPUT FORMAT:
{
  "enrichment": { "success", "contact_email", "contact_name" },
  "rufus_score": { "overall", "worst_axis", "citations" },
  "sequence": [
    { "step": 1, "subject": "...", "body": "...", "timing": "Day 0" },
    ...
  ],
  "validation": { "status": "PASS", "checks": [...] },
  "sequence_status": "PENDING_APPROVAL"
}
```

**Tools Used:**
- `apollo_enrich_tool`
- `email_draft_tool`
- `pipeline_trigger_tool` (sequence enrollment)
- `store_read_tool`

**Capabilities:**
- Apollo contact enrichment
- Rufus scoring
- Cold email generation
- Anti-template validation
- Sequence enrollment

**Boundaries:**
- Cannot send without HITL approval
- Cannot skip validation
- Cannot exceed Apollo rate limits

---

### 4.6 EmailAgent

**Role:** Classify inbound replies and draft contextual responses.

**System Prompt:**
```text
You are the Email Agent. Your job is to read inbound replies, classify intent, select the right strategy, and draft a response.

CLASSIFICATION CATEGORIES:
- INTERESTED: Wants to learn more. Strategy: Qualify + push demo.
- OBJECTION: Has concerns. Strategy: Acknowledge + reframe with social proof.
- NOT_NOW: Timing issue. Strategy: Soft nurture, 14-day follow-up.
- BOOKING_READY: Wants to book. Strategy: Send Calendly link immediately.
- UNSUBSCRIBE: Wants out. Strategy: Graceful exit.
- WRONG_PERSON: Not the decision maker. Strategy: Ask for referral.
- COMPETITOR: Competitor fishing. Strategy: Minimal response.
- NOISE: Spam/automated. Strategy: Ignore.

STRATEGY PLAYBOOKS:
1. qualify_and_demo: Ask 2 qualifying questions, link to calculator.
2. acknowledge_reframe: "I get it — [objection]. Here's what [client] found..."
3. nurture_14_day: "No problem. I'll circle back in two weeks with a case study."
4. graceful_exit: "Totally understand. Removing you now. Best of luck."
5. referrer_thank: "Thanks for the forward. I'll reach out to [name] directly."

OUTPUT FORMAT:
{
  "classification": { "category", "confidence", "reason" },
  "strategy": "qualify_and_demo",
  "draft_reply": "...",
  "suggested_next_stage": "DEMO_SCHEDULED"
}
```

**Tools Used:**
- `store_read_tool` (conversation history)
- `store_write_tool` (save draft)

**Capabilities:**
- Intent classification
- Strategy selection
- Reply drafting
- Compliance checking

**Boundaries:**
- Cannot send without human approval (except auto-sent nurture)
- Cannot modify brand stage directly (recommends only)

---

### 4.7 AdminCopilotAgent

**Role:** Natural language interface for operators to query telemetry and trigger actions.

**System Prompt:**
```text
You are the Admin Copilot for Optimus Rufus. Help operators manage the pipeline by querying telemetry and triggering actions.

AVAILABLE TOOLS:
- get_dashboard_metrics_tool: Fetch KPIs (today/week/month)
- list_prospects_tool: Filter prospects by stage, score, date
- get_prospect_detail_tool: Full brand record with history
- update_prospect_stage_tool: Advance/reject prospect (REQUIRES CONFIRMATION)
- trigger_pipeline_stage_tool: Trigger scrape/enrich/score/draft/sequence (REQUIRES CONFIRMATION)

RULES:
1. ALWAYS confirm destructive actions before executing.
2. Present metrics in compact tables, not prose.
3. If the user asks for something outside your tools, say so clearly.
4. Do NOT make up data. Query the tools.
5. When listing prospects, show: brand_key, stage, score, contact, last active.

EXAMPLE INTERACTIONS:

User: "How many prospects replied this week?"
→ get_dashboard_metrics_tool(period="week")
→ "12 prospects replied. Average Rufus score: 78.4. Top stage: LOOM_SENT."

User: "Advance all REPLIED to DEMO_SCHEDULED"
→ "This will affect 12 prospects. Confirm? (yes/no)"
→ [If yes] update_prospect_stage_tool for each.
```

**Tools Used:**
- `get_dashboard_metrics_tool`
- `list_prospects_tool`
- `get_prospect_detail_tool`
- `update_prospect_stage_tool`
- `trigger_pipeline_stage_tool`

**Capabilities:**
- Natural language to SQL/query translation
- Telemetry aggregation
- Bulk operations with confirmation
- Pipeline stage triggers

**Boundaries:**
- Cannot send emails directly
- Cannot modify email drafts
- Cannot access LLM optimization tools

---

## 5. Human-in-the-Loop Tool Interactions

### 5.1 HITL Triggers

| Tool | HITL Trigger | Prompt | Options |
|------|-------------|--------|---------|
| `pipeline_trigger_tool` (sequence) | Before Apollo enrollment | "Approve email draft for {brand_key}?" | Approve / Reject / Edit |
| `update_prospect_stage_tool` (SKIP) | Before destructive update | "Mark {brand_key} as SKIP? This cannot be undone." | Confirm / Cancel |
| `update_prospect_stage_tool` (PAID) | Before revenue stage | "Mark {brand_key} as PAID?" | Confirm / Cancel |
| `email_draft_tool` | After validation warning | "Draft has 30% 5-gram overlap. Regenerate or proceed?" | Regenerate / Proceed / Manual Edit |

### 5.2 HITL Payload Schema

```python
class HumanInterrupt(BaseModel):
    prompt: str
    payload: Dict[str, Any]
    step_index: int
    options: List[str] = ["approve", "reject", "modify"]
    deadline: Optional[datetime] = None  # Auto-reject after N minutes
    
class HumanResponse(BaseModel):
    action: str                       # "approve" | "reject" | "modify"
    modifications: Optional[str] = None  # Free-text edits
    modified_payload: Optional[Dict] = None  # Structured overrides
```

---

## 6. Tool Execution Patterns

### 6.1 Synchronous (Blocking)

```python
# Used for: fast operations (<1s), read-only queries
result = await tool.invoke(input)
```

### 6.2 Asynchronous (Background)

```python
# Used for: slow operations (LLM calls, external APIs)
task = asyncio.create_task(tool.invoke(input))
# Stream progress via SSE while task runs
```

### 6.3 Batch (Parallel)

```python
# Used for: multiple independent operations
results = await asyncio.gather(*[
    tool.invoke(input_i) for input_i in batch
])
```

### 6.4 Retry with Backoff

```python
async def invoke_with_retry(tool, input, policy):
    for attempt in range(policy.max_retries):
        try:
            return await tool.invoke(input)
        except RetryableError as e:
            delay = policy.base_delay_ms * (2 ** attempt)
            if policy.backoff_strategy == "jitter":
                delay += random.uniform(0, delay * 0.1)
            await asyncio.sleep(delay / 1000)
    raise MaxRetriesExceeded()
```

---

## 7. Tool Extensibility

### 7.1 Adding a New Tool

```python
# 1. Define the tool function
@tool(args_schema=MyToolInput)
def my_new_tool(param1: str, param2: int) -> Dict:
    """Description of what this tool does."""
    return {"result": param1 * param2}

# 2. Register in UnifiedToolRegistry
UnifiedToolRegistry.register(
    metadata=ToolMetadata(
        name="my_new_tool",
        description="Description of what this tool does.",
        category=ToolCategory.ANALYSIS,
        input_schema=MyToolInput.model_json_schema(),
        output_schema={"type": "object", "properties": {"result": {"type": "integer"}}},
        latency_target_ms=1000,
    ),
    fn=my_new_tool,
)

# 3. Update agent system prompts to mention the new tool
# 4. No other code changes required
```

### 7.2 Tool Discovery by Agents

```python
# Agent self-selects tools based on intent
def select_tools(intent: str) -> List[ToolMetadata]:
    # Phase 2: Keyword matching
    tools = UnifiedToolRegistry.discover(intent)
    
    # Phase 3: Embedding-based semantic search
    # intent_embedding = embed(intent)
    # tool_embeddings = [embed(t.description) for t in all_tools]
    # tools = semantic_search(intent_embedding, tool_embeddings)
    
    return tools
```

---

## 8. Files & Implementation

| Component | File | Status |
|-----------|------|--------|
| Tool Registry | `backend/agent/graph/tools.py` | ✅ Implemented |
| Tool Schemas | `backend/agent/graph/tools.py` (Pydantic) | ✅ Implemented |
| Orchestrator Prompt | `backend/agent/graph/supervisor.py` | ✅ Implemented (rule-based) |
| Listing Agent Prompt | `docs/architecture/agent-specs.md` | ✅ Documented |
| Outreach Agent Prompt | `docs/architecture/agent-specs.md` | ✅ Documented |
| Email Agent Prompt | `docs/architecture/agent-specs.md` | ✅ Documented |
| Admin Copilot Prompt | `docs/architecture/agent-specs.md` | ✅ Documented |
| HITL Schema | `backend/agent/graph/state.py` | ✅ Implemented |
| UnifiedToolRegistry | `backend/agent/graph/tools.py` | ✅ Partial |
| LangSmith Tracing | `backend/core/langsmith.py` | 🔲 Pending |
