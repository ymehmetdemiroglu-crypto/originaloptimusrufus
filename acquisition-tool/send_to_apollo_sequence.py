#!/usr/bin/env python3
"""Optimus Rufus — Resilient Apollo Sequence Sync & Enrollment Utility (v3).

Queries all verified EMAIL_DRAFTED brands, runs exhaustive pre-flight quality
audits (spam blocks, founder titles, domain mismatches), maps custom personalized 
templates to Apollo under both subject_X/body_X and custom_subject_X/custom_body_X 
namespaces, and automatically enrolls them in your sequences.
"""
import sys
import os
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.box import ROUNDED, DOUBLE

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db
import config
import apollo_api
from models import Brand

console = Console()

def run_preflight_check(brand: Brand) -> list[str]:
    """Exhaustive lead audit to protect domain reputation and sequence alignment."""
    issues = []
    
    # 1. Founder Title Gate
    if brand.contact_title and not apollo_api._is_target_title(brand.contact_title):
        issues.append(f"Non-founder contact title: '{brand.contact_title}'")
        
    # 2. Blocklisted Mega-Brands
    name_lower = (brand.brand_name or "").lower()
    if any(block in name_lower for block in config.AMAZON_BRAND_BLOCKLIST):
        issues.append(f"Mega-brand blocklist collision (name matches blocklist)")
        
    # 3. Domain Mismatch Audit
    if brand.contact_email and brand.domain:
        email_parts = brand.contact_email.split("@")
        if len(email_parts) > 1:
            email_domain = email_parts[1].lower()
            clean_domain = brand.domain.lower().replace("www.", "")
            email_prefix = email_domain.split(".")[0]
            if email_domain != clean_domain and email_prefix not in clean_domain:
                issues.append(f"Domain mismatch: Email '{email_domain}' ≠ Listing '{clean_domain}'")
                
    return issues

