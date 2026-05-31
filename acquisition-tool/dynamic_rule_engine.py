"""Dynamic rule engine for cold-email anti-template guards.

Rules are loaded from an external JSON file so they can be updated without
code redeploy. The module caches in memory and provides a reload function.
"""
import json
from pathlib import Path
from typing import Optional

import config

_RULES_CACHE: Optional[dict] = None


def load_rules(path: str | None = None) -> dict:
    """Load banned-phrase rules from JSON. Caches in memory."""
    global _RULES_CACHE
    if path is None:
        path = config.COLD_EMAIL_RULES_PATH
    if _RULES_CACHE is not None and _RULES_CACHE.get("_path") == path:
        return _RULES_CACHE
    full = Path(path)
    if not full.is_absolute():
        full = Path(__file__).parent.resolve() / path
    with full.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["_path"] = path
    _RULES_CACHE = data
    return data


def reload_rules(path: str | None = None) -> dict:
    """Force re-read of rules from disk."""
    global _RULES_CACHE
    _RULES_CACHE = None
    return load_rules(path)


def subject_banned_phrases() -> list[str]:
    return load_rules().get("subject_banned_phrases", [])


def body_banned_phrases() -> list[str]:
    return load_rules().get("body_banned_phrases", [])


def forbidden_openers() -> list[str]:
    return load_rules().get("forbidden_openers", [])


def max_5gram_overlap() -> float:
    return load_rules().get("max_5gram_overlap", 0.25)


def word_count_tolerance() -> float:
    return load_rules().get("word_count_tolerance", 0.2)


def corpus_size() -> int:
    return load_rules().get("corpus_size", 50)
