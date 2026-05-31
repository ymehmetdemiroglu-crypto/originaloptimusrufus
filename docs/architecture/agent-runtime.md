# Phase 3: AI Copilot Tooling & Agent Spec
# Agent Runtime Recommendation

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Executive Summary

The Omni-Dashboard MAS requires an embedded agent engine capable of **stateful cyclic execution**, **human-in-the-loop interrupts**, **structured checkpointing**, and **fine-grained streaming** — capabilities that traditional task queues and DAG orchestrators cannot provide natively.

**Recommendation:** **LangGraph** as the primary agent runtime, with **Model Context Protocol (MCP)** as the interoperability layer for external tool integration (Phase 4+).

**Secondary components:**
- **LangChain Core:** Tool definitions, prompt templates, output parsers
- **LangSmith:** LLM tracing, observability, and evaluation
- **APScheduler:** Legacy cron-based pipeline (preserved, not replaced)

---

## 2. Agent Runtime Evaluation Matrix

| Criterion | LangGraph | CrewAI | AutoGen | Temporal | Pure FastAPI + Celery |
|-----------|-----------|--------|---------|----------|----------------------|
| **Stateful cycles** | ✅ Native | ❌ DAG only | ⚠️ Conversational loops | ⚠️ Workflow loops | ❌ Manual state mgmt |
| **Human-in-the-loop** | ✅ `interrupt` / `Command(resume=...)` | ❌ External only | ⚠️ Manual | ✅ Native | ❌ Manual impl |
| **Checkpoint persistence** | ✅ Postgres/SQLite/Redis/Memory | ❌ External only | ❌ External only | ✅ Native | ❌ Custom impl |
| **Structured output** | ✅ Pydantic schemas per node | ⚠️ High-level | ⚠️ Conversational | ✅ Type-safe | ✅ Pydantic |
| **Streaming events** | ✅ `astream_events` with tool/node granularity | ❌ Limited | ⚠️ Partial | ❌ No streaming | ❌ Manual SSE |
| **Tool use (ReAct)** | ✅ Native `ToolNode` | ✅ Native | ✅ Native | ❌ No LLM | ⚠️ Manual impl |
| **Sub-graph composition** | ✅ `StateGraph` as node in parent | ❌ Flat only | ⚠️ Nested groups | ✅ Sub-workflows | ❌ Manual impl |
| **Observability** | ✅ LangSmith integration | ⚠️ Basic | ⚠️ Basic | ✅ UI + metrics | ⚠️ Custom logs |
| **Ecosystem fit** | ✅ Python-native; FastAPI-friendly | ✅ Python-native | ✅ Python-native | ❌ Go/Java SDK | ✅ Python-native |
| **Operational complexity** | Medium (checkpoints + threads) | Low | Low | High | Medium |
| **Team expertise ramp** | Medium (graph concepts) | Low (role-based) | Low (chat-based) | High (DSL) | Low (existing) |

---

## 3. Deep Dive: LangGraph

### 3.1 Why LangGraph Wins for Optimus Rufus

**1. The COSMO Catalyst ↔ SEO Guardian Loop Requires Cycles**

The existing `agentic_optimizer.py` runs a 5-round iterative loop where:
- Agent A generates copy
- Agent B audits and re-inserts keywords
- If unsafe, loop back to Agent A

CrewAI's DAG-only model cannot express this without external state hacks. LangGraph's `StateGraph` supports arbitrary cycles natively:

```python
builder.add_conditional_edges(
    "safety_gate",
    lambda state: "safe" if state.wlpi >= 0.85 and state.drift <= 0.15 else "unsafe",
    {"safe": "persist", "unsafe": "agentic_optimize"}  # Cycle!
)
```

**2. HITL is a First-Class Primitive, Not an Afterthought**

LangGraph provides `interrupt()` and `Command(resume=...)` for true breakpoints:

