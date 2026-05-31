"""APScheduler-based orchestrator for autonomous pipeline execution.

Usage:
    # Start scheduler alongside FastAPI (auto-start if AGENT_ENABLED)
    from agent.orchestrator import get_orchestrator
    orch = get_orchestrator()
    orch.start()

    # Manual trigger
    orch.trigger_job("scrape", triggered_by="manual")

    # One-off full pipeline (blocking)
    orch.run_full_pipeline_once(triggered_by="manual")
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from agent.config import (
    AGENT_AUTO_DRAFT,
    AGENT_AUTO_ENRICH,
    AGENT_AUTO_SCORE,
    AGENT_AUTO_SCRAPE,
    AGENT_AUTO_SEQUENCE,
    AGENT_ENABLED,
    AGENT_SCHEDULE_DRAFT_UTC,
    AGENT_SCHEDULE_ENRICH_UTC,
    AGENT_SCHEDULE_REPLY_UTC,
    AGENT_SCHEDULE_SCORE_UTC,
    AGENT_SCHEDULE_SCRAPE_UTC,
    AGENT_SCHEDULE_SEQUENCE_UTC,
    AGENT_SCHEDULE_SNAPSHOT_UTC,
)
from agent.db_logger import AgentRunLogger
from agent.jobs import JobRegistry

logger = logging.getLogger("agent.orchestrator")


class AgentOrchestrator:
    """Wraps APScheduler with logging, safety toggles, and manual triggers."""

    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
        self._lock = threading.Lock()
        self._running = False
        self.db_logger = AgentRunLogger()

    # ------------------------------------------------------------------
    # Scheduler lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background scheduler if not already running."""
        with self._lock:
            if self._running:
                logger.info("Scheduler already running.")
                return

            if not AGENT_ENABLED:
                logger.info("AGENT_ENABLED=false — scheduler will not start.")
                return

            self.scheduler = BackgroundScheduler(timezone="UTC")
            self._register_jobs()
            self.scheduler.start()
            self._running = True
            logger.info("Agent scheduler started. Jobs registered: %s", self._list_scheduled_jobs())

    def stop(self):
        """Gracefully shut down the scheduler."""
        with self._lock:
            if self.scheduler:
                self.scheduler.shutdown(wait=True)
                self.scheduler = None
            self._running = False
            logger.info("Agent scheduler stopped.")

    def is_running(self) -> bool:
        with self._lock:
            return self._running and (self.scheduler is not None)

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def _register_jobs(self):
        """Map feature toggles to cron triggers."""
        sched = self.scheduler
        if sched is None:
            return

        def _parse_time(t: str):
            h, m = map(int, t.split(":"))
            return h, m

        # Scrape
        if AGENT_AUTO_SCRAPE:
            h, m = _parse_time(AGENT_SCHEDULE_SCRAPE_UTC)
            sched.add_job(
                self._wrapped_job,
                trigger=CronTrigger(hour=h, minute=m),
                args=["scrape"],
                id="scrape_daily",
                replace_existing=True,
            )

        # Enrich
        if AGENT_AUTO_ENRICH:
            h, m = _parse_time(AGENT_SCHEDULE_ENRICH_UTC)
            sched.add_job(
                self._wrapped_job,
                trigger=CronTrigger(hour=h, minute=m),
                args=["enrich"],
                id="enrich_daily",
                replace_existing=True,
            )

        # Score
        if AGENT_AUTO_SCORE:
            h, m = _parse_time(AGENT_SCHEDULE_SCORE_UTC)
            sched.add_job(
                self._wrapped_job,
                trigger=CronTrigger(hour=h, minute=m),
                args=["score"],
                id="score_daily",
                replace_existing=True,
            )

        # Draft
        if AGENT_AUTO_DRAFT:
            h, m = _parse_time(AGENT_SCHEDULE_DRAFT_UTC)
            sched.add_job(
                self._wrapped_job,
                trigger=CronTrigger(hour=h, minute=m),
                args=["draft"],
                id="draft_daily",
                replace_existing=True,
            )

        # Sequence
        if AGENT_AUTO_SEQUENCE:
            h, m = _parse_time(AGENT_SCHEDULE_SEQUENCE_UTC)
            sched.add_job(
                self._wrapped_job,
                trigger=CronTrigger(hour=h, minute=m),
                args=["sequence"],
                id="sequence_daily",
                replace_existing=True,
            )

        # Reply poll (placeholder until Phase 2)
        h, m = _parse_time(AGENT_SCHEDULE_REPLY_UTC)
        sched.add_job(
            self._wrapped_job,
            trigger=CronTrigger(hour=h, minute=m),
            args=["reply_poll"],
            id="reply_poll_daily",
            replace_existing=True,
        )

        # End-of-day snapshot
        h, m = _parse_time(AGENT_SCHEDULE_SNAPSHOT_UTC)
        sched.add_job(
            self._wrapped_job,
            trigger=CronTrigger(hour=h, minute=m),
            args=["snapshot"],
            id="snapshot_daily",
            replace_existing=True,
        )

    def _list_scheduled_jobs(self) -> list[str]:
        if not self.scheduler:
            return []
        return [j.id for j in self.scheduler.get_jobs()]

    # ------------------------------------------------------------------
    # Execution wrappers
    # ------------------------------------------------------------------

    def _wrapped_job(self, job_type: str):
        """Execute a job with logging and error isolation."""
        run_id = self.db_logger.start_run(job_type, triggered_by="scheduler")
        logger.info("[run=%s] Starting scheduled job: %s", run_id, job_type)
        try:
            result = JobRegistry.run(job_type, run_id, self.db_logger)
            logger.info("[run=%s] Job %s completed: %s", run_id, job_type, result.get("status"))
        except Exception as exc:
            logger.exception("[run=%s] Job %s crashed: %s", run_id, job_type, exc)
            self.db_logger.finish_run(run_id, status="failed", error_log=[str(exc)])

    def trigger_job(self, job_type: str, triggered_by: str = "manual") -> dict:
        """Trigger a job immediately (blocking)."""
        run_id = self.db_logger.start_run(job_type, triggered_by=triggered_by)
        logger.info("[run=%s] Manually triggering job: %s", run_id, job_type)
        try:
            result = JobRegistry.run(job_type, run_id, self.db_logger)
            return {"run_id": run_id, **result}
        except Exception as exc:
            logger.exception("[run=%s] Manual job %s crashed: %s", run_id, job_type, exc)
            self.db_logger.finish_run(run_id, status="failed", error_log=[str(exc)])
            return {"run_id": run_id, "status": "failed", "error": str(exc)}

    def run_full_pipeline_once(self, triggered_by: str = "manual") -> list[dict]:
        """Run scrape → enrich → score → draft → sequence sequentially.

        Useful for testing or back-filling. Each stage is still idempotent.
        """
        results = []
        for job_type in ["scrape", "enrich", "score", "draft", "sequence"]:
            results.append(self.trigger_job(job_type, triggered_by=triggered_by))
        return results

    def get_status(self) -> dict:
        """Return current scheduler status + today's stats."""
        jobs = []
        if self.scheduler:
            for j in self.scheduler.get_jobs():
                jobs.append({
                    "id": j.id,
                    "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
                })
        return {
            "enabled": AGENT_ENABLED,
            "running": self.is_running(),
            "scheduled_jobs": jobs,
            "today_stats": self.db_logger.get_today_stats(),
            "recent_runs": self.db_logger.get_recent_runs(limit=10),
        }


# Singleton instance --------------------------------------------------------
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
