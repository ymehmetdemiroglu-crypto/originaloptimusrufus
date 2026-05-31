"""Helper for the /generate-emails Claude Code skill.

Reads a JSON draft file written by Claude Code and persists it to SQLite +
syncs to Supabase. Called by the skill after Claude generates email copy.

Usage:
    py save_email_draft.py --file=draft.json [--no-supabase]

draft.json shape:
{
  "brand_key": "somebranda",
  "worst_axis": "intent",
  "steps": [
    {"step": 1, "subject": "...", "body": "..."},
    {"step": 2, "subject": "...", "body": "..."},
    {"step": 3, "subject": "...", "body": "..."},
    {"step": 4, "subject": "...", "body": "..."},
    {"step": 5, "subject": "...", "body": "..."}
  ]
}
"""
import json
import re
import sys
from pathlib import Path

import config
import db
from cold_email import max_overlap, _word_count


def _shingles(text, n=5):
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)}


def save_draft(draft: dict, sync_supabase: bool = True):
    brand_key = draft.get("brand_key", "").strip()
    worst_axis = draft.get("worst_axis", "intent").strip().lower()
    steps = draft.get("steps", [])

    if not brand_key:
        print("[save_email_draft] ERROR: brand_key is required")
        sys.exit(1)

    db.init_db()

    brand = db.get_brand(brand_key)
    if brand is None:
        print(f"[save_email_draft] ERROR: brand '{brand_key}' not found in DB")
        sys.exit(1)

    print(f"\nSaving draft for: {brand.brand_name} ({brand_key})")
    print(f"Worst axis: {worst_axis}")

    for s in steps:
        step_num = int(s.get("step", 0))
        subject = (s.get("subject") or "").strip()
        body = (s.get("body") or "").strip()

        if not step_num or not subject or not body:
            print(f"  [step {step_num}] SKIP — missing subject or body")
            continue

        corpus = db.get_recent_brand_bodies(limit=50, step_num=step_num)
        overlap = max_overlap(body, corpus)
        wc = _word_count(body)

        db.save_brand_step_email(brand_key, step_num, subject, body, overlap)
        print(f"  [step {step_num}] saved  subject='{subject[:50]}'  words={wc}  overlap={overlap:.0%}")

    # Mirror step 1 onto brands.custom_subject / custom_body for Apollo back-compat
    step1 = next((s for s in steps if s.get("step") == 1), None)
    if step1:
        db.save_brand_custom_copy(
            brand_key=brand_key,
            subject=(step1.get("subject") or "").strip(),
            body=(step1.get("body") or "").strip(),
            worst_axis=worst_axis,
            teardown=(step1.get("body") or "").strip(),
        )

    db.update_brand_stage(brand_key, "EMAIL_DRAFTED")
    print(f"  -> stage: EMAIL_DRAFTED")

    if sync_supabase and config.SUPABASE_URL and config.SUPABASE_KEY:
        try:
            import supabase_sync
            r = supabase_sync.run_full_sync()
            print(f"  -> Supabase: brands={r['brands_upserted']} emails={r['emails_upserted']} errors={r['errors']}")
        except Exception as e:
            print(f"  -> Supabase sync skipped: {e}")


def main():
    file_path = None
    sync_supabase = True

    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            file_path = arg.split("=", 1)[1]
        elif arg == "--no-supabase":
            sync_supabase = False

    if not file_path:
        print("Usage: py save_email_draft.py --file=draft.json [--no-supabase]")
        sys.exit(1)

    p = Path(file_path)
    if not p.exists():
        print(f"ERROR: file not found: {file_path}")
        sys.exit(1)

    draft = json.loads(p.read_text(encoding="utf-8"))
    save_draft(draft, sync_supabase=sync_supabase)


if __name__ == "__main__":
    main()
