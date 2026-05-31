#!/usr/bin/env python3
"""Optimus Rufus — Strategic Mass Scrape Orchestrator.

Runs a highly optimized, budget-aware multi-category Amazon listing harvest.
Collapses N category search and details scraper calls to minimize Apify credit burn,
applies loosened BSR/review targeting filters, and performs automatic local quality
scoring and brand-rollup consolidation in Supabase.

Usage:
    python mass_scrape.py                    # Scrape Tier 1 (default)
    python mass_scrape.py --dry-run          # Print budget estimates only
    python mass_scrape.py --tier 1,2         # Run Tier 1 + Tier 2
    python mass_scrape.py --limit 15         # Override limit per category (default 30)
"""
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
from datetime import datetime
from rich.console import Console

# Adjust path if run from root
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
import db
import amazon_scraper
import listing_quality_scorer
import brand_rollup
import client_quality_scorer

console = Console()


def check_apify_balance() -> tuple[float, float]:
    """Retrieve Apify monthly usage limit and current spent amount from the API."""
    if not config.APIFY_TOKEN:
        return 0.0, 0.0
    try:
        from apify_client import ApifyClient
        client = ApifyClient(config.APIFY_TOKEN)
        limits_data = client.user().limits()
        
        # Access pydantic attributes safely
        max_usd = getattr(limits_data.limits, "max_monthly_usage_usd", 0.0)
        spent_usd = getattr(limits_data.current, "monthly_usage_usd", 0.0)
        
        return float(max_usd), float(spent_usd)
    except Exception as e:
        console.print(f"[yellow]⚠ Could not fetch Apify balance from API: {e}[/yellow]")
        return 0.0, 0.0


def print_budget_sheet(tiers: list[int], limit_per_cat: int, balance_remaining: float):
    """Print a beautiful breakdown of the strategic categories and expected costs."""
    console.print("\n[bold bright_blue]📊 Strategic Mass Scrape — Cost & Yield Estimates[/bold bright_blue]")
    console.print("═" * 65)
    
    total_categories = 0
    categories_to_run = []
    
    if 1 in tiers:
        categories_to_run.extend(config.AMAZON_TIER_1_CATEGORIES)
        console.print(f"• [bold green]Tier 1 (Supplements + Beauty):[/bold green] {len(config.AMAZON_TIER_1_CATEGORIES)} niches")
    if 2 in tiers:
        categories_to_run.extend(config.AMAZON_TIER_2_CATEGORIES)
        console.print(f"• [bold yellow]Tier 2 (Pet + Trending Wellness):[/bold yellow] {len(config.AMAZON_TIER_2_CATEGORIES)} niches")
    if 3 in tiers:
        categories_to_run.extend(config.AMAZON_TIER_3_CATEGORIES)
        console.print(f"• [bold cyan]Tier 3 (Kitchen + Office + Baby):[/bold cyan] {len(config.AMAZON_TIER_3_CATEGORIES)} niches")
        
    total_categories = len(categories_to_run)
    
    # 5 pages of search = ~100 items per category
    search_cost_est = total_categories * 5 * 20 * (0.10 / 1000) # $0.10/1k items
    
    # Detail cost estimate assumes 40% survival rate after brand-cap and filters
    estimated_survivors = int(total_categories * limit_per_cat * 0.40)
    detail_cost_est = estimated_survivors * (8.00 / 1000) # $8.00/1k items
    
    total_cost_est = search_cost_est + detail_cost_est
    
    console.print("═" * 65)
    console.print(f"  [bold]Categories Selected:[/bold]      {total_categories}")
    console.print(f"  [bold]Limit Per Category:[/bold]       {limit_per_cat} ASINs")
    console.print(f"  [bold]Estimated Search Cost:[/bold]     ${search_cost_est:.2f}")
    console.print(f"  [bold]Estimated Details Cost:[/bold]    ${detail_cost_est:.2f} (~{estimated_survivors} ASINs)")
    console.print(f"  [bold]Total Est. Apify Cost:[/bold]     [bold bright_green]${total_cost_est:.2f}[/bold bright_green]")
    
    if balance_remaining > 0:
        console.print(f"  [bold]Apify Balance Remaining:[/bold]  ${balance_remaining:.2f}")
        if total_cost_est > balance_remaining:
            console.print(f"  [bold red]⚠ WARNING:[/bold red] Estimated cost (${total_cost_est:.2f}) exceeds remaining balance (${balance_remaining:.2f})!")
        else:
            console.print(f"  [bold green]✓ Balance Sufficient![/bold green] (Covered with ${balance_remaining - total_cost_est:.2f} buffer)")
            
    console.print("═" * 65 + "\n")
    return categories_to_run


