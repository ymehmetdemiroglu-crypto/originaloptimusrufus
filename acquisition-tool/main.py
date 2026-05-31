#!/usr/bin/env python3
"""Optimus Rufus — Amazon listing → Rufus audit → Apollo outreach CLI."""
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console

console = Console()

import re
_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
def validate_asin(asin: str) -> bool:
    return bool(_ASIN_RE.match(asin))
EMAIL_STATUSES_ALLOWED = {"verified"}


# ---------------------------------------------------------------------------
# /rufus-audit — END-TO-END: scrape → rule-score → Rufus LLM-score → rollup → enrich queue
# ---------------------------------------------------------------------------

def cmd_rufus_audit(args):
    """rufus-audit [<category> ...] [--limit=N] [--with-llm]

    End-to-end audit pipeline:
      1. Apify Amazon search across given categories (or default top-5 seeds).
      2. Cheap pre-filter on search-stage data (price/reviews/blocklist/brand-cap/dedupe).
      3. Detail fetch on survivors only (the expensive call).
      4. Rule-based weakness score → flag WEAK_LISTING vs SKIP.
      5. Brand rollup → one Brand row per brand_key (anchor = worst weak ASIN).
      6. Print enrich queue: ready for Apollo MCP enrichment in this conversation.

    LLM Rufus scoring is intentionally EXCLUDED from this command.
    After enrichment, run `rufus-score-enriched` to score only brands that have contacts.

    Flags:
      --limit=N    per-category ASIN harvest cap (default 30)
      --with-llm   score ALL weak listings with LLM (old behaviour — expensive, not recommended)
    """
    import db
    import amazon_scraper
    import listing_quality_scorer
    import rufus_scorer
    import brand_rollup
    import config

    db.init_db()

    limit = 30
    use_llm = False  # LLM scoring only fires AFTER enrichment via rufus-score-enriched
    categories: list[str] = []
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--with-llm":
            use_llm = True
        elif arg == "--no-llm":
            pass  # now the default; accepted silently for backwards compat
        elif arg.startswith("--"):
            console.print(f"[yellow]Unknown flag: {arg}[/yellow]")
        else:
            categories.append(arg)

    if not categories:
        categories = config.AMAZON_SEED_CATEGORIES[:5]

    console.print(
        f"\n[bold bright_blue]/rufus-audit[/bold bright_blue] — "
        f"{len(categories)} categor{'y' if len(categories)==1 else 'ies'}, limit={limit}/cat, "
        f"llm={'ON (--with-llm)' if use_llm else 'off — run rufus-score-enriched after enrichment'}\n"
    )

    # 1+2+3. Batched scrape — single search actor run + single detail actor run across ALL categories
    try:
        total_kept, total_new = amazon_scraper.scrape_many(
            categories, limit_per_category=limit, console=console,
        )
    except (ValueError, ImportError) as e:
        console.print(f"[red]{e}[/red]")
        return
    except Exception as e:
        console.print(f"[yellow]Scrape error: {e}[/yellow]")
        total_kept, total_new = 0, 0

    console.print(f"[green]✓[/green] Scrape complete — {total_kept} listings kept, {total_new} new\n")

    # 4. Enhanced listing quality score
    unscored = db.get_unscored_listings(limit=1000)
    if unscored:
        console.print(f"[dim]Quality-scoring {len(unscored)} listings…[/dim]")
        weak = listing_quality_scorer.score_all(unscored)
        console.print(f"[green]✓[/green] {weak} flagged WEAK_LISTING (quality-based)\n")

    # 5. LLM Rufus 4-axis score
    if use_llm:
        rufus_targets = db.get_listings_needing_rufus_score(limit=200)
        if rufus_targets:
            console.print(f"[dim]Rufus-scoring {len(rufus_targets)} weak listings (LLM)…[/dim]")
            scored = rufus_scorer.score_all(rufus_targets, console=console)
            console.print(f"[green]✓[/green] Rufus-scored {scored}/{len(rufus_targets)}\n")
        else:
            console.print("[dim]No WEAK_LISTING rows need Rufus scoring.[/dim]\n")
    else:
        console.print("[dim]LLM scoring skipped. After enrichment run: py main.py rufus-score-enriched[/dim]\n")

    # 6. Brand rollup
    brand_rollup.consolidate(console=console)

    # 7. Client quality scoring (new)
    import client_quality_scorer
    cq_scored = client_quality_scorer.score_all_brands(stage="WEAK_BRAND", limit=200, console=console)
    console.print(f"[dim]{cq_scored} brands scored for client quality[/dim]\n")

    # 8. Enrich queue — show what Claude should pull through Apollo MCP next
    brands = db.get_brands_needing_enrichment(limit=50)
    if not brands:
        console.print("\n[dim]No new brands to enrich.[/dim]")
        return

    console.print(f"\n[bold]{len(brands)} brand(s) ready for Apollo enrichment:[/bold]\n")
    for b in brands:
        ri_label = f"  RI={b.reachability_index}" if b.reachability_index is not None else ""
        console.print(
            f"  brand_key=[cyan]{b.brand_key}[/cyan]  "
            f"brand=[yellow]{b.brand_name}[/yellow]  "
            f"anchor_asin={b.anchor_asin}  "
            f"max_weakness={b.max_weakness_score}  "
            f"signals={b.weakness_signals or '—'}{ri_label}"
        )
    console.print(
        "\n[dim]Next: Claude calls apollo_organizations_enrich(brand_name) → domain, "
        "then apollo_people_match(domain, titles) → contact, then "
        "`python main.py set-enrichment <brand_key> --domain=… --email=… …`[/dim]"
    )


# ---------------------------------------------------------------------------
# Granular ops (used inside /rufus-audit but also exposed for manual control)
# ---------------------------------------------------------------------------

def cmd_amazon_scrape(args):
    if not args:
        console.print("[red]Usage: main.py amazon-scrape <category> [--limit=N][/red]")
        console.print(f"[dim]Available seeds: {', '.join(__import__('config').AMAZON_SEED_CATEGORIES)}[/dim]")
        return
    import db
    import amazon_scraper
    import listing_quality_scorer
    import brand_rollup

    category = args[0]
    limit = 100
    for arg in args[1:]:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    db.init_db()
    console.print(f"[dim]Scraping Amazon listings for category: {category}…[/dim]")
    try:
        found, new_count = amazon_scraper.scrape(category, limit=limit, console=console)
    except (ValueError, ImportError) as e:
        console.print(f"[red]{e}[/red]")
        return
    console.print(f"[green]✓[/green] Pulled {found} listings, {new_count} new")

    unscored = db.get_unscored_listings(limit=500)
    if unscored:
        console.print(f"[dim]Quality-scoring {len(unscored)} listings…[/dim]")
        weak = listing_quality_scorer.score_all(unscored)
        console.print(f"[green]✓[/green] {weak} flagged WEAK_LISTING")
    brand_rollup.consolidate(console=console)


def cmd_score():
    import db
    import listing_quality_scorer
    db.init_db()
    unscored = db.get_unscored_listings(limit=1000)
    if not unscored:
        console.print("[dim]No unscored listings.[/dim]")
        return
    console.print(f"[dim]Quality-scoring {len(unscored)} listings…[/dim]")
    weak = listing_quality_scorer.score_all(unscored)
    console.print(f"[green]✓[/green] {weak} flagged WEAK_LISTING")


