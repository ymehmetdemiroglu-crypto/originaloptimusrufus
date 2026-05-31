"""Specialized sub-graphs for the Omni-Dashboard MAS.

Each subgraph is a standalone LangGraph StateGraph that operates on a
forked OmniState. They wrap existing backend modules as tool nodes.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.agent.graph.state import OmniState
from backend.agent.graph.tools import (
    LISTING_TOOLS,
    COMPETITOR_TOOLS,
    ATTRIBUTION_TOOLS,
    OUTREACH_TOOLS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sync_tool_runner(tool_fn: Callable, state: OmniState) -> Dict[str, Any]:
    """Run a sync or async tool against the current workspace."""
    try:
        result = tool_fn.invoke({"asin": state.workspace.asin})
        return {"success": True, "data": result}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Listing Subgraph
# ---------------------------------------------------------------------------

def _listing_analysis_node(state: OmniState) -> Dict[str, Any]:
    """Run COSMO semantic analysis on the active ASIN."""
    from backend.agent.graph.tools import cosmo_analysis_tool, store_read_tool

    store_result = store_read_tool.invoke({"key": "listings", "id": state.workspace.asin})
    listing = store_result.get("data", {})
    if not listing:
        return {
            "agent_outputs": {
                **state.agent_outputs,
                "listing": {"agent": "listing", "success": False, "error": "ASIN not found in store"},
            }
        }

    cosmo_result = cosmo_analysis_tool.invoke(
        {
            "asin": state.workspace.asin,
            "title": listing.get("title", ""),
            "bullets": listing.get("bullets", []),
            "description": listing.get("description", ""),
        }
    )
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "listing": {"agent": "listing", "success": True, "data": cosmo_result},
        }
    }


def _listing_safety_node(state: OmniState) -> Dict[str, Any]:
    """Placeholder for WLPI + semantic drift safety gate.

    In the full implementation this wraps the agentic_optimizer dual-agent loop.
    For the partial implementation we validate that COSMO score exists.
    """
    listing_out = state.agent_outputs.get("listing", {})
    if not listing_out.get("success"):
        return {"errors": state.errors + ["Listing analysis failed; skipping safety gate."]}

    score = listing_out.get("data", {}).get("overall_score", 0)
    if score < 50:
        return {
            "errors": state.errors + [f"COSMO score {score} below threshold (50). Optimization recommended."]
        }
    return {}


def build_listing_subgraph() -> StateGraph:
    """Build the Listing Analysis & Optimization subgraph."""
    builder = StateGraph(OmniState)
    builder.add_node("cosmo_analysis", _listing_analysis_node)
    builder.add_node("safety_gate", _listing_safety_node)

    builder.set_entry_point("cosmo_analysis")
    builder.add_edge("cosmo_analysis", "safety_gate")
    builder.add_edge("safety_gate", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Competitor Subgraph
# ---------------------------------------------------------------------------

def _competitor_analysis_node(state: OmniState) -> Dict[str, Any]:
    """Run competitor intelligence on the active ASIN."""
    from backend.agent.graph.tools import competitor_intel_tool

    result = competitor_intel_tool.invoke({"asin": state.workspace.asin})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "competitor": {"agent": "competitor", "success": True, "data": result},
        }
    }


def build_competitor_subgraph() -> StateGraph:
    """Build the Competitor Intelligence subgraph."""
    builder = StateGraph(OmniState)
    builder.add_node("competitor_analysis", _competitor_analysis_node)
    builder.set_entry_point("competitor_analysis")
    builder.add_edge("competitor_analysis", END)
    return builder.compile()


# ---------------------------------------------------------------------------
# Attribution Subgraph
# ---------------------------------------------------------------------------

def _attribution_analysis_node(state: OmniState) -> Dict[str, Any]:
    """Run DiD/SCM causal analysis on the active ASIN."""
    from backend.agent.graph.tools import attribution_tool, store_read_tool

    # Fetch competitor ASINs from store to use as controls
    comp_result = store_read_tool.invoke({"key": "competitors", "id": state.workspace.asin})
    competitors = comp_result.get("data", [])
    control_asins = [c.get("asin") for c in competitors if c.get("asin")][:5]

    if not control_asins:
        return {
            "agent_outputs": {
                **state.agent_outputs,
                "attribution": {
                    "agent": "attribution",
                    "success": False,
                    "error": "No control ASINs available for causal analysis.",
                },
            }
        }

    result = attribution_tool.invoke({"asin": state.workspace.asin, "control_asins": control_asins})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "attribution": {"agent": "attribution", "success": True, "data": result},
        }
    }


def build_attribution_subgraph() -> StateGraph:
    """Build the Causal Attribution subgraph."""
    builder = StateGraph(OmniState)
    builder.add_node("attribution_analysis", _attribution_analysis_node)
    builder.set_entry_point("attribution_analysis")
    builder.add_edge("attribution_analysis", END)
    return builder.compile()


# ---------------------------------------------------------------------------
# Outreach Subgraph
# ---------------------------------------------------------------------------

def _outreach_enrich_node(state: OmniState) -> Dict[str, Any]:
    """Trigger enrichment for the active brand."""
    from backend.agent.graph.tools import pipeline_trigger_tool

    result = pipeline_trigger_tool.invoke({"stage": "enrich", "limit": 1})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "outreach": {"agent": "outreach", "success": result.get("success"), "data": result},
        }
    }


def _outreach_draft_node(state: OmniState) -> Dict[str, Any]:
    """Trigger email drafting for the active brand."""
    from backend.agent.graph.tools import pipeline_trigger_tool

    result = pipeline_trigger_tool.invoke({"stage": "draft", "limit": 1})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "outreach": {
                **state.agent_outputs.get("outreach", {}),
                "draft_result": result,
            },
        }
    }


def _outreach_human_gate_node(state: OmniState) -> Dict[str, Any]:
    """Interrupt for human approval before sequencing.

    Sets pending_human_input so the supervisor knows to pause.
    """
    draft = state.agent_outputs.get("outreach", {}).get("draft_result", {})
    return {
        "pending_human_input": {
            "prompt": "Approve email draft before Apollo sequence enrollment?",
            "payload": draft,
            "step_index": state.current_step_index,
        }
    }


def _outreach_sequence_node(state: OmniState) -> Dict[str, Any]:
    """Trigger Apollo sequence enrollment (only runs after human approval)."""
    from backend.agent.graph.tools import pipeline_trigger_tool

    result = pipeline_trigger_tool.invoke({"stage": "sequence", "limit": 1})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "outreach": {
                **state.agent_outputs.get("outreach", {}),
                "sequence_result": result,
            },
        }
    }


def _outreach_router(state: OmniState) -> Literal["human_gate", "sequence"]:
    """Route based on whether human approval has been received."""
    if state.pending_human_input is not None:
        # Still waiting
        return "human_gate"
    # If we reached this node and pending is cleared, resume to sequence
    return "sequence"


def build_outreach_subgraph() -> StateGraph:
    """Build the Outreach Pipeline subgraph with HITL gate."""
    builder = StateGraph(OmniState)
    builder.add_node("enrich", _outreach_enrich_node)
    builder.add_node("draft", _outreach_draft_node)
    builder.add_node("human_gate", _outreach_human_gate_node)
    builder.add_node("sequence", _outreach_sequence_node)

    builder.set_entry_point("enrich")
    builder.add_edge("enrich", "draft")
    builder.add_edge("draft", "human_gate")
    builder.add_conditional_edges("human_gate", _outreach_router, {"human_gate": "human_gate", "sequence": "sequence"})
    builder.add_edge("sequence", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Email Subgraph
# ---------------------------------------------------------------------------

def _email_classify_node(state: OmniState) -> Dict[str, Any]:
    """Classify the incoming reply email."""
    from backend.agent.graph.tools import classify_email_tool

    last_msg = state.get_last_human_message() or ""
    result = classify_email_tool.invoke({"reply_text": last_msg})
    classification = result.get("classification", {})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "email": {"agent": "email", "success": result.get("success", False), "data": {"classification": classification}},
        }
    }


def _email_draft_reply_node(state: OmniState) -> Dict[str, Any]:
    """Draft reply email based on classification."""
    from backend.agent.graph.tools import draft_reply_tool

    last_msg = state.get_last_human_message() or ""
    classification = state.agent_outputs.get("email", {}).get("data", {}).get("classification", {})
    category = classification.get("category", "OBJECTION")

    brand_key = state.workspace.brand_key or "default_brand"
    result = draft_reply_tool.invoke({
        "brand_key": brand_key,
        "reply_text": last_msg,
        "category": category
    })
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "email": {
                **state.agent_outputs.get("email", {}),
                "draft_result": result
            }
        }
    }


def build_email_subgraph() -> StateGraph:
    """Build the email classification and reply drafting subgraph."""
    builder = StateGraph(OmniState)
    builder.add_node("classify", _email_classify_node)
    builder.add_node("draft_reply", _email_draft_reply_node)
    builder.set_entry_point("classify")
    builder.add_edge("classify", "draft_reply")
    builder.add_edge("draft_reply", END)
    return builder.compile()


# ---------------------------------------------------------------------------
# Admin Subgraph
# ---------------------------------------------------------------------------

def _admin_metrics_node(state: OmniState) -> Dict[str, Any]:
    """Pull dashboard and operational health metrics."""
    from backend.agent.graph.tools import get_dashboard_metrics_tool

    result = get_dashboard_metrics_tool.invoke({"client_id": state.workspace.client_id})
    return {
        "agent_outputs": {
            **state.agent_outputs,
            "admin": {"agent": "admin", "success": result.get("success", False), "data": result},
        }
    }


def build_admin_subgraph() -> StateGraph:
    """Build the admin diagnostic and operations subgraph."""
    builder = StateGraph(OmniState)
    builder.add_node("metrics", _admin_metrics_node)
    builder.set_entry_point("metrics")
    builder.add_edge("metrics", END)
    return builder.compile()
