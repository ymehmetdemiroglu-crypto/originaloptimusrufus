# Omni-Dashboard MAS — Observability & Logs

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Observability Philosophy

The Omni-Dashboard MAS operates as a distributed system of LLM agents, statistical models, and external APIs. Traditional logging is insufficient. We implement **three pillars**:

| Pillar | Question | Implementation |
|--------|----------|----------------|
| **Metrics** | Is the system fast and healthy? | Prometheus + Grafana |
| **Logs** | What happened and why? | `structlog` → JSON → Loki |
| **Traces** | Where did time go? | LangSmith + OpenTelemetry |

---

## 2. Log Sources

### 2.1 Source Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOG SOURCES                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  FastAPI        │  │  LangGraph      │  │  External APIs  │             │
│  │  (structlog)    │  │  (langsmith)    │  │  (httpx +      │             │
│  │                 │  │                 │  │   apollo_client)│             │
│  │  • Requests     │  │  • Node entry   │  │                 │             │
│  │  • Responses    │  │  • Tool calls   │  │  • Gemini       │             │
│  │  • Exceptions   │  │  • Transitions  │  │  • OpenRouter   │             │
│  │  • Middleware   │  │  • Checkpoints  │  │  • Apollo       │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           │                    │                    │                       │
│  ┌────────┴────────────────────┴────────────────────┴──────────────────┐   │
│  │                         AGGREGATION LAYER                           │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │   │
│  │  │  Loki           │  │  LangSmith      │  │  Supabase       │    │   │
│  │  │  (log storage)  │  │  (LLM traces)   │  │  (audit trail)  │    │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘    │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Source Detail

| Source | Log Format | Volume/Day | Retention |
|--------|-----------|------------|-----------|
| FastAPI access logs | JSON (`structlog`) | ~50MB | 30 days |
| LangGraph execution traces | JSON + LangSmith | ~100MB | 90 days |
| Tool call telemetry | JSON (`structlog`) | ~20MB | 30 days |
| LLM completions | JSON (via LangSmith) | ~200MB | 90 days |
| External API calls | JSON (`httpx` interceptor) | ~30MB | 14 days |
| Frontend events | JSON (console + beacon) | ~10MB | 7 days |
| Supabase audit | Postgres rows | ~5MB | 1 year |

---

## 3. Log Aggregation Pipeline

### 3.1 Pipeline Architecture

```
Application ──▶ structlog ──▶ JSON stdout ──▶ Promtail ──▶ Loki ──▶ Grafana
     │                                              │
     │              ┌───────────────────────────────┘
     │              │
     ▼              ▼
LangSmith ──▶ Cloud API ──▶ LangSmith Dashboard
     │
     ▼
Supabase ──▶ Postgres CDC ──▶ Webhook ──▶ Audit Log Table
```

### 3.2 structlog Configuration

```python
# backend/core/logging.py
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.filter_by_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Bound context for every Omni request
logger = structlog.get_logger("omni")
logger = logger.bind(
    thread_id=thread_id,
    workspace=workspace.model_dump(),
    user_id=user_id,
    trace_id=trace_id,
)
```

### 3.3 JSON Log Schema

```json
{
    "timestamp": "2026-05-30T11:35:57.682Z",
    "level": "info",
    "logger": "omni.supervisor",
    "thread_id": "B08X_1717067757_a1b2",
    "trace_id": "abc-123-def",
    "user_id": "admin@agency.co",
    "workspace": {
        "asin": "B08X",
        "brand_key": "hydromax",
        "client_id": "client-42"
    },
    "event": "agent.step.complete",
    "agent": "listing",
    "node": "cosmo_analysis",
    "tool": "cosmo_analysis_tool",
    "latency_ms": 3240,
    "input_tokens": 450,
    "output_tokens": 120,
    "output": {
        "overall_score": 62,
        "keyword_safety": "SAFE"
    },
    "error": null,
    "retry_count": 0
}
```

### 3.4 Context Propagation