def main():
    parser = argparse.ArgumentParser(description="Optimus Rufus Outbound Sequence Sync & Enrollment Deck")
    parser.add_argument("--limit", type=int, default=100, help="Max number of prospects to enroll")
    parser.add_argument("--dry-run", action="store_true", help="Audit prospects and simulate sequence sync without modifications")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip spam block and founder title pre-flight safeguards")
    args = parser.parse_args()

    db.init_db()
    
    console.print(Panel(
        "[bold yellow]🛸 OUTBOUND ACQUISITION PILOT — APOLLO DECK v3[/bold yellow]\n"
        "[dim]Synchronizing local listing teardown copies, custom dynamic pitch links, and sequence payloads.[/dim]",
        box=DOUBLE,
        border_style="yellow"
    ))
    
    console.print("[dim]Fetching EMAIL_DRAFTED brands ready for outreach...[/dim]")
    brands = db.get_brands_ready_to_send(limit=args.limit)
    
    if not brands:
        console.print("[yellow]No brands in EMAIL_DRAFTED stage waiting in the send queue.[/yellow]")
        return
        
    console.print(f"Loaded [bold green]{len(brands)}[/bold green] brands from database.")
    
    seq_id = config.APOLLO_SEQUENCE_ID
    send_from_id = config.APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID
    
    if not seq_id or not send_from_id:
        console.print("[bold red]✗ Configuration Error: APOLLO_SEQUENCE_ID or APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID is missing from .env.[/bold red]")
        sys.exit(1)
        
    audit_table = Table(box=ROUNDED, show_header=True)
    audit_table.add_column("Brand Key", style="cyan")
    audit_table.add_column("Contact Email", style="green")
    audit_table.add_column("Score (RI)", justify="center", style="magenta")
    audit_table.add_column("Pre-flight Audit Status", style="bold")
    
    clean_brands: list[Brand] = []
    flagged_count = 0
    
    for b in brands:
        if args.skip_preflight:
            issues = []
        else:
            issues = run_preflight_check(b)
            
        ri_label = str(b.reachability_index) if b.reachability_index is not None else "—"
        
        if issues:
            flagged_count += 1
            issues_str = ", ".join(issues)
            audit_table.add_row(b.brand_key, b.contact_email or "—", ri_label, f"[red]Flagged: {issues_str}[/red]")
            
            # Auto-progress bad leads out of active pipelines
            if not args.dry_run:
                now = datetime.utcnow().isoformat()
                db._sb().table("brands").update({
                    "stage": "WEAK_BRAND",
                    "contact_email": None,
                    "contact_first_name": None,
                    "contact_last_name": None,
                    "contact_title": None,
                    "apollo_person_id": None,
                    "apollo_contact_id": None,
                    "email_teardown": None,
                    "updated_at": now
                }).eq("brand_key", b.brand_key).execute()
        else:
            audit_table.add_row(b.brand_key, b.contact_email or "—", ri_label, "[green]PASSED[/green]")
            clean_brands.append(b)
            
    console.print(audit_table)
    
    if flagged_count > 0 and not args.dry_run:
        console.print(f"[yellow]⚠ Auto-cleaned {flagged_count} flagged leads: Reset back to WEAK_BRAND for re-enrichment.[/yellow]")
        
    if not clean_brands:
        console.print("\n[yellow]No verified clean leads remaining for sequence enrollment.[/yellow]\n")
        return
        
    console.print(f"\n[bold bright_blue]🔄 SYNCHRONIZING {len(clean_brands)} PROSPECTS TO APOLLO SEQUENCE...[/bold bright_blue]")
    if args.dry_run:
        console.print("[yellow]DRY RUN ACTIVE: Simulating sync payloads. No API calls will be made.[/yellow]")
        
    enrolled = 0
    failed = 0
    
    for b in clean_brands:
        # Construct fully-redundant custom variables map mapping both subject_X and custom_subject_X namespaces
        custom_fields = {}
        
        # Step 1 Legacy / Fallback fields
        if b.custom_subject:
            custom_fields["custom_subject"] = b.custom_subject
        if b.custom_body:
            custom_fields["custom_body"] = b.custom_body
        if b.email_teardown:
            custom_fields["weakness_teardown"] = b.email_teardown
        if b.category:
            custom_fields["custom_category"] = b.category
            
        # Standardized 5-step custom templates variables
        steps_map = db.get_brand_step_emails(b.brand_key)
        for step_num, payload in steps_map.items():
            # Standard namespace (expected by APOLLO_SEQUENCE_SETUP.md)
            custom_fields[f"subject_{step_num}"] = payload["subject"]
            custom_fields[f"body_{step_num}"] = payload["body"]
            # Current python codebase namespace
            custom_fields[f"custom_subject_{step_num}"] = payload["subject"]
            custom_fields[f"custom_body_{step_num}"] = payload["body"]
            
        if args.dry_run:
            console.print(f"  [dim]dry-run[/dim] {b.brand_key} ({b.contact_email}) would be created in Apollo and enrolled in sequence {seq_id}")
            continue
            
        # 1. Create or match contact on Apollo
        last = b.contact_last_name or ""
        contact_id = apollo_api.create_contact(
            email=b.contact_email,
            first_name=b.contact_first_name or "",
            last_name=last,
            title=b.contact_title or "",
            organization_name=b.brand_name,
            website_url=f"https://{b.domain}" if b.domain and not b.domain.startswith("http") else (b.domain or ""),
            typed_custom_fields=custom_fields or None
        )
        
        if not contact_id:
            console.print(f"  [red]✗[/red] {b.brand_key} — Apollo contact creation failed")
            failed += 1
            continue
            
        # 2. Enroll contact in sequence under Yahya's mailbox
        success = apollo_api.add_to_sequence(seq_id, contact_id, send_from_id)
        if not success:
            console.print(f"  [yellow]⚠[/yellow] {b.brand_key} — contact '{contact_id}' created, but sequence enrollment failed")
            db.set_brand_apollo_contact(b.brand_key, contact_id)
            failed += 1
            continue
            
        # 3. Success: progress pipeline stage to SEQUENCED in database
        db.set_brand_apollo_contact(b.brand_key, contact_id)
        db.update_brand_stage(b.brand_key, "SEQUENCED")
        
        console.print(f"  [green]✓[/green] [bold]{b.brand_key}[/bold] — Synced & Enrolled (Contact ID: {contact_id})")
        enrolled += 1
        
    console.print(Panel(
        f"[green]Outbound Sync Summary Completion Deck[/green]\n\n"
        f" • [cyan]Prospects Enrolled successfully:[/cyan] [bold green]{enrolled}[/bold green]\n"
        f" • [cyan]Synchronization Failures:[/cyan]        [bold red]{failed}[/bold red]\n"
        f" • [cyan]Filtered Flagged Prospects:[/cyan]    [bold yellow]{flagged_count}[/bold yellow]",
        title="[bold green]Sync Process Complete[/bold green]",
        box=ROUNDED,
        border_style="green"
    ))

if __name__ == "__main__":
    main()
