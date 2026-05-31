# Omni-Dashboard MAS — Tech Stack Recommendation

**Version:** 1.0  
**Date:** 2026-05-30  
**Scope:** High-throughput, real-time Multi-Agent System for Optimus Rufus

---

## 1. Evaluation Framework

| Criterion | Weight | Definition |
|-----------|--------|------------|
| **Throughput** | 25% | Concurrent agent threads, SSE connections, and tool invocations per second |
| **Latency** | 25% | End-to-end time from user message to first UI paint of agent output |
| **Real-Time Fidelity** | 20% | Granularity of progress visibility (tool-start → tool-end streaming) |
| **Operational Complexity** | 15% | Deployment footprint, monitoring surface, team expertise required |
| **Ecosystem Fit** | 15% | Compatibility with existing Optimus Rufus codebase (FastAPI, Supabase, Next.js) |

---

## 2. Layer-by-Layer Recommendation

### 2.1 Frontend — Real-Time UI Layer

| Option | Real-Time Mechanism | Throughput Ceiling | Verdict |
|--------|---------------------|-------------------|---------|
| **Next.js 14 + React 18 + SSE** | Server-Sent Events via `EventSource` | ~1,000 concurrent SSE streams per Node.js instance | **✅ Recommended** |
| Next.js + WebSockets (`ws` or Socket.io) | Bidirectional WebSocket | ~10,000 concurrent sockets per Node.js instance | Consider for Phase 4+ |
| Next.js + Server Components +Polling | `useEffect` interval polling | ~100 req/s before DB saturation | ❌ Rejected (existing pattern) |
| React + tRPC + Streaming | tRPC `subscription` with HTTP/2 | Excellent, but adds RPC abstraction | ❌ Rejected (overkill for current team) |

**Recommendation:** **Next.js 14 (App Router) + React 18 + Server-Sent Events**

**Rationale:**
- The existing `rufus-dashboard` already uses Next.js 14 with App Router. Zero migration cost.
- SSE is unidirectional (server → client), which matches the Omni-Dashboard data flow perfectly: agents push progress events; users respond via discrete HTTP POSTs (`/chat`, `/resume`).
- SSE auto-reconnects natively (`EventSource` handles connection drops). WebSockets require manual heartbeat/reconnect logic.
- HTTP/1.1 and HTTP/2 both support SSE multiplexing without additional protocol overhead.
- **When to upgrade to WebSockets:** If we need bidirectional streaming (e.g., voice input, live collaborative editing of agent outputs) or >1,000 concurrent operator sessions.

**Capacity Estimate:**
```
1 operator session  = 1 SSE stream + periodic HTTP POSTs
100 operators       = 100 SSE streams  (negligible load)
1,000 operators     = 1,000 SSE streams (~50 MB RAM on Node.js)
10,000 operators    = WebSocket migration required
```

**Implementation Pattern:**
```typescript
// rufus-dashboard/src/components/omni/agent-chat.tsx (already implemented)
const eventSource = new EventSource(`/api/omni/chat?thread_id=${threadId}`);
eventSource.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.event === "tool_start") setActiveAgent(msg.data.agent);
  if (msg.event === "synthesis") appendMessage(msg.data.content);
  if (msg.event === "human_input_required") renderApprovalCard(msg.data.payload);
};
```

---

### 2.2 API Gateway — Request Routing & Orchestration

| Option | Concurrency Model | LangGraph Integration | Verdict |
|--------|-----------------|----------------------|---------|
| **FastAPI + Uvicorn (ASGI)** | `asyncio` event loop + thread pool | Native Python; direct LangGraph invocation | **✅ Recommended** |
| Node.js + Express/NestJS | Single-threaded event loop | Requires `child_process` or HTTP bridge to Python LangGraph | ❌ Rejected (polyglot complexity) |
| Go + Gin/Fiber | Goroutines | Requires Python service boundary | ❌ Rejected (polyglot complexity) |

**Recommendation:** **FastAPI + Uvicorn (ASGI) + Python 3.11+**

