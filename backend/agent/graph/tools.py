"""Tool definitions for the Omni-Dashboard MAS.

Each tool wraps existing backend or acquisition-tool functionality in a
langchain-compatible @tool interface so agents can invoke them via LLM
tool-calling or direct node execution.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Lazy imports of heavy / existing modules to keep import-time fast and
# avoid circular deps when LangGraph is not yet installed.
# ---------------------------------------------------------------------------

_cosmo_mapper: Any = None
_competitor_analyzer: Any = None
_attribution_model: Any = None
_data_store: Any = None


def _get_cosmo_mapper():
    global _cosmo_mapper
    if _cosmo_mapper is None:
        from backend.analysis.cosmo_mapper import CosmoMapper
        from backend.core.embedding_engine import get_engine

        _cosmo_mapper = CosmoMapper(get_engine())
    return _cosmo_mapper


def _get_competitor_analyzer():
    global _competitor_analyzer
    if _competitor_analyzer is None:
        from backend.analysis.competitor_analyzer import CompetitorAnalyzer
        from backend.core.embedding_engine import get_engine

        _competitor_analyzer = CompetitorAnalyzer(get_engine())
    return _competitor_analyzer


def _get_attribution_model():
    global _attribution_model
    if _attribution_model is None:
        from backend.analysis.attribution import CausalAttributionModel

        _attribution_model = CausalAttributionModel()
    return _attribution_model


def _get_data_store():
    global _data_store
    if _data_store is None:
        from backend.data.store import store

        _data_store = store
    return _data_store


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class CosmoAnalysisInput(BaseModel):
    """Input for COSMO semantic analysis."""

    asin: str = Field(description="Amazon ASIN to analyze")
    title: str = Field(description="Current product title")
    bullets: List[str] = Field(default_factory=list, description="Current bullet points")
    description: str = Field(default="", description="Current product description")


class CompetitorIntelInput(BaseModel):
    """Input for competitor intelligence."""

    asin: str = Field(description="Client ASIN")
    competitor_asins: Optional[List[str]] = Field(default=None, description="Explicit competitor ASINs; if omitted, auto-discover")


class AttributionInput(BaseModel):
    """Input for causal attribution analysis."""

    asin: str = Field(description="Treatment ASIN")
    control_asins: List[str] = Field(default_factory=list, description="Control ASINs for DiD/SCM")
    start_date: Optional[str] = Field(default=None, description="ISO start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="ISO end date (YYYY-MM-DD)")


class StoreReadInput(BaseModel):
    """Input for reading from the in-memory data store."""

    key: str = Field(description="Entity type: listings | competitors | clients | jobs | traffic_history")
    id: Optional[str] = Field(default=None, description="Optional entity ID (e.g., ASIN)")


class PipelineTriggerInput(BaseModel):
    """Input for triggering a pipeline stage."""

    stage: str = Field(description="Pipeline stage name: scrape | enrich | score | draft | sequence")
    limit: int = Field(default=10, description="Max items to process")


class SupabaseQueryInput(BaseModel):
    """Input for querying Supabase safely."""

    table: str = Field(description="White-listed table to query: brands | prospects | agent_runs | email_conversations | landing_copy_variants")
    action: Literal["select", "insert", "update"] = Field(default="select", description="Database operation: select | insert | update")
    query_params: Optional[Dict[str, Any]] = Field(default=None, description="Select filters (e.g., {'brand_key': 'xyz'}) or update matching query")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Data to insert or update")


class ClassifyEmailInput(BaseModel):
    """Input for classifying an inbound email reply."""

    reply_text: str = Field(description="Content of the email reply to classify")


class DraftReplyInput(BaseModel):
    """Input for drafting a B2B sales email reply."""

    brand_key: str = Field(description="Unique brand identifier")
    reply_text: str = Field(description="Content of the inbound email reply")
    category: str = Field(description="Classified category: INTERESTED | OBJECTION | NOT_NOW | WRONG_PERSON | COMPETITOR | NOISE")


class DashboardMetricsInput(BaseModel):
    """Input for pulling live dashboard performance metrics."""

    client_id: Optional[str] = Field(default=None, description="Optional client ID to filter by")


class ListProspectsInput(BaseModel):
    """Input for listing prospects matching filters."""

    stage: Optional[str] = Field(default=None, description="Stage to filter by")
    limit: int = Field(default=50, description="Max prospects to return")


class UpdateProspectStageInput(BaseModel):
    """Input for updating prospect or brand stage."""

    identifier: str = Field(description="Target ASIN (prospect) or Brand Key (brand)")
    stage: str = Field(description="Stage name to update")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(args_schema=CosmoAnalysisInput)
def cosmo_analysis_tool(asin: str, title: str, bullets: list, description: str = "") -> Dict[str, Any]:
    """Analyze an Amazon listing for COSMO semantic relation coverage and return scores + gap alerts."""
    mapper = _get_cosmo_mapper()
    # Offload CPU-heavy embedding work to thread pool
    result = asyncio.get_event_loop().run_in_executor(
        None,
        mapper.analyze,
        asin,
        title,
        bullets,
        description,
    )
    # If called from async context, the caller should await; sync fallback here:
    if asyncio.iscoroutine(result):
        return result  # type: ignore[return-value]
    return result


@tool(args_schema=CompetitorIntelInput)
def competitor_intel_tool(asin: str, competitor_asins: Optional[list] = None) -> Dict[str, Any]:
    """Generate competitor landscape, similarity scores, and clustered gap opportunities."""
    analyzer = _get_competitor_analyzer()
    result = asyncio.get_event_loop().run_in_executor(
        None,
        analyzer.analyze,
        asin,
        competitor_asins or [],
    )
    if asyncio.iscoroutine(result):
        return result  # type: ignore[return-value]
    return result


@tool(args_schema=AttributionInput)
def attribution_tool(asin: str, control_asins: list, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """Run Difference-in-Differences and Synthetic Control causal lift analysis."""
    model = _get_attribution_model()
    store = _get_data_store()

    treatment_history = store.traffic_history.get(asin, [])
    control_histories = {c: store.traffic_history.get(c, []) for c in control_asins}

    did_result = model.calculate_did_lift(treatment_history, control_histories)
    scm_result = model.calculate_synthetic_control_lift(treatment_history, control_histories)
    financial = model.estimate_financial_impact(did_result.get("lift_percent", 0), treatment_history)

    return {
        "did": did_result,
        "scm": scm_result,
        "financial_projection": financial,
    }


@tool(args_schema=StoreReadInput)
def store_read_tool(key: str, id: Optional[str] = None) -> Dict[str, Any]:
    """Read entities from the shared in-memory data store."""
    store = _get_data_store()
    data: Dict[str, Any] = {}
    if key == "listings":
        data = store.listings.get(id, {}) if id else store.listings
    elif key == "competitors":
        data = store.competitors.get(id, []) if id else store.competitors
    elif key == "clients":
        data = [c for c in store.clients if not id or c.get("id") == id]
    elif key == "jobs":
        data = store.jobs
    elif key == "traffic_history":
        data = store.traffic_history.get(id, []) if id else store.traffic_history
    return {"key": key, "id": id, "data": data}


@tool(args_schema=PipelineTriggerInput)
def pipeline_trigger_tool(stage: str, limit: int = 10) -> Dict[str, Any]:
    """Trigger an acquisition pipeline stage manually (scrape, enrich, score, draft, sequence)."""
    from backend.agent.jobs import JobRegistry

    registry = JobRegistry()
    job_type = f"{stage}_job"
    if not hasattr(registry, job_type):
        return {"success": False, "error": f"Unknown stage: {stage}"}

    runner = getattr(registry, job_type)
    try:
        result = runner(limit=limit)
        return {"success": True, "stage": stage, "result": result}
    except Exception as exc:
        return {"success": False, "stage": stage, "error": str(exc)}


@tool(args_schema=SupabaseQueryInput)
def supabase_query_tool(table: str, action: str = "select", query_params: Optional[dict] = None, data: Optional[dict] = None) -> Dict[str, Any]:
    """Safely query or update whitelisted tables in Supabase."""
    allowed_tables = {"brands", "prospects", "agent_runs", "email_conversations", "landing_copy_variants"}
    if table not in allowed_tables:
        return {"success": False, "error": f"Table '{table}' is not whitelisted. Access denied."}

    try:
        try:
            from core.supabase import get_supabase
        except ImportError:
            from backend.core.supabase import get_supabase

        sb = get_supabase()
        if not sb:
            return {"success": False, "error": "Supabase client not initialized."}

        q = sb.table(table)
        if action == "select":
            builder = q.select("*")
            if query_params:
                for k, v in query_params.items():
                    builder = builder.eq(k, v)
            res = builder.execute()
            return {"success": True, "data": res.data}
        elif action == "insert":
            if not data:
                return {"success": False, "error": "No data provided for insert operation."}
            res = q.insert(data).execute()
            return {"success": True, "data": res.data}
        elif action == "update":
            if not data:
                return {"success": False, "error": "No data provided for update operation."}
            builder = q.update(data)
            if query_params:
                for k, v in query_params.items():
                    builder = builder.eq(k, v)
            else:
                return {"success": False, "error": "Query parameters are required for update operations to prevent massive updates."}
            res = builder.execute()
            return {"success": True, "data": res.data}
        else:
            return {"success": False, "error": f"Unsupported action '{action}'."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool(args_schema=ClassifyEmailInput)
def classify_email_tool(reply_text: str) -> Dict[str, Any]:
    """Classify an inbound email reply to determine buyer intent, objections, etc."""
    try:
        import sys
        from pathlib import Path
        acq_path = Path(__file__).resolve().parent.parent.parent.parent / "acquisition-tool"
        if str(acq_path) not in sys.path:
            sys.path.append(str(acq_path))

        from reply_classifier import classify_reply
        classification = classify_reply(reply_text)
        return {"success": True, "classification": classification}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool(args_schema=DraftReplyInput)
def draft_reply_tool(brand_key: str, reply_text: str, category: str) -> Dict[str, Any]:
    """Draft an objection-handling or scheduling email response tailored in Alex Hormozi style."""
    try:
        import sys
        from pathlib import Path
        acq_path = Path(__file__).resolve().parent.parent.parent.parent / "acquisition-tool"
        if str(acq_path) not in sys.path:
            sys.path.append(str(acq_path))

        import config
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)

        system_prompt = (
            "You are an elite B2B sales development representative ghost-writing a reply "
            "email for Yahya. The recipient is a brand founder who replied to our cold outreach. "
            "Write a short, direct, value-first reply in the punchy style of Alex Hormozi.\n\n"
            "Rules:\n"
            "- Clarity over cleverness. Short sentences.\n"
            "- Direct, blunt honesty. Sound like a peer operator.\n"
            "- Low friction. No generic formal greetings or signatures. Output ONLY the response body.\n"
            "- Use the objection handler pattern matching their response style."
        )

        user_prompt = (
            f"Brand Key: {brand_key}\n"
            f"Original Inbound Reply: {reply_text}\n"
            f"Classification: {category}\n\n"
            "Draft the reply now."
        )

        resp = client.chat.completions.create(
            model=config.OPENROUTER_DRAFT_MODEL,
            max_tokens=300,
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        draft = (resp.choices[0].message.content or "").strip()
        return {"success": True, "draft": draft}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool(args_schema=DashboardMetricsInput)
def get_dashboard_metrics_tool(client_id: Optional[str] = None) -> Dict[str, Any]:
    """Pull high-level dashboard performance and conversion metrics."""
    try:
        try:
            from core.supabase import get_supabase
        except ImportError:
            from backend.core.supabase import get_supabase

        sb = get_supabase()
        store_obj = _get_data_store()

        jobs = store_obj.get_jobs()
        clients = store_obj.get_clients()

        prospect_stats = {}
        if sb:
            try:
                res = sb.table("prospects").select("stage").execute()
                from collections import Counter
                stages = [r.get("stage") for r in res.data or []]
                prospect_stats = dict(Counter(stages))
            except Exception:
                pass

        metrics = {
            "active_listings": sum(c.get("listings", 0) for c in clients),
            "jobs_count": len(jobs),
            "jobs_running": sum(1 for j in jobs if j.get("status") == "running"),
            "jobs_completed": sum(1 for j in jobs if j.get("status") == "completed"),
            "stage_distribution": prospect_stats,
        }
        return {"success": True, "metrics": metrics}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool(args_schema=ListProspectsInput)
def list_prospects_tool(stage: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """List prospects matching specific stage filters."""
    try:
        try:
            from core.supabase import get_supabase
        except ImportError:
            from backend.core.supabase import get_supabase

        sb = get_supabase()
        if not sb:
            return {"success": False, "error": "Supabase not configured."}

        q = sb.table("prospects").select("*").limit(limit)
        if stage:
            q = q.eq("stage", stage)
        res = q.execute()
        return {"success": True, "prospects": res.data}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@tool(args_schema=UpdateProspectStageInput)
def update_prospect_stage_tool(identifier: str, stage: str) -> Dict[str, Any]:
    """Enforce dual-write updates of brand/prospect stages to both store cache and Supabase."""
    try:
        store_obj = _get_data_store()
        memory_updated = False
        if identifier in store_obj.listings:
            store_obj.listings[identifier]["stage"] = stage
            store_obj._save()
            memory_updated = True

        try:
            from core.supabase import get_supabase
        except ImportError:
            from backend.core.supabase import get_supabase

        sb = get_supabase()
        supabase_updated = False
        if sb:
            if identifier.startswith("B0") and len(identifier) == 10:
                sb.table("prospects").update({"stage": stage}).eq("asin", identifier).execute()
                supabase_updated = True
            else:
                sb.table("brands").update({"stage": stage}).eq("brand_key", identifier).execute()
                supabase_updated = True

        return {
            "success": True,
            "identifier": identifier,
            "stage": stage,
            "memory_updated": memory_updated,
            "supabase_updated": supabase_updated,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool registry for easy agent binding
# ---------------------------------------------------------------------------

TOOLS = [
    cosmo_analysis_tool,
    competitor_intel_tool,
    attribution_tool,
    store_read_tool,
    pipeline_trigger_tool,
    supabase_query_tool,
    classify_email_tool,
    draft_reply_tool,
    get_dashboard_metrics_tool,
    list_prospects_tool,
    update_prospect_stage_tool,
]

LISTING_TOOLS = [cosmo_analysis_tool, store_read_tool]
COMPETITOR_TOOLS = [competitor_intel_tool, store_read_tool]
ATTRIBUTION_TOOLS = [attribution_tool, store_read_tool]
OUTREACH_TOOLS = [pipeline_trigger_tool, store_read_tool, classify_email_tool, draft_reply_tool]
ADMIN_TOOLS = [
    pipeline_trigger_tool,
    store_read_tool,
    get_dashboard_metrics_tool,
    list_prospects_tool,
    update_prospect_stage_tool,
    supabase_query_tool,
]
