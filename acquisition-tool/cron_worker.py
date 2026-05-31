"""Optimus Rufus Continuous Background Agent Worker Daemon"""
import os
import sys
import time
import asyncio
from datetime import datetime

# Path setups to align imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db
import config
import main

async def run_pipeline():
    """Runs the outreach pipeline (Funnel B) non-interactively."""
    print(f"[{datetime.now().isoformat()}] Starting Daily Outreach Pipeline...")
    
    # 1. Harvest prospects from Apollo (Supplement niche default or custom)
    target_category = os.getenv("OUTREACH_CATEGORY", "supplements")
    enrich_limit = int(os.getenv("DAILY_ENRICH_LIMIT", "20"))
    
    print(f"[{datetime.now().isoformat()}] STAGE 1: Auto-prospecting '{target_category}' via Apollo...")
    try:
        main.cmd_auto_prospect([target_category, f"--limit={enrich_limit}"])
    except Exception as e:
        print(f"Error in Auto-Prospect stage: {e}")
    
    # 2. Backfill ASINs from Amazon
    print(f"[{datetime.now().isoformat()}] STAGE 2: Running Amazon ASIN fuzzy-match backfill...")
    try:
        import backfill_asins
        backfill_asins.run_backfill()
    except Exception as e:
        print(f"Error in Backfill ASIN stage: {e}")

    # 3. LLM Rufus scoring
    print(f"[{datetime.now().isoformat()}] STAGE 3: Scoring enriched anchor listings via Gemini...")
    try:
        main.cmd_rufus_score_enriched()
    except Exception as e:
        print(f"Error in Rufus Score stage: {e}")

    # 4. Draft personalised emails
    print(f"[{datetime.now().isoformat()}] STAGE 4: Drafting customized cold-email sequences...")
    try:
        main.cmd_draft_emails()
    except Exception as e:
        print(f"Error in Email Drafting stage: {e}")

    # 5. Enroll in Apollo campaigns
    print(f"[{datetime.now().isoformat()}] STAGE 5: Enrolling ready drafts to Apollo sequence...")
    try:
        # Fetch EMAIL_DRAFTED brands ready to send
        db.init_db()
        ready_brands = db.get_brands_ready_to_send(limit=enrich_limit)
        if ready_brands:
            print(f"Found {len(ready_brands)} drafts. Pushing to Apollo sequences...")
            main.cmd_apollo_sequence([f"--limit={len(ready_brands)}"])
        else:
            print("No new verified drafts ready in queue.")
    except Exception as e:
        print(f"Error in Apollo enrollment stage: {e}")
        
    print(f"[{datetime.now().isoformat()}] Background agent outreach pass complete!")

async def main_loop():
    interval_hours = float(os.getenv("AGENT_INTERVAL_HOURS", "24"))
    print(f"============================================================")
    print(f"Optimus Rufus continuous outreach background agent started!")
    print(f"Running every {interval_hours} hours. Sleep mode: active.")
    print(f"============================================================")
    
    # Trigger a dry run or warm run on startup to confirm credentials
    if os.getenv("RUN_ON_STARTUP", "true").lower() == "true":
        await run_pipeline()

    while True:
        await asyncio.sleep(interval_hours * 3600)
        await run_pipeline()

if __name__ == "__main__":
    asyncio.run(main_loop())