def main():
    parser = argparse.ArgumentParser(description="Strategic Mass Scrape Orchestrator")
    parser.add_argument("--tier", default="1", help="Niche Tiers to scrape, comma-separated (e.g. 1 or 1,2 or 1,2,3)")
    parser.add_argument("--limit", type=int, default=30, help="ASIN detail cap per category (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Print budget sheet and exits without scraping")
    args = parser.parse_args()
    
    db.init_db()
    
    # Parse tiers argument
    try:
        tiers = [int(t.strip()) for t in args.tier.split(",")]
    except ValueError:
        console.print("[red]Error: --tier must be comma-separated integers (e.g. 1 or 1,2)[/red]")
        sys.exit(1)
        
    # Check Apify limits
    max_usd, spent_usd = check_apify_balance()
    balance_remaining = max_usd - spent_usd
    
    # Print budget breakdown and resolve categories
    categories = print_budget_sheet(tiers, args.limit, balance_remaining)
    
    if args.dry_run:
        console.print("[yellow]Dry-run finished. No scraping performed.[/yellow]")
        return
        
    if not categories:
        console.print("[red]No categories resolved for the selected tiers.[/red]")
        return
        
    # Safeguard balance check before commencing
    if balance_remaining > 0 and balance_remaining < 1.0:
        console.print("[red]Error: Remaining Apify balance is too low (< $1.00). Aborting scrape.[/red]")
        return

    console.print(f"[bold bright_blue]🚀 COMMENCING STRATEGIC MASS SCRAPE[/bold bright_blue]")
    console.print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1+2+3. Batched Scrape across all categories in single batch search + details calls
    try:
        total_kept, total_new = amazon_scraper.scrape_many(
            categories, limit_per_category=args.limit, console=console
        )
    except Exception as e:
        console.print(f"\n[red]CRITICAL Scrape Error: {e}[/red]")
        sys.exit(1)
        
    console.print(f"\n[green]✓[/green] Amazon Scrape complete — {total_kept} listings kept, {total_new} new\n")
    
    # Step 4. Local Listing Quality Scoring (LQS)
    unscored = db.get_unscored_listings(limit=1500)
    if unscored:
        console.print(f"[dim]Quality-scoring {len(unscored)} listings locally…[/dim]")
        weak_count = listing_quality_scorer.score_all(unscored)
        console.print(f"[green]✓[/green] {weak_count} flagged as WEAK_LISTING\n")
    else:
        console.print("[dim]No unscored listings in prospects table.[/dim]\n")
        
    # Step 5. Consolidation / Brand Rollup
    console.print("[dim]Running Brand Rollup consolidation…[/dim]")
    created_brands = brand_rollup.consolidate(console=console)
    console.print(f"[green]✓[/green] Rollup complete — {created_brands} brand(s) created\n")
    
    # Step 6. Client Quality Scoring (CQS)
    console.print("[dim]Evaluating Client Quality Scores (CQS) on weak brands…[/dim]")
    cq_scored = client_quality_scorer.score_all_brands(stage="WEAK_BRAND", limit=200, console=console)
    console.print(f"[green]✓[/green] Client scoring complete — {cq_scored} brand(s) evaluated\n")
    
    # Step 7. Print statistics and next step
    enrich_queue = db.get_brands_needing_enrichment(limit=10)
    console.print("\n[bold bright_green]🎉 MASS SCRAPE COMPLETE![/bold bright_green]")
    console.print(f"Total Kept ASINs: {total_kept}")
    console.print(f"New ASINs Inserted: {total_new}")
    console.print(f"New Brands Consolidated: {created_brands}")
    
    if enrich_queue:
        console.print(f"\n[bold]{len(enrich_queue)} brands at the top of the enrichment queue:[/bold]")
        for b in enrich_queue:
            console.print(f"  • brand_key=[cyan]{b.brand_key}[/cyan] (RI={b.reachability_index or 0}, max_weakness={b.max_weakness_score or 0})")
        console.print("\n[dim]Next step: Run 'python main.py auto-enrich' to fetch verified contact details via Apollo API.[/dim]")
    else:
        console.print("\n[dim]No new brands ready for enrichment.[/dim]")


if __name__ == "__main__":
    main()