def cmd_rufus_score(args):
    """rufus-score [<prospect_id>] [--v2] — LLM-powered Rufus optimization scoring."""
    import db
    import rufus_scorer

    db.init_db()
    use_v2 = False
    pid = None
    for arg in args:
        if arg == "--v2":
            use_v2 = True
        elif not arg.startswith("--"):
            pid = arg

    if pid:
        p = db.get_prospect(pid)
        if not p:
            console.print(f"[red]Prospect {pid} not found[/red]")
            return
        console.print(f"[dim]Scoring {pid} ({p.brand}) {'(v2)' if use_v2 else '(v1)'}…[/dim]")
        try:
            result = rufus_scorer.score_listing(p, save=True, use_v2=use_v2)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return

        prob = result.get("rufus_citation_probability", "?")
        colour = {"high": "green", "medium": "yellow", "low": "red"}.get(prob, "white")
        max_possible = result.get("max_possible", 100)
        console.print(f"\n[bold]{p.brand}[/bold] ({p.asin})")
        console.print(f"  Overall Rufus Score: [bold]{result['overall_score']}/{max_possible}[/bold]  Citation Probability: [{colour}]{prob}[/{colour}]")
        console.print(f"  Intent Alignment:           {result.get('intent_alignment', 0)}/{20 if use_v2 else 25}")
        console.print(f"  Attribute Density:          {result.get('attribute_density', 0)}/{20 if use_v2 else 25}")
        console.print(f"  Conversational Readability: {result.get('conversational_readability', 0)}/{20 if use_v2 else 25}")
        console.print(f"  Q&A Coverage:               {result.get('qa_coverage', 0)}/{20 if use_v2 else 25}")
        if use_v2:
            console.print(f"  Visual & Structured:        {result.get('visual_structured_content', 0)}/20")
            console.print(f"  Competitive Relativity:     {result.get('competitive_relativity', 0)}/20")
        console.print(f"\n  [bold]Summary:[/bold] {result.get('summary', '')}")
        if use_v2 and result.get("competitive_summary"):
            console.print(f"  [bold]Competitive:[/bold] {result['competitive_summary']}")
        for w in result.get("top_weaknesses", []):
            sev = w.get("severity", "")
            sev_color = {"critical": "red", "high": "yellow", "medium": "white", "low": "dim"}.get(sev, "white")
            console.print(f"  [red]▸[/red] [{w.get('axis','?')}] [{sev_color}]{sev}[/{sev_color}] {w.get('issue','')}")
            console.print(f"    [dim]Fix: {w.get('fix','')}[/dim]")
        return

    rows = db.get_listings_needing_rufus_score(limit=100)
    if not rows:
        console.print("[dim]No WEAK_LISTING prospects need Rufus scoring.[/dim]")
        return
    console.print(f"[dim]Rufus-scoring {len(rows)} listings ({'v2' if use_v2 else 'v1'})…[/dim]\n")
    scored = rufus_scorer.score_all(rows, console=console, use_v2=use_v2)
    console.print(f"\n[green]✓[/green] {scored}/{len(rows)} scored")


def cmd_rufus_score_enriched(args=()):
    """rufus-score-enriched [--v2] — LLM Rufus-score only anchor ASINs of CONTACT_ENRICHED brands.

    This is the cost-efficient scoring step: runs AFTER Apollo enrichment so we only
    pay for LLM calls on brands that actually have a reachable contact.
    """
    import db
    import rufus_scorer

    use_v2 = "--v2" in args
    db.init_db()
    targets = db.get_enriched_anchor_prospects(limit=100)
    if not targets:
        console.print("[dim]No CONTACT_ENRICHED anchor ASINs need Rufus scoring.[/dim]")
        return
    console.print(f"[dim]Rufus-scoring {len(targets)} enriched anchor listing(s) ({'v2' if use_v2 else 'v1'})…[/dim]\n")
    scored = rufus_scorer.score_all(targets, console=console, use_v2=use_v2)
    console.print(f"\n[green]✓[/green] Rufus-scored {scored}/{len(targets)}")


def cmd_consolidate_brands():
    import db
    import brand_rollup
    db.init_db()
    brand_rollup.consolidate(console=console)


def cmd_client_quality_score(args=()):
    """client-quality-score [<stage>] [--limit=N] — Score brands for client quality + reachability."""
    import client_quality_scorer
    import db

    stage = "WEAK_BRAND"
    limit = 100
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif not arg.startswith("--"):
            stage = arg.upper()

    db.init_db()
    console.print(f"[dim]Scoring client quality for {stage} brands…[/dim]\n")
    scored = client_quality_scorer.score_all_brands(stage=stage, limit=limit, console=console)
    console.print(f"\n[green]✓[/green] Scored {scored} brand(s)")


# ---------------------------------------------------------------------------
# Automated Apollo API integrations (bypasses MCP/LLM)
# ---------------------------------------------------------------------------

def cmd_auto_enrich():
    """auto-enrich — Process WEAK_BRANDs concurrently via Apollo API.

    Fan-out via asyncio: one mixed_people/api_search per brand under
    MAX_APOLLO_CONCURRENCY. Brands without a directly-returned email get
    one batched bulk_match pass to fill in verified emails.
    """
    import asyncio

    import apollo_api
    import config as _config
    import db

    db.init_db()
    brands = db.get_brands_needing_enrichment(limit=50)
    if not brands:
        console.print("[dim]No brands awaiting enrichment.[/dim]")
        return

    console.print(
        f"\n[bold]Auto-enriching {len(brands)} brands via Apollo API "
        f"(concurrency={_config.MAX_APOLLO_CONCURRENCY})[/bold]\n"
    )

    async def _run() -> int:
        # Stage 1 — concurrent target-title searches
        people = await apollo_api.enrich_brands_async(
            [(b.brand_name, b.domain) for b in brands]
        )

        # Stage 2 — bulk_match anyone missing a verified email
        need_match = []
        need_match_idx: list[int] = []
        for i, person in enumerate(people):
            if person and not person.get("email"):
                org = person.get("organization") or {}
                need_match.append({
                    "id": person.get("id", ""),
                    "first_name": person.get("first_name", ""),
                    "last_name": person.get("last_name", ""),
                    "organization_name": org.get("name") or brands[i].brand_name,
                })
                need_match_idx.append(i)

        if need_match:
            console.print(
                f"[dim]bulk_match resolving {len(need_match)} contacts missing emails…[/dim]"
            )
            matched = await apollo_api.bulk_match_async(need_match)
            matched_by_id = {m.get("id"): m for m in matched if m.get("email")}
            for i in need_match_idx:
                pid = (people[i] or {}).get("id")
                if pid and pid in matched_by_id:
                    people[i].update(matched_by_id[pid])

        enriched = 0
        for b, person in zip(brands, people):
            if not person:
                console.print(f"  [yellow]⚠[/yellow] No verified target for {b.brand_name}")
                continue
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
            console.print(f"  [green]✓[/green] {b.brand_key} → {new_stage} ({email or '(no email)'})")
            if email:
                enriched += 1
        return enriched

    enriched_count = asyncio.run(_run())
    console.print(f"\n[green]✓[/green] Successfully enriched {enriched_count}/{len(brands)} brands.")

def _process_and_insert_prospects(people, category, _config, db, apollo_api, console):
    """Bulk-match emails and insert into DB. Returns count of newly inserted rows."""
    need_email = [p for p in people if not p.get("email")]
    have_email = [p for p in people if p.get("email")]

    if need_email:
        console.print(f"[dim]Bulk-matching {len(need_email)} contacts missing emails (batches of 10)…[/dim]")
        bulk_payload = [
            {
                "id": p.get("id", ""),
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "organization_name": (p.get("organization") or {}).get("name", ""),
            }
            for p in need_email
        ]
        matched = apollo_api.bulk_match(bulk_payload)
        matched_by_id = {m.get("id"): m for m in matched if m.get("email")}
        for p in need_email:
            pid = p.get("id", "")
            if pid in matched_by_id:
                p.update(matched_by_id[pid])
        have_email.extend(need_email)
        console.print(f"[dim]  → bulk_match resolved {len(matched_by_id)} emails[/dim]")

    inserted_count = 0
    for p in have_email:
        email = p.get("email")
        if not email:
            continue
        if p.get("email_status") not in EMAIL_STATUSES_ALLOWED:
            continue
        if p.get("asin") and not validate_asin(p.get("asin")):
            continue

        org = p.get("organization", {})
        org_name = org.get("name")
        domain = org.get("primary_domain") or org.get("website_url")

        if not org_name or not domain:
            continue

        if any(b.lower() in org_name.lower() for b in _config.AMAZON_BRAND_BLOCKLIST) or "amazon.com" in domain.lower():
            continue

        import hashlib
        base = "".join(c.lower() for c in org_name if c.isalnum())
        digest = hashlib.sha256((domain or "").lower().encode()).hexdigest()[:6]
        brand_key = f"{base}-{digest}"

        inserted = db.insert_apollo_brand(
            brand_key=brand_key,
            brand_name=org_name,
            domain=domain,
            contact_email=email,
            contact_first_name=p.get("first_name"),
            contact_last_name=p.get("last_name"),
            contact_title=p.get("title"),
            category=category,
            contact_linkedin=p.get("linkedin_url"),
            apollo_person_id=p.get("id"),
            apollo_organization_id=org.get("id")
        )
        if inserted:
            console.print(f"  [green]✓[/green] Inserted {org_name} ({email})")
            inserted_count += 1

    return inserted_count


