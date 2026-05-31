import sqlite3
conn = sqlite3.connect("data/prospects.db")

# All brands
total = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
print(f"Total brands: {total}")

by_source = conn.execute("SELECT source, COUNT(*) FROM brands GROUP BY source").fetchall()
print("By source:", by_source)

by_stage = conn.execute("SELECT stage, COUNT(*) FROM brands GROUP BY stage").fetchall()
print("By stage:", by_stage)

# Check columns
cols = [r[1] for r in conn.execute("PRAGMA table_info(brands)").fetchall()]
print("Brands columns:", cols)
