#!/usr/bin/env python3
"""Optimus Rufus — Scientific Lead Scoring & Prioritization Suite (v3).

Loads all consolidated brands in your database, evaluates them using a highly 
precise Scientific Prioritization Matrix (SPM) formula, synchronizes the database 
reachability index, and outputs a complete outreach priority leaderboard.
"""
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Adjust path to find everything
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db
import client_quality_scorer
from rich.console import Console
from datetime import datetime
from resilience import retry_call

console = Console()

@retry_call(max_attempts=5, backoff_seconds=1.0)
def resilient_batch_update(updates: list):
    """Performs a single bulk upsert to update reachability indexes rapidly."""
    if not updates:
        return
    db._sb().table("brands").upsert(updates).execute()


def main():
    db.init_db()
    console.print("[bold bright_green]🔬 LAUNCHING SCIENTIFIC LEAD SCORING FUNNEL (SPM v3)[/bold bright_green]")
    console.print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Fetch all active weak/enriched brands in the funnel
    console.print("[dim]Fetching active brands from Supabase...[/dim]")
    res_brands = db._sb().table("brands").select("*").in_("stage", ["WEAK_BRAND", "CONTACT_ENRICHED", "EMAIL_DRAFTED"]).execute()
    brands = [db._row_to_brand(r) for r in res_brands.data]
    console.print(f"  Loaded {len(brands)} brands.")
    
    if not brands:
        console.print("[yellow]No active brands found in funnel stages (WEAK_BRAND, CONTACT_ENRICHED, EMAIL_DRAFTED). Finalizing...[/yellow]")
        return
        
    # Batch load all anchor prospects to maximize speed and bypass sequential lag
    console.print("[dim]Batch pre-fetching anchor prospects...[/dim]")
    anchor_asins = [b.anchor_asin for b in brands if b.anchor_asin]
    prospect_map = {}
    
    if anchor_asins:
        try:
            res_prospects = db._sb().table("prospects").select("*").in_("asin", anchor_asins).execute()
            for row in res_prospects.data:
                p = db._row_to_prospect(row)
                if p.asin:
                    prospect_map[p.asin] = p
            console.print(f"  Batch fetched {len(prospect_map)} anchor prospects successfully.")
        except Exception as e:
            console.print(f"[yellow]⚠ Batch fetch failed: {e}. Falling back to lazy loading.[/yellow]")

    ranked_results = []
    db_updates = []
    
    # Create a lookup map of raw dictionaries to preserve all existing columns for PostgreSQL NOT NULL constraint safety
    brands_dict_map = {r["brand_key"]: r for r in res_brands.data}

    console.print("\n[bold bright_blue]🔄 COMPUTING SCIENTIFIC COMPOSITE MATRIX (SPM)...[/bold bright_blue]")
    
    for brand in brands:
        anchor = prospect_map.get(brand.anchor_asin)
        if not anchor:
            # Fall back to single lookup if missing from batch map
            anchor = db.get_anchor_prospect(brand.anchor_asin)
            
        if not anchor:
            continue
            
        # 1. Listing Quality Gaps (LQS) -> 40% Weight
        lqs_val = anchor.quality_score or anchor.weakness_score or 0
        
        # 2. Revenue Potential -> 25% Weight
        rev_val, _ = client_quality_scorer.score_revenue_potential(anchor)
        rev_normalized = rev_val * 4.0  # Normalize 0-25 to 0-100
        
        # 3. Decision Maker Access -> 20% Weight
        dm_val, _ = client_quality_scorer.score_decision_maker_access(brand)
        dm_normalized = dm_val * 4.0   # Normalize 0-25 to 0-100
        
        # 4. Niche / Category Attractiveness -> 15% Weight
        cat_val, _ = client_quality_scorer.score_category_attractiveness(anchor.category)
        cat_normalized = cat_val * 10.0 # Normalize 0-10 to 0-100
        
        # Calculate Scientific Prioritization Matrix (SPM) Score
        spm_score = (0.40 * lqs_val) + (0.25 * rev_normalized) + (0.20 * dm_normalized) + (0.15 * cat_normalized)
        spm_score = min(100, max(0, int(spm_score)))
        
        # Store for reporting
        ranked_results.append({
            "brand_key": brand.brand_key,
            "brand_name": brand.brand_name or brand.brand_key,
            "category": anchor.category or "Unknown",
            "spm_score": spm_score,
            "lqs": lqs_val,
            "cqs": brand.client_quality_score or 0,
            "asins": brand.asin_count or 1,
            "anchor_asin": brand.anchor_asin
        })
        
        # Stage for batch database sync preserving full record structure
        row_dict = brands_dict_map.get(brand.brand_key)
        if row_dict:
            row_dict["reachability_index"] = spm_score
            db_updates.append(row_dict)

    # Sync with database via a single resilient batch call
    if db_updates:
        try:
            console.print(f"[dim]Syncing {len(db_updates)} scores back to Supabase via batch upsert...[/dim]")
            resilient_batch_update(db_updates)
        except Exception as e:
            console.print(f"[red] ✗ Batch update failed: {e}. Matrix calculated but DB sync unverified.[/red]")

    # Sort results by scientific score desc
    ranked_results.sort(key=lambda x: x["spm_score"], reverse=True)

    console.print(f"\n[green]✓[/green] Scientific ranking sweep complete! Processed [cyan]{len(ranked_results)}[/cyan] brand records.\n")

    # --- Step 3: Write comprehensive markdown directory report ---
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scientific_outreach_ranking.md")
    console.print(f"[dim]Generating scientific prioritised outreach directory report: {report_path}...[/dim]")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Scientific Outreach Prioritization Directory (SPM v3)\n\n")
        f.write("This prioritised outreach leaderboard was computed scientifically using your multi-dimensional matrix:\n")
        f.write("$$S_{SPM} = 40\\% \\cdot LQS + 25\\% \\cdot S_{rev} + 20\\% \\cdot S_{dm} + 15\\% \\cdot S_{cat}$$\n\n")
        f.write("| Rank | Brand Name | SPM Score | Listing Gaps (LQS) | Client Score (CQS) | Weak ASINs | Worst Anchor ASIN | Category | Brand Key |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for idx, r in enumerate(ranked_results, 1):
            name = r["brand_name"].removeprefix("Visit the ").removesuffix(" Store")
            f.write(f"| {idx} | **{name}** | **{r['spm_score']}** | {r['lqs']} | {r['cqs']} | {r['asins']} | `{r['anchor_asin']}` | {r['category']} | `{r['brand_key']}` |\n")

    console.print(f"[bold bright_green]🎉 LEAD PRIORITIZATION ROLL-OUT COMPLETE![/bold bright_green]")
    console.print(f"Leaderboard has been successfully written locally to [cyan]{report_path}[/cyan]!")

if __name__ == "__main__":
    main()