def cmd_auto_prospect(args):
    """auto-prospect <category> [--limit=N] — Direct Apollo search (Funnel B)."""
    if not args:
        console.print("[red]Usage: main.py auto-prospect <category> [--limit=N][/red]")
        return

    import db
    import apollo_api
    import config as _config

    category = args[0]
    limit = 20
    for arg in args[1:]:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    db.init_db()
    console.print(f"[dim]Auto-prospecting '{category}' via Apollo API (target {limit} new)...[/dim]")

    total_inserted = 0
    page = 1
    max_pages = 10
    per_page = 100

    while total_inserted < limit and page <= max_pages:
        console.print(f"[dim]  → Fetching page {page} (per_page={per_page})…[/dim]")
        people = apollo_api.search_prospects(category, limit=per_page, page=page)
        if not people:
            console.print("[dim]No more prospects from Apollo.[/dim]")
            break

        console.print(f"[dim]  → Got {len(people)} candidates.[/dim]")
        console.print(f"[dim]Inserting into DB...[/dim]")
        inserted = _process_and_insert_prospects(people, category, _config, db, apollo_api, console)
        total_inserted += inserted
        page += 1

        if len(people) < per_page:
            break  # Apollo returned fewer than requested — no more pages

    console.print(f"\n[green]✓[/green] Successfully inserted {total_inserted} new prospects.")

    # Mandatory ASIN backfill — no Apollo-sourced brand goes to draft without listing data.
    if total_inserted > 0:
        console.print("\n[dim]Running ASIN backfill (mandatory before drafting)…[/dim]")
        try:
            import backfill_asins
            backfill_asins.run_backfill(console=console)
        except Exception as e:
            console.print(f"[yellow]Backfill warning: {e}[/yellow]")


def cmd_run_funnel_b(args):
    """run-funnel-b <category> [--limit=N] — Full end-to-end Funnel B pipeline.

    Orchestrates all 5 stages in sequence:
      1. auto-prospect  — Apollo search → DB insert
      2. backfill-asins  — Amazon search → fuzzy-match → anchor ASIN
      3. rufus-score     — LLM 4-axis scoring on enriched anchor listings
      4. draft-emails    — Generate teardown cold emails
      5. export CSV      — Write apollo_import_ready.csv
    """
    if not args:
        console.print("[red]Usage: main.py run-funnel-b <category> [--limit=N][/red]")
        return

    console.print("\n[bold bright_blue]━━━ Funnel B — Full Pipeline ━━━[/bold bright_blue]\n")

    # Stage 1 — Auto-Prospect
    console.print("[bold]Stage 1/5 — Auto-Prospect via Apollo[/bold]")
    cmd_auto_prospect(args)

    # Stage 2 — Backfill ASINs from Amazon
    console.print("\n[bold]Stage 2/5 — Backfill ASINs from Amazon[/bold]")
    import backfill_asins
    backfill_asins.run_backfill(console=console)

    # Stage 3 — Rufus 4-axis score
    console.print("\n[bold]Stage 3/5 — Rufus LLM Scoring[/bold]")
    cmd_rufus_score_enriched()

    # Stage 4 — Draft emails
    console.print("\n[bold]Stage 4/5 — Draft Teardown Emails[/bold]")
    cmd_draft_emails()

    # Stage 5 — Export CSV
    console.print("\n[bold]Stage 5/5 — Export CSV[/bold]")
    import export_apollo
    # export_apollo runs as a script; we import and call inline
    try:
        import importlib
        importlib.reload(export_apollo)
    except Exception as e:
        console.print(f"[yellow]Export warning: {e}[/yellow]")

    console.print("\n[bold bright_green]━━━ Pipeline Complete ━━━[/bold bright_green]")
    console.print("[bold]CSV ready:[/bold] `apollo_import_ready.csv` — upload to Apollo, map columns, add to sequence.")


# ---------------------------------------------------------------------------
# Apollo enrichment / sequence ops (driven by Claude in conversation)
# ---------------------------------------------------------------------------

def cmd_enrich_queue():
    import db
    db.init_db()
    brands = db.get_brands_needing_enrichment(limit=50)
    if not brands:
        console.print("[dim]No brands awaiting enrichment.[/dim]")
        return
    console.print(f"\n[bold]{len(brands)} brands awaiting Apollo enrichment:[/bold]\n")
    for b in brands:
        console.print(
            f"  [cyan]{b.brand_key}[/cyan]  brand=[yellow]{b.brand_name}[/yellow]  "
            f"anchor_asin={b.anchor_asin}  asins={b.asin_count}  signals={b.weakness_signals}"
        )
    console.print("\n[dim]Claude → apollo_organizations_enrich + apollo_people_match → set-enrichment <brand_key> ….[/dim]")


def cmd_set_enrichment(args):
    if not args:
        console.print("[red]Usage: main.py set-enrichment <brand_key> --domain=… --email=… --first=… --last=… --title=… --apollo-person=… --apollo-org=…[/red]")
        return
    import db
    db.init_db()
    brand_key = args[0]
    fields = {}
    for arg in args[1:]:
        if arg.startswith("--domain="): fields["domain"] = arg.split("=", 1)[1]
        elif arg.startswith("--email="): fields["contact_email"] = arg.split("=", 1)[1]
        elif arg.startswith("--first="): fields["contact_first_name"] = arg.split("=", 1)[1]
        elif arg.startswith("--last="): fields["contact_last_name"] = arg.split("=", 1)[1]
        elif arg.startswith("--title="): fields["contact_title"] = arg.split("=", 1)[1]
        elif arg.startswith("--apollo-person="): fields["apollo_person_id"] = arg.split("=", 1)[1]
        elif arg.startswith("--apollo-org="): fields["apollo_organization_id"] = arg.split("=", 1)[1]

    db.set_brand_enrichment(brand_key, **fields)
    new_stage = "CONTACT_ENRICHED" if fields.get("contact_email") else "BRAND_RESOLVED"
    db.update_brand_stage(brand_key, new_stage)
    console.print(f"[green]✓[/green] {brand_key} → {new_stage}")


def cmd_save_apollo_prospect(args):
    """save-apollo-prospect <brand_key> --brand=X --domain=X --email=X --first=X --last=X --title=X [--category=X] [--linkedin=X] [--apollo-person=X] [--apollo-org=X]"""
    if not args:
        console.print("[red]Usage: main.py save-apollo-prospect <brand_key> --brand=X --domain=X --email=X --first=X --last=X --title=X[/red]")
        return
    import db
    db.init_db()

    brand_key = args[0]
    fields: dict = {}
    for arg in args[1:]:
        for flag, key in [
            ("--brand=", "brand_name"), ("--domain=", "domain"), ("--email=", "contact_email"),
            ("--first=", "contact_first_name"), ("--last=", "contact_last_name"),
            ("--title=", "contact_title"), ("--category=", "category"),
            ("--linkedin=", "contact_linkedin"), ("--apollo-person=", "apollo_person_id"),
            ("--apollo-org=", "apollo_organization_id"), ("--score=", "apollo_score"),
        ]:
            if arg.startswith(flag):
                fields[key] = arg.split("=", 1)[1]

    required = ["brand_name", "domain", "contact_email", "contact_first_name", "contact_last_name", "contact_title"]
    missing = [r for r in required if not fields.get(r)]
    if missing:
        console.print(f"[red]Missing required fields: {', '.join(missing)}[/red]")
        return

    apollo_score = int(fields["apollo_score"]) if fields.get("apollo_score") else None

    inserted = db.insert_apollo_brand(
        brand_key=brand_key,
        brand_name=fields["brand_name"],
        domain=fields["domain"],
        contact_email=fields["contact_email"],
        contact_first_name=fields["contact_first_name"],
        contact_last_name=fields["contact_last_name"],
        contact_title=fields["contact_title"],
        category=fields.get("category", ""),
        contact_linkedin=fields.get("contact_linkedin"),
        apollo_person_id=fields.get("apollo_person_id"),
        apollo_organization_id=fields.get("apollo_organization_id"),
        apollo_score=apollo_score,
    )
    if inserted:
        score_label = f"  score={apollo_score}" if apollo_score is not None else ""
        console.print(f"[green]✓[/green] {brand_key} → CONTACT_ENRICHED ({fields['contact_email']}){score_label}")
    else:
        console.print(f"[yellow]⚠[/yellow] {brand_key} already exists, skipped")


