"""Audit which brands have full 5-step copy vs partial vs none."""
import sqlite3
con = sqlite3.connect("data/prospects.db")
con.row_factory = sqlite3.Row

print("=== Brand counts by stage ===")
for r in con.execute("SELECT stage, COUNT(*) c FROM brands GROUP BY stage ORDER BY c DESC"):
    print(f"  {r['stage']}: {r['c']}")

print("\n=== Step-email coverage by brand ===")
rows = con.execute("""
    SELECT b.brand_key, b.stage,
           (SELECT COUNT(*) FROM brand_emails be WHERE be.brand_key=b.brand_key) AS step_count,
           CASE WHEN b.custom_subject IS NOT NULL THEN 1 ELSE 0 END AS has_legacy
      FROM brands b
""").fetchall()

bucket = {}
for r in rows:
    key = (r["stage"], r["step_count"], r["has_legacy"])
    bucket[key] = bucket.get(key, 0) + 1

print(f"{'stage':<22} {'steps':>6} {'legacy':>7}  count")
for (stage, sc, lg), c in sorted(bucket.items(), key=lambda x: (-x[1], x[0])):
    print(f"  {stage:<20} {sc:>6} {lg:>7}  {c}")

print("\n=== Suspect 'Nicolas' enrichment data ===")
n = con.execute("""
    SELECT COUNT(*) FROM brands
    WHERE apollo_person_id='54a2973f7468693cddf5412e'
      AND contact_email IS NULL
""").fetchone()[0]
print(f"  Brands with Nicolas-junk apollo_person_id and no email: {n}")

print("\n=== SEQUENCED reply state ===")
rep = con.execute("""
    SELECT
      SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) AS replied,
      SUM(CASE WHEN replied_at IS NULL THEN 1 ELSE 0 END) AS no_reply
    FROM brands WHERE stage='SEQUENCED'
""").fetchone()
print(f"  Replied: {rep['replied']}   No reply: {rep['no_reply']}")
