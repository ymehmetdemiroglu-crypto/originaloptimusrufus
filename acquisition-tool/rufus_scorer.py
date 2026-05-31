"""Rufus Optimization Scorer — LLM-powered listing analysis.

Supports both v1 (4-axis, 0-100) and v2 (6-axis, 0-120) scoring.
v2 adds:
  - Visual & Structured Content axis
  - Competitive Relativity axis (benchmarked against top 3 competitors)
  - Category-aware attribute detection
  - Severity ratings on weaknesses

Results stored in DB: rufus_score, per-axis scores, rufus_citation_probability,
rufus_top_weaknesses (JSON array), rufus_summary, competitive_summary.
"""
import asyncio
import json
import os
import re
import threading

import httpx
from openai import OpenAI

import config
import db
from models import Prospect
import resilience

# Optional backend integration for richer, cheaper LLM prompts
if config.USE_BACKEND_SCORING:
    import backend_client as _backend
else:
    _backend = None  # type: ignore


_client = None
_client_lock = threading.Lock()

# Load from external file so prompt edits don't require code redeploy.
SYSTEM_PROMPT_V1 = config.load_prompt(config.RUFUS_PROMPT_PATH)
SYSTEM_PROMPT_V2 = config.load_prompt(config.RUFUS_V2_PROMPT_PATH)

# Toggle v2 scoring (6-axis with competitors)
USE_V2 = os.getenv("USE_RUFUS_V2", "true").lower() == "true"


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)
    return _client


def _build_prompt(p: Prospect, competitors: list[dict] | None = None, backend_analysis: dict | None = None) -> str:
    comp_block = ""
    if competitors:
        comp_block = "\n\nTOP COMPETITORS (for benchmarking):\n"
        for i, c in enumerate(competitors[:3], 1):
            comp_block += (
                f"\n{i}. {c.get('competitor_brand', 'Unknown')} — {c.get('title', '')[:80]}\n"
                f"   Bullets: {c.get('bullet_count', 0)} | Images: {c.get('image_count', 0)} | "
                f"Q&A: {c.get('qa_count', 0)} | A+: {'yes' if c.get('has_a_plus') else 'no'} | "
                f"Rating: {c.get('rating', '—')} ({c.get('review_count', 0)} reviews)\n"
                f"   Bullet text: {c.get('bullets', '')[:500]}\n"
            )

    backend_block = ""
    if backend_analysis:
        overall = backend_analysis.get("overall_score", "N/A")
        relations = backend_analysis.get("relations", [])
        safety = backend_analysis.get("keyword_safety", "N/A")
        backend_block = f"""\n\nBACKEND COSMO SEMANTIC ANALYSIS (pre-computed embedding-based scores):
- Overall COSMO readiness: {overall}/100
- Lexical keyword safety: {safety}
- Relation coverage (embeddings detected these semantic signals):
"""
        for r in relations:
            grade = r.get("coverage_grade", "?")
            conf = r.get("confidence_score", 0)
            signals = ", ".join(r.get("detected_signals", [])[:3]) or "none"
            backend_block += f"  • {r.get('relation', '')} ({r.get('cluster', '')}) — grade {grade}, confidence {conf:.0%}, signals: {signals}\n"

    return f"""Score this Amazon listing for Rufus AI optimization.

ASIN: {p.asin}
Brand: {p.brand}
Category: {p.category}
Price: ${p.listing_price or 'unknown'}
Rating: {p.listing_rating or 'unknown'} stars ({p.listing_review_count or 0} reviews)

TITLE ({len(p.post_title or '')} chars):
{p.post_title}

BULLETS ({p.bullet_count or 0} bullets found):
{p.post_body[:2500] if p.post_body else '(none)'}

LISTING METADATA:
- Image count: {p.image_count or 0}
- Has A+ Content: {p.has_a_plus}
- Q&A count: {p.qa_count or 0}
- Rule-based weakness signals already flagged: {p.weakness_signals or 'none'}
- Quality signals: {p.quality_signals or 'none'}{comp_block}{backend_block}

Score all axes and output the JSON object exactly as specified in your instructions."""