def cmd_apollo_enrich(args):
    """apollo-enrich --file=<path.json> [--grade=AB|A]

    Reads a JSON array of scored Apollo contacts, bulk-matches them via the
    Apollo REST API (batches of 10, no LLM tokens used), and saves every
    verified-email result directly to the DB at CONTACT_ENRICHED.

    Input JSON format (one object per contact):
      [{"apollo_person_id":"<id>","first_name":"Del","organization_name":"Harmony Baby Nutrition",
        "title":"Founder-CEO","score":100,"category":"supplements"}, ...]

    Outputs a one-line summary per contact and a final tally.
    """
    import json
    import db
    import apollo_api
    import config as _config

    file_path = None
    min_score = 0
    for arg in args:
        if arg.startswith("--file="):
            file_path = arg.split("=", 1)[1]
        elif arg.startswith("--grade="):
            grade = arg.split("=", 1)[1].upper()
            min_score = 85 if grade == "A" else 70

    if not file_path:
        console.print("[red]Usage: main.py apollo-enrich --file=<path.json> [--grade=AB|A][/red]")
        return

    from pathlib import Path
    path = Path(file_path).resolve()
    base_dir = Path(__file__).parent / "data"
    try:
        path.relative_to(base_dir)
    except ValueError:
        console.print(f"[red]Invalid file path: must be inside {base_dir}[/red]")
        return

    try:
        with open(file_path, encoding="utf-8") as f:
            contacts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Cannot read {file_path}: {e}[/red]")
        return

    if min_score:
        contacts = [c for c in contacts if c.get("score", 0) >= min_score]

    console.print(f"\n[bold]apollo-enrich[/bold] — {len(contacts)} contacts from {file_path}")
    if not contacts:
        console.print("[dim]Nothing to enrich.[/dim]")
        return

    db.init_db()

    # Build payload for bulk_match
    people = [
        {
            "id": c.get("apollo_person_id", ""),
            "first_name": c.get("first_name", ""),
            "organization_name": c.get("organization_name", ""),
        }
        for c in contacts
    ]

    # Index input by apollo_person_id so we can merge metadata back after match
    by_pid = {c.get("apollo_person_id", ""): c for c in contacts}

    console.print(f"[dim]Calling Apollo bulk match in batches of 10…[/dim]")
    matched = apollo_api.bulk_match(people)

    saved = 0
    skipped = 0
    no_email = len(contacts) - len(matched)

    for person in matched:
        email = person.get("email", "")
        if not email:
            continue

        pid = person.get("id", "")
        meta = by_pid.get(pid, {})

        org = person.get("organization") or {}
        domain = (
            org.get("primary_domain")
            or org.get("website_url")
            or person.get("present_raw_address", "")
        )
        org_name = org.get("name") or meta.get("organization_name", "")
        if not org_name:
            skipped += 1
            continue

        import hashlib
        base = "".join(c.lower() for c in org_name if c.isalnum())
        digest = hashlib.sha256((domain or "").lower().encode()).hexdigest()[:6]
        brand_key = f"{base}-{digest}"
        score = meta.get("score")
        category = meta.get("category", "")
        title = meta.get("title") or person.get("title", "")

        # Skip mega-brands / marketplace domains
        if any(b in org_name.lower() for b in _config.AMAZON_BRAND_BLOCKLIST):
            skipped += 1
            console.print(f"  [dim]skip blocklist: {org_name}[/dim]")
            continue
        if domain and any(x in domain.lower() for x in ("amazon.com", "etsy.com", "shopify.com")):
            skipped += 1
            console.print(f"  [dim]skip marketplace domain: {domain}[/dim]")
            continue

        inserted = db.insert_apollo_brand(
            brand_key=brand_key,
            brand_name=org_name,
            domain=domain or "",
            contact_email=email,
            contact_first_name=person.get("first_name", ""),
            contact_last_name=person.get("last_name", ""),
            contact_title=title,
            category=category,
            contact_linkedin=person.get("linkedin_url"),
            apollo_person_id=pid,
            apollo_organization_id=org.get("id"),
            apollo_score=score,
        )
        if inserted:
            score_label = f"  score={score}" if score is not None else ""
            console.print(f"  [green]✓[/green] {brand_key}  {email}{score_label}")
            saved += 1
        else:
            skipped += 1
            console.print(f"  [yellow]⚠[/yellow] {brand_key} already in DB")

    console.print(
        f"\n[bold]Done.[/bold] matched={len(matched)}  saved={saved}  "
        f"skipped={skipped}  no_email≈{no_email}\n"
        f"[dim]Next: py main.py draft-emails[/dim]"
    )


def cmd_draft_emails(args=()):
    """draft-emails [--limit=N] — Mini-batch JSON drafter (N brands per API call, shared system prompt)."""
    import asyncio
    from itertools import islice

    import httpx

    import config as _config
    if _config.USE_CLAUDE_EMAIL:
        import claude_email as cold_email
    else:
        import cold_email
    import db

    db.init_db()
    limit = 100
    for a in args:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    brands = db.get_brands_needing_email_draft(limit=limit)
    if not brands:
        console.print("[dim]No brands awaiting email draft.[/dim]")
        return

    batch_size = _config.EMAIL_MINI_BATCH_SIZE
    n_batches = (len(brands) + batch_size - 1) // batch_size
    console.print(
        f"[dim]Drafting teardowns for {len(brands)} brands in {n_batches} mini-batches "
        f"(batch_size={batch_size}, concurrency={_config.MAX_LLM_CONCURRENCY})…[/dim]"
    )

    drafted = 0
    skipped_no_listing = 0

    def _chunked(iterable, n):
        it = iter(iterable)
        while chunk := list(islice(it, n)):
            yield chunk

    async def _process_batch(batch_brands, client, sem):
        nonlocal drafted, skipped_no_listing
        valid = []
        for b in batch_brands:
            if b.anchor_asin == "apollo_direct":
                db.update_brand_stage(b.brand_key, "SKIP_NO_LISTING")
                skipped_no_listing += 1
                console.print(f"[dim]  ↳ {b.brand_key}: no ASIN — SKIP_NO_LISTING[/dim]")
                continue
            anchor = db.get_anchor_prospect(b.anchor_asin)
            if anchor is None:
                console.print(f"[yellow]{b.brand_key}: anchor {b.anchor_asin} not found, skipping[/yellow]")
                continue
            valid.append((b, anchor))

        if not valid:
            return

        try:
            results = await cold_email.draft_batch_async(valid, client, sem, save=True)
        except Exception as e:
            for b, _ in valid:
                console.print(f"[yellow]{b.brand_key}: batch error {e}[/yellow]")
            return

        for brand, anchor in valid:
            seq = results.get(brand.brand_key)
            if not seq:
                console.print(f"[yellow]{brand.brand_key}: missing from batch result[/yellow]")
                continue
            db.update_brand_stage(brand.brand_key, "EMAIL_DRAFTED")
            drafted += 1
            avg_overlap = sum(s["overlap"] for s in seq["steps"].values()) / max(1, len(seq["steps"]))
            console.print(
                f"  [green]✓[/green] {brand.brand_key}  axis={seq['worst_axis']}  "
                f"steps={len(seq['steps'])}  avg_overlap={avg_overlap:.0%}  "
                f"subj1=[italic]{seq['steps'][1]['subject']}[/italic]"
            )

    async def _run():
        sem = asyncio.Semaphore(_config.MAX_LLM_CONCURRENCY)
        async with httpx.AsyncClient(timeout=_config.LLM_REQUEST_TIMEOUT_S) as client:
            batches = list(_chunked(brands, batch_size))
            await asyncio.gather(*(_process_batch(b, client, sem) for b in batches))

    asyncio.run(_run())
    console.print(f"[green]✓[/green] {drafted} drafted, {skipped_no_listing} skipped (no listing)")


def cmd_send_queue():
    import db
    import config as _config
    db.init_db()
    brands = db.get_brands_ready_to_send(limit=50)
    if not brands:
        console.print("[dim]No drafts ready to send.[/dim]")
        return
    console.print(f"\n[bold]{len(brands)} brand drafts ready for Apollo sequence:[/bold]\n")
    seq_id = _config.APOLLO_SEQUENCE_ID
    for b in brands:
        score_label = f"  score={b.apollo_score}" if b.apollo_score is not None else ""
        axis_label = f"  axis={b.worst_axis_at_send}" if b.worst_axis_at_send else ""
        console.print(
            f"  [cyan]{b.brand_key}[/cyan]  brand=[yellow]{b.brand_name}[/yellow]  "
            f"email={b.contact_email}  source={b.source}{score_label}{axis_label}  "
            f"sequence=[magenta]{seq_id or 'MISSING'}[/magenta]  "
            f"apollo_contact={b.apollo_contact_id or '(create needed)'}"
        )
    console.print("\n[dim]Claude → apollo_contacts_create + apollo_emailer_campaigns_add_contact_ids → mark-sequenced <brand_key> <apollo_contact_id>.[/dim]")


