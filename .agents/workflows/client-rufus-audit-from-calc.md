---
description: Connect a calculator submission to the existing Rufus audit pipeline for automated teardown
---

// turbo-all

When a prospect submits their ASIN through the calculator, this workflow triggers the Rufus scoring and teardown pipeline.

---

## Step 1 — Check if ASIN already scored

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py -c "import db; p = db.get_anchor_prospect('<ASIN>'); print(f'Score: {p.rufus_score}' if p and p.rufus_score else 'Not scored')"
```

*(Replace `<ASIN>` with the actual ASIN from the calculator submission)*

---

## Step 2 — If not scored, run the Rufus scorer

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py rufus-score-enriched
```

---

## Step 3 — Draft the personalized teardown email

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\acquisition_tool"
py main.py draft-emails --limit=1
```

---

## Step 4 — Report

Output the Rufus score, per-axis breakdown, and generated teardown subject line to the user. The personalized Loom should be recorded within 4 hours using this data.