Every log entry inherits context from parent operations:

```python
# In FastAPI middleware
@asynccontextmanager
async def logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    thread_id = request.headers.get("X-Thread-ID")
    
    with structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        thread_id=thread_id,
        path=request.url.path,
        method=request.method,
    ):
        response = await call_next(request)
        return response

# In LangGraph nodes
def _plan_node(state: OmniState):
    logger = structlog.get_logger("omni.supervisor.plan")
    logger = logger.bind(
        message=state.get_last_human_message()[:100],
        plan_length=len(state.plan),
    )
    logger.info("Planning execution")
    # ... plan logic
    logger.info("Plan generated", plan=plan.model_dump())
```

---

## 4. Filtering & Search

### 4.1 LogQL Queries (Loki)

| Search Intent | LogQL Query |
|---------------|-------------|
| All Omni events for thread | `{app="omni"} \|= `\| json \| thread_id="B08X_1717067757_a1b2"` |
| Failed tool calls | `{app="omni"} \|= `\| json \| level="error" \| event="agent.step.failed"` |
| Slow operations (>5s) | `{app="omni"} \|= `\| json \| latency_ms > 5000` |
| Specific agent | `{app="omni"} \|= `\| json \| agent="outreach"` |
| LLM token usage | `{app="omni"} \|= `\| json \| input_tokens > 1000 or output_tokens > 500` |
| User activity | `{app="omni"} \|= `\| json \| user_id="admin@agency.co"` |
| Error stack traces | `{app="omni"} \|= "Traceback"` |
| HITL events | `{app="omni"} \|= `\| json \| event="hitl.pending" or event="hitl.resumed"` |

### 4.2 Real-Time Filtering

```python
# backend/routers/omni.py — SSE streaming with log correlation
async def _stream_graph_events(thread_id: str, state: OmniState):
    logger = structlog.get_logger("omni.sse")
    logger = logger.bind(thread_id=thread_id)
    
    try:
        async for event in graph.astream_events(state, config={"thread_id": thread_id}):
            # Log every event for traceability
            logger.info(
                "Streaming event",
                event_type=event["event"],
                agent=event.get("data", {}).get("agent"),
                latency_ms=event.get("data", {}).get("latency_ms"),
            )
            
            # Filter: only stream relevant events to client
            if event["event"] in STREAMABLE_EVENTS:
                yield f"data: {json.dumps(event)}\n\n"
                
    except Exception as exc:
        logger.error("Stream error", error=str(exc), exc_info=True)
        yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(exc)}})}\n\n"
```

### 4.3 Log Levels by Environment

| Level | Dev | Staging | Production |
|-------|-----|---------|------------|
| `DEBUG` | All agent internals | Tool calls only | Disabled |
| `INFO` | All requests | All requests | All requests |
| `WARNING` | Slow queries | Slow queries | Slow queries |
| `ERROR` | All exceptions | All exceptions | All exceptions |
| `CRITICAL` | System failures | System failures | System failures + PagerDuty |

---

## 5. LangSmith Tracing

### 5.1 Trace Structure

```
Trace: optimus-rufus-omni
├─ Run: SupervisorGraph
│  ├─ Run: plan_node
│  │  └─ LLM Call: deepseek-chat-v3 (plan generation)
│  ├─ Run: delegate_node
│  │  ├─ Run: ListingGraph
│  │  │  ├─ Run: cosmo_analysis
│  │  │  │  └─ Tool: cosmo_analysis_tool
│  │  │  │      ├─ Input: {asin: "B08X", title: "..."}
│  │  │  │      ├─ Output: {overall_score: 62}
│  │  │  │      └─ Latency: 3240ms
│  │  │  └─ Run: safety_gate
│  │  │      └─ Tool: verify_semantic_drift
│  │  │          └─ Output: {status: "SAFE", drift: 0.08}
│  │  └─ Run: CompetitorGraph
│  │      └─ Run: embed_landscape
│  │          └─ Tool: competitor_intel_tool
│  │              └─ Output: {profiles: [...]}
│  └─ Run: synthesize_node
│      └─ LLM Call: deepseek-chat-v3 (synthesis)
```

### 5.2 LangSmith Configuration

```python
# backend/core/langsmith.py
from langsmith import Client
from langchain_core.tracers.langchain import LangChainTracer

