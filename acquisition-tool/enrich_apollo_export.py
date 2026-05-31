import sqlite3
import csv
import sys

INPUT_CSV = r"C:\Users\hp\Downloads\apollo-contacts-export.csv"
OUTPUT_CSV = r"C:\Users\hp\Downloads\apollo-contacts-enriched.csv"

conn = sqlite3.connect("data/prospects.db")
conn.row_factory = sqlite3.Row

# Build email -> brand lookup from brands table
brands_by_email = {}
for row in conn.execute("SELECT * FROM brands WHERE contact_email IS NOT NULL"):
    email = (row["contact_email"] or "").strip().lower()
    if email:
        brands_by_email[email] = dict(row)

# Build asin -> rufus data from prospects table
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

print(f"Brands indexed: {len(brands_by_email)}")
print(f"ASIN Rufus scores indexed: {len(rufus_by_asin)}")

matched = 0
unmatched = 0

with open(INPUT_CSV, newline="", encoding="utf-8") as fin, \
     open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fout:

    reader = csv.DictReader(fin)
    fieldnames = reader.fieldnames
    writer = csv.DictWriter(fout, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        email = (row.get("Email") or "").strip().lower()
        brand = brands_by_email.get(email)

        if brand:
            matched += 1
            asin = brand.get("anchor_asin") or ""
            category = brand.get("category") or ""
            teardown = brand.get("email_teardown") or ""
            apollo_score = brand.get("apollo_score") or ""

            # Rufus scores from prospects table (anchor ASIN)
            rufus = rufus_by_asin.get(asin, {})
            rufus_score = rufus.get("rufus_score") or apollo_score
            rufus_prob = rufus.get("rufus_citation_probability") or ""

            # Fill variable columns
            row["asin"] = asin if asin != "apollo_direct" else ""
            row["{{asin}}"] = asin if asin != "apollo_direct" else ""
            row["anchor_asin"] = asin if asin != "apollo_direct" else ""
            row["custom_category"] = category
            row["{{custom_category}}"] = category
            row["weakness_teardown"] = teardown
            row["rufus_score"] = rufus_score
            row["rufus_citation_probability"] = rufus_prob
        else:
            unmatched += 1

        writer.writerow(row)

print(f"\nMatched:   {matched}")
print(f"Unmatched: {unmatched}")
print(f"\nOutput: {OUTPUT_CSV}")