def cmd_apollo_sequence(args):
    """apollo-sequence [--limit=N] [--dry-run]

    For every EMAIL_DRAFTED brand with no apollo_contact_id:
      1. Creates the contact in Apollo via REST API.
      2. Enrolls it in the correct sequence (generic or personalized).
      3. Marks the brand SEQUENCED in the DB.
    Zero MCP tokens used.
    """
    import db
    import apollo_api
    import config as _config

    limit = 100
    dry_run = False
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--dry-run":
            dry_run = True

    db.init_db()
    brands = db.get_brands_ready_to_send(limit=limit)
    if not brands:
        console.print("[dim]No brands in send queue.[/dim]")
        return

    console.print(f"\n[bold]apollo-sequence[/bold] — {len(brands)} brands{'  [DRY RUN]' if dry_run else ''}\n")

    enrolled = 0
    failed = 0

    seq_id = _config.APOLLO_SEQUENCE_ID
    for b in brands:
        if not seq_id:
            console.print(f"  [red]✗[/red] {b.brand_key}  MISSING APOLLO_SEQUENCE_ID")
            failed += 1
            continue

        if dry_run:
            console.print(f"  [dim]dry-run[/dim] {b.brand_key}  {b.contact_email}  axis={b.worst_axis_at_send}")
            continue

        # 1. Create contact — push fully generated subject + body as custom fields
        last = b.contact_last_name or ""
        custom = {}
        if b.custom_subject:
            custom["custom_subject"] = b.custom_subject
        if b.custom_body:
            custom["custom_body"] = b.custom_body
        # Per-step copy (5-step sequence) — pushed as step_1..5 fields
        steps_map = db.get_brand_step_emails(b.brand_key)
        for step_num, payload in steps_map.items():
            custom[f"custom_subject_{step_num}"] = payload["subject"]
            custom[f"custom_body_{step_num}"] = payload["body"]
        # Back-compat: keep weakness_teardown populated for any legacy template still referencing it
        if b.email_teardown:
            custom["weakness_teardown"] = b.email_teardown
        if b.category:
            custom["custom_category"] = b.category

        contact_id = apollo_api.create_contact(
            email=b.contact_email,
            first_name=b.contact_first_name or "",
            last_name=last,
            title=b.contact_title or "",
            organization_name=b.brand_name,
            website_url=f"https://{b.domain}" if b.domain and not b.domain.startswith("http") else (b.domain or ""),
            typed_custom_fields=custom or None,
        )
        if not contact_id:
            console.print(f"  [red]✗[/red] {b.brand_key}  contact create failed")
            failed += 1
            continue

        # 2. Enroll in sequence
        ok = apollo_api.add_to_sequence(seq_id, contact_id, _config.APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID)
        if not ok:
            console.print(f"  [yellow]⚠[/yellow] {b.brand_key} sequence enroll failed — will retry next run")
            failed += 1
            continue

        # 3. Mark sequenced
        db.set_brand_apollo_contact(b.brand_key, contact_id)
        db.update_brand_stage(b.brand_key, "SEQUENCED")
        score_label = f"  score={b.apollo_score}" if b.apollo_score else ""
        console.print(f"  [green]✓[/green] {b.brand_key}  {b.contact_email}  axis={b.worst_axis_at_send or '?'}{score_label}")
        enrolled += 1

    if not dry_run:
        console.print(f"\n[bold]Done.[/bold]  enrolled={enrolled}  failed={failed}")


def cmd_apollo_sequence_v3(args):
    """apollo-sequence-v3 [--limit=N] [--dry-run] [--skip-preflight]"""
    import send_to_apollo_sequence
    old_argv = sys.argv
    sys.argv = ["main.py apollo-sequence-v3"] + args
    try:
        send_to_apollo_sequence.main()
    finally:
        sys.argv = old_argv


def cmd_mark_sequenced(args):
    if len(args) < 2:
        console.print("[red]Usage: main.py mark-sequenced <brand_key> <apollo_contact_id>[/red]")
        return
    import db
    db.init_db()
    brand_key, contact_id = args[0], args[1]
    db.set_brand_apollo_contact(brand_key, contact_id)
    db.update_brand_stage(brand_key, "SEQUENCED")
    console.print(f"[green]✓[/green] {brand_key} → SEQUENCED (apollo_contact_id={contact_id})")


# ---------------------------------------------------------------------------
# Quality audit — retroactively flag bad contacts in EMAIL_DRAFTED queue
# ---------------------------------------------------------------------------

def cmd_reply_classify(args):
    """reply-classify <brand_key> <"reply text">

    Classify an inbound reply and apply auto-action.
    Example: python main.py reply-classify toniiq "Thanks for reaching out — can you send more info on pricing?"
    """
    import reply_classifier

    if len(args) < 2:
        console.print("[red]Usage: main.py reply-classify <brand_key> \"<reply text>\"[/red]")
        return

    brand_key = args[0]
    reply_text = " ".join(args[1:])

    db.init_db()
    brand = db.get_brand(brand_key)
    if not brand:
        console.print(f"[red]Brand '{brand_key}' not found.[/red]")
        return

    result = reply_classifier.process_reply(brand_key, reply_text, console=console)
    console.print(
        f"\n[bold]Classification:[/bold] {result['category']} "
        f"(confidence: {result['confidence']:.0%})"
    )
    console.print(f"[dim]Reason:[/dim] {result['reason']}")
    console.print(f"[dim]Suggested action:[/dim] {result['suggested_action']}")
    console.print(f"[dim]New stage:[/dim] {result['new_stage']}")


def cmd_linkedin_export(args):
    """linkedin-export [--limit=N] [--out=path.csv]

    Export EMAIL_DRAFTED brands with LinkedIn URLs to a CSV ready for
    HeyReach, Expandi, or any LinkedIn automation tool.
    Prints integration guide after export.
    """
    import linkedin_export

    limit = 50
    out_path = None
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg.startswith("--out="):
            out_path = arg.split("=", 1)[1]

    db.init_db()
    filename = linkedin_export.export_linkedin_csv(limit=limit, out_path=out_path)
    if not filename:
        console.print("[dim]No EMAIL_DRAFTED brands with LinkedIn URLs to export.[/dim]")
        return

    console.print(f"[green]✓[/green] LinkedIn export ready: [bold]{filename}[/bold]")
    console.print(f"[dim]{linkedin_export.print_integration_guide()}[/dim]")


def cmd_intent_score(args):
    """intent-score [<stage>] [--limit=N]

    Compute intent scores for all brands in a given stage.
    Default stage: CONTACT_ENRICHED.
    Also runs competitor intel loading automatically if available.
    """
    import intent_signals

    stage = "CONTACT_ENRICHED"
    limit = 100
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif not arg.startswith("--"):
            stage = arg.upper()

    db.init_db()
    console.print(f"[dim]Scoring intent for {limit} brand(s) in stage {stage}…[/dim]")
    scored = intent_signals.score_all_brands(stage=stage, limit=limit, console=console)
    console.print(f"[green]✓[/green] Intent scoring complete — {scored} brand(s) scored.")


def cmd_competitor_scrape(args):
    """competitor-scrape [<brand_key> ...] [--batch]

    Scrape top 3 competitors for one or more brands.
    Without args: scrapes competitors for all CONTACT_ENRICHED brands.
    With brand_key(s): scrapes only those brands.
    --batch: scrape for all EMAIL_DRAFTED brands (pre-send competitive intel).
    """
    import competitor_scraper

    db.init_db()
    limit = 50
    brand_keys: list[str] = []
    batch_mode = False

    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--batch":
            batch_mode = True
        elif not arg.startswith("--"):
            brand_keys.append(arg)

    if batch_mode:
        brands = db.get_brands_ready_to_send(limit=limit)
        brand_keys = [b.brand_key for b in brands]
        console.print(f"[dim]Competitor scrape for {len(brand_keys)} EMAIL_DRAFTED brand(s)…[/dim]")
    elif not brand_keys:
        brands = db.get_brands_needing_email_draft(limit=limit)
        brand_keys = [b.brand_key for b in brands]
        console.print(f"[dim]Competitor scrape for {len(brand_keys)} CONTACT_ENRICHED brand(s)…[/dim]")

    if not brand_keys:
        console.print("[dim]No brands to scrape competitors for.[/dim]")
        return

    scraped = 0
    for bk in brand_keys:
        comps = competitor_scraper.scrape_competitors_for_brand(bk, console=console)
        if comps:
            scraped += 1

    console.print(f"[green]✓[/green] Competitor scrape complete — {scraped}/{len(brand_keys)} brands have competitor data.")