```python
from langgraph.types import interrupt, Command

def human_gate(state: OmniState):
    """Pause execution and wait for human input."""
    response = interrupt({
        "prompt": "Approve email draft?",
        "payload": state.agent_outputs["outreach"]["draft"]
    })
    return {"human_response": response}

# Resume later:
graph.invoke(
    Command(resume={"action": "approve"}),
    config={"configurable": {"thread_id": "B08X_123"}}
)
```

CrewAI and AutoGen require manual HTTP polling or external state machines to achieve the same.

**3. Checkpointing Enables Deterministic Recovery**

LangGraph's `CheckpointSaver` persists full thread state after every node:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver(conn=supabase_pool)
graph = builder.compile(checkpointer=checkpointer)

# If server crashes mid-workflow, resume exactly where it left off:
graph.invoke(
    None,  # No new input; resume from checkpoint
    config={"configurable": {"thread_id": "B08X_123"}}
)
```

**4. `astream_events` Provides Surgical Streaming**

The frontend needs to show "COSMO analysis running..." then "Competitor intel running..." — not just a single spinner. LangGraph emits granular events:

```python
async for event in graph.astream_events(state, config, version="v2"):
    if event["event"] == "on_tool_start":
        yield f"tool_start: {event['name']}"
    elif event["event"] == "on_tool_end":
        yield f"tool_end: {event['name']} = {event['data']['output']}"
    elif event["event"] == "on_chat_model_stream":
        yield f"token: {event['data']['chunk'].content}"
```

**5. Sub-Graph Composition Matches Our Architecture**

The Supervisor-Subgraph pattern maps directly to LangGraph's composable graphs:

```python
# Each subgraph is independently testable
listing_graph = build_listing_subgraph()
competitor_graph = build_competitor_subgraph()

# Supervisor delegates by spawning subgraph with forked state
async def delegate_listing(state: OmniState):
    forked = state.model_copy(deep=True)
    result = await listing_graph.ainvoke(forked)
    return {"agent_outputs": {**state.agent_outputs, "listing": result}}
```

### 3.2 LangGraph Architecture in Optimus Rufus

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH RUNTIME                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    SupervisorGraph (compiled)                          │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  StateGraph(OmniState) ──▶ compiled ──▶ Runnable               │  │  │
│  │  │  ├─ Nodes: plan, delegate, synthesize, human_gate              │  │  │
│  │  │  ├─ Edges: conditional routing                                │  │  │
│  │  │  └─ Config: recursion_limit=50, checkpointer=PostgresSaver     │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                              │                                         │  │
│  │           ┌──────────┬───────┴────┬──────────┬──────────┐            │  │
│  │           ▼          ▼            ▼          ▼          ▼            │  │
│  │  ┌────────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │  │
│  │  │ Listing    │ │Compet- │ │Attrib- │ │Outreach│ │ Email  │        │  │
│  │  │ Subgraph   │ │itor    │ │ution   │ │Subgraph│ │Subgraph│        │  │
│  │  │ (cyclic)   │ │Subgraph│ │Subgraph│ │(+HITL) │ │Subgraph│        │  │
│  │  └────────────┘ └────────┘ └────────┘ └────────┘ └────────┘        │  │
│  │           │          │          │          │          │             │  │
│  │           └──────────┴──────────┴──────────┴──────────┘             │  │
│  │                              │                                      │  │
│  │                              ▼                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────┐   │  │
│  │  │                    ToolNode Layer                            │   │  │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │   │  │
│  │  │  │ cosmo_ │ │compet- │ │attrib- │ │apollo_ │ │store_  │  │   │  │
│  │  │  │analysis│ │itor    │ │ution   │ │enrich  │ │read    │  │   │  │
│  │  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │   │  │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │   │  │
│  │  │  │email_  │ │pipeline│ │store_  │ │admin_  │            │   │  │
│  │  │  │draft   │ │trigger │ │write   │ │query   │            │   │  │
│  │  │  └────────┘ └────────┘ └────────┘ └────────┘            │   │  │
│  │  └─────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 State Management

**State Schema:**
```python
class OmniState(BaseModel):
    messages: List[Dict] = []
    workspace: WorkspaceSnapshot = Field(default_factory=WorkspaceSnapshot)
    plan: List[PlanStep] = []
    current_step_index: int = 0
    agent_outputs: Dict[str, AgentOutput] = {}
    pending_human_input: Optional[HumanInterrupt] = None
    errors: List[str] = []
    completed: bool = False
    synthesis: Optional[str] = None
