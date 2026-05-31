---
name: acquisition-tool-operations
description: "Outbound prospecting pipeline manual for scraping weak Amazon listings, scoring them on Rufus axes, enriching contacts via Apollo, and drafting personalized cold email sequences."
metadata:
  author: Antigravity Agent
  version: "1.0.0"
---

# Optimus Rufus Outbound Acquisition Pipeline Skill

This skill governs the execution and management of the outbound prospecting pipeline (`first client/acquisition_tool`).

---

## 1. Outbound Prospecting Strategy

Optimus Rufus uses an ASIN-grounded, AI-personalized outbound strategy. We never send generic templates. Every lead receives a custom, multi-step teardown email based on their listing's actual Rufus visibility scores.

---

## 2. Command Reference (Funnel Workflows)

### Funnel A: Amazon-First Scrape & Outreach
Use this when targeting listings under a specific category or ingredient on Amazon.

```powershell
# 1. Scrape, rule-score, and consolidate listings under a category (Free; no LLM costs)
python main.py rufus-audit "magnesium glycinate" --limit=50

# 2. Enrich crawled brands with Apollo decision-makers
python main.py auto-enrich

# 3. Compute LLM Rufus scores for ONLY enriched contacts
python main.py rufus-score-enriched

# 4. Generate highly personalized 5-step cold email teardowns
python main.py draft-emails

# 5. Review the send queue
python main.py send-queue

# 6. Enroll EMAIL_DRAFTED prospects directly into Apollo sequences
python main.py apollo-sequence
```

### Funnel B: Apollo-First Targeting & ASIN Backfill
Use this when you want to target contacts in a specific industry (e.g. "supplements") first, then find their listings on Amazon.

```powershell
# 1. Prospect contacts under broad tags from Apollo directly
python main.py auto-prospect "supplements"

# 2. Backfill Amazon ASINs for the new leads (fuzzy brand matching)
python backfill_asins.py

# 3. LLM Rufus-score the backfilled ASINs
python main.py rufus-score-enriched

# 4. Generate personalized cold email sequences
python main.py draft-emails

# 5. Enroll in Apollo sequences
python main.py apollo-sequence
```

---

## 3. The 5-Step Email Sequence Structure

The outbound engine generates a unique 5-step sequence for every contact (`cold_email.py`):

| Step | Subject/Body Focus | Objective |
|------|--------------------|-----------|
| **1** | Opening teardown | Highlights the worst-performing Rufus axis score + specific listing flaw |
| **2** | Concrete fix | Lays out a clear, actionable listing optimization fix |
| **3** | Shopper-query proof | Provides examples of conversational search queries Rufus shoppers type |
| **4** | Soft nudge | Short check-in referencing step 1's observation |
| **5** | Final breakaway | One-line professional sign-off opening future doors |

---

## 4. Pipeline Stages & Troubleshooting

### Pipeline Stages
`LISTING_FOUND` ➔ `WEAK_LISTING` ➔ `WEAK_BRAND` ➔ `CONTACT_ENRICHED` ➔ `EMAIL_DRAFTED` ➔ `SEQUENCED` ➔ `REPLIED`

### Common Actions
* **Check overall stats:** `python main.py stats` or `python main.py dashboard`
* **Examine single brand details:** `python main.py show <brand_key>`
* **Mark brand as Replied manually:** `python main.py replied <brand_key> "reply text"`
* **Export ready contacts to CSV:** `python export_apollo.py`
