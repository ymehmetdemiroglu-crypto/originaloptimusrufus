import csv

EMAIL_TEMPLATE = """{first_name} --running Rufus audits across {custom_category} brands this week. the pattern is consistent: most listings were built for A9 keyword search. Rufus AI -- now showing up in ~35% of Amazon product searches -- works completely differently. it cites structured attributes, not keyword density.{weakness_teardown}the brands dominating Rufus citations in your space aren't the biggest. they rewrote first.i can pull the full audit for {org} and send it as a doc -- four-axis breakdown, exact rewrite roadmap. no call needed first.worth it?"""

with open(r"C:\Users\hp\Downloads\apollo-upload-ready.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 3:
            break
        rendered = EMAIL_TEMPLATE.format(
            first_name=row["First Name"],
            custom_category=row["{{custom_category}}"],
            weakness_teardown=row["weakness_teardown"],
            org=row["Company Name"],
        )
        print(f"=== {row['Email']} | ASIN: {row['{{asin}}'] or '(none)'} ===")
        print(rendered)
        print()
