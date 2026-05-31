"""Full-field enriched CSV export — all 40+ columns in a single SQL JOIN.

Unlike export_apollo.py (Apollo import format only), this exports every field
useful for analysis: contact info, Rufus 4-axis scores, weakness signals,
LinkedIn, all 5 email steps, teardown, and pipeline metadata.

Usage:
    python export_enriched.py [--stage=EMAIL_DRAFTED] [--since=2026-01-01] [--out=my.csv]
    python main.py export-enriched [--stage=STAGE] [--since=YYYY-MM-DD] [--out=path.csv]
"""
import csv
import sys
from datetime import datetime

import db


COLUMNS = [
    # Contact
    "first_name", "last_name", "email", "organization_name", "title",
    "linkedin_url", "domain",
    "apollo_person_id", "apollo_organization_id", "apollo_contact_id",
    # Listing
    "anchor_asin", "category", "asin_count",
    "max_weakness_score", "weakness_signals",
    # Rufus 4-axis
    "rufus_score",
    "intent_alignment_score", "attribute_density_score",
    "conversational_readability_score", "qa_coverage_score",
    "rufus_citation_probability", "rufus_summary", "rufus_top_weaknesses",
    # 5-step email copy
    "custom_subject_1", "custom_body_1",
    "custom_subject_2", "custom_body_2",
    "custom_subject_3", "custom_body_3",
    "custom_subject_4", "custom_body_4",
    "custom_subject_5", "custom_body_5",
    # Meta
    "worst_axis_at_send", "email_teardown", "stage", "source",
    "created_at", "updated_at",
]


def export_enriched(output_path=None, stage_filter=None, since=None, console=None):
    """Export full enriched CSV. Returns the output file path."""
    if output_path is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = f"export_enriched_{ts}.csv"

    # Fetch brands
    q = db._sb().table("brands").select("*").order("updated_at", desc=True)
    if stage_filter:
        q = q.eq("stage", stage_filter)
    else:
        q = q.in_("stage", ["EMAIL_DRAFTED", "SEQUENCED"])
    if since:
        q = q.gte("updated_at", since)
    brands_data = q.execute().data

    if not brands_data:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
        msg = f"Exported 0 rows → {output_path}"
        (console.print(f"[green]✓[/green] {msg}") if console else print(msg))
        return output_path

    # Fetch prospects for anchor ASINs (LEFT JOIN equivalent)
    anchor_asins = [b["anchor_asin"] for b in brands_data if b.get("anchor_asin") and b["anchor_asin"] != "apollo_direct"]
    prospect_by_asin: dict[str, dict] = {}
    if anchor_asins:
        pres = db._sb().table("prospects").select("*").in_("asin", anchor_asins).execute()
        for p in pres.data:
            if p.get("asin") and p["asin"] not in prospect_by_asin:
                prospect_by_asin[p["asin"]] = p

    # Fetch step emails for all brands
    brand_keys = [b["brand_key"] for b in brands_data]
    steps_by_brand = db.get_brand_step_emails_batch(brand_keys)

    rows = []
    for b in brands_data:
        p = prospect_by_asin.get(b.get("anchor_asin") or "", {})
        steps = steps_by_brand.get(b["brand_key"], {})
        row = {
            "first_name":            b.get("contact_first_name") or "",
            "last_name":             b.get("contact_last_name") or "",
            "email":                 b.get("contact_email") or "",
            "organization_name":     b.get("brand_name") or "",
            "title":                 b.get("contact_title") or "",
            "linkedin_url":          b.get("contact_linkedin") or "",
            "domain":                b.get("domain") or "",
            "apollo_person_id":      b.get("apollo_person_id") or "",
            "apollo_organization_id":b.get("apollo_organization_id") or "",
            "apollo_contact_id":     b.get("apollo_contact_id") or "",
            "anchor_asin":           b.get("anchor_asin") or "",
            "category":              b.get("category") or "",
            "asin_count":            b.get("asin_count") or "",
            "max_weakness_score":    b.get("max_weakness_score") or "",
            "weakness_signals":      b.get("weakness_signals") or "",
            "rufus_score":                      p.get("rufus_score") or "",
            "intent_alignment_score":           p.get("intent_alignment_score") or "",
            "attribute_density_score":          p.get("attribute_density_score") or "",
            "conversational_readability_score": p.get("conversational_readability_score") or "",
            "qa_coverage_score":                p.get("qa_coverage_score") or "",
            "rufus_citation_probability":       p.get("rufus_citation_probability") or "",
            "rufus_summary":                    p.get("rufus_summary") or "",
            "rufus_top_weaknesses":             p.get("rufus_top_weaknesses") or "",
            "custom_subject_1": steps.get(1, {}).get("subject", ""),
            "custom_body_1":    steps.get(1, {}).get("body", ""),
            "custom_subject_2": steps.get(2, {}).get("subject", ""),
            "custom_body_2":    steps.get(2, {}).get("body", ""),
            "custom_subject_3": steps.get(3, {}).get("subject", ""),
            "custom_body_3":    steps.get(3, {}).get("body", ""),
            "custom_subject_4": steps.get(4, {}).get("subject", ""),
            "custom_body_4":    steps.get(4, {}).get("body", ""),
            "custom_subject_5": steps.get(5, {}).get("subject", ""),
            "custom_body_5":    steps.get(5, {}).get("body", ""),
            "worst_axis_at_send": b.get("worst_axis_at_send") or "",
            "email_teardown":     b.get("email_teardown") or "",
            "stage":              b.get("stage") or "",
            "source":             b.get("source") or "",
            "created_at":         str(b.get("created_at") or ""),
            "updated_at":         str(b.get("updated_at") or ""),
        }
        rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    msg = f"Exported {len(rows)} rows → {output_path}"
    (console.print(f"[green]✓[/green] {msg}") if console else print(msg))
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export enriched prospects CSV")
    parser.add_argument("--stage", default=None, help="Filter by stage (default: EMAIL_DRAFTED + SEQUENCED)")
    parser.add_argument("--since", default=None, help="ISO date lower bound on updated_at (e.g. 2026-01-01)")
    parser.add_argument("--out", default=None, help="Output CSV path")
    args = parser.parse_args()
    export_enriched(output_path=args.out, stage_filter=args.stage, since=args.since)
