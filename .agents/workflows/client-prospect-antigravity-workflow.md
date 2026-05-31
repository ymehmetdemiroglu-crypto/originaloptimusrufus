// turbo-all

Full end-to-end outbound pipeline (Funnel B). Single command: Apollo search → Amazon ASIN backfill (parallel) → 4-axis Rufus score → ASIN-specific teardown → CSV export.

---

## Step 1 — Run the full pipeline

Single command that orchestrates all 5 stages automatically:

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py run-funnel-b "<category>"
```

*(Note: <category> will be whatever the user specifies when invoking the workflow)*

This runs:
1. **Auto-Prospect** — Apollo API search → DB insert (with bulk email matching)
2. **Backfill ASINs** — Parallel Amazon search → fuzzy brand match → anchor ASIN
3. **Rufus Score** — LLM 4-axis scoring on enriched anchor listings
4. **Draft Emails** — Generate personalised teardown emails
5. **Export CSV** — Write `apollo_import_ready.csv`

---

## Step 2 — Check DB and Auto-Enrich

Check the database for any new brands that haven't been enriched yet, and enrich them directly via the Apollo API:

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py -c "import sqlite3; conn = sqlite3.connect('data/prospects.db'); conn.row_factory = sqlite3.Row; [print(dict(r)) for r in conn.execute('SELECT brand_name, domain, contact_email, stage, anchor_asin FROM brands ORDER BY created_at DESC LIMIT 5').fetchall()]"
py main.py auto-enrich
```

---

## Step 3 — Report and hand off

Let the user know the pipeline is finished:
**"CSV ready: `apollo_import_ready.csv` — you can now upload this directly to Apollo, map the columns, and add them to your sequence."**
