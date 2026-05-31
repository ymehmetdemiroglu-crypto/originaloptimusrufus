"""Optimus Rufus Autonomous Agent — Phase 1 Orchestrator.

This package provides scheduled, idempotent job execution for the outbound
acquisition pipeline. Jobs are logged to Supabase (`agent_runs`) and can be
triggered manually via API or automatically via APScheduler.
"""

from .orchestrator import AgentOrchestrator, get_orchestrator
from .jobs import JobRegistry
from .db_logger import AgentRunLogger

__all__ = ["AgentOrchestrator", "get_orchestrator", "JobRegistry", "AgentRunLogger"]