def cmd_quality_check(args):
    """quality-check [--fix]

    Scans EMAIL_DRAFTED brands for quality problems introduced before the new
    title filter was in place:
      - Non-founder contacts (Directors, Managers, VPs, etc.)
      - Email domain doesn't match brand domain
      - Brand name matches the blocklist

    Without --fix: prints a report only.
    With --fix: moves flagged brands back to CONTACT_ENRICHED so they can be
                re-enriched or skipped, and clears their contact data.
    """
    import db
    import config as _config
    import apollo_api
    from datetime import datetime as _dt

    fix = "--fix" in args
    db.init_db()

    res = (
        db._sb().table("brands")
        .select("brand_key,brand_name,contact_email,contact_title,domain,stage")
        .in_("stage", ["EMAIL_DRAFTED", "CONTACT_ENRICHED"])
        .order("stage").order("brand_name")
        .execute()
    )
    rows = [
        (r["brand_key"], r["brand_name"], r["contact_email"], r["contact_title"], r["domain"], r["stage"])
        for r in res.data
    ]

    issues: list[tuple] = []  # (brand_key, brand_name, email, title, domain, stage, reason)

    for brand_key, brand_name, email, title, domain, stage in rows:
        reasons = []

        # 1. Non-founder title
        if not apollo_api._is_target_title(title):
            reasons.append(f"title='{title or 'none'}' — not a founder/owner/CEO")

        # 2. Email domain mismatch
        if email and domain:
            email_domain = email.split("@")[1].lower() if "@" in email else ""
            clean_domain = (domain or "").lower().replace("www.", "")
            brand_part = clean_domain.split(".")[0] if clean_domain else ""
            email_brand_part = email_domain.split(".")[0] if email_domain else ""
            if email_domain and clean_domain and email_domain != clean_domain and email_brand_part not in clean_domain:
                reasons.append(f"email domain '{email_domain}' ≠ brand domain '{clean_domain}'")

        # 3. Blocklisted brand
        if any(b in (brand_name or "").lower() for b in _config.AMAZON_BRAND_BLOCKLIST):
            matching = next(b for b in _config.AMAZON_BRAND_BLOCKLIST if b in (brand_name or "").lower())
            reasons.append(f"blocklisted brand (matched '{matching}')")

        if reasons:
            issues.append((brand_key, brand_name, email, title, domain, stage, reasons))

    if not issues:
        console.print("[green]✓ No quality issues found in EMAIL_DRAFTED / CONTACT_ENRICHED brands.[/green]")
        return

    console.print(f"\n[bold yellow]Quality audit — {len(issues)} issue(s) found{'  [FIX MODE]' if fix else '  (pass --fix to move back)'}:[/bold yellow]\n")

    for brand_key, brand_name, email, title, domain, stage, reasons in issues:
        colour = "red" if fix else "yellow"
        console.print(f"  [{colour}]▸[/{colour}] [cyan]{brand_key}[/cyan]  [bold]{brand_name}[/bold]  stage={stage}")
        console.print(f"     email={email}  title={title or 'n/a'}  domain={domain or 'n/a'}")
        for r in reasons:
            console.print(f"     [dim]• {r}[/dim]")

        if fix:
            now = _dt.utcnow().isoformat()
            db._sb().table("brands").update({
                "stage": "WEAK_BRAND",
                "contact_email": None,
                "contact_first_name": None,
                "contact_last_name": None,
                "contact_title": None,
                "apollo_person_id": None,
                "apollo_contact_id": None,
                "email_teardown": None,
                "updated_at": now,
            }).eq("brand_key", brand_key).execute()
            console.print(f"     [green]→ moved back to WEAK_BRAND (contact cleared)[/green]")

    if fix:
        console.print(f"\n[green]✓[/green] {len(issues)} brands reset to WEAK_BRAND. Run [cyan]auto-enrich[/cyan] to re-enrich with the new title filter.")
    else:
        console.print(f"\n[dim]Run with --fix to automatically move these brands back to WEAK_BRAND for re-enrichment.[/dim]")


# ---------------------------------------------------------------------------
# Pipeline ops (read-only display + manual stage moves)
# ---------------------------------------------------------------------------

def cmd_dashboard():
    from cli import show_dashboard
    show_dashboard()


def cmd_list(args):
    from cli import list_prospects
    stage = None
    limit = None
    for arg in args:
        if arg.startswith("--stage="):
            stage = arg.split("=", 1)[1].upper()
        elif arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
    list_prospects(stage, limit=limit)


def cmd_stats():
    from cli import show_stats
    show_stats()


def cmd_export(args):
    from cli import export_csv
    stage = None
    for arg in args:
        if arg.startswith("--stage="):
            stage = arg.split("=", 1)[1].upper()
    export_csv(stage)


def cmd_move(args):
    if len(args) < 2:
        console.print("[red]Usage: main.py move <prospect_id> <stage>[/red]")
        return
    from cli import move_stage
    move_stage(args[0], args[1])


def cmd_note(args):
    if len(args) < 2:
        console.print("[red]Usage: main.py note <prospect_id> <text>[/red]")
        return
    from cli import add_note
    add_note(args[0], " ".join(args[1:]))


def cmd_show(args):
    if not args:
        console.print("[red]Usage: main.py show <prospect_id>[/red]")
        return
    from cli import show_prospect
    show_prospect(args[0])


def cmd_replied(args):
    if not args:
        console.print("[red]Usage: main.py replied <prospect_id> [\"their reply text\"][/red]")
        return
    from cli import mark_replied
    reply_text = " ".join(args[1:]) if len(args) > 1 else None
    mark_replied(args[0], reply_text)


def cmd_brand_replied(args):
    """brand-replied <brand_key> — mark brand REPLIED + stamp replied_at."""
    if not args:
        console.print("[red]Usage: main.py brand-replied <brand_key>[/red]")
        return
    import db
    db.init_db()
    db.set_brand_replied(args[0])
    console.print(f"[green]✓[/green] {args[0]} → REPLIED")


def cmd_reply_stats():
    """reply-stats — reply rate by worst Rufus axis at send."""
    import db
    db.init_db()
    rows = db.get_reply_stats_by_axis()
    if not rows:
        console.print("[dim]No sequenced brands with worst_axis_at_send yet.[/dim]")
        return
    console.print("\n[bold]Reply rate by worst Rufus axis at send:[/bold]\n")
    for r in rows:
        sent = r["sent"] or 0
        replied = r["replied"] or 0
        rate = (replied / sent * 100) if sent else 0.0
        console.print(
            f"  [cyan]{r['axis']:<14}[/cyan]  sent={sent:<4}  "
            f"replied={replied:<4}  rate=[bold]{rate:>5.1f}%[/bold]"
        )


def cmd_uniqueness_report(args):
    """uniqueness-report [--limit=N] — pairwise 5-gram overlap across last N drafts."""
    import db
    import cold_email
    limit = 50
    for arg in args:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                pass
    db.init_db()
    bodies = db.get_recent_brand_bodies(limit=limit)
    if len(bodies) < 2:
        console.print("[dim]Need at least 2 generated bodies to report overlap.[/dim]")
        return
    overlaps = []
    for i, body in enumerate(bodies):
        others = bodies[:i] + bodies[i + 1:]
        overlaps.append(cold_email.max_overlap(body, others))
    avg = sum(overlaps) / len(overlaps)
    worst = max(overlaps)
    over_threshold = sum(1 for o in overlaps if o > 0.25)
    console.print(
        f"\n[bold]Uniqueness report ({len(bodies)} drafts):[/bold]\n"
        f"  avg max-overlap:  {avg:.1%}\n"
        f"  worst overlap:    {worst:.1%}\n"
        f"  over 25% threshold: {over_threshold}/{len(bodies)}\n"
    )


def cmd_open(args):
    if not args:
        console.print("[red]Usage: main.py open <prospect_id>[/red]")
        return
    from cli import open_prospect_url
    open_prospect_url(args[0])


def cmd_pipeline_run(args):
    """pipeline-run [--limit=N] — Streaming async pipeline: enrich → score → draft.

    Runs all three LLM/Apollo stages with bounded concurrency over a single async
    event loop. Each stage's input is whatever rows the DB currently holds in
    that stage's source state, so reruns resume cleanly after interruption.
    """
    import db
    import pipeline as _pipeline

    limit = 50
    for a in args:
        if a.startswith("--limit="):
            try:
                limit = int(a.split("=", 1)[1])
            except ValueError:
                pass

    db.init_db()
    console.print(f"\n[bold bright_blue]━━━ Pipeline Run (limit={limit}) ━━━[/bold bright_blue]\n")
    stats = _pipeline.run_pipeline(limit=limit, console=console)
    console.print(
        f"\n[green]✓[/green] Pipeline complete: "
        f"enriched={stats.get('enriched', 0)}  "
        f"scored={stats.get('scored', 0)}  "
        f"drafted={stats.get('drafted', 0)}"
    )


def cmd_morning_routine(args):
    """morning [--dry-run] — Interactive morning routine cockpit for daily prospecting."""
    import morning_workflow
    morning_workflow.run_morning_cockpit(args)


# ---------------------------------------------------------------------------
# New strategy — mass prospecting, Claude email, Supabase sync, enriched CSV
# ---------------------------------------------------------------------------

