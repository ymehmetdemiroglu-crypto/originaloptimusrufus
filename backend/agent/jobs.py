"""Idempotent job functions for the autonomous acquisition pipeline.

Each job wraps an acquisition_tool CLI command via subprocess. Jobs are
idempotent because the underlying CLI commands query the DB for rows in
their prior stage and only process what hasn't been advanced yet.

All jobs accept a `run_id` and use `AgentRunLogger` to persist progress.
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.config import (
    ACQUISITION_TOOL_DIR,
    AGENT_SCRAPE_CATEGORIES,
    AGENT_SCRAPE_CATEGORIES_PER_RUN,
    AGENT_SCRAPE_LIMIT_PER_CATEGORY,
    JOB_TIMEOUT_DRAFT,
    JOB_TIMEOUT_ENRICH,
    JOB_TIMEOUT_REPLY,
    JOB_TIMEOUT_SCORE,
    JOB_TIMEOUT_SCRAPE,
    JOB_TIMEOUT_SEQUENCE,
    SLACK_WEBHOOK_URL,
)
from agent.db_logger import AgentRunLogger

logger = logging.getLogger("agent.jobs")


def _notify_slack(message: str):
    """Fire-and-forget Slack notification if webhook is configured."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        import httpx
        httpx.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    except Exception:
        pass


def _run_acq_cmd(
    args: list[str],
    timeout: int = 600,
    run_id: Optional[str] = None,
    db_logger: Optional[AgentRunLogger] = None,
) -> tuple[int, str, str]:
    """Execute a command inside the acquisition_tool directory.

    Returns (returncode, stdout, stderr). Logs errors to the run row.
    """
    cmd = [sys.executable, "main.py"] + args
    cwd = str(ACQUISITION_TOOL_DIR) if ACQUISITION_TOOL_DIR.exists() else None

    logger.info("[run=%s] Executing: %s (cwd=%s)", run_id, " ".join(cmd), cwd)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"Command timed out after {timeout}s: {' '.join(args)}"
        logger.error(msg)
        if db_logger and run_id:
            db_logger.log_error(run_id, msg)
        return -1, "", msg
    except Exception as exc:
        msg = f"Subprocess error: {exc}"
        logger.exception(msg)
        if db_logger and run_id:
            db_logger.log_error(run_id, msg)
        return -1, "", msg

    if proc.returncode != 0:
        err_summary = proc.stderr[-800:] if proc.stderr else "(no stderr)"
        msg = f"Exit code {proc.returncode} for '{' '.join(args)}': {err_summary}"
        logger.error(msg)
        if db_logger and run_id:
            db_logger.log_error(run_id, msg)
    else:
        logger.info("[run=%s] Command succeeded: %s", run_id, " ".join(args))

    return proc.returncode, proc.stdout, proc.stderr


def _pick_categories_for_today() -> list[str]:
    """Rotate through categories so we don't scrape the same ones every day.

    Uses a simple day-based rotation. Can be enhanced later to track per-category
    freshness in the DB.
    """
    if not AGENT_SCRAPE_CATEGORIES:
        return []

    # Use day-of-year to rotate starting index
    day_index = datetime.utcnow().timetuple().tm_yday
    count = AGENT_SCRAPE_CATEGORIES_PER_RUN
    total = len(AGENT_SCRAPE_CATEGORIES)

    picked = []
    for i in range(count):
        idx = (day_index + i) % total
        picked.append(AGENT_SCRAPE_CATEGORIES[idx])
    return picked


# ===========================================================================
# Individual jobs
# ===========================================================================

