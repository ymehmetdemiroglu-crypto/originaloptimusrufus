---
description: REPL loop for iterating on the Rufus Visibility Calculator until it meets quality bar
---

// turbo-all

Iterative build loop for the Rufus Visibility Calculator. Preview → evaluate → fix → repeat until the calculator passes all quality checks.

---

## Step 1 — Start the dev server

```bash
cd "C:\Users\hp\OneDrive\Desktop\first client\rufus-calculator"
npm run dev
```

The dev server will start on localhost. Use the browser to preview.

---

## Step 2 — Preview in browser

Open the calculator at `http://localhost:5173` and walk through the full 3-step flow:

1. Enter a test ASIN (e.g. `B0BQ1KBX3Q`)
2. Select a category
3. Rate all 4 axes
4. Submit email
5. Review the results page

---

## Step 3 — Evaluate against quality rubric

Score the current state on these criteria (1-10 each):

| Criterion | Check |
|---|---|
| Visual polish | Dark theme, glassmorphism, amber accents, animations |
| Mobile responsive | Test at 375px width |
| Flow smoothness | No jank between steps, smooth transitions |
| Score accuracy | Calculation matches spec (0-100, per-axis 0-25) |
| Revenue projection | Numbers are credible, bands displayed |
| CTA clarity | $497 audit with guarantee prominently shown |
| ASIN lookup | Status indicators for found/new/loading |
| Email gate | Clean, minimal, blurred preview hint |

Target: 90/100 total (average 9+ per criterion).

---

## Step 4 — Fix top issues

Identify the top 3 issues from evaluation and fix them. Priorities:
1. Broken functionality (won't render, crashes)
2. Visual defects (alignment, colors, spacing)
3. UX friction (confusing flow, unclear labels)
4. Polish (animations, micro-interactions)

---

## Step 5 — Loop

Repeat Steps 2-4 until total score ≥ 90/100.

---

## Step 6 — Report

Summarize the final state:
- Screenshot of each step
- Final quality score
- Known limitations or remaining issues
