"""Agent Control API — manual triggers, status, and emergency pause.

Routes:
  GET  /api/agent/status          → Scheduler health + today's stats
  POST /api/agent/run             → Trigger a job manually
  POST /api/agent/run-pipeline    → Trigger full pipeline sequentially
  POST /api/agent/pause           → Pause scheduler (jobs finish, no new ones)
  POST /api/agent/resume          → Resume scheduler
  GET  /api/agent/runs            → List recent agent_runs rows
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from middleware.auth import require_admin
from agent.orchestrator import get_orchestrator
from agent.db_logger import AgentRunLogger
from agent.jobs import JobRegistry

router = APIRouter(prefix="/api/agent", tags=["Agent Control"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RunJobRequest(BaseModel):
    job_type: str


class RunPipelineRequest(BaseModel):
    triggered_by: str = "manual"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status", dependencies=[Depends(require_admin)])
async def agent_status():
    """Return real-time agent scheduler status and pipeline velocity."""
    orch = get_orchestrator()
    status = orch.get_status()

    # Augment with DB-driven feature flags if available
    db_logger = AgentRunLogger()
    sb = db_logger._sb
    if sb:
        try:
            res = sb.table("agent_config").select("*").limit(1).execute()
            if res.data:
                cfg = res.data[0]
                status["config"] = {
                    "agent_enabled": cfg.get("agent_enabled"),
                    "auto_scrape": cfg.get("auto_scrape"),
                    "auto_enrich": cfg.get("auto_enrich"),
                    "auto_score": cfg.get("auto_score"),
                    "auto_draft": cfg.get("auto_draft"),
                    "auto_sequence": cfg.get("auto_sequence"),
                    "auto_reply": cfg.get("auto_reply"),
                    "max_daily_sequences": cfg.get("max_daily_sequences"),
                }
        except Exception:
            pass

    return status


@router.post("/run", dependencies=[Depends(require_admin)])
async def run_job(request: RunJobRequest):
    """Manually trigger a single agent job by type."""
    if request.job_type not in JobRegistry.list_jobs():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown job type. Valid types: {', '.join(JobRegistry.list_jobs())}",
        )

    orch = get_orchestrator()
    if not orch.is_running():
        # Allow manual runs even if scheduler is paused
        pass

    result = orch.trigger_job(request.job_type, triggered_by="manual")
    return result


@router.post("/run-pipeline", dependencies=[Depends(require_admin)])
async def run_full_pipeline(request: RunPipelineRequest):
    """Trigger the entire pipeline (scrape → enrich → score → draft → sequence) sequentially."""
    orch = get_orchestrator()
    results = await asyncio.to_thread(orch.run_full_pipeline_once, triggered_by=request.triggered_by)
    return {
        "triggered_by": request.triggered_by,
        "stages": results,
        "overall_status": "success" if all(r.get("status") in ("success", "skipped") for r in results) else "partial",
    }


@router.post("/pause", dependencies=[Depends(require_admin)])
async def pause_agent():
    """Pause the scheduler — existing jobs finish, no new jobs start."""
    orch = get_orchestrator()
    orch.stop()
    return {"status": "paused", "running": False}


@router.post("/resume", dependencies=[Depends(require_admin)])
async def resume_agent():
    """Resume the scheduler."""
    orch = get_orchestrator()
    orch.start()
    return {"status": "resumed", "running": orch.is_running()}


@router.get("/runs", dependencies=[Depends(require_admin)])
async def list_runs(run_type: Optional[str] = None, limit: int = 20):
    """List recent agent runs from the database."""
    db_logger = AgentRunLogger()
    runs = db_logger.get_recent_runs(run_type=run_type, limit=limit)
    return {"count": len(runs), "runs": runs}