def cmd_mass_prospect(args=()):
    """mass-prospect [--niches=a,b,...] [--per-niche=N] — Apollo search across 30+ niches in parallel."""
    import mass_prospect
    import config as _config

    niches = None
    per_niche = _config.MASS_PROSPECT_PER_NICHE
    for arg in args:
        if arg.startswith("--niches="):
            niches = [n.strip() for n in arg.split("=", 1)[1].split(",") if n.strip()]
        elif arg.startswith("--per-niche="):
            try:
                per_niche = int(arg.split("=", 1)[1])
            except ValueError:
                pass

    niche_list = niches or list(_config.APOLLO_NICHE_TAG_MAP.keys())
    console.print(
        f"\n[bold bright_blue]mass-prospect[/bold bright_blue] — "
        f"{len(niche_list)} niches × {per_niche}/niche target\n"
    )

    total = mass_prospect.run_mass_prospect(niches=niches, per_niche=per_niche, console=console)
    console.print(f"\n[green]✓[/green] Inserted {total} new brands.")

    if total > 0:
        console.print("\n[dim]Running mandatory ASIN backfill…[/dim]")
        try:
            import backfill_asins
            backfill_asins.run_backfill(console=console)
        except Exception as e:
            console.print(f"[yellow]Backfill warning: {e}[/yellow]")


def cmd_supabase_sync(args=()):
    """supabase-sync [--stage=STAGE] — Upsert brands + step emails to Supabase cloud PostgreSQL."""
    import supabase_sync
    import config as _config

    if not _config.SUPABASE_URL or not _config.SUPABASE_KEY:
        console.print("[red]SUPABASE_URL and SUPABASE_KEY must be set in .env[/red]")
        return

    stage = None
    for arg in args:
        if arg.startswith("--stage="):
            stage = arg.split("=", 1)[1].upper()

    console.print(f"\n[bold bright_blue]supabase-sync[/bold bright_blue]\n")

    try:
        result = supabase_sync.run_full_sync(stage_filter=stage, console=console)
        console.print(
            f"\n[green]✓[/green] brands={result.get('brands_upserted', 0)}  "
            f"step_emails={result.get('emails_upserted', 0)}  "
            f"errors={result.get('errors', 0)}"
        )
    except Exception as e:
        console.print(f"[red]Supabase sync failed: {e}[/red]")


def cmd_export_send(args=()):
    """export-send [--all-time] [--limit=N] [--out=path.csv] — Platform send CSV (email, first_name, subject_1, body_2..5)."""
    import export_send as _es

    all_time = "--all-time" in args
    out = next((a.split("=", 1)[1] for a in args if a.startswith("--out=")), None)
    lim = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--limit=")), None)
    path = _es.export_send(all_time=all_time, output_path=out, limit=lim, console=console)
    console.print(f"\n[green]✓[/green] Send CSV ready: [bold]{path}[/bold]")


def cmd_export_enriched(args=()):
    """export-enriched [--stage=STAGE] [--since=YYYY-MM-DD] [--out=path.csv] — Full 40-column enriched CSV."""
    import export_enriched as _ee

    stage = out = since = None
    for arg in args:
        if arg.startswith("--stage="):
            stage = arg.split("=", 1)[1].upper()
        elif arg.startswith("--out="):
            out = arg.split("=", 1)[1]
        elif arg.startswith("--since="):
            since = arg.split("=", 1)[1]

    path = _ee.export_enriched(output_path=out, stage_filter=stage, since=since, console=console)
    console.print(f"\n[green]✓[/green] Exported to [bold]{path}[/bold]")


def cmd_add_loom(args):
    """add-loom <brand_key> <loom_url> — Register Loom video, draft dynamic sequence, stage EMAIL_DRAFTED."""
    if len(args) < 2:
        console.print("[red]Usage: main.py add-loom <brand_key> <loom_url>[/red]")
        return
    import db
    import config as _config
    if _config.USE_CLAUDE_EMAIL:
        import claude_email as cold_email
    else:
        import cold_email
    db.init_db()
    brand_key = args[0]
    loom_url = args[1]

    brand = db.get_brand(brand_key)
    if not brand:
        console.print(f"[red]Brand {brand_key} not found[/red]")
        return

    if brand.anchor_asin == "apollo_direct":
        console.print(f"[red]Brand {brand_key} has no listing data (anchor_asin is apollo_direct)[/red]")
        return

    anchor = db.get_anchor_prospect(brand.anchor_asin)
    if not anchor:
        console.print(f"[red]Anchor prospect {brand.anchor_asin} not found for brand {brand_key}[/red]")
        return

    # Update Loom URL in database
    db.set_brand_loom_url(brand_key, loom_url)
    console.print(f"[green]✓[/green] Registered Loom URL for brand {brand_key}")

    # Reload brand from DB to ensure the Loom URL is picked up
    brand = db.get_brand(brand_key)

    # Regenerate sequence with Loom-specific copy
    console.print(f"[dim]Regenerating sequence with Loom CTAs…[/dim]")
    seq = cold_email.draft_sequence(brand, anchor, save=True)

    # Move brand stage to EMAIL_DRAFTED
    db.update_brand_stage(brand_key, "EMAIL_DRAFTED")
    console.print(f"[green]✓[/green] Sequence drafted and brand {brand_key} stage updated to EMAIL_DRAFTED.")

    avg_overlap = sum(s["overlap"] for s in seq["steps"].values()) / max(1, len(seq["steps"]))
    console.print(
        f"  [green]✓[/green] {brand_key}  axis={seq['worst_axis']}  "
        f"steps={len(seq['steps'])}  avg_overlap={avg_overlap:.0%}\n"
        f"  subj1=[italic]{seq['steps'][1]['subject']}[/italic]"
    )


def cmd_outstanding_looms(args=()):
    """outstanding-looms — List brands in CALCULATOR_USED or REPLIED stage without a recorded Loom video."""
    import db
    db.init_db()
    brands = db.get_brands_needing_loom(limit=50)
    if not brands:
        console.print("[dim]No brands currently require Loom recordings.[/dim]")
        return

    console.print(f"\n[bold]{len(brands)} brand(s) awaiting Loom recordings:[/bold]\n")
    for b in brands:
        console.print(
            f"  [cyan]{b.brand_key}[/cyan]  brand=[yellow]{b.brand_name}[/yellow]  "
            f"stage=[magenta]{b.stage}[/magenta]  email={b.contact_email or '—'}  "
            f"worst_axis={b.worst_axis_at_send or '—'}"
        )


