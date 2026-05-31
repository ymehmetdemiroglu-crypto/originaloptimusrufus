import csv

with open(r"C:\Users\hp\Downloads\apollo-contacts-enriched.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    cols = ["Email", "asin", "{{asin}}", "custom_category", "{{custom_category}}", "rufus_score", "rufus_citation_probability", "weakness_teardown"]
    for i, row in enumerate(reader):
        if i >= 5:
            break
        print(f"--- Row {i+1}: {row.get('Email')} ---")
        for c in cols:
            val = row.get(c, "")
            print(f"  {c}: {val[:90] if val else '(empty)'}")
        print()
