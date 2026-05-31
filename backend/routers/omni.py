"""FastAPI router for the Omni-Dashboard Multi-Agent System.

Exposes:
- POST /api/omni/chat        — Invoke the supervisor graph (SSE streaming)
- POST /api/omni/resume      — Resume from a human-in-the-loop interrupt
- GET  /api/omni/threads/{id}— Fetch thread checkpoint state
- GET  /api/omni/agents      — List available agents and their status
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

# Conditional import so the app still starts if langgraph is not installed.
try:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver

    from backend.agent.graph.state import OmniState, WorkspaceSnapshot
    from backend.agent.graph.supervisor import build_supervisor_graph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover
    LANGGRAPH_AVAILABLE = False

router = APIRouter(prefix="/api/omni")

# In-memory checkpoint saver for partial implementation.
# In production, swap to PostgresSaver pointing at Supabase.
_memory_checkpointer: Optional[Any] = None
_graph: Optional[Any] = None


def _get_checkpointer():
    global _memory_checkpointer
    if _memory_checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        _memory_checkpointer = MemorySaver()
    return _memory_checkpointer


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_supervisor_graph()
    return _graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_to_dict(state: OmniState) -> Dict[str, Any]:
    return state.model_dump(mode="json")


async def _stream_graph_events(
    thread_id: str,
    state: OmniState,
) -> AsyncGenerator[str, None]:
    """Run the supervisor graph and yield SSE events."""
    if not LANGGRAPH_AVAILABLE:
        yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'LangGraph not installed. Run: pip install -r backend/requirements.txt'}})}\n\n"
        return

    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

    # Stream execution events
    try:
        # For the partial implementation we use ainvoke + manual event emission.
        # In production, switch to graph.astream_events for finer granularity.
        yield f"data: {json.dumps({'event': 'plan_start', 'data': {'thread_id': thread_id}})}\n\n"

        final_state = await graph.ainvoke(state, config=config)

        # Emit agent outputs as they appear
        for agent_key, output in final_state.get("agent_outputs", {}).items():
            yield f"data: {json.dumps({'event': 'agent_complete', 'data': {'agent': agent_key, 'output': output}})}\n\n"

        # Emit synthesis
        synthesis = final_state.get("synthesis")
        if synthesis:
            yield f"data: {json.dumps({'event': 'synthesis', 'data': {'content': synthesis}})}\n\n"

        # Emit HITL if pending
        pending = final_state.get("pending_human_input")
        if pending:
            yield f"data: {json.dumps({'event': 'human_input_required', 'data': pending})}\n\n"

        yield f"data: {json.dumps({'event': 'final', 'data': _state_to_dict(final_state)})}\n\n"

    except Exception as exc:
        yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(exc)}})}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def omni_chat(request: Request):
    """Start or continue an Omni-Dashboard conversation.

    Request body:
    {
      "thread_id": "uuid-or-null",
      "message": "user intent",
      "workspace": { "asin": "B08X", "brand_key": "...", "client_id": "..." }
    }

    Returns Server-Sent Events stream.
    """
    body = await request.json()
    thread_id: str = body.get("thread_id") or str(uuid.uuid4())
    message: str = body.get("message", "")
    workspace_raw: Dict[str, Any] = body.get("workspace", {})

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    workspace = WorkspaceSnapshot(**workspace_raw)

    # Build initial state
    state = OmniState(
        messages=[{"role": "human", "content": message}],
        workspace=workspace,
    )

    return StreamingResponse(
        _stream_graph_events(thread_id, state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Thread-Id": thread_id,
        },
    )


@router.post("/resume")
async def omni_resume(request: Request):
    """Resume a thread from a human-in-the-loop interrupt.

    Request body:
    {
      "thread_id": "uuid",
      "human_response": { "action": "approve|reject|modify", "modifications": "..." }
    }
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph not available")

    body = await request.json()
    thread_id: str = body.get("thread_id")
    human_response: Dict[str, Any] = body.get("human_response", {})

    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")

    # Retrieve prior checkpoint from memory saver
    checkpointer = _get_checkpointer()
    # Note: MemorySaver get_tuple API is internal; in production use PostgresSaver
    config = {"configurable": {"thread_id": thread_id}}

    # For partial implementation, we reconstruct state from a lightweight in-memory cache
    # or simply re-invoke with pending_human_input cleared.
    # A full implementation uses LangGraph's `Command(resume=...)` pattern.

    # Fetch existing state (simplified)
    # In production: checkpoint = checkpointer.get_tuple(config)
    # Here we require the frontend to send back the full prior state or we keep a cache.

    # As a pragmatic fallback, we accept the previous state in the request:
    prior_state_raw = body.get("prior_state")
    if not prior_state_raw:
        # Partial implementation: reconstruct empty state; production uses checkpoint saver
        state = OmniState(
            messages=[{"role": "human", "content": json.dumps(human_response)}],
            pending_human_input=None,
        )
    else:
        state = OmniState(**prior_state_raw)
        state.pending_human_input = None
        state.messages.append({"role": "human", "content": json.dumps(human_response)})

    # Partial implementation: return final JSON instead of SSE for simplicity.
    # Production should stream via _stream_graph_events.
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph not available")

    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    final_state = await graph.ainvoke(state, config=config)
    return _state_to_dict(final_state)


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Fetch thread state (checkpoint) by ID."""
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=503, detail="LangGraph not available")

    # In production: query PostgresSaver
    raise HTTPException(status_code=501, detail="Checkpoint retrieval not yet implemented for memory saver")


@router.get("/agents")
async def list_agents():
    """List available agents and their health/status."""
    agents = [
        {
            "id": "listing",
            "name": "Listing Optimizer",
            "description": "COSMO semantic analysis + agentic copy optimization",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
        {
            "id": "competitor",
            "name": "Competitor Intelligence",
            "description": "Competitor landscape + gap clustering",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
        {
            "id": "attribution",
            "name": "Causal Attribution",
            "description": "DiD/SCM lift analysis + revenue projection",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
        {
            "id": "outreach",
            "name": "Outreach Pipeline",
            "description": "Enrichment + email drafting + Apollo sequencing",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
        {
            "id": "email",
            "name": "Email Agent",
            "description": "Inbound reply classification + response drafting",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
        {
            "id": "admin",
            "name": "Admin Copilot",
            "description": "Dashboard telemetry queries + pipeline triggers",
            "status": "healthy" if LANGGRAPH_AVAILABLE else "unavailable",
        },
    ]
    return {"agents": agents}
