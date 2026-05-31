"""Supabase-backed logger for agent job executions."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from core.supabase import get_supabase

logger = logging.getLogger("agent")


class AgentRunLogger:
    """Create and update agent_runs rows in Supabase."""

    def __init__(self):
        self._sb = get_supabase()

    def start_run(
        self,
        run_type: str,
        triggered_by: str = "scheduler",
        metadata: Optional[dict] = None,
    ) -> str:
        """Insert a new agent_runs row and return its UUID."""
        run_id = str(uuid4())
        if not self._sb:
            logger.warning("Supabase not available — run will not be persisted.")
            return run_id

        try:
            self._sb.table("agent_runs").insert({
                "id": run_id,
                "run_type": run_type,
                "status": "running",
                "triggered_by": triggered_by,
                "metadata": json.dumps(metadata or {}),
            }).execute()
        except Exception as exc:
            logger.exception("Failed to insert agent_runs row: %s", exc)

        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        records_processed: int = 0,
        records_succeeded: int = 0,
        records_failed: int = 0,
        error_log: Optional[list] = None,
        metadata: Optional[dict] = None,
    ):
        """Update the agent_runs row with completion stats."""
        if not self._sb:
            return

        payload = {
            "status": status,
            "completed_at": datetime.utcnow().isoformat(),
            "records_processed": records_processed,
            "records_succeeded": records_succeeded,
            "records_failed": records_failed,
        }
        if error_log:
            payload["error_log"] = json.dumps(error_log[-50:])  # cap size
        if metadata:
            payload["metadata"] = json.dumps(metadata)

        try:
            self._sb.table("agent_runs").update(payload).eq("id", run_id).execute()
        except Exception as exc:
            logger.exception("Failed to update agent_runs row %s: %s", run_id, exc)

    def log_error(self, run_id: str, message: str):
        """Append an error message to the run's error_log."""
        if not self._sb:
            return
        try:
            # Fetch existing log
            res = self._sb.table("agent_runs").select("error_log").eq("id", run_id).limit(1).execute()
            existing = []
            if res.data and res.data[0].get("error_log"):
                try:
                    existing = json.loads(res.data[0]["error_log"])
                except Exception:
                    existing = []
            existing.append({"ts": datetime.utcnow().isoformat(), "msg": message})
            self._sb.table("agent_runs").update({
                "error_log": json.dumps(existing[-50:]),
            }).eq("id", run_id).execute()
        except Exception as exc:
            logger.exception("Failed to log error for run %s: %s", run_id, exc)

    def get_recent_runs(self, run_type: Optional[str] = None, limit: int = 20) -> list[dict]:
        """Return recent agent runs for the dashboard."""
        if not self._sb:
            return []
        try:
            q = self._sb.table("agent_runs").select("*").order("started_at", desc=True).limit(limit)
            if run_type:
                q = q.eq("run_type", run_type)
            res = q.execute()
            return [dict(r) for r in (res.data or [])]
        except Exception as exc:
            logger.exception("Failed to fetch recent runs: %s", exc)
            return []

    def get_last_successful_run(self, run_type: str) -> Optional[datetime]:
        """Return the completed_at timestamp of the most recent successful run."""
        if not self._sb:
            return None
        try:
            res = (
                self._sb.table("agent_runs")
                .select("completed_at")
                .eq("run_type", run_type)
                .eq("status", "success")
                .order("completed_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and res.data[0].get("completed_at"):
                ts = res.data[0]["completed_at"]
                # Parse ISO string
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception as exc:
            logger.exception("Failed to fetch last successful run: %s", exc)
        return None

    def get_today_stats(self) -> dict:
        """Return aggregate stats for today's runs."""
        if not self._sb:
            return {}
        try:
            from datetime import date
            today = date.today().isoformat()
            res = (
                self._sb.table("agent_runs")
                .select("run_type, status, records_succeeded")
                .gte("started_at", f"{today}T00:00:00")
                .execute()
            )
            rows = res.data or []
            stats = {
                "total_runs": len(rows),
                "successful": sum(1 for r in rows if r.get("status") == "success"),
                "failed": sum(1 for r in rows if r.get("status") == "failed"),
                "total_processed": sum(r.get("records_succeeded", 0) or 0 for r in rows),
            }
            return stats
        except Exception as exc:
            logger.exception("Failed to fetch today stats: %s", exc)
            return {}
