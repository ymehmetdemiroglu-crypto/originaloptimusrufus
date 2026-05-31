Generate personalized 5-step cold-email sequences for all CONTACT_ENRICHED brands via the OpenRouter mini-batch drafter (Deepseek V3, `EMAIL_MINI_BATCH_SIZE` brands per API call).

---

## Step 1 — Check queue

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py list --stage=CONTACT_ENRICHED
```

If zero brands, tell the user to run `/prospect` first.

If any brands have `rufus_score = NULL`, score them first:
```bash
py main.py rufus-score-enriched
```

---

## Step 2 — Draft all emails

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py draft-emails
```

This calls the OpenRouter mini-batch drafter. One API call per `EMAIL_MINI_BATCH_SIZE` brands (default 3). For each batch:
1. Determines worst Rufus axis per brand (spine of all 5 steps)
2. Sends one JSON request with all brands in the batch (system prompt paid once)
3. Returns JSON array with all 5 steps (subject + body) per brand
4. Validates word count, banned phrases, shopper-query format, opener variety
5. Saves all 5 steps to `brand_step_emails` + syncs to Supabase
6. Moves each brand to `EMAIL_DRAFTED`

To limit: `py main.py draft-emails --limit=20`

---

## Step 3 — Verify + report

```bash
py main.py uniqueness-report
```

Tell the user:
- How many brands moved to `EMAIL_DRAFTED`
- Worst-axis breakdown (intent / attribute / conversational / qa)
- Average overlap % — healthy ≤ 15%; warn if > 20%
- Next step: `py main.py apollo-sequence`
