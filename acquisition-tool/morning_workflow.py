"""Morning Prospecting Cockpit - Daily outreach & pipeline optimization workflow."""
import sys
import os
import time
import asyncio
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

import db
import config
from models import STAGES, Brand, Prospect
import apollo_api
import cli

console = Console()

def print_banner():
    console.print()
    console.print(Panel(
        "[bold yellow]🌅 RUFUS PIPELINE COMMAND DECK 🌅[/bold yellow]\n"
        "[dim]Aggregating computational linguistics, Amazon Listing Integrity, and Reachability telemetry.[/dim]",
        border_style="yellow",
        box=box.ROUNDED,
        title="[bold yellow]Optimus Rufus Outbound Mission Control[/bold yellow]",
        title_align="center"
    ))
    console.print()

def show_cockpit_dashboard():
    """Renders the comprehensive daily overview cockpit with advanced scientific metrics."""
    db.init_db()
    counts = db.get_pipeline_counts()
    
    # 1. Pipeline Funnel Summary Table
    funnel_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    funnel_table.add_column("Pipeline Stage", style="bold bright_white")
    funnel_table.add_column("Count", justify="right")
    
    active_stages = [
        "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND", 
        "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED",
        "CALCULATOR_USED", "CALCULATOR_SUBMITTED", "REPLIED", 
        "DEMO_SCHEDULED", "PAID"
    ]
    for stage in active_stages:
        count = counts.get(stage, 0)
        color = cli._stage_color(stage)
        funnel_table.add_row(f"[{color}]{stage}[/{color}]", f"[bold {color}]{count}[/bold {color}]")

    # 2. Advanced Metrics Telemetry
    adv = db.get_dashboard_advanced_metrics()
    
    telemetry_text = (
        f"[bold bright_cyan]📊 ACQUISITION INTEL TELEMETRY[/bold bright_cyan]\n"
        f" • [cyan]Listing Integrity (ALII):[/cyan] [bold yellow]{adv['avg_lqs']:.1f}/100[/bold yellow] (max: {adv['max_lqs']})\n"
        f" • [cyan]Client Quality Score (CQS):[/cyan] [bold green]{adv['avg_cqs']:.1f}/100[/bold green]\n"
        f" • [cyan]Reachability Index (RI):[/cyan]    [bold magenta]{adv['avg_ri']:.1f}/100[/bold magenta] (max: {adv['max_ri']})\n\n"
        f"[bold bright_magenta]🗣️ COMPUTATIONAL LINGUISTICS[/bold bright_magenta]\n"
        f" • [magenta]Flesch Readability Ease:[/magenta]   [bold white]{adv['avg_flesch']:.1f}[/bold white] (target: >60)\n"
        f" • [magenta]Lexical Density (TTR):[/magenta]   [bold white]{adv['avg_ttr']:.1%}[/bold white] (target: >50%)\n"
        f" • [magenta]COSMO Relation Density:[/magenta]   [bold white]{adv['avg_cosmo']:.2f}[/bold white]/100w\n\n"
        f"[bold dim]Scored Listings: {adv['total_scored_listings']} | Scored Brands: {adv['total_scored_brands']}[/bold dim]"
    )
    
    # 3. Performance & Suggestions Panel
    sequenced = counts.get("SEQUENCED", 0)
    replied = counts.get("REPLIED", 0)
    warm_looms = len(db.get_brands_needing_loom(limit=100))
    drafts_ready = len(db.get_brands_ready_to_send(limit=100))
    enriched_waiting = len(db.get_brands_by_stage("CONTACT_ENRICHED", limit=100))
    
    conversion_rate = (replied / sequenced * 100) if sequenced > 0 else 0.0
    
    health_text = (
        f"[bold cyan]Funnel Stats:[/bold cyan] Sequenced: {sequenced} | Inbound Replies: {replied} (Conv: [bold green]{conversion_rate:.1f}%[/bold green])\n"
        f"[bold magenta]Daily Action Queue:[/bold magenta]\n"
        f" • [magenta]Warm Leads Awaiting Looms:[/magenta] [bold yellow]{warm_looms}[/bold yellow] 🔥\n"
        f" • [magenta]Enriched Leads Awaiting Score/Draft:[/magenta] [bold cyan]{enriched_waiting}[/bold cyan] ⚙️\n"
        f" • [magenta]Verified Drafts in Send Queue:[/magenta] [bold green]{drafts_ready}[/bold green] ✉️\n\n"
    )
    
    # Dynamic suggestion based on bottlenecks
    suggestion = "[bold green]💡 Pipeline Recommendation:[/bold green] "
    if warm_looms > 0:
        suggestion += "Prioritize recording Loom videos for warm leads. Personal video teardowns are your highest-converting asset!"
    elif enriched_waiting > 0:
        suggestion += "You have enriched leads waiting. Run MOFU Processing to calculate listing integrity/CQS and generate email drafts."
    elif drafts_ready > 5:
        suggestion += "Your send queue has ready drafts. Run the Send Queue manager to audit and enroll them in Apollo sequences."
    elif counts.get("WEAK_BRAND", 0) < 10:
        suggestion += "Your lead database is running thin. Schedule a new top-of-funnel Amazon category scrape or Apollo prospecting run."
    else:
        suggestion += "Pipeline healthy! Process ready drafts and monitor your inbox for replies."
        
    health_text += suggestion

    console.print(Panel(
        Columns([funnel_table, telemetry_text], equal=True),
        title="[bold yellow]🌅 RUFUS PIPELINE COCKPIT TELEMETRY[/bold yellow]",
        border_style="yellow",
        box=box.DOUBLE
    ))
    
    console.print(Panel(
        health_text,
        title="[bold cyan]🎯 DAILY PRIORITY CHECK[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()

def step_1_handle_warm_leads(dry_run=False):
    """Priority #1: Process replies and calculator hits needing Loom recordings."""
    console.print("[bold yellow]🚀 STEP: Warm Leads Action Center (Personalized Loom Teardowns)[/bold yellow]")
    
    brands = db.get_brands_needing_loom(limit=25)
    if not brands:
        console.print("[green]✓ No warm leads currently awaiting Loom videos. Great job![/green]\n")
        return
        
    console.print(f"Found [bold yellow]{len(brands)}[/bold yellow] warm prospect(s) waiting for custom Loom teardowns:\n")
    
    table = Table(box=box.ROUNDED)
    table.add_column("Brand Key", style="cyan")
    table.add_column("Brand Name", style="bold")
    table.add_column("Stage", style="magenta")
    table.add_column("Contact Name")
    table.add_column("Worst Rufus Axis", style="red")
    
    for b in brands:
        table.add_row(
            b.brand_key,
            b.brand_name,
            b.stage,
            f"{b.contact_first_name or ''} {b.contact_last_name or ''}".strip() or "—",
            b.worst_axis_at_send or "—"
        )
    console.print(table)
    console.print()
    
    # Action prompt
    record = Confirm.ask("Would you like to register a recorded Loom video now?")
    if record:
        brand_key = Prompt.ask("Enter the [bold cyan]Brand Key[/bold cyan]")
        brand = db.get_brand(brand_key)
        if not brand:
            console.print(f"[red]✗ Brand '{brand_key}' not found.[/red]\n")
            return
            
        loom_url = Prompt.ask("Paste the Loom Video URL")
        if not loom_url.startswith("http"):
            console.print("[red]✗ Invalid URL. Must start with http/https.[/red]\n")
            return
            
        if dry_run:
            console.print(f"[dim][DRY RUN] Would update {brand_key} with Loom URL: {loom_url} and advance to EMAIL_DRAFTED[/dim]\n")
            return
            
        with console.status(f"[dim]Registering Loom & drafting Loom CTAs for {brand_key}…[/dim]"):
            # Update Loom URL
            db.set_brand_loom_url(brand_key, loom_url)
            
            # Fetch anchor prospect to draft Loom email sequence
            anchor = db.get_anchor_prospect(brand.anchor_asin)
            if not anchor:
                console.print(f"[red]✗ Anchor prospect {brand.anchor_asin} not found for {brand_key}. Cannot draft sequence.[/red]\n")
                return
                
            # Reload brand to pick up new Loom URL
            brand = db.get_brand(brand_key)
            
            # Regenerate copy with Loom custom CTAs
            if config.USE_CLAUDE_EMAIL:
                import claude_email as cold_email
            else:
                import cold_email
                
            seq = cold_email.draft_sequence(brand, anchor, save=True)
            db.update_brand_stage(brand_key, "EMAIL_DRAFTED")
            
        console.print(f"[green]✓ Registered Loom video for [bold]{brand_key}[/bold]![/green]")
        console.print(f"[green]✓ Personal email sequence regenerated. Brand advanced to [bold]EMAIL_DRAFTED[/bold].[/green]\n")

def step_mofu_process_leads(dry_run=False):
    """Priority: Process enriched contacts into drafts (CQS calculation + LLM score + draft generation)."""
    console.print("[bold yellow]⚙️ STEP: Process Enriched Leads (Middle-of-Funnel)[/bold yellow]")
    
    # Check how many brands are in CONTACT_ENRICHED stage
    db.init_db()
    brands = db.get_brands_by_stage("CONTACT_ENRICHED", limit=200)
    if not brands:
        console.print("[green]✓ No brands currently in CONTACT_ENRICHED stage awaiting processing.[/green]\n")
        return
        
    console.print(f"Found [bold yellow]{len(brands)}[/bold yellow] enriched brand(s) awaiting LLM scoring and email drafting:\n")
    
    table = Table(box=box.ROUNDED)
    table.add_column("Brand Key", style="cyan")
    table.add_column("Brand Name", style="bold")
    table.add_column("Email", style="green")
    table.add_column("Reachability Index", style="magenta")
    
    for b in brands[:15]:
        ri = b.reachability_index if b.reachability_index is not None else "—"
        table.add_row(
            b.brand_key,
            b.brand_name,
            b.contact_email or "—",
            str(ri)
        )
    console.print(table)
    if len(brands) > 15:
        console.print(f"[dim]... and {len(brands) - 15} more[/dim]")
    console.print()
    
    process = Confirm.ask(f"Would you like to run the automated scoring and email drafting pipeline on these [bold yellow]{len(brands)}[/bold yellow] brands now?")
    if process:
        if dry_run:
            console.print("[dim][DRY RUN] Would initiate CQS calculation, LLM scoring, and draft generation for enriched brands.[/dim]\n")
            return
            
        console.print("\n[bold bright_blue]━━━ Processing Enriched Leads ━━━[/bold bright_blue]\n")
        
        # 1. Compute CQS and RI first to ensure telemetry is fully populated
        console.print("[bold]Stage 1/3: Calculating Client Quality and Reachability Indices...[/bold]")
        import main
        main.cmd_client_quality_score(["CONTACT_ENRICHED", f"--limit={len(brands)}"])
        
        # 2. Run LLM scoring on these enriched anchor ASINs
        console.print("\n[bold]Stage 2/3: Running LLM Rufus scoring on enriched anchor ASINs...[/bold]")
        main.cmd_rufus_score_enriched()
        
        # 3. Draft dynamic 5-step email sequences
        console.print("\n[bold]Stage 3/3: Generating personalized cold email sequences...[/bold]")
        main.cmd_draft_emails()
        
        console.print("\n[bold green]✓ Processing complete! Newly drafted leads are now staged in the send queue.[/bold green]\n")

def step_2_send_queue_manager(dry_run=False):
    """Priority #2: Quality audit and send ready drafts to Apollo sequence."""
    console.print("[bold yellow]✉️ STEP: Send Queue & Quality Audit[/bold yellow]")
    
    brands = db.get_brands_ready_to_send(limit=100)
    if not brands:
        console.print("[green]✓ Send queue is empty. No drafts ready to send.[/green]\n")
        return
        
    console.print(f"There are [bold green]{len(brands)}[/bold green] personalized email draft(s) ready in the send queue.")
    
    # Run the quality-check audit automatically to catch bad contacts before sending
    with console.status("[dim]Auditing send queue for spam indicators & bad contacts…[/dim]"):
        import apollo_api
        issues = []
        for b in brands:
            reasons = []
            # 1. Title verification
            if b.contact_title and not apollo_api._is_target_title(b.contact_title):
                reasons.append(f"Title '{b.contact_title}' — not a founder/owner/CEO")
            # 2. Blocklist verification
            if any(block in b.brand_name.lower() for block in config.AMAZON_BRAND_BLOCKLIST):
                reasons.append("Blocklisted brand")
            # 3. Domain mismatch
            if b.contact_email and b.domain:
                email_domain = b.contact_email.split("@")[1].lower() if "@" in b.contact_email else ""
                clean_domain = b.domain.lower().replace("www.", "")
                if email_domain and clean_domain and email_domain != clean_domain and email_domain.split(".")[0] not in clean_domain:
                    reasons.append(f"Email domain '{email_domain}' ≠ brand domain '{clean_domain}'")
                    
            if reasons:
                issues.append((b, reasons))
                
    if issues:
        console.print(Panel(
            f"[bold red]⚠ Warning: {len(issues)} draft(s) flagged for quality concerns:[/bold red]\n" +
            "\n".join([f" • [cyan]{b.brand_key}[/cyan] ({b.brand_name}): {', '.join(reasons)}" for b, reasons in issues[:10]]) +
            (f"\n[dim]...and {len(issues)-10} more[/dim]" if len(issues) > 10 else "") +
            "\n\n[dim]It is highly recommended to clean these flagged leads to protect domain reputation.[/dim]",
            border_style="red"
        ))
        
        clean = Confirm.ask("Would you like to auto-clean and reset flagged drafts?", default=True)
        if clean:
            if dry_run:
                console.print("[dim][DRY RUN] Would reset flagged brands back to WEAK_BRAND and clear contact info.[/dim]\n")
            else:
                from datetime import datetime
                for b, _ in issues:
                    db._sb().table("brands").update({
                        "stage": "WEAK_BRAND",
                        "contact_email": None,
                        "contact_first_name": None,
                        "contact_last_name": None,
                        "contact_title": None,
                        "apollo_person_id": None,
                        "apollo_contact_id": None,
                        "email_teardown": None,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("brand_key", b.brand_key).execute()
                console.print(f"[green]✓ Reset {len(issues)} brands to WEAK_BRAND for re-enrichment.[/green]\n")
                # Refresh our list of clean brands
                brands = db.get_brands_ready_to_send(limit=100)
                if not brands:
                    console.print("[dim]No clean drafts remaining in queue.[/dim]\n")
                    return
        else:
            console.print("[yellow]⚠ Proceeding with all ready drafts in queue.[/yellow]\n")
            
    # One-click sequence enrollment
    send = Confirm.ask(f"Would you like to enroll the [bold green]{len(brands)}[/bold green] verified drafts in their Apollo sequences now?")
    if send:
        if dry_run:
            console.print("[dim][DRY RUN] Would initiate Apollo campaign enrollment for the send queue.[/dim]\n")
            return
            
        console.print("[dim]Enrolling contacts via Apollo REST API…[/dim]")
        
        # We can dynamically invoke the apollo_sequence logic inline
        import main
        main.cmd_apollo_sequence([f"--limit={len(brands)}"])
        console.print()

def step_3_pipeline_refuel(dry_run=False):
    """Priority #3: Outbound fuel. Schedule/run lead generation runs in the background."""
    console.print("[bold yellow]⛽ STEP: Fuel the Pipeline (Top of Funnel Lead Gen)[/bold yellow]")
    
    refuel = Confirm.ask("Would you like to kick off a new prospecting run today?")
    if not refuel:
        console.print("[dim]Outbound fuel skipped. Ready to start daily tasks![/dim]\n")
        return
        
    console.print(
        "\nSelect your prospecting channel:\n"
        "  [1] [bold cyan]Funnel A (Amazon-first Scrape):[/bold cyan] Scrapes specific e-commerce keywords, pre-filters, enriches, and scores.\n"
        "  [2] [bold cyan]Funnel B (Apollo-first Search):[/bold cyan] Searches Apollo for supplement/skincare founders, auto-backfills ASINs, and scores."
    )
    
    channel = Prompt.ask("Select funnel option", choices=["1", "2"], default="1")
    
    if channel == "1":
        # Funnel A Categories selection
        console.print(f"\nDefault high-relevance niches: [bold cyan]{', '.join(config.AMAZON_SEED_CATEGORIES[:5])}[/bold cyan]")
        use_default = Confirm.ask("Use default high-relevance niches?")
        
        categories = []
        if not use_default:
            niche_input = Prompt.ask("Enter custom keywords separated by commas (e.g. collagen peptides, beard oil)")
            categories = [c.strip() for c in niche_input.split(",") if c.strip()]
        else:
            categories = config.AMAZON_SEED_CATEGORIES[:3]
            
        limit = int(Prompt.ask("Enter harvest limit per category", default="30"))
        
        if dry_run:
            console.print(f"[dim][DRY RUN] Would run: python main.py rufus-audit {', '.join(categories)} --limit={limit}[/dim]\n")
            return
            
        console.print(f"\n[green]✓ Launching Amazon Scrape & Lead Enrichment pipeline for categories: {', '.join(categories)}...[/green]")
        console.print("[bold yellow]This is running in foreground. You can leave this process open while it works.[/bold yellow]\n")
        
        import main
        args = categories + [f"--limit={limit}"]
        # run rufus-audit (scrape, filter, rollup, enrich queue)
        main.cmd_rufus_audit(args)
        
        # Run auto-enrichment on any new WEAK_BRANDs
        console.print("\n[dim]Auto-enriching newly found brands via Apollo REST API…[/dim]")
        main.cmd_auto_enrich()
        
    else:
        # Funnel B Apollo Prospecting
        console.print("\nApollo Controlled Vocab Niches: supplements, skincare, cosmetics, haircare, pet care, baby products")
        category = Prompt.ask("Enter Apollo keyword/category", default="supplements")
        limit = int(Prompt.ask("Enter target number of contacts to enrich", default="15"))
        
        if dry_run:
            console.print(f"[dim][DRY RUN] Would run: python main.py run-funnel-b {category} --limit={limit}[/dim]\n")
            return
            
        console.print(f"\n[green]✓ Launching Apollo search & Amazon backfill pipeline for {category}...[/green]\n")
        import main
        main.cmd_run_funnel_b([category, f"--limit={limit}"])

    console.print("\n[bold green]✓ Pipeline replenished! Tomorrow's personalized drafts are now cooking in the database.[/bold green]\n")

def run_morning_cockpit(args=()):
    """Main runner for the morning prospecting routine."""
    dry_run = "--dry-run" in args
    
    print_banner()
    
    while True:
        show_cockpit_dashboard()
        
        console.print("[bold yellow]Select a pipeline action to execute:[/bold yellow]")
        console.print("  [1] [bold yellow]Loom Action Center[/bold yellow] (Warm Leads needing Loom recordings)")
        console.print("  [2] [bold cyan]MOFU Processing[/bold cyan] (Score & Draft Enriched Leads)")
        console.print("  [3] [bold green]Send Queue Manager[/bold green] (Audit & Enroll verified drafts to Apollo)")
        console.print("  [4] [bold magenta]TOFU Replenishment[/bold magenta] (Scrape Amazon / Apollo Prospecting)")
        console.print("  [5] [bold red]Exit Cockpit[/bold red]\n")
        
        choice = Prompt.ask("Enter selection", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice == "1":
            try:
                step_1_handle_warm_leads(dry_run)
            except Exception as e:
                console.print(f"[red]Error in Loom Action Center: {e}[/red]\n")
        elif choice == "2":
            try:
                step_mofu_process_leads(dry_run)
            except Exception as e:
                console.print(f"[red]Error in MOFU Processing: {e}[/red]\n")
        elif choice == "3":
            try:
                step_2_send_queue_manager(dry_run)
            except Exception as e:
                console.print(f"[red]Error in Send Queue Manager: {e}[/red]\n")
        elif choice == "4":
            try:
                step_3_pipeline_refuel(dry_run)
            except Exception as e:
                console.print(f"[red]Error in TOFU Replenishment: {e}[/red]\n")
        elif choice == "5":
            console.print(Panel(
                "[bold green]🎉 COCKPIT OPERATION COMPLETED 🎉[/bold green]\n"
                "[dim]Outbound systems active. Have a highly profitable day![/dim]",
                border_style="green",
                box=box.ROUNDED,
                title="[bold green]Goodbye[/bold green]"
            ))
            break
            
        # Give a small pause and prompt before reloading dashboard
        Prompt.ask("\nPress [bold enter]Enter[/bold enter] to return to the cockpit dashboard")
        console.print()
