"""Parse Apollo bulk_match response files and extract key contact fields."""
import json
import re
import os

BASE = r"C:\Users\hp\.claude\projects\C--Users-hp-OneDrive-Desktop-first-client\b04b1bd8-1246-4074-b39c-5540b551ee67\tool-results"

FILES = [
    ("batch1_supp",  os.path.join(BASE, "mcp-claude_ai_Apollo_io-apollo_people_bulk_match-1777743534325.txt")),
    ("batch2_supp",  os.path.join(BASE, "mcp-claude_ai_Apollo_io-apollo_people_bulk_match-1777743537780.txt")),
    ("batch3_mixed", os.path.join(BASE, "mcp-claude_ai_Apollo_io-apollo_people_bulk_match-1777743541074.txt")),
    ("batch4_skin",  os.path.join(BASE, "toolu_01UX2RAbg8sJ9hJbVMRt8yX8.json")),
]

def parse_file(label, path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    # The txt files wrap content in a JSON envelope with a "text" key containing the real JSON
    # The .json file may also be wrapped
    try:
        outer = json.loads(raw)
        if isinstance(outer, list) and outer and "text" in outer[0]:
            inner_text = outer[0]["text"]
        elif isinstance(outer, dict) and "text" in outer:
            inner_text = outer["text"]
        else:
            inner_text = raw
        data = json.loads(inner_text)
    except Exception:
        # Try extracting JSON directly from text
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
        else:
            print(f"  Could not parse {label}")
            return

    matches = data.get("matches", [])
    credits = data.get("credits_consumed", "?")
    print(f"\n=== {label} | {len(matches)} matches | {credits} credits ===")
    for p in matches:
        pid = p.get("id", "")
        first = p.get("first_name", "")
        last = p.get("last_name", "")
        email = p.get("email") or ""
        status = p.get("email_status") or "none"
        org = p.get("organization") or {}
        org_name = org.get("name", "")
        domain = org.get("primary_domain") or org.get("website_url") or ""
        org_id = org.get("id", "")
        flag = "" if (email and status == "verified") else "  *** NO VERIFIED EMAIL"
        print(f"  {pid} | {first} {last} | {email} ({status}) | {org_name} | {domain} | {org_id}{flag}")

for label, path in FILES:
    parse_file(label, path)
