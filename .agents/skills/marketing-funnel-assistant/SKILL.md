---
name: marketing-funnel-assistant
description: "Use when the user requests a complete marketing funnel optimization (TOFU, MOFU, BOFU) for an Amazon ASIN, or mentions the name of the assistant. Triggers: marketing assistant, marketing funnel, marketing cone, optimize funnel, run marketing assistant."
metadata:
  author: Antigravity Agent
  version: "1.1.0"
---

# E-commerce Marketing Funnel Assistant Skill

This skill governs the automated generation, analysis, and optimization of the complete **E-commerce Marketing Funnel (TOFU, MOFU, BOFU)** for Amazon listings, aligned with **Amazon Rufus** (conversational search) and **COSMO** (semantic knowledge graph).

---

## 1. Agent Pre-Flight Checklist

Before launching the optimization pipeline, verify your local workspace and environment are fully sound:

```powershell
# Run the built-in validation suite
python .agents/skills/marketing-funnel-assistant/scripts/marketing_assistant.py --validate
```

Verify that:
1. `GEMINI_API_KEY` is present in your environment (if absent, deterministically seeded local mocks will execute safely).
2. The FastAPI backend is running (defaults to `http://localhost:8000`).

---

## 2. Triggering the Repeatable Workflow

When the user requests a marketing funnel analysis (e.g., *"run marketing assistant on ASIN B08N5WRWNW"* or mentions the marketing funnel assistant), initiate the automated optimization workflow.

### A. Running on a Single ASIN
Execute the Python runner from the terminal to run the full pipeline in one command:

```powershell
python .agents/skills/marketing-funnel-assistant/scripts/marketing_assistant.py <ASIN> [options]
```

### B. Running on Multiple ASINs (Batch Sequential Mode)
To optimize multiple listings back-to-back, use the `--batch` flag:

```powershell
python .agents/skills/marketing-funnel-assistant/scripts/marketing_assistant.py --batch "B08N5WRWNW,B07ZPKBL6P" [options]
```

### Options:
* `--control <ASIN>`: (Optional) Specify a control ASIN for Difference-in-Differences causal A/B testing attribution.
* `--keywords <keyword1,keyword2>`: (Optional) Explicit keywords to preserve, separated by commas.
* `--audience <audience>`: (Optional) Target lifestyle or occupational audience.
* `--location <location>`: (Optional) Target location or setting context.

---

## 3. Funnel Framework (The Marketing Cone)

The workflow automates three distinct layers of the marketing funnel:

### A. TOFU (Top of Funnel - Discovery & Semantic Awareness)
* **Objective:** Expand the semantic surface area so Amazon Rufus retrieves the product in response to conversational customer questions.
* **Outputs:** 
  1. Identifies weak semantic relations using the COSMO 15-relation mapper.
  2. Maps the search intent structure.

### B. MOFU (Middle of Funnel - Consideration & Evaluation)
* **Objective:** Address common customer concerns and position the product against competitors in comparative searches.
* **Outputs:**
  1. Generates 5 high-converting, COSMO-aligned Q&A seeds to be published in the listing Q&A section.
  2. Creates a competitor gap analysis detailing semantic uniqueness vs close category competitors.

### C. BOFU (Bottom of Funnel - Conversion & Listing Rewrite)
* **Objective:** Optimize the visible listing copy to convert visitors while strictly maintaining A9 keyword rankings.
* **Outputs:**
  1. Generates optimized title, 5 bullet points (mapped to COSMO clusters), and product description.
  2. Validates copy against the **Lexical Keyword Preservation Gate** to ensure $S_{\text{lexical}} \ge 0.95$.
  3. Projects conversion rate (CR) improvements.

### D. Causal Attribution (Return on Investment)
* **Objective:** Prove the incremental sales lift driven by the optimization using Difference-in-Differences (DiD) causal inference.
* **Outputs:**
  1. Calculates attributed conversion lift.
  2. Models simulated pre/post conversion trends to establish statistical significance.

---

## 4. Troubleshooting & Error Recovery

| Symptom | Probable Cause | Action |
|---------|----------------|--------|
| `ModuleNotFoundError` | Virtual env is not activated or dependencies missing. | Run `backend-venv\Scripts\Activate.ps1` and run `pip install -r backend/requirements.txt`. |
| SQLite locks / Database locked | Concurrent writes on cache. | The caching layer now uses `check_same_thread=False` with `threading.Lock()`. If errors persist, delete `backend/embedding_cache.db` to rebuild. |
| Supabase connection fails | Bad credentials. | The backend will log warnings and fallback gracefully to deterministic mocks. Verify `.env` values if Supabase is strictly required. |

---

## 5. Reporting Results

The workflow script automatically generates a comprehensive, beautiful report at `reports/<ASIN>_marketing_funnel_report.md`. 

When completing a workflow run:
1. Direct the user to the generated markdown report.
2. Present a clean, high-level summary table of the metrics (current vs optimized COSMO score, lexical safety status, and causal lift).
3. Confirm that the optimized copy and a completed pipeline job have successfully synced to the visual dashboard (updates `http://localhost:3000` instantly).
