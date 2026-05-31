"""Structured JSON logging for the acquisition pipeline.

All modules should obtain a logger via `get_logger(__name__)` so every log line
is emitted as JSON with component, timestamp, level, and message.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_OUTPUT = os.getenv("LOG_OUTPUT", "stdout")


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _setup() -> None:
    handler: logging.Handler
    if _LOG_OUTPUT == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(_LOG_OUTPUT, encoding="utf-8")
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger("acquisition_tool")
    root.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
    root.handlers = [handler]
    root.propagate = False


_setup()


def get_logger(name: str) -> logging.Logger:
    """Return a structured JSON logger prefixed under `acquisition_tool`."""
    return logging.getLogger(f"acquisition_tool.{name}")


def log_extra(**kwargs) -> dict:
    """Convenience helper to build the `extra` dict for structured fields."""
    return {"extra": kwargs}
