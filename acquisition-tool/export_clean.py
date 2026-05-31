"""
Export a clean Apollo-import CSV with variables filled in for this sequence:

  {{first_name}} — running Rufus audits across {{custom_category}} brands this week...
  it cites structured attributes, not keyword density.
  {{weakness_teardown}}
  the brands dominating Rufus citations in your space...
  worth it?

weakness_teardown is formatted with a leading blank line, the ASIN header line (if available),
the bullet points, and a trailing blank line so it drops cleanly into the template.
"""
import sqlite3
import csv

INPUT_CSV  = r"C:\Users\hp\Downloads\apollo-contacts-export.csv"
OUTPUT_CSV = r"C:\Users\hp\Downloads\apollo-upload-ready.csv"

conn = sqlite3.connect("data/prospects.db")
conn.row_factory = sqlite3.Row

# email -> brand row
brands_by_email = {}
for row in conn.execute("SELECT * FROM brands WHERE contact_email IS NOT NULL"):
    email = (row["contact_email"] or "").strip().lower()
    if email:
        brands_by_email[email] = dict(row)

# asin -> rufus row
rufus_by_asin = {}
for row in conn.execute(
    "SELECT asin, rufus_score, rufus_citation_probability FROM prospects WHERE rufus_score IS NOT NULL"
):
    asin = (row["asin"] or "").strip()
    if asin:
        rufus_by_asin[asin] = {
            "rufus_score": row["rufus_score"],
            "rufus_citation_probability": row["rufus_citation_probability"],
        }

FIELDNAMES = [
    "Email",
    "First Name",
    "Last Name",
    "Company Name",
    "{{asin}}",
    "{{custom_category}}",
    "weakness_teardown",
]

def format_teardown(raw_teardown: str, asin: str) -> str:
    """
    Wrap the raw bullet lines so they sit cleanly inside:
      ...keyword density.\n{{weakness_teardown}}\nthe brands dominating...
    """
    if not raw_teardown:
        return ""

    lines = [l.strip() for l in raw_teardown.strip().splitlines() if l.strip()]

    # Insert ASIN context header if we have a real ASIN and it isn't already in line 1
    asin_header = ""
    if asin and asin != "apollo_direct":
        if asin not in (lines[0] if lines else ""):
            asin_header = f"pulled your anchor listing ({asin}):\n"

    body = "\n".join(lines)
    # leading + trailing newline so template spacing works
    return f"\n\n{asin_header}{body}\n\n"

matched = 0
unmatched_emails = []

with open(INPUT_CSV, newline="", encoding="utf-8") as fin, \
     open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fout:

    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=FIELDNAMES)
    writer.writeheader()

    for row in reader:
        email = (row.get("Email") or "").strip().lower()
        brand  = brands_by_email.get(email)

        if not brand:
            unmatched_emails.append(row.get("Email", ""))
            continue

        matched += 1
        asin     = brand.get("anchor_asin") or ""
        asin_val = asin if asin != "apollo_direct" else ""
        category = brand.get("category") or ""
        teardown = brand.get("email_teardown") or ""

        writer.writerow({
            "Email":              row.get("Email", ""),
            "First Name":         row.get("First Name", ""),
            "Last Name":          row.get("Last Name", ""),
            "Company Name":       row.get("Company Name", ""),
            "{{asin}}":           asin_val,
            "{{custom_category}}": category,
            "weakness_teardown":  format_teardown(teardown, asin_val),
        })

print(f"Matched:   {matched}")
if unmatched_emails:
    print(f"Unmatched ({len(unmatched_emails)}):")
    for e in unmatched_emails:
        print(f"  {e}")
print(f"\nOutput: {OUTPUT_CSV}")
