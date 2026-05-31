"""Re-draft step 1 bodies for brands where it came out empty."""
import db, cold_email, config, sqlite3, sys

config.OPENROUTER_DRAFT_MODEL = "deepseek/deepseek-v4-pro"
db.init_db()

conn = sqlite3.connect("data/prospects.db")
conn.row_factory = sqlite3.Row
brand_keys = [r[0] for r in conn.execute("""
    SELECT DISTINCT be.brand_key FROM brand_emails be
    WHERE be.step_num=1 AND (be.body IS NULL OR be.body='')
""").fetchall()]
conn.close()

print(f"Re-drafting step 1 for {len(brand_keys)} brands...")
for bk in brand_keys:
    brand = db.get_brand(bk)
    if not brand or not brand.anchor_asin or brand.anchor_asin == "apollo_direct":
        print(f"  SKIP {bk} (no anchor)")
        continue
    anchor = db.get_anchor_prospect(brand.anchor_asin)
    if not anchor:
        print(f"  SKIP {bk} (anchor not found)")
        continue
    try:
        seq = cold_email.draft_sequence(brand, anchor, save=True, steps=(1,))
        body = seq["steps"].get(1, {}).get("body", "")
        print(f"  OK {bk}  body_len={len(body)}")
    except Exception as e:
        print(f"  ERR {bk}: {e}")

print("Done.")
