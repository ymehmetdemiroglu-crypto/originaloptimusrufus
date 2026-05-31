#!/usr/bin/env python3
"""Optimus Rufus — Recovery Scrape Orchestrator.

Loads the completed Apify datasets from our strategic blowout scrape runs,
processes listing quality scoring, brand consolidation, and Supabase sync
without re-running the scraper and burning any extra credits.

Usage:
    python recover_mass_scrape.py
"""
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Adjust path to find everything
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from rich.console import Console
from apify_client import ApifyClient

import config
import db
import amazon_scraper
import listing_quality_scorer
import brand_rollup
import client_quality_scorer

console = Console()

# Hardcoded run IDs from our successful Apify runs in task-537
SEARCH_RUN_ID = "DUtt9v51eRzCbd9gB"
DETAIL_RUN_IDS = [
    "3jj5cTyMM0IR09x7r",  # Batch 1 (200 ASINs)
    "6wIdHYLR4NowDnzIX",  # Batch 2 (200 ASINs)
    "IesErHJ5vSeB70JmG"   # Batch 3 (109 ASINs)
]

def main():
    db.init_db()
    
    if not config.APIFY_TOKEN:
        console.print("[red]Error: APIFY_TOKEN is not set in .env[/red]")
        sys.exit(1)
        
    client = ApifyClient(config.APIFY_TOKEN)
    
    console.print("[bold bright_blue]🔄 COMMENCING PIPELINE RECOVERY FROM COMPLETED RUNS[/bold bright_blue]")
    console.print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # --- Step 1: Reconstruct ASIN-to-Category mappings from search dataset ---
    console.print(f"[dim]Step 1/4: Loading search dataset {SEARCH_RUN_ID}…[/dim]")
    try:
        search_run = client.run(SEARCH_RUN_ID).get()
        search_dataset_id = getattr(search_run, "default_dataset_id", getattr(search_run, "defaultDatasetId", ""))
        if not search_dataset_id:
            raise ValueError(f"Could not resolve dataset ID for run {SEARCH_RUN_ID}")
            
        raw_search = list(client.dataset(search_dataset_id).iterate_items())
        console.print(f"[dim]  Loaded {len(raw_search)} raw search records.[/dim]")
    except Exception as e:
        console.print(f"[red]Error fetching search run: {e}[/red]")
        sys.exit(1)
        
    categories = config.AMAZON_SEED_CATEGORIES
    keyword_to_category = {cat.lower(): cat for cat in categories}
    
    # Pre-filter and map ASINs to category exactly as amazon_scraper.scrape_many does
    category_state = {
        cat: {"asins": [], "seen_asin": set(), "seen_brand": {}, "rejects": {}, "cached": 0, "raw_count": 0}
        for cat in categories
    }
    asin_to_category = {}
    
    for item in raw_search:
        kw = (item.get("keyword") or item.get("searchQuery") or "").lower()
        cat = keyword_to_category.get(kw)
        if cat is None:
            title = (item.get("title") or "").lower()
            for c in categories:
                if c.lower() in title:
                    cat = c
                    break
            if cat is None:
                continue
                
        st = category_state[cat]
        st["raw_count"] += 1
        
        asin = item.get("asin") or item.get("ASIN")
        if not asin or asin in st["seen_asin"]:
            continue
        st["seen_asin"].add(asin)
        
        # In recovery, let's process all ASINs that were surviving pre-filters
        ok, reason = amazon_scraper._search_passes_prefilter(item)
        if not ok:
            st["rejects"][reason] = st["rejects"].get(reason, 0) + 1
            continue
            
        brand_key = amazon_scraper._brand_key(item.get("brand") or item.get("manufacturer") or "")
        if brand_key:
            if st["seen_brand"].get(brand_key, 0) >= config.AMAZON_MAX_ASINS_PER_BRAND:
                st["rejects"]["brand_cap"] = st["rejects"].get("brand_cap", 0) + 1
                continue
            st["seen_brand"][brand_key] = st["seen_brand"].get(brand_key, 0) + 1
            
        st["asins"].append(asin)
        asin_to_category[asin] = cat

    # --- Step 2: Load detail records from completed detail datasets ---
    console.print(f"\n[dim]Step 2/4: Loading and parsing detailed records from runs: {', '.join(DETAIL_RUN_IDS)}…[/dim]")
    detail_items = []
    for rid in DETAIL_RUN_IDS:
        try:
            detail_run = client.run(rid).get()
            detail_dataset_id = getattr(detail_run, "default_dataset_id", getattr(detail_run, "defaultDatasetId", ""))
            if not detail_dataset_id:
                console.print(f"[yellow]⚠ Warning: Could not resolve dataset ID for detail run {rid}. Skipping.[/yellow]")
                continue
            items = list(client.dataset(detail_dataset_id).iterate_items())
            detail_items.extend(items)
            console.print(f"  Loaded {len(items)} items from run {rid}")
        except Exception as e:
            console.print(f"[yellow]⚠ Warning: Error reading detail run {rid}: {e}. Skipping.[/yellow]")
            
    console.print(f"Total detailed items loaded: {len(detail_items)}")
    
    # --- Step 3: Parse, Filter BSR, and Persist prospects ---
    console.print(f"\n[dim]Step 3/4: Parsing, post-detail filtering, and inserting prospects to Supabase…[/dim]")
    rejects = {}
    kept = 0
    new_count = 0
    errors = 0
    
    for item in detail_items:
        asin = item.get("asin") or item.get("ASIN")
        if not asin:
            continue
            
        cat = asin_to_category.get(asin)
        if not cat:
            # Fallback to general category matching if missing from search mapping
            title = (item.get("title") or item.get("productTitle") or "").lower()
            for c in categories:
                if c.lower() in title:
                    cat = c
                    break
            if not cat:
                cat = categories[0] if categories else "Health"
                
        prospect = amazon_scraper._to_prospect(item, cat)
        if prospect is None:
            rejects["malformed"] = rejects.get("malformed", 0) + 1
            continue
            
        ok, reason = amazon_scraper._passes_post_detail_filters(prospect)
        if not ok:
            rejects[reason] = rejects.get(reason, 0) + 1
            continue
            
        kept += 1
        try:
            if db.upsert_listing(prospect):
                new_count += 1
        except Exception as e:
            errors += 1
            console.print(f"[red]Error saving ASIN {asin}: {e}[/red]")
            
    breakdown = ", ".join(f"{k}={v}" for k, v in sorted(rejects.items())) or "(none)"
    console.print(f"\n[green]✓[/green] Amazon Scrape recovered — kept {kept} ASINs after filters. New inserts: {new_count}. Errors: {errors}. Rejects breakdown: {breakdown}\n")
    
    if errors > 0:
        console.print("[red]❌ CRITICAL: Supabase inserts failed. Please disable RLS on prospects and brands in the Supabase Dashboard and run this script again.[/red]")
        sys.exit(1)
        
    # --- Step 4: Run scoring, Brand Rollup, and Client Scoring ---
    console.print("[dim]Step 4/4: Commencing local pipeline modules…[/dim]")
    
    # 4a. Local Listing Quality Scoring (LQS)
    unscored = db.get_unscored_listings(limit=1500)
    if unscored:
        console.print(f"[dim]Quality-scoring {len(unscored)} listings locally…[/dim]")
        weak_count = listing_quality_scorer.score_all(unscored)
        console.print(f"[green]✓[/green] {weak_count} flagged as WEAK_LISTING\n")
    else:
        console.print("[dim]No unscored listings in prospects table.[/dim]\n")
        
    # 4b. Consolidation / Brand Rollup
    console.print("[dim]Running Brand Rollup consolidation…[/dim]")
    created_brands = brand_rollup.consolidate(console=console)
    console.print(f"[green]✓[/green] Rollup complete — {created_brands} brand(s) created\n")
    
    # 4c. Client Quality Scoring (CQS)
    console.print("[dim]Evaluating Client Quality Scores (CQS) on weak brands…[/dim]")
    cq_scored = client_quality_scorer.score_all_brands(stage="WEAK_BRAND", limit=200, console=console)
    console.print(f"[green]✓[/green] Client scoring complete — {cq_scored} brand(s) evaluated\n")
    
    # Summary stats
    enrich_queue = db.get_brands_needing_enrichment(limit=10)
    console.print("\n[bold bright_green]🎉 RECOVERY PIPELINE RUN COMPLETE![/bold bright_green]")
    console.print(f"Total Kept ASINs: {kept}")
    console.print(f"New ASINs Inserted: {new_count}")
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
