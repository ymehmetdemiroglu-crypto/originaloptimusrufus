"""Platform-ready send CSV export.

Produces the exact column format required for direct import into cold-email
sending platforms (Instantly, Lemlist, Smartlead, etc.):

    email, first_name, custom_subject_1,
    custom_body_2, custom_body_3, custom_body_4, custom_body_5

Step 1 body is intentionally omitted — the platform renders it from the
sequence template. Only the subject and the 4 follow-up bodies are needed.

Usage:
    py export_send.py [--all-time] [--out=filename.csv]
    py main.py export-send [--all-time] [--out=filename.csv]
"""
import csv
import sys
from datetime import datetime

import db

FIELDNAMES = [
    "email",
    "first_name",
    "custom_subject_1",
    "custom_body_2",
    "custom_body_3",
    "custom_body_4",
    "custom_body_5",
]


def export_send(all_time=False, output_path=None, limit=None, console=None):
    """Export EMAIL_DRAFTED brands in platform send format. Returns file path."""
    if output_path is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = f"send_ready_{ts}.csv"

    q = (
        db._sb().table("brands")
        .select("brand_key,contact_first_name,contact_email,custom_subject")
        .in_("stage", ["EMAIL_DRAFTED", "SEQUENCED"])
        .not_.is_("contact_email", "null")
        .neq("contact_email", "")
        .order("updated_at", desc=True)
    )
    if not all_time:
        today = datetime.utcnow().date().isoformat()
        q = q.gte("updated_at", today)
    if limit:
        q = q.limit(limit * 3)  # over-fetch to account for skips
    brands = q.execute().data

    brand_keys = [b["brand_key"] for b in brands]
    steps_by_brand = db.get_brand_step_emails_batch(brand_keys)

    exported = 0
    skipped = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for b in brands:
            steps = steps_by_brand.get(b["brand_key"], {})

            subject_1 = steps.get(1, {}).get("subject") or b["custom_subject"] or ""
            body_2 = steps.get(2, {}).get("body", "")
            body_3 = steps.get(3, {}).get("body", "")
            body_4 = steps.get(4, {}).get("body", "")
            body_5 = steps.get(5, {}).get("body", "")

            # Skip rows missing required fields
            if not all([b["contact_email"], subject_1, body_2, body_3, body_4, body_5]):
                skipped += 1
                continue

            writer.writerow({
                "email":            b["contact_email"],
                "first_name":       b["contact_first_name"] or "",
                "custom_subject_1": subject_1,
                "custom_body_2":    body_2,
                "custom_body_3":    body_3,
                "custom_body_4":    body_4,
                "custom_body_5":    body_5,
            })
            exported += 1
            if limit and exported >= limit:
                break

    label = "all-time" if all_time else "today"
    msg = f"Exported {exported} rows [{label}] → {output_path}"
    if skipped:
        msg += f"  ({skipped} skipped — missing steps)"
    (console.print(f"[green]✓[/green] {msg}") if console else print(msg))

    return output_path


if __name__ == "__main__":
    all_time = "--all-time" in sys.argv
    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), None)
    lim = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--limit=")), None)
    export_send(all_time=all_time, output_path=out, limit=lim)
