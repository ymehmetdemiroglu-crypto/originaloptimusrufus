"""Async streaming pipeline — runs scrape → enrich → score → draft as overlapping
producer/consumer stages over asyncio.Queues.

Each stage is a coroutine that pulls a brand_key off its input queue, advances it
to the next stage, commits state to the DB, and pushes onto the next queue.
The DB stays the source of truth; if the orchestrator dies, rerunning resumes
cleanly because each stage queries the DB for whatever rows are still in its
prior state.

Stages run with bounded concurrency:
    enrich → MAX_APOLLO_CONCURRENCY
    score / draft → MAX_LLM_CONCURRENCY

Only stage 0 (Apify scrape / backfill) is synchronous and batched — Apify actor
runs are themselves the primary cost and are already collapsed to 1-2 calls per
cohort by amazon_scraper.scrape_many and backfill_asins.run_backfill.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import httpx

import apollo_api
import cold_email
import config
import db
import rufus_scorer


# ---------------------------------------------------------------------------
# Per-brand stage workers
# ---------------------------------------------------------------------------

async def _enrich_brand_row(b, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> bool:
    """Enrich one brand. Returns True if it advanced to CONTACT_ENRICHED."""
    person = await apollo_api.enrich_brand_async(
        brand_name=b.brand_name, domain=b.domain, client=client, semaphore=sem,
    )
    if not person:
        return False

    if not person.get("email"):
        org = person.get("organization") or {}
        matched = await apollo_api.bulk_match_async(
            [{
                "id": person.get("id", ""),
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "organization_name": org.get("name") or b.brand_name,
            }],
            client=client,
            semaphore=sem,
        )
        if matched:
            person.update(matched[0])

    org = person.get("organization") or {}
    email = person.get("email")
    db.set_brand_enrichment(
        b.brand_key,
        domain=org.get("primary_domain") or org.get("website_url"),
        contact_email=email,
        contact_first_name=person.get("first_name"),
        contact_last_name=person.get("last_name"),
        contact_title=person.get("title"),
        apollo_person_id=person.get("id"),
        apollo_organization_id=org.get("id"),
    )
    new_stage = "CONTACT_ENRICHED" if email else "BRAND_RESOLVED"
    db.update_brand_stage(b.brand_key, new_stage)
    return bool(email)


async def _score_anchor(b, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> bool:
    """LLM-Rufus-score the brand's anchor ASIN. Returns True if a score landed."""
    if not b.anchor_asin or b.anchor_asin == "apollo_direct":
        return False
    anchor = db.get_anchor_prospect(b.anchor_asin)
    if anchor is None:
        return False
    result = await rufus_scorer._score_one_async(anchor, client, sem, save=True)
    return bool(result and not result.get("_error"))


async def _draft_for_brand(b, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> bool:
    """Draft the 5-step sequence in a single LLM call. Returns True if drafted."""
    if b.anchor_asin == "apollo_direct" or not b.anchor_asin:
        db.update_brand_stage(b.brand_key, "SKIP_NO_LISTING")
        return False
    anchor = db.get_anchor_prospect(b.anchor_asin)
    if anchor is None:
        return False
    try:
        await cold_email.draft_sequence_async(b, anchor, client, sem, save=True)
    except Exception as e:
        print(f"[pipeline] draft failed for {b.brand_key}: {e}")
        return False
    db.update_brand_stage(b.brand_key, "EMAIL_DRAFTED")
    return True


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

async def _run_stage(
    name: str,
    inputs: list,
    worker,
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    next_queue: Optional[asyncio.Queue],
    console=None,
) -> int:
    """Execute `worker(item, client, sem)` for each input concurrently. If the
    worker returns truthy and `next_queue` is given, the input row is requeried
    from the DB (post-state-update) and pushed onto the next queue."""
    successes = 0

    async def _wrap(item):
        nonlocal successes
        try:
            ok = await worker(item, client, semaphore)
        except Exception as e:
            if console:
                console.print(f"[yellow]{name}: {getattr(item, 'brand_key', '?')} error {e}[/yellow]")
            return
        if ok:
            successes += 1
            if next_queue is not None:
                # Re-fetch the row so downstream stages see the freshly-committed state.
                refreshed = db.get_brand(getattr(item, "brand_key", None)) if hasattr(db, "get_brand") else item
                await next_queue.put(refreshed or item)

    await asyncio.gather(*(_wrap(x) for x in inputs))
    if console:
        console.print(f"[green]✓[/green] {name}: {successes}/{len(inputs)} advanced")
    return successes


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_pipeline_async(limit: int = 50, console=None) -> dict:
    """Run the streaming pipeline over rows currently in the DB.

    Stages:
      a. enrich  — WEAK_BRAND  → CONTACT_ENRICHED
      b. score   — CONTACT_ENRICHED (no rufus_score on anchor) → scored anchor
      c. draft   — CONTACT_ENRICHED + scored anchor → EMAIL_DRAFTED
    """
    apollo_sem = asyncio.Semaphore(config.MAX_APOLLO_CONCURRENCY)
    llm_sem = asyncio.Semaphore(config.MAX_LLM_CONCURRENCY)

    stats: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=config.LLM_REQUEST_TIMEOUT_S) as llm_client, \
               httpx.AsyncClient(timeout=config.APOLLO_REQUEST_TIMEOUT_S) as apollo_client:

        # Stage A — concurrent Apollo enrichment for everything still in WEAK_BRAND
        weak = db.get_brands_needing_enrichment(limit=limit)
        if console and weak:
            console.print(f"[dim]Pipeline stage A — enrich {len(weak)} brand(s)…[/dim]")
        stats["enriched"] = await _run_stage(
            "enrich", weak, _enrich_brand_row, apollo_sem, apollo_client,
            next_queue=None, console=console,
        )

        # Stage B — LLM Rufus-score every CONTACT_ENRICHED anchor that's still unscored
        score_targets = db.get_enriched_anchor_prospects(limit=limit)
        if console and score_targets:
            console.print(f"[dim]Pipeline stage B — Rufus-score {len(score_targets)} anchor(s)…[/dim]")

        async def _score_prospect(p, client, sem):
            r = await rufus_scorer._score_one_async(p, client, sem, save=True)
            return bool(r and not r.get("_error"))

        stats["scored"] = await _run_stage(
            "score", score_targets, _score_prospect, llm_sem, llm_client,
            next_queue=None, console=console,
        )

        # Stage C — single-call draft for every brand needing an email
        draft_targets = db.get_brands_needing_email_draft(limit=limit)
        if console and draft_targets:
            console.print(f"[dim]Pipeline stage C — draft sequences for {len(draft_targets)} brand(s)…[/dim]")
        stats["drafted"] = await _run_stage(
            "draft", draft_targets, _draft_for_brand, llm_sem, llm_client,
            next_queue=None, console=console,
        )

    return stats


def run_pipeline(limit: int = 50, console=None) -> dict:
    """Synchronous entry point — wraps the async pipeline."""
    return asyncio.run(run_pipeline_async(limit=limit, console=console))
