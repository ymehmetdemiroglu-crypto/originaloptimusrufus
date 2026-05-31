"""Claude API email drafter — drop-in replacement for cold_email.py.

Uses the Anthropic SDK with prompt caching on the system prompt (cache_control:
ephemeral). The ~1,500-token system prompt is cached after the first call in a
batch, saving ~80% of input tokens for subsequent calls within the 5-min TTL.

Identical public API to cold_email.py:
    draft_sequence(brand, anchor, save, steps)
    draft_sequence_async(brand, anchor, client, semaphore, save)

All anti-template guards (banned phrases, 5-gram overlap, validation) are
imported from cold_email.py — no duplication.

Toggle with USE_CLAUDE_EMAIL=true in .env.
"""
import asyncio

import anthropic as _anthropic

import config
import db
from models import Brand, Prospect

# Import all anti-template + validation helpers from cold_email — no duplication.
from cold_email import (
    SEQUENCE_SYSTEM_PROMPT,
    _build_sequence_user_prompt,
    _extract_json,
    _finalize_sequence,
    _worst_axis,
    _draft_sequence_legacy,
)


_async_client = None


def _get_async_client():
    global _async_client
    if _async_client is None:
        _async_client = _anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _async_client


def _build_cached_system_block():
    """Return the system parameter as a list with cache_control: ephemeral on the
    static system prompt. After the first API call in a batch, Anthropic caches
    this block for 5 minutes, saving ~80% of input tokens on subsequent calls."""
    return [
        {
            "type": "text",
            "text": SEQUENCE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


async def _draft_sequence_claude_async(brand, anchor, worst_axis, corpus_by_step, sem):
    """Single async API call that drafts all 5 steps via Claude with prompt caching."""
    user_prompt = _build_sequence_user_prompt(brand, anchor, worst_axis, corpus_by_step)
    client = _get_async_client()

    async with sem:
        try:
            resp = await client.messages.create(
                model=config.CLAUDE_EMAIL_MODEL,
                max_tokens=2400,
                system=_build_cached_system_block(),
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = (resp.content[0].text or "").strip() if resp.content else ""
            return _extract_json(raw)
        except Exception as e:
            raise RuntimeError(f"Claude API error for {brand.brand_key}: {e}") from e


def draft_sequence(brand: Brand, anchor: Prospect, save: bool = True,
                   steps: tuple = (1, 2, 3, 4, 5)) -> dict:
    """Synchronous draft — same signature as cold_email.draft_sequence."""
    worst_axis = _worst_axis(anchor)
    corpus_by_step = {n: db.get_recent_brand_bodies(limit=10, step_num=n) for n in (1, 2, 3, 4, 5)}

    async def _run():
        sem = asyncio.Semaphore(1)
        return await _draft_sequence_claude_async(brand, anchor, worst_axis, corpus_by_step, sem)

    try:
        parsed = asyncio.run(_run())
    except Exception as e:
        print(f"[claude_email] single-call failure for {brand.brand_key}: {e} — falling back")
        return _draft_sequence_legacy(brand, anchor, worst_axis, save=save, steps=steps)

    return _finalize_sequence(brand, anchor, parsed, save=save)


async def draft_sequence_async(brand: Brand, anchor: Prospect,
                               client,            # accepted for API compat, unused
                               semaphore: asyncio.Semaphore,
                               save: bool = True) -> dict:
    """Async draft — same signature as cold_email.draft_sequence_async.

    The `client` parameter is accepted but not used (Anthropic SDK manages its
    own connection pool). This keeps the call site in main.py unchanged.
    """
    worst_axis = _worst_axis(anchor)
    corpus_by_step = {n: db.get_recent_brand_bodies(limit=10, step_num=n) for n in (1, 2, 3, 4, 5)}

    try:
        parsed = await _draft_sequence_claude_async(
            brand, anchor, worst_axis, corpus_by_step, semaphore
        )
    except Exception as e:
        print(f"[claude_email] {brand.brand_key}: {e} — falling back sync legacy")
        return await asyncio.to_thread(
            _draft_sequence_legacy, brand, anchor, worst_axis, save, (1, 2, 3, 4, 5),
        )

    return await asyncio.to_thread(_finalize_sequence, brand, anchor, parsed, save)
