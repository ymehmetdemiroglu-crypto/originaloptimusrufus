"""Supervisor graph for the Omni-Dashboard MAS.

The Supervisor receives high-level user intent, builds an execution plan,
delegates to specialized sub-graphs in parallel where possible, and
synthesizes their outputs into a final response.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Literal, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from backend.agent.graph.state import OmniState, PlanStep
from backend.agent.graph.subgraphs import (
    build_listing_subgraph,
    build_competitor_subgraph,
    build_attribution_subgraph,
    build_outreach_subgraph,
    build_email_subgraph,
    build_admin_subgraph,
)

# ---------------------------------------------------------------------------
# Sub-graph registry
# ---------------------------------------------------------------------------

_SUBGRAPH_BUILDERS = {
    "listing": build_listing_subgraph,
    "competitor": build_competitor_subgraph,
    "attribution": build_attribution_subgraph,
    "outreach": build_outreach_subgraph,
    "email": build_email_subgraph,
    "admin": build_admin_subgraph,
}


# ---------------------------------------------------------------------------
# Supervisor nodes
# ---------------------------------------------------------------------------

def _plan_node(state: OmniState) -> Dict[str, Any]:
    """Parse the latest human message and generate a structured plan.

    For the partial implementation we use a rule-based planner.
    In production this becomes an LLM call with structured output.
    """
    message = state.get_last_human_message() or ""
    message_lower = message.lower()
    plan: List[PlanStep] = []

    # Detect intent keywords and build plan
    needs_listing = any(k in message_lower for k in ["optimize", "listing", "cosmo", "score", "fix"])
    needs_competitor = any(k in message_lower for k in ["competitor", "gap", "landscape", "intel"])
    needs_attribution = any(k in message_lower for k in ["revenue", "impact", "lift", "did", "attribution", "causal"])
    needs_outreach = any(k in message_lower for k in ["outreach", "sequence", "apollo"])
    needs_email = any(k in message_lower for k in ["classify", "objection", "reply", "inbox", "nurture", "draft reply", "email reply"])
    needs_admin = any(k in message_lower for k in ["metrics", "health", "admin", "dashboard", "prospects", "stage", "supabase"])

    step_idx = 0
    if needs_listing:
        plan.append(PlanStep(agent="listing", task="Run COSMO analysis and safety gate", status="pending"))
        step_idx += 1
    if needs_competitor:
        plan.append(PlanStep(agent="competitor", task="Generate competitor landscape and gaps", status="pending"))
        step_idx += 1
    if needs_attribution:
        depends = []
        if needs_listing:
            depends = [0]  # attribution usually needs listing baseline
        plan.append(
            PlanStep(
                agent="attribution",
                task="Run DiD/SCM causal analysis and project revenue",
                depends_on=depends,
                status="pending",
            )
        )
        step_idx += 1
    if needs_outreach:
        plan.append(
            PlanStep(
                agent="outreach",
                task="Enrich contact, draft sequence, and await approval",
                requires_human_approval=True,
                status="pending",
            )
        )
        step_idx += 1
    if needs_email:
        plan.append(
            PlanStep(
                agent="email",
                task="Classify reply and draft objection/intent handling email",
                status="pending",
            )
        )
        step_idx += 1
    if needs_admin:
        plan.append(
            PlanStep(
                agent="admin",
                task="Query dashboard metrics, list prospects and update status",
                status="pending",
            )
        )
        step_idx += 1

    # Fallback direct answer if no agents matched
    if not plan:
        plan.append(PlanStep(agent="synthesize", task="Answer user question directly", status="pending"))

    return {"plan": plan, "current_step_index": 0}


def _delegate_node(state: OmniState) -> Dict[str, Any]:
    """Execute all plan steps whose dependencies are satisfied.

    Parallel steps are gathered with asyncio.gather().
    """
    if state.current_step_index >= len(state.plan):
        return {}

    # Identify ready steps (no pending dependencies)
    ready_steps: List[int] = []
    for idx, step in enumerate(state.plan):
        if step.status != "pending":
            continue
        deps_satisfied = all(state.plan[d].status == "completed" for d in step.depends_on)
        if deps_satisfied:
            ready_steps.append(idx)

    if not ready_steps:
        return {}

    async def _run_step(idx: int) -> Dict[str, Any]:
        step = state.plan[idx]
        builder = _SUBGRAPH_BUILDERS.get(step.agent)
        if builder is None:
            return {
                "agent_outputs": {
                    **state.agent_outputs,
                    step.agent: {"agent": step.agent, "success": False, "error": "Unknown agent"},
                }
            }

        subgraph = builder()
        # Fork state for subgraph (shallow copy of outputs to avoid cross-contamination)
        forked = state.model_copy(deep=True)
        forked.plan = [step]  # subgraph sees only its own step context
        forked.current_step_index = 0

        result_state = await subgraph.ainvoke(forked, config=RunnableConfig(recursion_limit=25))
        return {
            "agent_outputs": {
                **state.agent_outputs,
                step.agent: result_state.get("agent_outputs", {}).get(step.agent, {}),
            }
        }

    # Run ready steps concurrently
    results = asyncio.get_event_loop().run_until_complete(
        asyncio.gather(*[_run_step(idx) for idx in ready_steps])
    )

    # Merge outputs back into state
    merged_outputs = dict(state.agent_outputs)
    for r in results:
        merged_outputs.update(r.get("agent_outputs", {}))

    # Mark completed
    new_plan = [s.model_copy() for s in state.plan]
    for idx in ready_steps:
        new_plan[idx].status = "completed"

    return {"agent_outputs": merged_outputs, "plan": new_plan}


def _synthesize_node(state: OmniState) -> Dict[str, Any]:
    """Build the final response from all agent outputs.

    In production this is an LLM call. For partial implementation we
    construct a structured markdown synthesis.
    """
    parts: List[str] = []
    parts.append("## Omni-Dashboard Report\n")

    if "listing" in state.agent_outputs:
        lo = state.agent_outputs["listing"]
        if lo.get("success"):
            data = lo.get("data", {})
            parts.append(f"**Listing Analysis** — Overall COSMO Score: {data.get('overall_score', 'N/A')}\n")
            parts.append(f"- Keyword Safety: {data.get('keyword_safety', 'N/A')}\n")
            parts.append(f"- Embedding Dimensions: {data.get('embedding_dimensions', 'N/A')}\n")
        else:
            parts.append(f"**Listing Analysis** — Error: {lo.get('error')}\n")

    if "competitor" in state.agent_outputs:
        co = state.agent_outputs["competitor"]
        if co.get("success"):
            data = co.get("data", {})
            parts.append(f"**Competitor Intel** — {len(data.get('competitor_profiles', []))} competitors analyzed.\n")
            parts.append(f"- Positioning: {data.get('positioning_summary', 'N/A')}\n")
        else:
            parts.append(f"**Competitor Intel** — Error: {co.get('error')}\n")

    if "attribution" in state.agent_outputs:
        ao = state.agent_outputs["attribution"]
        if ao.get("success"):
            data = ao.get("data", {})
            did = data.get("did", {})
            fin = data.get("financial_projection", {})
            parts.append(f"**Attribution** — DiD Lift: {did.get('lift_percent', 'N/A')}%\n")
            parts.append(f"- Projected Monthly Revenue: ${fin.get('projected_monthly_revenue', 'N/A')}\n")
        else:
            parts.append(f"**Attribution** — Error: {ao.get('error')}\n")

    if "outreach" in state.agent_outputs:
        oo = state.agent_outputs["outreach"]
        parts.append(f"**Outreach** — Enrichment success: {oo.get('success')}\n")
        if oo.get("draft_result"):
            parts.append("- Email draft generated and awaiting approval.\n")
        if oo.get("sequence_result"):
            parts.append("- Apollo sequence enrolled.\n")

    if "email" in state.agent_outputs:
        eo = state.agent_outputs["email"]
        if eo.get("success"):
            classification = eo.get("data", {}).get("classification", {})
            parts.append(f"**Email Reply Intelligence** — Classification: {classification.get('category', 'OBJECTION')} (Confidence: {int(classification.get('confidence', 0.0) * 100)}%)\n")
            if eo.get("draft_result", {}).get("success"):
                parts.append("- AI Objection-Handling Reply drafted successfully.\n")
        else:
            parts.append(f"**Email Reply Intelligence** — Error: {eo.get('error')}\n")

    if "admin" in state.agent_outputs:
        ad = state.agent_outputs["admin"]
        if ad.get("success"):
            metrics = ad.get("data", {}).get("metrics", {})
            parts.append(f"**Admin Operations Diagnostics** — Active Listings: {metrics.get('active_listings', 0)}\n")
            parts.append(f"- Active Jobs: {metrics.get('jobs_count', 0)} (Running: {metrics.get('jobs_running', 0)})\n")
        else:
            parts.append(f"**Admin Operations Diagnostics** — Error: {ad.get('error')}\n")

    synthesis = "\n".join(parts)
    return {"synthesis": synthesis, "completed": True}


def _router(state: OmniState) -> Literal["delegate", "synthesize", "end"]:
    """Route after planning or delegation."""
    if state.completed:
        return "end"

    # If there are still pending plan steps, keep delegating
    has_pending = any(s.status == "pending" for s in state.plan)
    if has_pending:
        return "delegate"

    # All steps done → synthesize
    return "synthesize"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_supervisor_graph() -> StateGraph:
    """Compile and return the Omni-Dashboard supervisor graph."""
    builder = StateGraph(OmniState)

    builder.add_node("plan", _plan_node)
    builder.add_node("delegate", _delegate_node)
    builder.add_node("synthesize", _synthesize_node)

    builder.set_entry_point("plan")
    builder.add_conditional_edges("plan", _router, {"delegate": "delegate", "synthesize": "synthesize", "end": END})
    builder.add_conditional_edges("delegate", _router, {"delegate": "delegate", "synthesize": "synthesize", "end": END})
    builder.add_edge("synthesize", END)

    return builder.compile()
