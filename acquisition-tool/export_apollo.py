import sqlite3
import csv
import sys

# Usage: py export_apollo.py [--all-time]
# Default: only EMAIL_DRAFTED brands with 5-step sequences drafted today.
# --all-time: include all EMAIL_DRAFTED brands regardless of date.
args = sys.argv[1:]
new_only = "--all-time" not in args

try:
    conn = sqlite3.connect('data/prospects.db')
    conn.row_factory = sqlite3.Row

    date_filter = "AND DATE(b.updated_at) = DATE('now')" if new_only else ""
    brands = conn.execute(f"""
        SELECT b.brand_key, b.brand_name, b.contact_first_name, b.contact_last_name,
               b.contact_email, b.anchor_asin, b.category, b.email_teardown,
               b.custom_subject, b.custom_body
        FROM brands b
        WHERE b.stage IN ('EMAIL_DRAFTED', 'SEQUENCED')
          AND b.contact_email IS NOT NULL AND b.contact_email != ''
          {date_filter}
        ORDER BY b.updated_at DESC
    """).fetchall()

    # Load all step emails in one query for efficiency
    brand_keys = [b["brand_key"] for b in brands]
    step_rows = conn.execute("""
        SELECT brand_key, step_num, subject, body FROM brand_step_emails
        WHERE brand_key IN ({})
        ORDER BY brand_key, step_num
    """.format(",".join("?" * len(brand_keys))), brand_keys).fetchall() if brand_keys else []

    steps_by_brand: dict[str, dict[int, dict]] = {}
    for r in step_rows:
        steps_by_brand.setdefault(r["brand_key"], {})[r["step_num"]] = {
            "subject": r["subject"] or "",
            "body": r["body"] or "",
        }

    label = "today" if new_only else "all-time"
    print(f"Found {len(brands)} EMAIL_DRAFTED brands [{label}].")

    fieldnames = [
        "First Name", "Last Name", "Email", "Organization Name",
        "asin", "custom_category",
        "custom_subject_1", "custom_body_1",
        "custom_subject_2", "custom_body_2",
        "custom_subject_3", "custom_body_3",
        "custom_subject_4", "custom_body_4",
        "custom_subject_5", "custom_body_5",
        "weakness_teardown",
    ]

    outfile = "apollo_import_ready.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        exported = 0
        for b in brands:
            steps = steps_by_brand.get(b["brand_key"], {})
            row = {
                "First Name": b["contact_first_name"] or "",
                "Last Name": b["contact_last_name"] or "",
                "Email": b["contact_email"] or "",
                "Organization Name": b["brand_name"] or "",
                "asin": b["anchor_asin"] or "",
                "custom_category": b["category"] or "",
                "weakness_teardown": b["email_teardown"] or "",
            }
            for n in range(1, 6):
                s = steps.get(n, {})
                row[f"custom_subject_{n}"] = s.get("subject", b["custom_subject"] if n == 1 else "")
                row[f"custom_body_{n}"] = s.get("body", b["custom_body"] if n == 1 else "")
            writer.writerow(row)
            exported += 1

    print(f"Exported {exported} rows to {outfile}")
except Exception as e:
    print(f"Error: {e}")
    raise
