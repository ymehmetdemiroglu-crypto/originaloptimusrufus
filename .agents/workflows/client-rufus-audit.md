---
description: End-to-end Rufus audit — scrape Amazon → rule-score → roll up brands → Apollo enrichment → score only enriched anchors → draft → send.
---

End-to-end Rufus audit pipeline. LLM scoring runs AFTER Apollo enrichment so you only pay per brand that has a reachable contact.

Usage: `/rufus-audit [category1] [category2] ... [--limit=N]`
- No categories → defaults to top 5 seed categories from `config.AMAZON_SEED_CATEGORIES`
- `--limit=N` → per-category ASIN harvest cap (default 30)
- `--with-llm` → score ALL weak listings immediately (expensive — not recommended)

## Step 1 — Run the audit (scrape + rule-score + rollup only, no LLM)

If the user provided specific categories after `/rufus-audit`, use those. Otherwise default to no arguments.

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && py main.py rufus-audit
```

This prints:
- Per-category scrape results
- Rule-based weakness flag count (WEAK_LISTING vs SKIP)
- Brand rollup count
- Enrich queue: `brand_key` / `brand_name` / `anchor_asin` / `max_weakness` / `signals`

Read the enrich queue carefully — Step 2 processes each one.

## Step 2 — Apollo enrichment loop

For each brand in the enrich queue (process up to 20 per run):

### 2a. Organization enrichment
Call `apollo_organizations_enrich` with `domain=<guessed_domain>`. Extract `domain` and `id` (= `apollo_org_id`).

### 2b. People match
If a domain was found, call `apollo_people_match` with:
- `domain=<domain>`

Extract `first_name`, `last_name`, `email`, `title`, `id` (= `apollo_person_id`).

### 2b fallback — no domain or no contact found
Call `apollo_mixed_people_api_search` with:
- `q_organization_name=<brand_name>`
- `person_titles=["Founder","CEO","Owner","Brand Manager","Ecommerce Manager"]`
- `organization_num_employees_ranges=["1,50"]`
- `contact_email_status=["verified","likely to engage"]`

Take the first result that has an email.

### 2c. Write enrichment back

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && py main.py set-enrichment <brand_key> --domain=<domain> --email=<email> --first=<first_name> --last=<last_name> --title=<title> --apollo-person=<person_id> --apollo-org=<org_id>
```

### Skip rules
- No email after both org-enrich and people-search fallback → leave at WEAK_BRAND
- Email domain doesn't match the brand domain (contact unrelated) → skip

## Step 3 — LLM Rufus-score ONLY enriched brands' anchor ASINs

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && py main.py rufus-score-enriched
```

This scores only the anchor ASIN of each CONTACT_ENRICHED brand — paying for LLM only on listings where a contact was found.

## Step 4 — Draft Rufus-grounded teardowns

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && py main.py draft-emails
```

The teardown uses per-axis Rufus scores + top weaknesses to write 3–4 specific gaps tied to Rufus citation behavior.

## Step 5 — Show send queue

```
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool" && py main.py send-queue
```

Report total drafts ready. Then create Apollo contacts + add to sequence + mark-sequenced.