def run_scrape_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Scrape Amazon listings for rotated categories.

    Idempotent: the acquisition tool skips ASINs already in the DB.
    """
    categories = _pick_categories_for_today()
    if not categories:
        db_logger.log_error(run_id, "No categories configured for scraping.")
        return {"status": "failed", "reason": "no_categories", "records_processed": 0}

    total_inserted = 0
    errors = []

    for category in categories:
        rc, stdout, stderr = _run_acq_cmd(
            ["rufus-audit", category, f"--limit={AGENT_SCRAPE_LIMIT_PER_CATEGORY}"],
            timeout=JOB_TIMEOUT_SCRAPE,
            run_id=run_id,
            db_logger=db_logger,
        )
        if rc == 0:
            # Try to parse how many were inserted from stdout
            inserted = 0
            for line in stdout.splitlines():
                if "inserted" in line.lower() or "upserted" in line.lower():
                    # Heuristic: look for a number
                    import re
                    nums = re.findall(r"\d+", line)
                    if nums:
                        inserted = max(inserted, int(nums[-1]))
            total_inserted += inserted
        else:
            errors.append(f"Category '{category}' failed with rc={rc}")

    status = "success" if not errors else "partial"
    db_logger.finish_run(
        run_id,
        status=status,
        records_processed=total_inserted,
        records_succeeded=total_inserted,
        records_failed=len(errors),
        error_log=errors,
        metadata={"categories": categories},
    )
    return {
        "status": status,
        "categories": categories,
        "records_processed": total_inserted,
        "errors": errors,
    }


def run_enrich_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Enrich WEAK_BRAND rows with Apollo decision-makers.

    Idempotent: Apollo match is skipped if contact already exists.
    """
    rc, stdout, stderr = _run_acq_cmd(
        ["auto-enrich"],
        timeout=JOB_TIMEOUT_ENRICH,
        run_id=run_id,
        db_logger=db_logger,
    )

    # Heuristic: count how many brands moved to CONTACT_ENRICHED
    enriched = 0
    for line in stdout.splitlines():
        if "enriched" in line.lower() or "contact_enriched" in line.lower():
            import re
            nums = re.findall(r"\d+", line)
            if nums:
                enriched = max(enriched, int(nums[-1]))

    status = "success" if rc == 0 else "failed"
    db_logger.finish_run(
        run_id,
        status=status,
        records_processed=enriched,
        records_succeeded=enriched if rc == 0 else 0,
        records_failed=0 if rc == 0 else 1,
        metadata={"command": "auto-enrich"},
    )
    return {"status": status, "enriched": enriched}


def run_score_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """LLM-Rufus-score enriched anchor ASINs.

    Idempotent: only scores anchors where rufus_score IS NULL.
    """
    rc, stdout, stderr = _run_acq_cmd(
        ["rufus-score-enriched"],
        timeout=JOB_TIMEOUT_SCORE,
        run_id=run_id,
        db_logger=db_logger,
    )

    scored = 0
    for line in stdout.splitlines():
        if "scored" in line.lower():
            import re
            nums = re.findall(r"\d+", line)
            if nums:
                scored = max(scored, int(nums[-1]))

    status = "success" if rc == 0 else "failed"
    db_logger.finish_run(
        run_id,
        status=status,
        records_processed=scored,
        records_succeeded=scored if rc == 0 else 0,
        records_failed=0 if rc == 0 else 1,
        metadata={"command": "rufus-score-enriched"},
    )
    return {"status": status, "scored": scored}