**Rationale:**
- FastAPI is already the backbone of the Optimus Rufus backend. All existing routers, middleware, and models are FastAPI-native.
- LangGraph is Python-native. Running it inside FastAPI eliminates cross-language serialization overhead.
- `Uvicorn` with `--workers N` (where `N` = CPU cores) handles concurrency via process pooling. Within each worker, `asyncio` manages thousands of concurrent SSE connections.
- CPU-bound tool calls (embeddings, HDBSCAN, scipy optimization) are offloaded to `asyncio.to_thread()`, preventing event-loop blocking.

**Performance Tuning:**
```bash
# Production Uvicorn configuration
uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http h11 \
  --ws none           # Disable WebSocket; we use SSE
```

**Capacity Estimate:**
```
1 Uvicorn worker      = ~500 concurrent SSE streams
4 workers (4 cores)   = ~2,000 concurrent SSE streams
+ Nginx load balancer = horizontal scaling to 10,000+
```

---

### 2.3 Real-Time Transport — Streaming Protocol

| Protocol | Direction | Latency | Browser Support | Complexity | Verdict |
|----------|-----------|---------|-----------------|------------|---------|
| **SSE (text/event-stream)** | Server → Client | <50ms | Universal | Low | **✅ Recommended (Phase 1-3)** |
| WebSockets | Bidirectional | <20ms | Universal | Medium | **Consider (Phase 4+)** |
| Long Polling | Client → Server (simulated push) | 100-500ms | Universal | Low | ❌ Rejected (inefficient) |
| gRPC + Web Transports | Bidirectional | <10ms | Chrome/Edge only | High | ❌ Rejected (limited browser support) |

**Recommendation:** **SSE for Phase 1-3; WebSockets for Phase 4+ if scale demands**

**Decision Matrix:**

| Scenario | Protocol |
|----------|----------|
| Agent progress streaming (tool_start → tool_end) | SSE |
| HITL approval prompt | SSE |
| Final synthesis delivery | SSE |
| Live collaborative editing (future) | WebSockets |
| Voice input streaming (future) | WebSockets |
| >1,000 concurrent operator sessions | WebSockets + Redis Pub/Sub |

**SSE Architecture in FastAPI:**
```python
# backend/routers/omni.py (already implemented)
from fastapi.responses import StreamingResponse

async def _stream_graph_events(thread_id: str, state: OmniState):
    async for event in graph.astream_events(state, config={"thread_id": thread_id}):
        yield f"data: {json.dumps(event)}\n\n"

return StreamingResponse(
    _stream_graph_events(thread_id, state),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
)
```

**WebSocket Migration Path (Phase 4+):**
```python
# Future enhancement: backend/routers/omni_ws.py
from fastapi import WebSocket

@app.websocket("/api/omni/ws/{thread_id}")
async def omni_websocket(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    redis = await aioredis.create_redis_pool("redis://localhost")
    channel = await redis.subscribe(f"omni:thread:{thread_id}")
    while True:
        msg = await channel.get()
        await websocket.send_json(msg)
```

---

### 2.4 Message Broker — Inter-Agent Communication

| Option | Persistence | Ordering | Throughput | Verdict |
|--------|-------------|----------|------------|---------|
| **None (direct function calls)** | N/A | Guaranteed | Unlimited (in-process) | **✅ Phase 1-2** |
| **Redis Streams** | Append-only log | Per-stream FIFO | 100K+ msg/s | **✅ Phase 3+** |
| Apache Kafka | Durable log partitions | Partition-scoped | 1M+ msg/s | ❌ Rejected (overkill) |
| RabbitMQ | Queue-based | Per-queue FIFO | 50K+ msg/s | ❌ Rejected (no need for AMQP semantics) |
| NATS JetStream | Stream-based | Stream-scoped | 3M+ msg/s | ❌ Rejected (new operational surface) |

**Recommendation:** **Direct function calls (Phase 1-2) → Redis Streams (Phase 3+)**