```

**Checkpoint Strategy:**

| Layer | Saver | Use Case | Durability |
|-------|-------|----------|------------|
| Dev | `MemorySaver` | Local testing | Ephemeral |
| Staging | `SqliteSaver` | CI/CD tests | File-based |
| Production | `PostgresSaver` | Persistent threads | Supabase Postgres |
| Distributed | `RedisSaver` | Multi-worker | Redis |

**Checkpoint Config:**
```python
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

pool = ConnectionPool(conninfo=SUPABASE_URL, max_size=20)
checkpointer = PostgresSaver(sync_connection=pool)

# Every node execution auto-checkpoints:
# INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint, metadata)
```

### 3.4 Streaming Architecture

```python
# backend/routers/omni.py
from fastapi.responses import StreamingResponse

async def _stream_graph_events(thread_id: str, state: OmniState):
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50
    }
    
    async for event in graph.astream_events(state, config, version="v2"):
        # Transform LangGraph events to frontend-friendly SSE
        if event["event"] == "on_chain_start":
            yield sse_json({"event": "agent_start", "agent": event["name"]})
            
        elif event["event"] == "on_tool_start":
            yield sse_json({"event": "tool_start", "tool": event["name"]})
            
        elif event["event"] == "on_tool_end":
            yield sse_json({
                "event": "tool_end",
                "tool": event["name"],
                "output": sanitize_output(event["data"]["output"])
            })
            
        elif event["event"] == "on_chat_model_stream":
            yield sse_json({
                "event": "token",
                "content": event["data"]["chunk"].content
            })
            
        elif event["event"] == "on_interrupt":
            yield sse_json({
                "event": "human_input_required",
                "payload": event["data"]
            })
            
        elif event["event"] == "on_chain_end":
            yield sse_json({
                "event": "agent_complete",
                "agent": event["name"],
                "output": event["data"]["output"]
            })
```

**Frontend Consumption:**
```typescript
const eventSource = new EventSource(`/api/omni/chat?thread_id=${id}`);
eventSource.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    switch (msg.event) {
        case "agent_start": setActiveAgent(msg.agent); break;
        case "tool_start": appendLog(`Running ${msg.tool}...`); break;
        case "token": appendToken(msg.content); break;
        case "human_input_required": renderApprovalCard(msg.payload); break;
        case "agent_complete": updateMetricCard(msg.agent, msg.output); break;
    }
};
```

### 3.5 Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Graph compilation | ~50ms | One-time at startup |
| Node overhead | ~5ms | Pydantic serialization + checkpoint write |
| Checkpoint write (Postgres) | ~20ms | Async, non-blocking |
| Checkpoint read (Postgres) | ~10ms | Index on `(thread_id, checkpoint_id)` |
| Stream latency (first byte) | ~100ms | HTTP handshake + plan_node |
| Max recursion depth | 50 | Hard limit to prevent infinite loops |
| Max concurrent threads | 2,000 | Per 4-worker Uvicorn instance |
| Memory per thread | ~50KB | State size depends on message history |

---

## 4. Model Context Protocol (MCP) — Phase 4+

### 4.1 What is MCP?

MCP (Model Context Protocol) is an open standard for connecting AI assistants to external systems. It defines a JSON-RPC based protocol for tool discovery, invocation, and context sharing.

### 4.2 When to Introduce MCP

| Scenario | MCP Benefit |
|----------|-------------|
| External SaaS integration | Apollo, Calendly, HubSpot expose MCP servers |
| Multi-tenant tool sharing | One MCP server serves multiple agent systems |
| Third-party plugin ecosystem | External developers build MCP tools for your platform |
| Cross-language agents | Node.js MCP server consumed by Python LangGraph |

### 4.3 MCP + LangGraph Integration

```python
# Future: backend/agent/mcp_client.py
from mcp import ClientSession, StdioServerParameters
from langchain_mcp_adapters.tools import load_mcp_tools

