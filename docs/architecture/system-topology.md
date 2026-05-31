# Omni-Dashboard MAS — System Topology

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. High-Level Data Flow Topology

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    EXTERNAL DATA SOURCES                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  Backend Logs   │  │   CRM / DB      │  │  Email Servers  │  │   External APIs         │ │
│  │  (FastAPI,      │  │  (Supabase      │  │  (IMAP/SMTP,    │  │   (Gemini, OpenRouter,  │ │
│  │   Agent Runs)   │  │   Postgres)     │  │   Apollo,       │  │    Apify, Reddit)       │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └───────────┬─────────────┘ │
└───────────┼────────────────────┼────────────────────┼───────────────────────┼───────────────┘
            │                    │                    │                       │
            │ HTTP / Webhook     │ PostgREST /        │ Webhook /             │ HTTP / gRPC
            │                    │ Realtime           │ Polling / SSE         │
            ▼                    ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION & MESSAGE BROKER LAYER                                │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                           Redis Streams / Pub-Sub (Future)                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │  │
│  │  │  log:omni:*  │  │ crm:changes  │  │email:inbound │  │  api:responses           │  │  │
│  │  │  (structured │  │ (prospect    │  │ (classified  │  │  (embeddings,            │  │  │
│  │  │   JSON logs) │  │  stage, email│  │  replies)    │  │   competitor             │  │  │
│  │  │              │  │  sequences)  │  │              │  │   intel)                 │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│                                              │                                               │
│  ┌───────────────────────────────────────────┼───────────────────────────────────────────┐  │
│  │           CENTRALIZED DATABASE             │                                           │  │
│  │  ┌────────────────────────────────────────┼─────────────────────────────────────────┐ │  │
│  │  │         Supabase Postgres              │                                         │ │  │
│  │  │  ┌─────────────────┐  ┌──────────────┼──┐  ┌─────────────────┐  ┌───────────┐  │ │  │
│  │  │  │ agent_runs      │  │ brands       │  │  │ chat_sessions   │  │ meetings  │  │ │  │
│  │  │  │ (execution      │  │ (prospect    │  │  │ (conversation   │  │ (calendly │  │ │  │
│  │  │  │  telemetry)     │  │  pipeline)   │  │  │  history)       │  │  webhooks)│  │ │  │
│  │  │  └─────────────────┘  └──────────────┼──┘  └─────────────────┘  └───────────┘  │ │  │
│  │  │  ┌─────────────────┐  ┌──────────────┼──┐  ┌─────────────────┐  ┌───────────┐  │ │  │
│  │  │  │ landing_analytics│  │pipeline_     │  │  │ brand_step_     │  │ langgraph │  │ │  │
│  │  │  │ (apollo events) │  │ snapshots    │  │  │ emails          │  │ checkpoints│ │  │
│  │  │  └─────────────────┘  └──────────────┼──┘  └─────────────────┘  └───────────┘  │ │  │
│  │  └────────────────────────────────────────┼─────────────────────────────────────────┘  │
│  └───────────────────────────────────────────┼───────────────────────────────────────────┘  │
└──────────────────────────────────────────────┼───────────────────────────────────────────────┘
                                               │
                                               │ reads / writes / checkpoints
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              LANGGRAPH MULTI-AGENT RUNTIME                                   │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         SupervisorGraph (OrchestratorAgent)                            │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  plan_node ──▶ delegate_node ──▶ synthesize_node                                │  │  │
│  │  │       │                │                                                            │  │  │
│  │  │       ▼                ▼                                                            │  │  │
│  │  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │  │  │
│  │  │  │Listing │  │Compet- │  │Attrib- │  │Outreach│  │ Email  │  │ Admin  │        │  │  │
│  │  │  │Graph   │  │itor    │  │ution   │  │Graph   │  │Graph   │  │Graph   │        │  │  │
│  │  │  │        │  │Graph   │  │Graph   │  │        │  │        │  │        │        │  │  │
│  │  │  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘        │  │  │
│  │  └───────┼───────────┼───────────┼───────────┼───────────┼───────────┼────────────┘  │  │
│  │          │           │           │           │           │           │               │  │
│  │          └───────────┴───────────┴───────────┴───────────┴───────────┘               │  │
│  │                                      │                                               │  │
│  │                                      ▼                                               │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │                         TOOL LAYER                                           │    │  │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│    │  │
│  │  │  │cosmo_analysis│ │competitor_  │ │ attribution │ │ pipeline_trigger        ││    │  │
│  │  │  │   _tool     │ │ _intel_tool │ │   _tool     │ │    _tool                ││    │  │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────┘│    │  │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│    │  │
│  │  │  │store_read   │ │ apollo_     │ │ email_      │ │ agentic_optimize        ││    │  │
│  │  │  │   _tool     │ │ enrich_tool │ │ draft_tool  │ │    _tool                ││    │  │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────┘│    │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               │ SSE / HTTP / WebSocket
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT LAYER                                              │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              Next.js — /omni Dashboard                                 │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  ┌──────────────┐  ┌─────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │   Sidebar    │  │                    Canvas                              │  │  │  │
│  │  │  │  (workspace  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │  │  │
│  │  │  │   selector)  │  │  │ Agent    │ │ COSMO    │ │ Compet-  │ │ Revenue  │   │  │  │  │
│  │  │  │              │  │  │ Status   │ │ Readiness│ │ itor Gap │ │ Project- │   │  │  │  │
│  │  │  │              │  │  │ Grid     │ │ Card     │ │ Chart    │ │ ion Card │   │  │  │  │
│  │  │  │              │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │  │  │
│  │  │  │              │  │  ┌──────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │              │  │  │        Contextual Agent Output View              │  │  │  │  │
│  │  │  │              │  │  │   (reports, charts, HITL approval cards)         │  │  │  │  │
│  │  │  │              │  │  └──────────────────────────────────────────────────┘  │  │  │  │
│  │  │  └──────────────┘  └─────────────────────────────────────────────────────────┘  │  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │                    Agent Chat Panel (SSE)                                │  │  │  │
│  │  │  │  • Streaming thought events                                             │  │  │  │
│  │  │  │  • Tool execution cards                                                 │  │  │  │
│  │  │  │  • Human-in-the-Loop approval/rejection                                 │  │  │  │
│  │  │  └─────────────────────────────────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Structural Breakdown by Layer

### 2.1 External Data Sources

| Source | Data Type | Ingestion Method | Destination |
|--------|-----------|------------------|-------------|
| **FastAPI Backend Logs** | Structured execution logs, embedding latencies, tool call metadata | Filebeat / Python `structlog` → Redis Streams (future) | `agent_runs` table, `langgraph_checkpoint` |
| **Supabase Postgres (CRM)** | Prospects, brands, pipeline stages, contact info, meeting bookings | Direct SQL / PostgREST / Realtime subscriptions | Primary operational database |
| **Email Servers** | Inbound replies, sequence opens/clicks, delivery events | Apollo webhooks → `/api/webhooks/apollo`; IMAP polling → `/api/email-engine/classify` | `brand_step_emails`, `landing_analytics` |
| **Gemini API** | Text embeddings (768-dim COSMO, 3072-dim competitor) | HTTP POST via `google-genai` | `embedding_cache.db` (SQLite) |
| **OpenRouter** | LLM completions (Rufus scoring, email drafting, copy optimization) | HTTP POST via `openai` compatible client | Ephemeral; streamed to UI |
| **Apollo API** | Contact enrichment, sequence enrollment, email tracking | REST API via `httpx` | Supabase `brands`, `brand_step_emails` |
| **Apify** | Amazon listing scrapes, competitor detail pages | Actor runs via `apify-client` | Supabase `prospects` |

### 2.2 Message Broker Layer

**Current State (Phase 1-2):** No dedicated message broker. The system uses:
- **Direct HTTP** for synchronous tool calls
- **Supabase Postgres** as the implicit event log (tables updated by agents)
- **In-Memory `DataStore`** (`store.py`) for fast, ephemeral operational state

**Future State (Phase 4+):** Redis Streams introduced for:
- `log:omni:{thread_id}` — Real-time agent execution telemetry
- `crm:changes` — CDC stream from Supabase for prospect stage changes
- `email:inbound` — Classified reply events queued for EmailAgent
- `api:responses` — Rate-limited, cached external API responses

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Streams (Future)                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Stream: log:omni:*                                     │ │
│  │  ├─ { thread_id, agent, tool, latency_ms, status }     │ │
│  │  └─ Consumer Group: omni-telemetry-workers             │ │
│  │                                                         │ │
│  │  Stream: crm:changes                                    │ │
│  │  ├─ { table, record_id, operation, old, new }          │ │
│  │  └─ Consumer Group: omni-sync-workers                  │ │
│  │                                                         │ │
│  │  Stream: email:inbound                                  │ │
│  │  ├─ { brand_key, classification, raw_body, confidence }│ │
│  │  └─ Consumer Group: email-agent-workers                │ │
│  │                                                         │ │
│  │  Stream: api:responses                                  │ │
│  │  ├─ { provider, endpoint, cache_key, response_hash }   │ │
│  │  └─ Consumer Group: api-cache-workers                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Centralized Database (Supabase Postgres)

**Schema Groups:**

| Group | Tables | Purpose |
|-------|--------|---------|
| **Agent Runtime** | `langgraph_checkpoint`, `langgraph_checkpoint_writes` | LangGraph thread persistence |
| **Pipeline** | `brands`, `prospects`, `brand_step_emails`, `pipeline_snapshots` | Acquisition funnel state |
| **Analytics** | `landing_analytics`, `agent_runs`, `meetings` | Event aggregation, execution telemetry |
| **Conversational** | `chat_sessions` | RAG chat history + Omni-Dashboard threads |

**Access Patterns:**
- FastAPI backend → Direct SQL via `supabase-py`
- LangGraph checkpoints → `PostgresSaver` (SQLAlchemy async)
- Frontend → `fetch` to FastAPI (never direct Supabase from browser for agent data)

### 2.4 LangGraph Multi-Agent Runtime

**Supervisor Graph State Machine:**

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  plan_node  │◄─────────────────┐
                    │ (classify   │                  │
                    │  intent)    │                  │
                    └──────┬──────┘                  │
                           │                        │
              ┌────────────┼────────────┐           │
              │            │            │           │
              ▼            ▼            ▼           │
       ┌──────────┐ ┌──────────┐ ┌──────────┐      │
       │ Direct   │ │ Single   │ │ Multi    │      │
       │ Answer   │ │ Subgraph │ │ Subgraph │      │
       └────┬─────┘ └────┬─────┘ └────┬─────┘      │
            │            │            │             │
            │            └─────┬──────┘             │
            │                  │                    │
            │                  ▼                    │
            │           ┌─────────────┐             │
            │           │delegate_node│             │
            │           │(parallel   │─────────────┘
            │           │ execution) │  (loop if more steps)
            │           └──────┬──────┘
            │                  │
            │                  ▼
            │           ┌─────────────┐
            │           │synthesize_  │
            │           │   node      │
            │           └──────┬──────┘
            │                  │
            └──────────────────┼──────────────────┐
                               │                  │
                               ▼                  ▼
                        ┌─────────────┐   ┌─────────────┐
                        │  HITL Gate? │   │    END      │
                        │ (interrupt) │   │             │
                        └──────┬──────┘   └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  WAIT_FOR   │
                        │  HUMAN      │
                        │  INPUT      │
                        └─────────────┘
```

**Subgraph Execution Model:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Subgraph Invocation                           │
│                                                                  │
│  Supervisor ──▶ fork_state() ──▶ subgraph.ainvoke(forked_state) │
│       ▲                              │                           │
│       │                              ▼                           │
│       │                    ┌─────────────────┐                   │
│       │                    │  Tool Node      │                   │
│       │                    │  (async def)    │                   │
│       │                    └────────┬────────┘                   │
│       │                             │                            │
│       │                    ┌────────┴────────┐                   │
│       │                    │                 │                   │
│       │                    ▼                 ▼                   │
│       │           ┌─────────────┐   ┌─────────────┐              │
│       │           │ CPU-Bound   │   │ I/O-Bound   │              │
│       │           │ (to_thread) │   │ (await)     │              │
│       │           │             │   │             │              │
│       │           │ • HDBSCAN   │   │ • HTTP API  │              │
│       │           │ • PCA       │   │ • DB Query  │              │
│       │           │ • scipy.opt │   │ • Embedding │              │
│       │           └─────────────┘   └─────────────┘              │
│       │                             │                            │
│       │                             ▼                            │
│       │                    ┌─────────────────┐                   │
│       │                    │  Result JSON    │                   │
│       │                    │  (serializable) │                   │
│       │                    └─────────────────┘                   │
│       │                             │                            │
│       └─────────────────────────────┘                            │
│                     merge_into_supervisor_state()                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.5 UI Layer

**Layout Topology:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              /omni Layout                                    │
│  ┌────────────────┬──────────────────────────────────┬────────────────────┐ │
│  │                │                                  │                    │ │
│  │   Sidebar      │          Main Canvas             │   Agent Chat       │ │
│  │   (256px)      │          (flex-1)                │   Panel (380px)    │ │
│  │                │                                  │                    │ │
│  │  • Overview    │  ┌────────────────────────────┐  │  ┌──────────────┐  │ │
│  │  • Omni        │  │  Workspace Bar             │  │  │ Status       │  │ │
│  │  • Listing     │  │  ASIN: [________] [Set]    │  │  │ Indicator    │  │ │
│  │  • Competitor  │  └────────────────────────────┘  │  └──────────────┘  │ │
│  │  • Pipeline    │                                  │                    │ │
│  │  • Marketing   │  ┌────────────────────────────┐  │  ┌──────────────┐  │ │
│  │  • Prospects   │  │  Agent Status Grid         │  │  │ Message      │  │ │
│  │  • Clients     │  │  ┌────┐┌────┐┌────┐┌────┐  │  │  │ Stream       │  │ │
│  │                │  │  │ L  ││ C  ││ A  ││ O  │  │  │  │ (scrollable) │  │ │
│  │                │  │  │ i  ││ o  ││ t  ││ u  │  │  │  └──────────────┘  │ │
│  │                │  │  │ s  ││ m  ││ t  ││ t  │  │  │                    │ │
│  │                │  │  │ t  ││ p  ││ r  ││ r  │  │  │  ┌──────────────┐  │ │
│  │                │  │  │ i  ││ e  ││ i  ││ e  │  │  │  │ Input + Send │  │ │
│  │                │  │  │ n  ││ t  ││ b  ││ a  │  │  │  └──────────────┘  │ │
│  │                │  │  │ g  ││ i  ││ u  ││ c  │  │  │                    │ │
│  │                │  │  │    ││ t  ││ t  ││ h  │  │  │                    │ │
│  │                │  │  │    ││ o  ││ i  ││    │  │  │                    │ │
│  │                │  │  │    ││ r  ││ o  ││    │  │  │                    │ │
│  │                │  │  └────┘└────┘└────┘└────┘  │  │                    │ │
│  │                │  └────────────────────────────┘  │                    │ │
│  │                │                                  │                    │ │
│  │                │  ┌────────────────────────────┐  │                    │ │
│  │                │  │  Contextual Metrics        │  │                    │ │
│  │                │  │  • COSMO Score             │  │                    │ │
│  │                │  │  • Competitor Similarity   │  │                    │ │
│  │                │  │  • Gap Alerts              │  │                    │ │
│  │                │  │  • Projected Revenue       │  │                    │ │
│  │                │  └────────────────────────────┘  │                    │ │
│  │                │                                  │                    │ │
│  │                │  ┌────────────────────────────┐  │                    │ │
│  │                │  │  Quick Intents             │  │                    │ │
│  │                │  │  [Analyze] [Competitors]   │  │                    │ │
│  │                │  │  [Revenue] [Outreach] ...  │  │                    │ │
│  │                │  └────────────────────────────┘  │                    │ │
│  │                │                                  │                    │ │
│  └────────────────┴──────────────────────────────────┴────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Flow in UI:**
1. User sets ASIN in Workspace Bar → writes to `OmniWorkspaceContext`
2. User sends message in Chat Panel → POST `/api/omni/chat` with SSE
3. SSE events update `OmniWorkspaceContext.activeAgents` and render streaming indicators
4. `agent_complete` events trigger Canvas re-renders (metric cards, status badges)
5. `human_input_required` events render approval cards in Chat Panel
6. User clicks Approve/Reject → POST `/api/omni/resume`

---

## 3. Data Flow by Scenario

### 3.1 Scenario: Full Listing Optimization + Outreach

```
User types: "Optimize B08X and draft outreach"

  UI ──▶ POST /api/omni/chat
         { message: "...", workspace: { asin: "B08X" } }

  FastAPI ──▶ SupervisorGraph.ainvoke(OmniState)

  plan_node ──▶ PlanStep[]:
    [0] listing:  "Run COSMO analysis"          (deps: [])
    [1] competitor: "Generate landscape"         (deps: [])
    [2] attribution: "Project revenue"           (deps: [0])
    [3] outreach: "Draft sequence"               (deps: [0, 1, 2])

  delegate_node ──▶ asyncio.gather(
    ListingGraph.ainvoke(forked_state_0),
    CompetitorGraph.ainvoke(forked_state_1)
  )

  ListingGraph:
    cosmo_analysis_tool ──▶ DataStore (read listing)
                        ──▶ CosmoMapper (embed + score)
                        ──▶ returns { overall_score: 62, keyword_safety: ... }

  CompetitorGraph:
    competitor_intel_tool ──▶ DataStore (read competitors)
                          ──▶ CompetitorAnalyzer (embed + HDBSCAN)
                          ──▶ returns { profiles: [...], gaps: [...] }

  delegate_node ──▶ AttributionGraph.ainvoke(forked_state_2)
    attribution_tool ──▶ DataStore (traffic_history)
                     ──▶ CausalAttributionModel (DiD + SCM)
                     ──▶ returns { did: {...}, financial: {...} }

  delegate_node ──▶ OutreachGraph.ainvoke(forked_state_3)
    pipeline_trigger_tool(enrich) ──▶ Apollo API
    pipeline_trigger_tool(draft) ──▶ OpenRouter LLM
    human_gate ──▶ sets OmniState.pending_human_input
                 ──▶ SSE event: human_input_required
                 ──▶ UI renders approval card

  User clicks "Approve"
    UI ──▶ POST /api/omni/resume
    FastAPI ──▶ clears pending_human_input
            ──▶ pipeline_trigger_tool(sequence) ──▶ Apollo API
            ──▶ returns { sequence_status: "SEQUENCED" }

  synthesize_node ──▶ merges all agent_outputs
                  ──▶ SSE event: synthesis
                  ──▶ UI renders final report in Canvas
```

### 3.2 Scenario: Inbound Email Reply

```
Apollo webhook ──▶ POST /api/webhooks/apollo
                 ──▶ Email classification stored in landing_analytics

  (Polling or Redis Stream trigger)
  EmailAgent ──▶ classify_node: "OBJECTION"
             ──▶ strategy_node: selects "reframe_value" playbook
             ──▶ draft_reply_tool ──▶ OpenRouter LLM
             ──▶ compliance_node: banned phrase scan
             ──▶ returns draft to operator inbox

  Operator reviews in /admin/emails ──▶ approves ──▶ send_reply
```

---

## 4. Integration Points

| System | Direction | Protocol | Data |
|--------|-----------|----------|------|
| **Supabase Postgres** | Bidirectional | `supabase-py` (async) | Checkpoints, prospects, emails, analytics |
| **Redis** | Inbound (future) | `redis-py` (async) | Stream consumers for real-time events |
| **Apollo** | Outbound | REST (`httpx`) | Contact enrichment, sequence enrollment |
| **Gemini** | Outbound | HTTP (`google-genai`) | Embeddings (768-d, 3072-d) |
| **OpenRouter** | Outbound | HTTP (`openai`) | LLM completions (scoring, drafting, optimization) |
| **Apify** | Outbound | REST (`apify-client`) | Amazon scraping actors |
| **Calendly** | Inbound | Webhook (`HMAC`) | Meeting bookings |
| **Next.js Frontend** | Bidirectional | SSE + HTTP JSON | Streaming events, thread management |

---

## 5. Operational Data Flow

### 5.1 Read Path (User loads /omni)

```
Browser ──▶ GET /api/overview
        ──▶ FastAPI ──▶ DataStore.listings + DataStore.clients
                  ──▶ returns KPIs (COSMO score, active listings, gap alerts)

Browser ──▶ GET /api/omni/agents
        ──▶ FastAPI ──▶ returns agent health/status

Browser ──▶ (renders Canvas with metrics + status grid)
```

### 5.2 Write Path (User triggers agent workflow)

```
Browser ──▶ POST /api/omni/chat (SSE)
        ──▶ FastAPI ──▶ LangGraph runtime
                  ──▶ Tool calls write to:
                      • DataStore (listings, competitors, jobs)
                      • Supabase (agent_runs, chat_sessions)
                      • SQLite (embedding_cache.db)
                  ──▶ SSE events stream back to browser
```

### 5.3 Background Path (Scheduled pipeline)

```
APScheduler ──▶ AgentOrchestrator (existing)
            ──▶ JobRegistry ──▶ subprocess (acquisition-tool/main.py)
                            ──▶ Supabase (update prospect stages)
                            ──▶ Supabase (insert pipeline_snapshots)

(LangGraph MAS reads from same Supabase tables, does not conflict)
```