LANGSMITH_PROJECT = "optimus-rufus-omni"

def get_tracer():
    return LangChainTracer(
        project_name=LANGSMITH_PROJECT,
        tags=["omni", "v1"],
    )

# Attach to every graph invocation
tracer = get_tracer()
result = graph.ainvoke(
    state,
    config={"callbacks": [tracer], "run_name": f"omni-{thread_id}"}
)
```

### 5.3 LangSmith Dashboards

| Dashboard | Metrics | Use Case |
|-----------|---------|----------|
| **Token Usage** | Input/output tokens per agent | Cost optimization |
| **Latency Heatmap** | p50/p95/p99 per node | Performance regression detection |
| **Error Rate** | Failed tool calls per agent | Reliability monitoring |
| **Trace Explorer** | Full execution waterfall | Debugging complex workflows |
| **Feedback** | Human approval ratings | RLHF data collection |

---

## 6. Real-Time Dashboards (Grafana)

### 6.1 Dashboard Panels

#### Omni-Dashboard Overview

| Panel | Query | Alert Threshold |
|-------|-------|----------------|
| **Active Threads** | `count(increase(omni_chat_requests[1h]))` | >1000/hour |
| **Avg Workflow Latency** | `histogram_quantile(0.95, omni_workflow_duration)` | >30s |
| **Error Rate** | `rate(omni_errors[5m]) / rate(omni_requests[5m])` | >1% |
| **Active SSE Connections** | `omni_sse_connections` | >500 |
| **LLM Token Burn** | `rate(omni_llm_tokens[5m])` | >10K/min |
| **Tool Success Rate** | `rate(omni_tool_success[5m]) / rate(omni_tool_calls[5m])` | <95% |
| **HITL Queue Depth** | `omni_hitl_pending` | >20 |
| **Embedding Cache Hit** | `rate(omni_embedding_cache_hit[5m])` | <80% |

#### Per-Agent Breakdown

| Panel | Agents | Metrics |
|-------|--------|---------|
| **Invocation Count** | All 6 | Bar chart per agent |
| **Avg Latency** | All 6 | p50/p95 per agent |
| **Error Rate** | All 6 | Line chart per agent |
| **Token Usage** | Listing, Outreach, Email | Input vs output tokens |

### 6.2 Alert Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: omni-alerts
    rules:
      - alert: OmniHighErrorRate
        expr: rate(omni_errors[5m]) / rate(omni_requests[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Omni-Dashboard error rate > 1%"
          
      - alert: OmniSlowWorkflow
        expr: histogram_quantile(0.95, omni_workflow_duration) > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 workflow latency > 60s"
          
      - alert: OmniLLMRatelimit
        expr: rate(omni_llm_rate_limit_hits[5m]) > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "LLM rate limiting detected"
          
      - alert: OmniHITLBacklog
        expr: omni_hitl_pending > 20
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "HITL queue depth > 20"
```

---

## 7. Audit Trail

### 7.1 Audit Events

Every HITL decision, destructive action, and stage advance is immutable:

```sql
-- Supabase table: audit_log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT now(),
    actor TEXT NOT NULL,              -- user_id or agent_id
    action TEXT NOT NULL,             -- APPROVE_EMAIL | REJECT_EMAIL | ADVANCE_STAGE
    resource_type TEXT NOT NULL,      -- email | prospect | pipeline
    resource_id TEXT NOT NULL,        -- brand_key or email_id
    thread_id TEXT,
    before_state JSONB,               -- snapshot before change
    after_state JSONB,                -- snapshot after change
    reason TEXT,                      -- human-provided rationale
    ip_address INET,
    user_agent TEXT
);

-- Index for fast lookups
CREATE INDEX idx_audit_thread ON audit_log(thread_id, timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor, timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
```

