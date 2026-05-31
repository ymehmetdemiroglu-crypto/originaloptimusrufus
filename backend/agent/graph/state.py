"""Shared state schemas for the Omni-Dashboard MAS."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class WorkspaceSnapshot(BaseModel):
    """Active workspace context shared across all agents."""

    asin: Optional[str] = None
    brand_key: Optional[str] = None
    client_id: Optional[str] = None
    category: Optional[str] = None


class PlanStep(BaseModel):
    """A single step in the supervisor's execution plan."""

    agent: Literal["listing", "competitor", "attribution", "outreach", "email", "admin", "synthesize"]
    task: str
    depends_on: List[int] = Field(default_factory=list)
    requires_human_approval: bool = False
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"


class HumanInterrupt(BaseModel):
    """Payload when the graph blocks for human input."""

    prompt: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    step_index: int


class AgentOutput(BaseModel):
    """Structured output from a single agent invocation."""

    agent: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: Optional[int] = None


class OmniState(BaseModel):
    """Root state object for the Omni-Dashboard supervisor graph.

    Designed to be checkpoint-friendly: all fields are Pydantic-serializable.
    """

    messages: List[Dict[str, Any]] = Field(default_factory=list)
    workspace: WorkspaceSnapshot = Field(default_factory=WorkspaceSnapshot)
    plan: List[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    agent_outputs: Dict[str, AgentOutput] = Field(default_factory=dict)
    pending_human_input: Optional[HumanInterrupt] = None
    errors: List[str] = Field(default_factory=list)
    completed: bool = False
    synthesis: Optional[str] = None

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Append a message to the conversation history."""
        msg = {"role": role, "content": content, **kwargs}
        self.messages.append(msg)

    def get_last_human_message(self) -> Optional[str]:
        """Return the content of the most recent human message."""
        for msg in reversed(self.messages):
            if msg.get("role") == "human":
                return msg.get("content")
        return None