def cmd_backend_audit(args):
    """backend-audit <asin> [--out=path.md] — Run backend COSMO analysis + competitors + Q&A seeds and write a Markdown brief.

    This command pulls the listing from the local database, pushes it to the
    Rufus/COSMO backend engine, and generates a structured audit brief you can
    reference when recording a Loom teardown.
    """
    import db
    import backend_client
    import config as _config

    db.init_db()

    if not args or args[0].startswith("--"):
        console.print("[red]Usage: main.py backend-audit <asin> [--out=path.md][/red]")
        return

    asin = args[0]
    out_path = next((a.split("=", 1)[1] for a in args if a.startswith("--out=")), None)

    # Fetch listing from local DB
    prospect = db.get_anchor_prospect(asin)
    if not prospect:
        console.print(f"[yellow]ASIN {asin} not found in local DB. Running backend audit with empty listing data.[/yellow]")
        title, bullets, description, brand = "", [], "", ""
    else:
        title = prospect.post_title or ""
        bullets = (prospect.post_body or "").split("\n") if prospect.post_body else []
        description = ""
        brand = prospect.brand or ""

    console.print(f"\n[bold bright_blue]backend-audit[/bold bright_blue] — {asin}\n")

    # Run full backend audit
    with console.status("[dim]Running backend COSMO analysis…[/dim]"):
        audit = backend_client.run_full_audit(
            asin=asin,
            title=title,
            bullets=bullets,
            description=description,
            brand=brand,
        )

    if not audit.get("backend_available"):
        console.print(f"[yellow]⚠ Backend unavailable ({_config.BACKEND_URL}). Ensure the backend server is running.[/yellow]")
        console.print("[dim]Falling back to local data only.[/dim]\n")

    # Print summary to console
    analysis = audit.get("analysis", {})
    if analysis:
        overall = analysis.get("overall_score", "N/A")
        grade = (
            "A" if isinstance(overall, (int, float)) and overall >= 80 else
            "B" if isinstance(overall, (int, float)) and overall >= 65 else
            "C" if isinstance(overall, (int, float)) and overall >= 50 else
            "D"
        )
        console.print(f"  [bold]COSMO Score:[/bold] {overall}/100  Grade {grade}")
        console.print(f"  [bold]Keyword Safety:[/bold] {analysis.get('keyword_safety', 'N/A')}")

        relations = analysis.get("relations", [])
        weak = [r for r in relations if r.get("confidence_score", 1.0) < 0.5]
        if weak:
            console.print(f"\n  [bold red]Top Semantic Gaps ({len(weak)} weak relations):[/bold red]")
            for r in weak[:5]:
                console.print(
                    f"    [red]•[/red] {r.get('relation', '')} ({r.get('cluster', '')}) — "
                    f"{r.get('confidence_score', 0):.0%} confidence"
                )

    competitors = audit.get("competitors", {})
    comp_profiles = competitors.get("competitor_profiles", [])
    if comp_profiles:
        console.print(f"\n  [bold]Competitors analyzed:[/bold] {len(comp_profiles)}")
        for cp in comp_profiles[:3]:
            console.print(
                f"    [dim]•[/dim] {cp.get('asin', '')} — {cp.get('title', '')[:50]} "
                f"(sim {cp.get('similarity', 0):.0%})"
            )

    qa = audit.get("qa_seeds", {})
    seeds = qa.get("seeds", [])
    if seeds:
        console.print(f"\n  [bold]Q&A Seeds:[/bold] {len(seeds)} generated")
        for s in seeds[:3]:
            console.print(f"    [dim]•[/dim] {s.get('question', '')[:60]}")

    # Write Markdown brief
    md = backend_client.format_audit_markdown(audit)
    from pathlib import Path
    from datetime import datetime
    if out_path:
        Path(out_path).write_text(md, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Audit brief written to [bold]{out_path}[/bold]")
    else:
        audit_dir = Path("audits")
        audit_dir.mkdir(exist_ok=True)
        safe_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        default_path = audit_dir / f"{asin}_{safe_ts}.md"
        default_path.write_text(md, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Audit brief written to [bold]{default_path}[/bold]")


# ---------------------------------------------------------------------------
COMMANDS = {
    # End-to-end
    "morning":           (cmd_morning_routine,   "Interactive morning routine cockpit for daily prospecting [--dry-run]"),
    "backend-audit":     (cmd_backend_audit,     "Run backend COSMO analysis + competitors + Q&A seeds for an ASIN <asin> [--out=path.md]"),
    "rufus-audit":       (cmd_rufus_audit,       "scrape → rule-score → rollup → enrich queue [cat …] [--limit=N] [--with-llm]"),
    "run-funnel-b":      (cmd_run_funnel_b,      "Full Funnel B pipeline: Apollo → ASIN backfill → Rufus score → teardown → CSV <category> [--limit=N]"),
    "pipeline-run":      (cmd_pipeline_run,      "Streaming async pipeline: enrich → score → draft over CONTACT_ENRICHED brands [--limit=N]"),

    # Granular Amazon → Rufus
    "amazon-scrape":          (cmd_amazon_scrape,          "Scrape one category (search → pre-filter → detail → BSR filter → rule-score → rollup) <cat> [--limit=N]"),
    "score":                  (cmd_score,                  "Run enhanced listing quality scoring on unscored listings"),
    "rufus-score":            (cmd_rufus_score,            "LLM Rufus score for WEAK_LISTING prospects [<id>] [--v2]"),
    "rufus-score-enriched":   (cmd_rufus_score_enriched,   "LLM Rufus-score ONLY anchor ASINs of CONTACT_ENRICHED brands (run after enrichment) [--v2]"),
    "consolidate-brands":     (cmd_consolidate_brands,     "Roll up WEAK_LISTING ASINs into brand-level rows"),

    # Apollo enrichment + sequence
    "auto-enrich":       (cmd_auto_enrich,       "Process WEAK_BRANDs and enrich them directly via Apollo API"),
    "auto-prospect":     (cmd_auto_prospect,     "Direct Apollo search for prospects in a category <category> [--limit=N]"),
    "enrich-queue":      (cmd_enrich_queue,      "List brands awaiting Apollo enrichment (Legacy MCP workflow)"),
    "set-enrichment":    (cmd_set_enrichment,    "Write Apollo enrichment results back to a brand"),
    "save-apollo-prospect":(cmd_save_apollo_prospect,"Save an Apollo-sourced contact directly at CONTACT_ENRICHED"),
    "apollo-enrich":     (cmd_apollo_enrich,     "Bulk-match + save Apollo contacts from JSON file --file=<path> [--grade=AB|A]"),
    "apollo-sequence":   (cmd_apollo_sequence,   "Create Apollo contacts + enroll in sequences for all EMAIL_DRAFTED brands [--limit=N] [--dry-run]"),
    "apollo-sequence-v3": (cmd_apollo_sequence_v3, "Resilient Apollo Sync & Sequence Enrollment (v3) [--limit=N] [--dry-run]"),
    "draft-emails":      (cmd_draft_emails,      "Generate cold-email teardown for CONTACT_ENRICHED brands"),
    "send-queue":        (cmd_send_queue,        "List EMAIL_DRAFTED brands ready for Apollo sequence"),
    "mark-sequenced":    (cmd_mark_sequenced,    "Mark brand as added to Apollo sequence"),
    "reply-classify":    (cmd_reply_classify,    "Classify inbound reply + auto-action <brand_key> \"<reply text>\""),
    "linkedin-export":   (cmd_linkedin_export,   "Export LinkedIn-ready CSV for EMAIL_DRAFTED brands [--limit=N] [--out=path.csv]"),
    "intent-score":      (cmd_intent_score,      "Compute intent scores for brands [<stage>] [--limit=N]"),
    "client-quality-score": (cmd_client_quality_score, "Compute client quality + reachability for brands [<stage>] [--limit=N]"),
    "competitor-scrape": (cmd_competitor_scrape, "Scrape top 3 competitors for brand(s) [<brand_key> …] [--batch] [--limit=N]"),
    "quality-check":     (cmd_quality_check,     "Audit EMAIL_DRAFTED queue for bad contacts [--fix to reset them]"),
    "mass-prospect":     (cmd_mass_prospect,     "Apollo search across 30+ niches in parallel → 500+ prospects/run [--niches=a,b] [--per-niche=N]"),
    "supabase-sync":     (cmd_supabase_sync,     "Upsert brands + step emails to Supabase cloud PostgreSQL [--stage=STAGE]"),
    "export-enriched":   (cmd_export_enriched,   "Full 40-column enriched CSV: contact + Rufus + emails [--stage=STAGE] [--since=YYYY-MM-DD] [--out=path.csv]"),
    "export-send":       (cmd_export_send,       "Platform send CSV: email,first_name,custom_subject_1,custom_body_2..5 [--all-time] [--out=path.csv]"),
    "add-loom":          (cmd_add_loom,          "Register a Loom video, redraft emails with Loom CTAs, advance to EMAIL_DRAFTED <brand_key> <loom_url>"),
    "outstanding-looms": (cmd_outstanding_looms, "List prospects awaiting Loom recordings (stage CALCULATOR_USED or REPLIED, no loom_url)"),

    # Pipeline ops
    "dashboard":     (cmd_dashboard,     "Pipeline overview panel"),
    "stats":         (cmd_stats,         "Conversion funnel summary"),
    "list":          (cmd_list,          "List prospects [--stage=STAGE]"),
    "show":          (cmd_show,          "Full detail view for prospect <id>"),
    "open":          (cmd_open,          "Open prospect <id> URL in browser"),
    "move":          (cmd_move,          "Move prospect <id> to <stage>"),
    "note":          (cmd_note,          "Add timestamped note to prospect <id>"),
    "export":        (cmd_export,        "Export to CSV [--stage=STAGE]"),
    "replied":       (cmd_replied,       "Mark prospect <id> as REPLIED"),
    "brand-replied": (cmd_brand_replied, "Mark brand <brand_key> as REPLIED + stamp replied_at"),
    "reply-stats":   (cmd_reply_stats,   "Reply rate broken down by worst Rufus axis at send"),
    "uniqueness-report": (cmd_uniqueness_report, "Pairwise 5-gram overlap across recent generated bodies [--limit=N]"),
}


def print_help():
    console.print("\n[bold]Optimus Rufus — Amazon listing audit → Apollo outreach[/bold]\n")
    console.print("[bold]Usage:[/bold] python main.py <command> [args]\n")
    for cmd, (_, desc) in COMMANDS.items():
        console.print(f"  [cyan]{cmd:<22}[/cyan] {desc}")
    console.print()


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return

    command = args[0].lower()
    rest = args[1:]

    if command not in COMMANDS:
        console.print(f"[red]Unknown command: {command}[/red]")
        print_help()
        sys.exit(1)

    fn, _ = COMMANDS[command]
    takes_args = {
        "morning", "backend-audit", "rufus-audit", "amazon-scrape", "rufus-score", "list", "move", "note",
        "show", "export", "replied", "open", "set-enrichment", "mark-sequenced",
        "save-apollo-prospect", "auto-prospect", "apollo-enrich", "apollo-sequence", "apollo-sequence-v3",
        "run-funnel-b", "quality-check", "brand-replied", "uniqueness-report",
        "draft-emails", "pipeline-run",
        "mass-prospect", "supabase-sync", "export-enriched", "export-send",
        "client-quality-score", "rufus-score-enriched",
        "add-loom", "outstanding-looms",
    }
    if command in takes_args:
        fn(rest)
    else:
        fn()


if __name__ == "__main__":
    main()
