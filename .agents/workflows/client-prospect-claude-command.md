Full end-to-end Optimus Rufus outbound pipeline.

Two modes:
- `/prospect` — mass mode: Apollo search across all 30+ niches in parallel → 500+ contacts/run
- `/prospect <category>` — targeted mode: Apollo search for one specific niche (e.g. `magnesium glycinate`)

Zero generic copy. Every lead is ASIN-backfilled before drafting. No ASIN found → SKIP_NO_LISTING, never emailed. Every email is written by Claude Code per recipient, uniqueness-checked, saved to SQLite + Supabase.

---

## Step 0 — Determine mode

**If `/prospect` with no argument → mass mode.**
Run across all 30+ configured niches in parallel. Target: 500+ raw contacts, 100+ new enriched brands.

**If `/prospect <category>` → targeted mode.**
Use the given category (e.g. `vitamin c serum`, `calming dog treats`, `foam roller`). You may run multiple categories if the user lists them.

Avoid generic terms like "supplements" or "beauty" — these surface mega-brands. Use niche subcategory queries that index to SMB owner-operated brands.

---

## Step 1 — Prospect discovery via Apollo

**Mass mode:**
```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py mass-prospect
```

**Targeted mode:**
```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py auto-prospect "<category>"
```

Both commands:
1. Search Apollo for founder/owner/CEO-level contacts (`person_seniorities=[founder, owner, c_suite]`, 1–25 employees, US, verified email)
2. Hard-filter titles — rejects Brand Manager, Head of Ecommerce, Operations, Analyst, etc.
3. Deduplicate against the existing DB (skips brand_keys already present)
4. Bulk-match any contacts missing emails
5. Insert qualifying contacts at `CONTACT_ENRICHED`
6. **Auto-chain ASIN backfill** — Apify fuzzy-matches each brand → finds its anchor Amazon listing
7. Brands with no findable ASIN → `SKIP_NO_LISTING` (never drafted, never emailed)

Print the count of new brands inserted and how many were skipped.

---

## Step 2 — Rufus 4-axis LLM score

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py rufus-score-enriched
```

Scores every `CONTACT_ENRICHED` anchor ASIN on:
- **Intent Alignment** (0–25) — does the listing copy match how shoppers phrase Rufus queries?
- **Attribute Density** (0–25) — are structured attributes (mg, IU, certifications, dietary flags) present?
- **Conversational Readability** (0–25) — can Rufus extract clean quotable sentences?
- **Q&A Coverage** (0–25) — does the Q&A section cover pre-purchase questions Rufus would be asked?

Also outputs: `rufus_citation_probability` (low/medium/high), `rufus_top_weaknesses` (JSON per-axis), `rufus_summary` (one sentence).

This data is the grounding for every email — do not skip it.

---

## Step 3 — Generate emails via OpenRouter

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py draft-emails
```

This runs the mini-batch OpenRouter drafter (Deepseek V3, `EMAIL_MINI_BATCH_SIZE` brands per API call). For each CONTACT_ENRICHED brand it:
1. Determines the worst Rufus axis (spine of all 5 steps)
2. Groups brands into mini-batches and calls the LLM once per batch (system prompt shared)
3. Drafts all 5 steps (subject + body) in one JSON response per batch
4. Validates word count, banned phrases, shopper-query constructions, opener variety
5. Saves all 5 steps to `brand_step_emails` + syncs to Supabase
6. Moves each brand to `EMAIL_DRAFTED`

If overlap warnings appear:
```bash
py main.py uniqueness-report
```

---

## Step 4 — Export send-ready CSV

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py export-send
```

Produces the platform import CSV with exactly these columns:
`email, first_name, custom_subject_1, custom_body_2, custom_body_3, custom_body_4, custom_body_5`

Ready to import into Instantly, Lemlist, Smartlead, or any cold-email platform. Rows with incomplete step data are automatically skipped.

Tell the user the filename and row count. If they need the full analysis CSV (39 columns with Rufus scores), also run:
```bash
py main.py export-enriched --stage=EMAIL_DRAFTED
```

---

## Step 5 — Enroll in Apollo sequence

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py apollo-sequence
```

For every `EMAIL_DRAFTED` brand:
1. Creates the contact in Apollo via REST API
2. Pushes all 10 custom fields: `subject_1..5`, `body_1..5` (plus back-compat `custom_subject`/`custom_body`)
3. Enrolls in `APOLLO_SEQUENCE_ID` (5-step shell sequence)
4. Marks brand `SEQUENCED` in SQLite and syncs to Supabase

Apollo then sends Step 1 immediately; Steps 2–5 follow on days +3 / +7 / +12 / +18 with auto-stop on reply.

Dry run first if the user wants to review: `py main.py apollo-sequence --dry-run`

---

## Step 6 — Final sync to Supabase

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py supabase-sync
```

Pushes the final SEQUENCED state to the `nexoptimus` Supabase project so the pipeline is fully reflected in the cloud DB.

---

## Step 7 — Report

Give the user a clean summary with real numbers from the command output:

```
Pipeline complete:
  • [N] new brands found (CONTACT_ENRICHED)
  • [N] dropped at SKIP_NO_LISTING (no Amazon listing)
  • [N] emails drafted via OpenRouter (EMAIL_DRAFTED)
  • [N] enrolled in Apollo sequence (SEQUENCED)
  • Avg email overlap: [X]% ([healthy / ⚠ high — run uniqueness-report])
  • Enriched CSV: export_enriched_YYYYMMDD_HHMMSS.csv
  • Supabase synced: nexoptimus project

When replies come in:  py main.py brand-replied <brand_key>
Reply analytics:       py main.py reply-stats
Next run:              /prospect  (or  /prospect <new category>)
```
