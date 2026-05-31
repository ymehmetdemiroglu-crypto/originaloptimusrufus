"""Thin HTTP client for the Rufus/COSMO Optimization Engine backend.

All calls are resilient: if the backend is unreachable or returns an error,
the client returns None/empty dicts and logs a warning. This ensures the
first-client pipeline never breaks when the backend is down.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx

import config

_BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
_BACKEND_API_KEY: str = os.getenv("BACKEND_API_KEY", "")
_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if _BACKEND_API_KEY:
        h["Authorization"] = f"Bearer {_BACKEND_API_KEY}"
    return h


def _warn(msg: str):
    """Print a concise warning (no rich console here to avoid circular imports)."""
    print(f"[backend-client] {msg}")


def health_check() -> dict[str, Any] | None:
    """Quick liveness probe. Returns dict or None if backend is down."""
    try:
        r = httpx.get(f"{_BACKEND_URL}/", headers=_headers(), timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _warn(f"backend unreachable ({_BACKEND_URL}): {e}")
        return None


def upsert_listing(asin: str, title: str, bullets: list[str], description: str = "", brand: str = "") -> bool:
    """Push listing data into the backend store so subsequent analyzes work.

    The backend exposes POST /api/listings which upserts into the in-memory store.
    Returns True on success.
    """
    payload = {
        "asin": asin,
        "title": title,
        "bullets": bullets,
        "description": description,
        "brand": brand,
    }
    try:
        r = httpx.post(
            f"{_BACKEND_URL}/api/listings",
            headers=_headers(),
            json=payload,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        _warn(f"failed to upsert listing {asin}: {e}")
        return False


def analyze_listing(asin: str) -> dict[str, Any] | None:
    """Call /api/analyze → COSMO readiness score, gap alerts, lexical safety."""
    try:
        r = httpx.post(
            f"{_BACKEND_URL}/api/analyze",
            headers=_headers(),
            json={"asin": asin},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _warn(f"analyze failed for {asin}: {e}")
        return None


def analyze_competitors(asin: str) -> dict[str, Any] | None:
    """Call /api/competitors → competitor profiles + gap opportunities + positioning summary."""
    try:
        r = httpx.post(
            f"{_BACKEND_URL}/api/competitors",
            headers=_headers(),
            json={"asin": asin},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _warn(f"competitor analysis failed for {asin}: {e}")
        return None


def get_qa_seeds(asin: str, target_relations: list[str] | None = None) -> dict[str, Any] | None:
    """Call /api/qa/seed → suggested Q&A pairs targeting weak relations."""
    payload: dict[str, Any] = {"asin": asin}
    if target_relations:
        payload["target_relations"] = target_relations
    try:
        r = httpx.post(
            f"{_BACKEND_URL}/api/qa/seed",
            headers=_headers(),
            json=payload,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _warn(f"qa-seed failed for {asin}: {e}")
        return None


def run_full_audit(
    asin: str,
    title: str = "",
    bullets: list[str] | None = None,
    description: str = "",
    brand: str = "",
) -> dict[str, Any]:
    """End-to-end backend-powered audit.

    1. Upsert listing data (so backend knows about it)
    2. Run analyze + competitors + qa_seed in parallel
    3. Return a unified dict with all backend insights
    """
    bullets = bullets or []

    # If we have listing text, push it first so the backend can analyze it
    if title or bullets:
        upsert_listing(asin, title, bullets, description, brand)

    # Run the three analysis calls sequentially (backend is local, so fast)
    analysis = analyze_listing(asin)
    competitors = analyze_competitors(asin)

    # Derive weak relations from analysis for targeted Q&A seeding
    target_relations: list[str] | None = None
    if analysis:
        target_relations = [
            r["relation"]
            for r in analysis.get("relations", [])
            if r.get("confidence_score", 1.0) < 0.5
        ][:5]

    qa = get_qa_seeds(asin, target_relations=target_relations if target_relations else None)

    return {
        "asin": asin,
        "brand": brand,
        "backend_available": analysis is not None,
        "analysis": analysis or {},
        "competitors": competitors or {},
        "qa_seeds": qa or {},
        "generated_at": datetime.utcnow().isoformat(),
    }


def format_audit_markdown(audit: dict[str, Any]) -> str:
    """Convert a unified backend audit dict into a Markdown brief suitable for Loom reference."""
    asin = audit.get("asin", "")
    brand = audit.get("brand", "")
    analysis = audit.get("analysis", {}) or {}
    competitors = audit.get("competitors", {}) or {}
    qa = audit.get("qa_seeds", {}) or {}

    lines: list[str] = [
        f"# Backend Rufus/COSMO Audit — {brand or asin}",
        "",
        f"**ASIN:** `{asin}`  ",
        f"**Generated:** {audit.get('generated_at', '')}",
        "",
    ]

    if not audit.get("backend_available"):
        lines.extend([
            "> ⚠️ **Backend unavailable** — COSMO analysis could not be generated.",
            "> Ensure `BACKEND_URL` is set and the backend server is running.",
            "",
        ])
        return "\n".join(lines)

    # Overall score
    overall = analysis.get("overall_score", "N/A")
    grade = "A" if isinstance(overall, int) and overall >= 80 else "B" if isinstance(overall, int) and overall >= 65 else "C" if isinstance(overall, int) and overall >= 50 else "D"
    lines.extend([
        "## COSMO Readiness Score",
        "",
        f"**Score:** {overall}/100  ",
        f"**Grade:** {grade}  ",
        f"**Keyword Safety:** {analysis.get('keyword_safety', 'N/A')}  ",
        f"**Embedding Dimensions:** {analysis.get('embedding_dimensions', 'N/A')}",
        "",
    ])

    # Safety checks
    safety = analysis.get("safety_checks", [])
    if safety:
        lines.extend(["### Safety Checks", ""])
        for check in safety:
            icon = "✅" if check.get("status") == "safe" else "⚠️" if check.get("status") == "caution" else "❌"
            lines.append(f"{icon} **{check.get('label', '')}** — {check.get('detail', '')}")
        lines.append("")

    # Semantic relations (gap alerts)
    relations = analysis.get("relations", [])
    if relations:
        lines.extend(["## Semantic Relation Coverage", ""])
        lines.append("| Relation | Cluster | Confidence | Grade | Signals |")
        lines.append("|----------|---------|------------|-------|---------|")
        for r in relations:
            signals = ", ".join(r.get("detected_signals", [])[:3])
            lines.append(
                f"| {r.get('relation', '')} | {r.get('cluster', '')} | "
                f"{r.get('confidence_score', 0):.0%} | {r.get('coverage_grade', '')} | {signals} |"
            )
        lines.append("")

    # Competitor analysis
    comp_profiles = competitors.get("competitor_profiles", [])
    gaps = competitors.get("gap_opportunities", [])
    positioning = competitors.get("positioning_summary", {})
    if comp_profiles or gaps:
        lines.extend(["## Competitor Landscape", ""])
        avg_sim = positioning.get("average_competitor_similarity", 0)
        lines.append(f"**Average Competitor Similarity:** {avg_sim:.0%}")
        lines.append("")
        if comp_profiles:
            lines.append("| ASIN | Title | Similarity | Price | Rating |")
            lines.append("|------|-------|------------|-------|--------|")
            for cp in comp_profiles[:5]:
                lines.append(
                    f"| `{cp.get('asin', '')}` | {cp.get('title', '')[:50]} | "
                    f"{cp.get('similarity', 0):.0%} | {cp.get('price', '—')} | {cp.get('rating', '—')} |"
                )
            lines.append("")
        if gaps:
            lines.extend(["### Gap Opportunities", ""])
            for g in gaps[:5]:
                lines.append(
                    f"- **{g.get('description', '')}**  \n"
                    f"  Competitors covering: {', '.join(g.get('competitors_covering', []))}  \n"
                    f"  Opportunity score: {g.get('opportunity_score', 0):.0%}  \n"
                    f"  Suggested content: *{g.get('suggested_content', '')}*  \n"
                    f"  Estimated traffic impact: {g.get('estimated_traffic_impact', 'N/A')}"
                )
            lines.append("")

    # Q&A Seeds
    seeds = qa.get("seeds", [])
    if seeds:
        lines.extend(["## Suggested Q&A Seeds", ""])
        for s in seeds[:5]:
            lines.append(
                f"**Q:** {s.get('question', '')}  \n"
                f"**A:** {s.get('answer', '')}  \n"
                f"*Target relation: {s.get('target_relation', 'N/A')}*")
            lines.append("")

    lines.append("---")
    lines.append("*Generated by Optimus Rufus Backend/COSMO Engine*")
    return "\n".join(lines)
