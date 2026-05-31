import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

conn = sqlite3.connect('data/prospects.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT b.brand_name, b.contact_email, bse.step_num, bse.subject, bse.body
    FROM brands b
    JOIN brand_step_emails bse ON bse.brand_key = b.brand_key
    WHERE b.stage IN ('EMAIL_DRAFTED','SEQUENCED')
    ORDER BY b.brand_name, bse.step_num
""").fetchall()

current_brand = None
for r in rows:
    if r["brand_name"] != current_brand:
        current_brand = r["brand_name"]
        print(f"\n{'='*70}")
        print(f"  {r['brand_name']}  <{r['contact_email']}>")
        print(f"{'='*70}")
    print(f"\n  [Step {r['step_num']}] {r['subject']}")
    print(f"  {'-'*60}")
    for line in (r['body'] or '').splitlines():
        print(f"  {line}")

print(f"\n{len(set(r['brand_name'] for r in rows))} brands, {len(rows)} steps total")