def _extract_json(text: str) -> dict:
    """Parse JSON, stripping any markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize_scores(result: dict, use_v2: bool) -> dict:
    """Normalize v1 or v2 scores into a consistent structure."""
    if use_v2:
        overall = (
            result.get("intent_alignment", 0)
            + result.get("attribute_density", 0)
            + result.get("conversational_readability", 0)
            + result.get("qa_coverage", 0)
            + result.get("visual_structured_content", 0)
            + result.get("competitive_relativity", 0)
        )
        result["overall_score"] = overall
        result["max_possible"] = 120
    else:
        overall = (
            result.get("intent_alignment", 0)
            + result.get("attribute_density", 0)
            + result.get("conversational_readability", 0)
            + result.get("qa_coverage", 0)
        )
        result["overall_score"] = overall
        result["max_possible"] = 100
    return result


def score_listing(p: Prospect, save: bool = True, use_v2: bool | None = None) -> dict:
    """Score a single listing for Rufus optimization. Returns the full result dict."""
    if use_v2 is None:
        use_v2 = USE_V2

    client = _get_client()
    system_prompt = SYSTEM_PROMPT_V2 if use_v2 else SYSTEM_PROMPT_V1

    competitors = db.get_competitors(p.brand_key) if p.brand_key else []

    # Optional: enrich prompt with backend COSMO analysis
    backend_analysis = None
    if _backend and config.USE_BACKEND_SCORING and p.asin:
        backend_analysis = _backend.analyze_listing(p.asin)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_prompt(p, competitors=competitors if use_v2 else None, backend_analysis=backend_analysis)},
    ]

    max_tokens = 1200 if use_v2 else 900

    response = client.chat.completions.create(
        model=config.OPENROUTER_MODEL,
        max_tokens=max_tokens,
        messages=messages,
    )
    raw = (response.choices[0].message.content or "").strip()

    try:
        if not raw:
            raise ValueError("empty response")
        result = _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        retry_messages = messages[:-1] + [{
            "role": "user",
            "content": messages[-1]["content"] + "\n\nRespond with valid JSON only, no markdown.",
        }]
        response = client.chat.completions.create(
            model=config.OPENROUTER_MODEL,
            max_tokens=max_tokens,
            messages=retry_messages,
        )
        raw = (response.choices[0].message.content or "").strip()
        result = _extract_json(raw)

    result = _normalize_scores(result, use_v2)

    if save:
        _persist_rufus_score(p.id, result, use_v2)
    return result


def _persist_rufus_score(prospect_id: str, result: dict, use_v2: bool):
    """Persist Rufus score to DB, handling both v1 and v2 field sets."""
    kwargs = {
        "prospect_id": prospect_id,
        "rufus_score": result.get("overall_score", 0),
        "intent_alignment_score": result.get("intent_alignment", 0),
        "attribute_density_score": result.get("attribute_density", 0),
        "conversational_readability_score": result.get("conversational_readability", 0),
        "qa_coverage_score": result.get("qa_coverage", 0),
        "rufus_citation_probability": result.get("rufus_citation_probability", "low"),
        "rufus_top_weaknesses": json.dumps(result.get("top_weaknesses", [])),
        "rufus_summary": result.get("summary", ""),
    }
    if use_v2:
        kwargs["visual_structured_content_score"] = result.get("visual_structured_content", 0)
        kwargs["competitive_relativity_score"] = result.get("competitive_relativity", 0)
        kwargs["competitive_summary"] = result.get("competitive_summary", "")

    db.set_rufus_score(**kwargs)


# ---------------------------------------------------------------------------
# Back-compat alias populated after definition below
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Async scoring — fan out across the LLM concurrency semaphore
# ---------------------------------------------------------------------------

OPENROUTER_CHAT_URL = f"{config.OPENROUTER_BASE_URL}/chat/completions"


def _openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def _score_one_async(
    p: Prospect,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    save: bool = True,
    use_v2: bool | None = None,
) -> dict | None:
    """Run one Rufus score over the wire. Single retry on JSON parse failure."""
    if use_v2 is None:
        use_v2 = USE_V2

    system_prompt = SYSTEM_PROMPT_V2 if use_v2 else SYSTEM_PROMPT_V1
    competitors = db.get_competitors(p.brand_key) if p.brand_key and use_v2 else []

    # Optional: enrich prompt with backend COSMO analysis
    backend_analysis = None
    if _backend and config.USE_BACKEND_SCORING and p.asin:
        backend_analysis = _backend.analyze_listing(p.asin)

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_prompt(p, competitors=competitors, backend_analysis=backend_analysis)},
    ]

    max_tokens = 1200 if use_v2 else 900

    @resilience.async_retry_call(max_attempts=5, backoff_seconds=3.0, exceptions=(httpx.HTTPStatusError, httpx.RequestError))
    async def _call(messages: list[dict]) -> str:
        async with semaphore:
            resp = await client.post(
                OPENROUTER_CHAT_URL,
                headers=_openrouter_headers(),
                json={
                    "model": config.OPENROUTER_MODEL,
                    "max_tokens": max_tokens,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip()

    try:
        raw = await _call(base_messages)
        if not raw:
            raise ValueError("empty response")
        result = _extract_json(raw)
    except (json.JSONDecodeError, ValueError, httpx.HTTPError):
        retry = base_messages[:-1] + [{
            "role": "user",
            "content": base_messages[-1]["content"] + "\n\nRespond with valid JSON only, no markdown.",
        }]
        try:
            raw = await _call(retry)
            result = _extract_json(raw)
        except Exception as e:
            return {"_error": str(e), "prospect_id": p.id}

    result = _normalize_scores(result, use_v2)
    result["_prospect"] = p

    if save:
        _persist_rufus_score(p.id, result, use_v2)
    return result


async def score_all_async(
    prospects: list[Prospect],
    console=None,
    semaphore: asyncio.Semaphore | None = None,
    use_v2: bool | None = None,
) -> int:
    """Score all prospects concurrently. Returns count successfully scored."""
    if not prospects:
        return 0
    if use_v2 is None:
        use_v2 = USE_V2

    sem = semaphore or asyncio.Semaphore(config.MAX_LLM_CONCURRENCY)
    scored = 0
    async with httpx.AsyncClient(timeout=config.LLM_REQUEST_TIMEOUT_S) as client:
        results = await asyncio.gather(
            *(_score_one_async(p, client, sem, save=True, use_v2=use_v2) for p in prospects),
            return_exceptions=True,
        )
    for p, result in zip(prospects, results):
        if isinstance(result, Exception):
            if console:
                console.print(f"  [red]Error scoring {p.id}: {result}[/red]")
            continue
        if not result or result.get("_error"):
            if console:
                console.print(f"  [red]Error scoring {p.id}: {result.get('_error') if result else 'no result'}[/red]")
            continue
        scored += 1
        prob = result.get("rufus_citation_probability", "?")
        colour = {"high": "green", "medium": "yellow", "low": "red"}.get(prob, "white")
        axis_str = (
            f"IA={result.get('intent_alignment',0)} "
            f"AD={result.get('attribute_density',0)} "
            f"CR={result.get('conversational_readability',0)} "
            f"QA={result.get('qa_coverage',0)}"
        )
        if use_v2:
            axis_str += (
                f" VC={result.get('visual_structured_content',0)} "
                f"CMP={result.get('competitive_relativity',0)}"
            )
        if console:
            console.print(
                f"  [dim]{p.asin}[/dim] {p.brand or '?'}  "
                f"[bold]{result['overall_score']}/{result.get('max_possible', 100)}[/bold]  "
                f"[{colour}]{prob}[/{colour}]  {axis_str}"
            )
    return scored


def score_all(prospects: list[Prospect], console=None, use_v2: bool | None = None) -> int:
    """Score all prospects in parallel via async fan-out. Returns count successfully scored."""
    if not prospects:
        return 0
    return asyncio.run(score_all_async(prospects, console=console, use_v2=use_v2))
