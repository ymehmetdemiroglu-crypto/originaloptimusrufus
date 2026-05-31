# ADR-001: Omni-Dashboard Multi-Agent System (MAS)

**Status:** Accepted  
**Date:** 2026-05-30  
**Author:** Principal AI Systems Architect  
**Scope:** `backend/`, `rufus-dashboard/`, `acquisition-tool/`

---

## 1. Context

Optimus Rufus currently operates three semi-autonomous subsystems:

1. **Backend FastAPI** — COSMO semantic analysis, competitor intelligence, causal attribution, email engine, and an APScheduler-based acquisition pipeline.
2. **Acquisition Tool** — A CLI-driven outbound prospecting pipeline (scrape → enrich → score → draft → sequence) plus a dual-agent listing optimizer (COSMO Catalyst + SEO Guardian).
3. **Next.js Dashboard** — A feature-rich admin UI with discrete pages for listing analysis, competitor intel, marketing assistant, pipeline control, and prospect management.

**Problem:** These subsystems are siloed. A user must manually navigate between pages, re-enter ASINs/brand keys, and mentally correlate insights from COSMO analysis with competitor gaps, attribution lift, and outreach sequences. The existing "agent" infrastructure is a collection of scripts and idempotent cron jobs, not a cohesive, goal-directed system.

**Goal:** Architect an **Omni-Dashboard** — a unified, action-oriented interface where a LangGraph Multi-Agent System (MAS) accepts high-level user intents ("Optimize ASIN B08X for Q3 and draft the outreach sequence") and autonomously coordinates specialized agents to deliver end-to-end outcomes.

---

## 2. Decision

We will implement the Omni-Dashboard MAS using **LangGraph** with a **Supervisor-Subgraph** pattern, integrated directly into the existing FastAPI backend and Next.js dashboard.

### 2.1 Framework Choice: LangGraph

| Criterion | LangGraph | CrewAI | AutoGen |
|-----------|-----------|--------|---------|
| Stateful cycles | ✅ Native | ❌ DAG-only | ⚠️ Conversational |
| Fine-grained control | ✅ Full graph API | ⚠️ Higher-level | ⚠️ Conversational |
| FastAPI integration | ✅ Python-native | ✅ Python-native | ✅ Python-native |
| Checkpoint persistence | ✅ Postgres/SQLite/Redis | ❌ External only | ❌ External only |
| Streaming tokens | ✅ `astream_events` | ❌ Limited | ⚠️ Partial |
| Human-in-the-loop | ✅ `interrupt` / `Command(resume=...)` | ⚠️ Manual | ⚠️ Manual |

LangGraph was selected because:
1. **Cyclic reasoning is essential** — The existing COSMO Catalyst ↔ SEO Guardian loop requires stateful cycles, not DAGs.
2. **Structured state** — Pydantic state schemas integrate seamlessly with our existing Pydantic v2 models.
3. **Persistence** — We can back checkpoints directly to Supabase (Postgres) using the same connection pool.
4. **Streaming** — The Next.js dashboard can consume `astream_events` via Server-Sent Events for real-time agent thought streams.

### 2.2 Architectural Pattern: Supervisor-Subgraph

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR GRAPH                            │
│  (OrchestratorAgent — intent parsing, delegation, synthesis)        │
└──────────────┬──────────────────────────────────────────────────────┘
               │ delegates via conditional edges
    ┌──────────┼──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ ┌────────┐
│Listing│ │Compet-│ │Attribut-│ │Outreach │ │ Email  │ │ Admin  │
│ Graph │ │itor   │ │ion Graph│ │ Graph   │ │ Graph  │ │ Graph  │
│       │ │Graph  │ │         │ │         │ │        │ │        │
└───────┘ └───────┘ └─────────┘ └─────────┘ └────────┘ └────────┘
```

Each subgraph is a reusable, independently testable LangGraph `StateGraph` that wraps existing backend capabilities as **tools**.

### 2.3 State Management: Shared Workspace + Thread Checkpoints

- **Global Workspace** (`OmniWorkspace`): A lightweight Zustand/React Context in the frontend holding the active `client_id`, `asin`, and `brand_key`. Eliminates the current pain of re-entering identifiers on every page.
- **Thread State** (`OmniState`): A Pydantic model persisted via LangGraph's checkpoint saver to Supabase. Contains:
  - `messages`: Conversation history (Human/AI/tool)
  - `workspace`: Active ASIN/brand/client snapshot
  - `agent_outputs`: Accumulated results from subgraphs
  - `pending_human_input`: Interrupt payloads for HITL gates
  - `plan`: The supervisor's current execution plan

### 2.4 Integration Strategy

**Backend:**
- New router: `/api/omni/*` — streaming chat, workspace sync, thread management.
- Refactor `backend/agent/` from APScheduler cron jobs into **LangGraph nodes** without destroying the existing `/api/agent/*` control surface.
- Existing modules (`cosmo_mapper`, `competitor_analyzer`, `attribution_model`, `conversation_drafter`) become `@tool` decorated functions.

**Frontend:**
- New page: `/omni` — replaces the fragmented `/listing-analyzer`, `/competitor-intel`, `/marketing-assistant`, `/pipeline`, and `/admin/assistant` experiences with a single command-center UI.
- Reuses existing `MetricCard`, `VectorRadar`, and `Sparkline` components.
- Introduces a **persistent agent chat panel** (right sidebar) and a **dynamic canvas** (main area) that renders subgraph outputs contextually.

---

## 3. Consequences

### Positive
- **Unified UX:** One ASIN entry, one conversation, end-to-end execution.
- **Observability:** LangSmith tracing over every agent step, tool call, and retry.
- **Extensibility:** New agents are new subgraphs; no changes to supervisor required if tool schema is stable.
- **Human-in-the-Loop:** Natural breakpoints for email approval, sequence launch, and copy rollback.

### Negative / Risks
- **Complexity:** LangGraph adds a learning curve and operational surface area.
- **Latency:** Subgraph orchestration introduces round-trip overhead; must stream intermediate states to keep UX snappy.
- **Migration:** The existing APScheduler orchestrator must be maintained in parallel during transition.
- **Dependency:** Adds `langgraph`, `langchain-core`, and `langchain-openai` (or `langchain-anthropic`) to the Python environment.

### Mitigations
- Keep the existing `/api/agent/*` router intact; the LangGraph system is additive.
- Use `asyncio.to_thread()` for CPU-bound tool calls (COSMO embeddings, HDBSCAN) to prevent graph event-loop blocking.
- Implement aggressive server-side streaming (`astream_events`) so the UI feels responsive even during long subgraph runs.

---

## 4. Alternatives Considered

**A) CrewAI** — Rejected because its role-based DAG model cannot natively express the COSMO Catalyst ↔ SEO Guardian cyclic optimization loop without external hackery.

**B) AutoGen** — Rejected because its GroupChat pattern is too conversational and lacks the structured state/checkpoint guarantees we need for deterministic pipeline execution.

**C) Pure FastAPI + Celery** — Rejected because while it handles async task queues well, it does not provide native LLM agent orchestration, stateful reasoning cycles, or human-in-the-loop breakpoints.

---

## 5. References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- Existing `backend/agent/orchestrator.py` (APScheduler baseline)
- Existing `acquisition-tool/agentic_optimizer.py` (dual-agent loop)
- `AGENTS.md` — Project coding standards and conventions