# Connect to Apollo MCP server
apollo_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-apollo"],
    env={"APOLLO_API_KEY": os.getenv("APOLLO_API_KEY")}
)

async with ClientSession(apollo_params) as session:
    apollo_tools = await load_mcp_tools(session)
    # apollo_tools now contains: apollo_search_people, apollo_enrich_contact, etc.
    
    # Add to LangGraph ToolNode
    tool_node = ToolNode([cosmo_analysis_tool, competitor_intel_tool, *apollo_tools])
```

### 4.4 MCP vs. Native Tools

| Aspect | Native LangChain Tools | MCP Tools |
|--------|----------------------|-----------|
| Setup | Python function + `@tool` | External process / HTTP server |
| Latency | In-process (<1ms overhead) | IPC / HTTP (~5-50ms) |
| Discovery | Registry lookup | JSON-RPC `tools/list` |
| Schema | Pydantic model | JSON Schema via MCP |
| Auth | Inherited from FastAPI | Per-server credentials |
| Updates | Redeploy backend | Restart MCP server |
| Use case | Core platform tools | External SaaS integrations |

**Recommendation:** Keep core tools (COSMO, competitor, attribution) as native LangChain tools. Migrate external integrations (Apollo, Calendly, HubSpot) to MCP servers in Phase 4+.

---

## 5. Runtime Deployment

### 5.1 In-Process (Current)

```
FastAPI Process
├── Uvicorn Worker 1
│   ├── LangGraph Runtime
│   │   ├── SupervisorGraph
│   │   └── Subgraphs
│   └── FastAPI Routers
└── Uvicorn Worker 2
    └── (same structure)
```

**Pros:** Zero network overhead; shared memory for DataStore
**Cons:** CPU-bound tools block event loop; limited horizontal scaling

### 5.2 Multi-Process (Phase 3)

```
FastAPI API Gateway
├── Uvicorn Workers (4) — HTTP + SSE
└── Celery Workers (4) — Background graph execution
    ├── CPU Queue: Embeddings, HDBSCAN
    ├── API Queue: Apollo, Gemini, OpenRouter
    └── Default Queue: General tasks
```

**Pros:** CPU work off main thread; horizontal scaling
**Cons:** State sharing via Redis/Postgres; higher latency

### 5.3 Microservices (Phase 5)

```
API Gateway (FastAPI)
├── /api/omni/chat → Supervisor Service
├── /api/omni/agents → Agent Registry Service
└── /api/omni/threads → Thread Management Service

Agent Services (Kubernetes)
├── listing-agent-service (2 replicas)
├── competitor-agent-service (2 replicas)
├── attribution-agent-service (1 replica)
└── outreach-agent-service (2 replicas)
```

**Pros:** Independent scaling per agent; fault isolation
**Cons:** Operational complexity; inter-service latency

---

## 6. Migration Path from APScheduler

### 6.1 Current State

```python
# backend/agent/orchestrator.py
class AgentOrchestrator:
    def start(self):
        self.scheduler.add_job(self.run_scrape, "cron", hour=2)
        self.scheduler.add_job(self.run_enrich, "cron", hour=4)
        self.scheduler.add_job(self.run_score, "cron", hour=6)
        self.scheduler.add_job(self.run_draft, "cron", hour=8)
        self.scheduler.add_job(self.run_sequence, "cron", hour=10)