### 7.2 Audit Log Examples

| Timestamp | Actor | Action | Resource | Before | After |
|-----------|-------|--------|----------|--------|-------|
| 2026-05-30 11:00 | `admin@agency.co` | `APPROVE_EMAIL` | brand:hydromax | `EMAIL_DRAFTED` | `SEQUENCED` |
| 2026-05-30 11:05 | `admin@agency.co` | `REJECT_EMAIL` | brand:matchaco | `EMAIL_DRAFTED` | `DO_NOT_CONTACT` |
| 2026-05-30 11:10 | `omni.outreach` | `AUTO_ENROLL` | brand:hydromax | `APPROVED` | `SEQUENCED` |
| 2026-05-30 11:15 | `admin@agency.co` | `TRIGGER_STAGE` | pipeline | `IDLE` | `RUNNING` |

---

## 8. Frontend Observability

### 8.1 Client-Side Logging

```typescript
// rufus-dashboard/src/lib/telemetry.ts
interface FrontendEvent {
    timestamp: string;
    session_id: string;
    user_id: string;
    event_type: "page_view" | "agent_stream" | "hitl_action" | "error";
    payload: Record<string, any>;
}

class Telemetry {
    private buffer: FrontendEvent[] = [];
    private flushInterval = 5000; // 5 seconds
    
    log(event: Omit<FrontendEvent, "timestamp">) {
        this.buffer.push({ ...event, timestamp: new Date().toISOString() });
        if (this.buffer.length >= 10) this.flush();
    }
    
    private flush() {
        fetch("/api/omni/telemetry", {
            method: "POST",
            body: JSON.stringify(this.buffer),
            keepalive: true,
        });
        this.buffer = [];
    }
}

// Usage in AgentChatPanel
telemetry.log({
    event_type: "hitl_action",
    payload: { action: "approve", thread_id: workspace.threadId, agent: "outreach" }
});
```

### 8.2 Real-Time Log Viewer (Admin)

```typescript
// Future: rufus-dashboard/src/app/admin/logs/page.tsx
interface LogViewerProps {
    filters: {
        level: "debug" | "info" | "warning" | "error";
        agent?: string;
        thread_id?: string;
        user_id?: string;
        time_range: "1h" | "24h" | "7d";
    };
}

// Features:
// - Live tail with auto-refresh (2s)
// - Filter by thread_id to see full agent execution
// - Collapsible JSON payload inspection
// - Export to CSV/JSON
// - Correlation: click log → jump to LangSmith trace
```

---

## 9. Log Retention & Compliance

| Data Type | Storage | Retention | Encryption |
|-----------|---------|-----------|------------|
| Application logs | Loki (S3 backend) | 30 days | At rest |
| LLM traces | LangSmith cloud | 90 days | TLS in transit |
| Audit logs | Supabase Postgres | 1 year | At rest + TLS |
| Frontend telemetry | Supabase Postgres | 7 days | TLS in transit |
| Embedding cache | SQLite | Indefinite | File-system |
| Checkpoints | Supabase Postgres | 30 days | At rest |

---

## 10. Files & Implementation

| Component | Path | Status |
|-----------|------|--------|
| structlog config | `backend/core/logging.py` | 🔲 Pending |
| LangSmith tracer | `backend/core/langsmith.py` | 🔲 Pending |
| Prometheus metrics | `backend/middleware/metrics.py` | 🔲 Pending |
| Audit log table | `backend/migrations/003_audit_log.sql` | 🔲 Pending |
| Frontend telemetry | `rufus-dashboard/src/lib/telemetry.ts` | 🔲 Pending |
| Grafana dashboards | `monitoring/grafana/omni-dashboard.json` | 🔲 Pending |
| Alert rules | `monitoring/prometheus/alerts.yml` | 🔲 Pending |
| Promtail config | `monitoring/promtail/promtail.yml` | 🔲 Pending |