**Rationale:**
- **Phase 1-2:** All agents run inside the same FastAPI process. LangGraph subgraphs are invoked via direct `await subgraph.ainvoke()` calls. No broker needed.
- **Phase 3+:** When we need:
  - Cross-process agent execution (e.g., outreach agent on a separate worker)
  - Real-time telemetry ingestion from external sources (Apollo webhooks, email IMAP)
  - Event replay for debugging
  → Introduce **Redis Streams** as a lightweight, persistent message log.

**Redis Streams Topology:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Streams (Phase 3+)                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Stream: log:omni:{thread_id}                           │ │
│  │  ├─ Producer: LangGraph tool nodes                      │ │
│  │  ├─ Consumer: SSE stream generator                      │ │
│  │  └─ Retention: 24 hours / max 10,000 entries            │ │
│  │                                                         │ │
│  │  Stream: crm:changes                                    │ │
│  │  ├─ Producer: Supabase CDC webhook                      │ │
│  │  ├─ Consumer: AdminCopilotAgent                         │ │
│  │  └─ Retention: 7 days                                   │ │
│  │                                                         │ │
│  │  Stream: email:inbound                                  │ │
│  │  ├─ Producer: Apollo webhook / IMAP poller              │ │
│  │  ├─ Consumer: EmailAgent                                │ │
│  │  └─ Retention: 48 hours                                 │ │
│  │                                                         │ │
│  │  Pub/Sub: omni:broadcast:{thread_id}                    │ │
│  │  ├─ Publisher: SupervisorGraph synthesis node           │ │
│  │  └─ Subscriber: All connected SSE clients               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Redis Configuration:**
```bash
# redis.conf for Omni-Dashboard
maxmemory 256mb
maxmemory-policy allkeys-lru
stream-node-max-entries 10000
stream-node-max-bytes 4096
appendonly yes
appendfsync everysec
```

---

### 2.5 Database — Persistence & Checkpoints

| Option | ACID | Checkpoints | Real-Time | Verdict |
|--------|------|-------------|-----------|---------|
| **Supabase Postgres** | Full ACID | Via `PostgresSaver` | Row-level CDC | **✅ Recommended** |
| SQLite (`embedding_cache.db`) | ACID (file) | Not suitable | None | **✅ Embedding cache only** |
| ClickHouse | Eventual | Custom implementation | Columnar aggregation | Consider for analytics |
| MongoDB | Document ACID | Custom implementation | Change streams | ❌ Rejected (no existing usage) |
| Redis (standalone) | None | `MemorySaver` only | Pub/Sub | ❌ Rejected (not durable) |

**Recommendation:** **Supabase Postgres for all persistent state; SQLite for embedding cache**

**Schema Additions for LangGraph:**
```sql
-- Supabase migration: enable LangGraph checkpointing
CREATE TABLE IF NOT EXISTS langgraph_checkpoint (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS langgraph_checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Index for fast thread lookups
CREATE INDEX idx_langgraph_thread ON langgraph_checkpoint(thread_id, checkpoint_id DESC);
```

**Why Not ClickHouse (yet):**
- ClickHouse excels at high-volume append-only analytics (billions of rows).
- Current agent throughput: ~100-1,000 runs/day. Postgres handles this effortlessly.
- **Future:** If landing analytics exceeds 10M events/month, mirror `landing_analytics` to ClickHouse for OLAP queries while keeping transactional data in Postgres.

---

### 2.6 Caching Layer

| Option | Use Case | Latency | Verdict |
|--------|----------|---------|---------|
| **In-Memory DataStore** | Hot operational state (listings, competitors, jobs) | <1ms | **✅ Existing** |
| **SQLite (`embedding_cache.db`)** | Precomputed embeddings | <5ms | **✅ Existing** |
| **Redis (Phase 3+)** | Session state, SSE backpressure buffer, rate limit counters | <1ms | **✅ Phase 3+** |
| CDN (Vercel Edge) | Static assets, public landing pages | <50ms global | **✅ Existing** |

