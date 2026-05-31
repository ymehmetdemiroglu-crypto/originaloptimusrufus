"""Resilience primitives: retry decorator with exponential back-off and
a lightweight in-memory circuit breaker for external API calls.
"""
import asyncio
import functools
import time
from typing import Any, Callable, Optional, TypeVar

import logging

logger = logging.getLogger("acquisition_tool.resilience")

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Retry (sync + async)
# ---------------------------------------------------------------------------

def retry_call(
    max_attempts: int = 5,
    backoff_seconds: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator that retries a sync function on failure.

    Uses exponential back-off: delay = backoff * 2^(attempt-1).
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        raise
                    delay = backoff_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "Retry %s/%s in %.1fs after %s: %s",
                        attempt, max_attempts - 1, delay,
                        fn.__name__, exc,
                    )
                    time.sleep(delay)
            raise last_exc  # pragma: no cover
        return wrapper
    return decorator


def async_retry_call(
    max_attempts: int = 5,
    backoff_seconds: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator that retries an async coroutine on failure."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        raise
                    delay = backoff_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "Async retry %s/%s in %.1fs after %s: %s",
                        attempt, max_attempts - 1, delay,
                        fn.__name__, exc,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # pragma: no cover
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Lightweight circuit breaker (sync + async)
# ---------------------------------------------------------------------------

_FAILURE_THRESHOLD = 5
_RECOVERY_TIMEOUT_S = 30.0

_circuit_states: dict[str, dict] = {}


def _get_state(name: str) -> dict:
    return _circuit_states.setdefault(name, {
        "failures": 0,
        "last_failure": 0.0,
        "open": False,
    })


class CircuitOpenError(Exception):
    pass


def circuit_guard(name: str = "default"):
    """Decorator that trips a circuit breaker after repeated failures.

    When the circuit is OPEN, the decorated function raises `CircuitOpenError`
    immediately so callers can fall back or skip.  After `_RECOVERY_TIMEOUT_S`
    seconds the next call is allowed through as a probe.
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            state = _get_state(name)
            now = time.time()
            if state["open"]:
                if now - state["last_failure"] < _RECOVERY_TIMEOUT_S:
                    raise CircuitOpenError(f"Circuit {name} is OPEN — last failure {now - state['last_failure']:.0f}s ago")
                # Half-open — probe call
                state["open"] = False
                state["failures"] = 0
            try:
                result = fn(*args, **kwargs)
                state["failures"] = 0
                return result
            except Exception as exc:
                state["failures"] += 1
                state["last_failure"] = now
                if state["failures"] >= _FAILURE_THRESHOLD:
                    state["open"] = True
                    logger.error("Circuit %s OPEN after %s consecutive failures", name, state["failures"])
                raise exc
        return wrapper
    return decorator


def circuit_guard_async(name: str = "default"):
    """Async variant of `circuit_guard`."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> Any:
            state = _get_state(name)
            now = time.time()
            if state["open"]:
                if now - state["last_failure"] < _RECOVERY_TIMEOUT_S:
                    raise CircuitOpenError(f"Circuit {name} is OPEN")
                state["open"] = False
                state["failures"] = 0
            try:
                result = await fn(*args, **kwargs)
                state["failures"] = 0
                return result
            except Exception as exc:
                state["failures"] += 1
                state["last_failure"] = now
                if state["failures"] >= _FAILURE_THRESHOLD:
                    state["open"] = True
                    logger.error("Circuit %s OPEN after %s consecutive failures", name, state["failures"])
                raise exc
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Write-buffer fallback for Supabase outages
# ---------------------------------------------------------------------------

_pending_writes: list[dict] = []


def buffer_write(table: str, payload: dict, operation: str = "upsert"):
    """Queue a write that failed due to circuit OPEN so it can be replayed later."""
    _pending_writes.append({"table": table, "payload": payload, "operation": operation})
    logger.info("Buffered %s to %s (queue depth %s)", operation, table, len(_pending_writes))


def flush_writes(sb_client):
    """Attempt to replay buffered writes.  Must be called manually when the
    circuit appears healthy again.  Returns count successfully flushed."""
    flushed = 0
    while _pending_writes:
        item = _pending_writes.pop(0)
        try:
            if item["operation"] == "upsert":
                sb_client.table(item["table"]).upsert(item["payload"])
            else:
                sb_client.table(item["table"]).insert(item["payload"])
            flushed += 1
        except Exception as exc:
            _pending_writes.insert(0, item)
            logger.error("Flush failed for %s: %s", item["table"], exc)
            break
    if flushed:
        logger.info("Flushed %s buffered writes", flushed)
    return flushed