def run_draft_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Generate 5-step cold email sequences for CONTACT_ENRICHED brands.

    Idempotent: skips brands already in EMAIL_DRAFTED or beyond.
    """
    rc, stdout, stderr = _run_acq_cmd(
        ["draft-emails"],
        timeout=JOB_TIMEOUT_DRAFT,
        run_id=run_id,
        db_logger=db_logger,
    )

    drafted = 0
    for line in stdout.splitlines():
        if "drafted" in line.lower() or "sequence" in line.lower():
            import re
            nums = re.findall(r"\d+", line)
            if nums:
                drafted = max(drafted, int(nums[-1]))

    status = "success" if rc == 0 else "failed"
    db_logger.finish_run(
        run_id,
        status=status,
        records_processed=drafted,
        records_succeeded=drafted if rc == 0 else 0,
        records_failed=0 if rc == 0 else 1,
        metadata={"command": "draft-emails"},
    )
    return {"status": status, "drafted": drafted}


def run_sequence_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Enroll EMAIL_DRAFTED brands into Apollo sequences.

    Idempotent: Apollo contact creation is upsert-based; sequence enrollment
    is idempotent within Apollo.
    """
    # Check daily limit
    today_stats = db_logger.get_today_stats()
    sequenced_today = today_stats.get("total_processed", 0)
    from agent.config import AGENT_MAX_DAILY_SEQUENCES
    if sequenced_today >= AGENT_MAX_DAILY_SEQUENCES:
        msg = f"Daily sequence limit reached ({sequenced_today}/{AGENT_MAX_DAILY_SEQUENCES}). Skipping."
        logger.info(msg)
        db_logger.finish_run(run_id, status="success", metadata={"skipped": True, "reason": msg})
        return {"status": "skipped", "reason": msg}

    rc, stdout, stderr = _run_acq_cmd(
        ["apollo-sequence"],
        timeout=JOB_TIMEOUT_SEQUENCE,
        run_id=run_id,
        db_logger=db_logger,
    )

    enrolled = 0
    for line in stdout.splitlines():
        if "enrolled" in line.lower() or "synced" in line.lower():
            import re
            nums = re.findall(r"\d+", line)
            if nums:
                enrolled = max(enrolled, int(nums[-1]))

    status = "success" if rc == 0 else "failed"
    db_logger.finish_run(
        run_id,
        status=status,
        records_processed=enrolled,
        records_succeeded=enrolled if rc == 0 else 0,
        records_failed=0 if rc == 0 else 1,
        metadata={"command": "apollo-sequence"},
    )

    if enrolled > 0 and status == "success":
        _notify_slack(f"🚀 Apollo Sequence: {enrolled} prospects enrolled today.")

    return {"status": status, "enrolled": enrolled}


def run_reply_poll_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Poll for inbound replies and classify them.

    Phase 1: classification only; auto-send comes in Phase 2.
    For now, this job is a placeholder that logs a reminder.
    """
    # TODO: Integrate with Apollo reply polling or email IMAP in Phase 2
    msg = "Reply polling not yet automated. Use backend reply_poller.py manually."
    logger.info(msg)
    db_logger.finish_run(
        run_id,
        status="success",
        metadata={"note": msg},
    )
    return {"status": "success", "note": msg}


def run_pipeline_snapshot_job(run_id: str, db_logger: AgentRunLogger) -> dict:
    """Capture end-of-day pipeline stage counts for trend analysis."""
    sb = db_logger._sb
    if not sb:
        db_logger.finish_run(run_id, status="failed", metadata={"reason": "no_supabase"})
        return {"status": "failed", "reason": "no_supabase"}

    try:
        # Get stage counts from brands
        res = sb.table("brands").select("stage").execute()
        rows = res.data or []
        from collections import Counter
        counts = Counter(r.get("stage", "UNKNOWN") for r in rows)

        from datetime import date
        today = date.today().isoformat()

        for stage, count in counts.items():
            sb.table("pipeline_snapshots").upsert({
                "snapshot_date": today,
                "stage": stage,
                "count": count,
            }, on_conflict="snapshot_date,stage").execute()

        db_logger.finish_run(
            run_id,
            status="success",
            records_processed=len(counts),
            metadata={"stages": dict(counts)},
        )
        return {"status": "success", "stages": dict(counts)}
    except Exception as exc:
        db_logger.finish_run(run_id, status="failed", error_log=[str(exc)])
        return {"status": "failed", "error": str(exc)}


# ===========================================================================
# Job registry
# ===========================================================================

class JobRegistry:
    """Maps job type names to callable functions."""

    JOBS: dict[str, callable] = {
        "scrape": run_scrape_job,
        "enrich": run_enrich_job,
        "score": run_score_job,
        "draft": run_draft_job,
        "sequence": run_sequence_job,
        "reply_poll": run_reply_poll_job,
        "snapshot": run_pipeline_snapshot_job,
    }

    @classmethod
    def run(cls, job_type: str, run_id: str, db_logger: AgentRunLogger) -> dict:
        if job_type not in cls.JOBS:
            raise ValueError(f"Unknown job type: {job_type}")
        return cls.JOBS[job_type](run_id, db_logger)

    @classmethod
    def list_jobs(cls) -> list[str]:
        return list(cls.JOBS.keys())