```

### 6.2 Hybrid State (Phase 2-3)

APScheduler continues running legacy pipeline. LangGraph handles new Omni-Dashboard requests. Both write to the same Supabase tables.

### 6.3 Unified State (Phase 4)

```python
# LangGraph scheduled execution via Celery
@app.task
def scheduled_outreach_pipeline():
    """Replaces APScheduler outreach cron."""
    graph = build_outreach_subgraph()
    
    # Fetch all CONTACT_ENRICHED brands
    brands = supabase.table("brands").select("*").eq("stage", "CONTACT_ENRICHED").execute()
    
    for brand in brands.data:
        state = OmniState(
            workspace=WorkspaceSnapshot(brand_key=brand["brand_key"]),
            messages=[{"role": "human", "content": "Process outreach for this brand"}]
        )
        graph.invoke(state, config={"configurable": {"thread_id": f"scheduled_{brand['brand_key']}"}})
```

---

## 7. Observability Integration

### 7.1 LangSmith Tracing

```python
from langchain_core.tracers.langchain import LangChainTracer

tracer = LangChainTracer(
    project_name="optimus-rufus-omni",
    tags=["production", "v1"]
)

# Trace every graph invocation
result = graph.ainvoke(
    state,
    config={
        "callbacks": [tracer],
        "run_name": f"omni-{thread_id}",
        "tags": [state.workspace.asin or "no-asin"]
    }
)
```

**Traced Data:**
- Full execution waterfall (node entry/exit)
- Tool call inputs/outputs
- LLM token usage and cost
- Latency per node
- Error stack traces

### 7.2 Custom Metrics

```python
# backend/middleware/metrics.py
from prometheus_client import Counter, Histogram, Gauge

omni_requests = Counter("omni_requests_total", "Total Omni requests", ["agent"])
omni_latency = Histogram("omni_latency_seconds", "Request latency", ["agent"])
omni_errors = Counter("omni_errors_total", "Total errors", ["agent", "error_type"])
omni_sse_connections = Gauge("omni_sse_connections", "Active SSE streams")
omni_hitl_pending = Gauge("omni_hitl_pending", "Pending HITL approvals")

# Instrument every node
def instrumented_node(func):
    async def wrapper(state: OmniState):
        agent = func.__name__
        omni_requests.labels(agent=agent).inc()
        with omni_latency.labels(agent=agent).time():
            try:
                return await func(state)
            except Exception as e:
                omni_errors.labels(agent=agent, error_type=type(e).__name__).inc()
                raise
    return wrapper
```

---

## 8. Files & Implementation

| Component | Path | Status |
|-----------|------|--------|
| LangGraph Supervisor | `backend/agent/graph/supervisor.py` | ✅ Implemented |
| LangGraph Subgraphs | `backend/agent/graph/subgraphs.py` | ✅ Implemented |
| LangGraph State | `backend/agent/graph/state.py` | ✅ Implemented |
| Tool Layer | `backend/agent/graph/tools.py` | ✅ Implemented |
| FastAPI Router | `backend/routers/omni.py` | ✅ Implemented |
| Streaming (SSE) | `backend/routers/omni.py` | ✅ Implemented |
| Legacy Orchestrator | `backend/agent/orchestrator.py` | ✅ Preserved |
| LangSmith Tracer | `backend/core/langsmith.py` | 🔲 Pending |
| Prometheus Metrics | `backend/middleware/metrics.py` | 🔲 Pending |
| MCP Client | `backend/agent/mcp_client.py` | 🔲 Phase 4 |
| Celery Integration | `backend/agent/tasks.py` | 🔲 Phase 3+ |
| PostgresSaver Migration | `backend/migrations/002_langgraph_checkpoint.sql` | 🔲 Pending |

---

## 9. Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Agent Runtime** | LangGraph | Stateful cycles, HITL, checkpointing, streaming |
| **Tool Framework** | LangChain Core | `@tool` decorator, Pydantic schemas, `ToolNode` |
| **Tracing** | LangSmith | Purpose-built for LLM agent observability |
| **External Tool Protocol** | MCP (Phase 4+) | Standardized interop for SaaS integrations |
| **Legacy Pipeline** | APScheduler (preserved) | Zero disruption; migrate incrementally |
| **Future Scale** | Celery + Redis | Distributed execution for high throughput |
