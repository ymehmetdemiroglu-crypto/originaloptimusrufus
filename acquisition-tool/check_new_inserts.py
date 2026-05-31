import sys
sys.path.append(r"c:\Users\hp\OneDrive\Desktop\optimus rufus\acquisition-tool")

import db
db.init_db()

res = db._sb().table("brand_step_emails").select("brand_key", "step_num", "created_at").order("created_at", desc=True).limit(20).execute()
print("Recently inserted brand step emails:")
for r in res.data:
    print(f"  brand_key={r.get('brand_key')}, step_num={r.get('step_num')}, created_at={r.get('created_at')}")