**Caching Strategy:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Hierarchy                           │
│                                                              │
│  L1: DataStore (in-memory dicts)                             │
│      • listings, competitors, clients, jobs                  │
│      • 5-second debounced JSON persistence                   │
│      • Thread-safe with threading.Lock()                     │
│                                                              │
│  L2: SQLite embedding_cache.db                               │
│      • Precomputed 768-d and 3072-d embeddings               │
│      • Avoids repeated Gemini API calls                      │
│                                                              │
│  L3: Redis (Phase 3+)                                        │
│      • Session tokens (5-min TTL)                            │
│      • Rate limit counters (sliding window)                  │
│      • SSE event backpressure buffer (per-thread)            │
│      • Apollo API response cache (1-hour TTL)                │
│                                                              │
│  L4: CDN (Vercel Edge)                                       │
│      • /optimize landing page                                │
│      • Prospect pitch demos                                  │
│      • Calculator static assets                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.7 Background Task Queue

| Option | Integration | Monitoring | Verdict |
|--------|-------------|------------|---------|
| **APScheduler (existing)** | In-process cron | Custom logs | **✅ Keep for legacy pipeline** |
| **Celery + Redis** | Distributed workers | Flower dashboard | **✅ Phase 3+ for MAS** |
| RQ (Redis Queue) | Lightweight | Built-in web UI | Consider (simpler than Celery) |
| Temporal | Durable workflows | Web UI + tracing | ❌ Rejected (overkill) |

**Recommendation:** **APScheduler for legacy acquisition pipeline; Celery + Redis for MAS background tasks**

**Celery Task Mapping:**
```python
# Future: backend/agent/tasks.py
from celery import Celery

app = Celery("omni", broker="redis://localhost:6379/0")

@app.task
def run_outreach_subgraph(thread_id: str, asin: str):
    """Execute outreach subgraph on a dedicated worker."""
    graph = build_outreach_subgraph()
    state = OmniState(workspace=WorkspaceSnapshot(asin=asin))
    graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

@app.task
def compute_embeddings_batch(asins: list[str]):
    """Batch embedding computation on a CPU-optimized worker."""
    mapper = CosmoMapper(engine)
    for asin in asins:
        mapper.compute_embedding(asin)
```

**Worker Topology:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Celery Worker Pool                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  default_queue  │  │  cpu_queue      │  │ api_queue   │ │
│  │  (API tasks)    │  │  (embeddings,   │  │ (Apollo,    │ │
│  │                 │  │   HDBSCAN)      │  │  Gemini)    │ │
│  │  Workers: 4     │  │  Workers: 2     │  │ Workers: 4  │ │
│  │  Concurrency:   │  │  Concurrency: 1 │  │ Concurrency:│ │
│  │  gevent         │  │  (prefork)      │  │ gevent      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.8 Monitoring & Observability

| Layer | Tool | Data | Verdict |
|-------|------|------|---------|
| **LLM Tracing** | LangSmith | All graph invocations, tool calls, token usage | **✅ Phase 2+** |
| **Metrics** | Prometheus + Grafana | `/api/omni/chat` latency, SSE connections, error rate | **✅ Phase 3+** |
| **Logging** | `structlog` + Rich | Structured JSON logs in prod; colored console in dev | **✅ Phase 1** |
| **APM** | Sentry | Exception tracking, performance profiles | **✅ Existing** |
| **Uptime** | UptimeRobot / Pingdom | Health check `/` endpoint | **✅ Existing** |

**LangSmith Configuration:**
```python
# backend/agent/graph/supervisor.py (future enhancement)
from langsmith import Client

ls_client = Client(project_name="optimus-rufus-omni")

# All graph invocations auto-traced with:
# - Thread ID
# - Agent name
# - Tool latency
# - Token consumption
# - Error stack traces
```

---

## 3. Recommended Stack Summary

### Phase 1-2 (Current Partial Implementation)

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Next.js 14 + React 18 | Dashboard UI, SSE consumption |
| **Real-Time Transport** | SSE (`text/event-stream`) | Agent progress streaming |
| **API Gateway** | FastAPI + Uvicorn | HTTP routing, graph invocation |
| **Agent Runtime** | LangGraph + LangChain | Supervisor + subgraph orchestration |
| **Database** | Supabase Postgres | Persistent state, checkpoints |
| **Cache L1** | In-Memory DataStore | Hot operational state |
| **Cache L2** | SQLite | Embedding cache |
| **Task Queue** | APScheduler (existing) | Legacy pipeline |
| **Observability** | `structlog` + Rich console | Logging |

