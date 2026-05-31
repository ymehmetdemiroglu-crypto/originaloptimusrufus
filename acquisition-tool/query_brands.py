import sqlite3

conn = sqlite3.connect("data/prospects.db")
conn.row_factory = sqlite3.Row

# Check prospects table columns
cols = conn.execute("PRAGMA table_info(prospects)").fetchall()
print("PROSPECTS COLUMNS:", [c["name"] for c in cols])

# Check if rufus fields are in prospects
rows = conn.execute("SELECT asin, brand_key, rufus_total_score, rufus_citation_probability FROM prospects WHERE rufus_total_score IS NOT NULL LIMIT 5").fetchall()
print("\nSAMPLE RUFUS SCORES:")
for r in rows:
    print(dict(r))