### Phase 3-4 (Production Hardening)

| Layer | Technology Addition | Role |
|-------|-------------------|------|
| **Message Broker** | Redis 7+ Streams | Inter-agent events, telemetry ingestion |
| **Cache L3** | Redis | Session state, rate limits, API response cache |
| **Task Queue** | Celery + Redis | Distributed MAS background workers |
| **Checkpoints** | `PostgresSaver` (Supabase) | Durable thread recovery |
| **Observability** | LangSmith + Prometheus | LLM tracing + metrics |
| **Load Balancing** | Nginx | Reverse proxy, SSE connection distribution |

### Phase 5+ (Scale)

| Layer | Technology Addition | Trigger |
|-------|-------------------|---------|
| **Real-Time Transport** | WebSockets | >1,000 concurrent operators |
| **Analytics DB** | ClickHouse | >10M landing analytics events/month |
| **CDN** | Vercel Edge Network | Global calculator + landing page latency |
| **Vector DB** | pgvector (Supabase) | Semantic search over >100K listings |

---

## 4. Performance Projections

### 4.1 Throughput Benchmarks (Target)

| Metric | Phase 1 | Phase 3 | Phase 5 |
|--------|---------|---------|---------|
| Concurrent SSE streams | 100 | 2,000 | 10,000 (WebSockets) |
| Agent invocations / minute | 10 | 100 | 1,000 (Celery workers) |
| Embedding computations / minute | 5 | 50 | 500 (Redis-cached) |
| LLM tokens / minute | 5K | 50K | 500K (rate-limited) |
| End-to-end latency (simple intent) | <3s | <2s | <1s |
| End-to-end latency (full workflow) | <30s | <20s | <10s |

### 4.2 Resource Estimates

| Component | Phase 1 | Phase 3 | Phase 5 |
|-----------|---------|---------|---------|
| FastAPI (Uvicorn workers) | 1 CPU, 2GB RAM | 4 CPU, 8GB RAM | 8 CPU, 16GB RAM |
| Redis | Not needed | 1 CPU, 1GB RAM | 2 CPU, 4GB RAM |
| Postgres (Supabase) | Free tier | Pro tier (8GB) | Team tier (64GB) |
| Celery workers | Not needed | 2 CPU, 4GB RAM | 8 CPU, 16GB RAM |
| Next.js (Vercel) | Hobby | Pro | Enterprise |

---

## 5. Risk Mitigation by Stack Choice

| Risk | Mitigation |
|------|------------|
| SSE connection limit reached | Nginx config `limit_conn_zone` + WebSocket migration path documented |
| Redis single point of failure | Redis Sentinel (3-node) or AWS ElastiCache replication |
| Postgres checkpoint bloat | 30-day TTL on `langgraph_checkpoint`; nightly `VACUUM` |
| Celery worker memory leak | `--max-tasks-per-child=1000` + Sentry memory profiling |
| LLM rate limiting | Token bucket in Redis; graceful degradation to offline mode |
| FastAPI event-loop blocking | All CPU tools wrapped in `asyncio.to_thread()` + latency alerts |

---

## 6. Files & Integration Points

| Artifact | Path | Status |
|----------|------|--------|
| SSE Streaming Router | `backend/routers/omni.py` | ✅ Implemented |
| Frontend SSE Consumer | `rufus-dashboard/src/components/omni/agent-chat.tsx` | ✅ Implemented |
| State Schema | `backend/agent/graph/state.py` | ✅ Implemented |
| LangGraph Supervisor | `backend/agent/graph/supervisor.py` | ✅ Implemented |
| Redis Integration (future) | `backend/core/redis.py` | 🔲 Pending |
| Celery Tasks (future) | `backend/agent/tasks.py` | 🔲 Pending |
| Prometheus Metrics (future) | `backend/middleware/metrics.py` | 🔲 Pending |
| Supabase Migration | `backend/migrations/002_langgraph_checkpoint.sql` | 🔲 Pending |
