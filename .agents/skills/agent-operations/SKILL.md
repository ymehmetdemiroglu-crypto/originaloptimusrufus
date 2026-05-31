---
name: agent-operations
description: "Master operability manual for AI coding agents managing the Optimus Rufus optimization engine and acquisition tool pipelines. Triggers: run workspace, operate systems, manage server, start services, platform runbook."
metadata:
  author: Antigravity Agent
  version: "1.0.0"
---

# Optimus Rufus Master Agent Operations Runbook

This manual serves as the primary instructions for an AI agent (such as Antigravity) to operate, manage, start, test, and troubleshoot the entire Optimus Rufus e-commerce platform.

---

## 1. Platform Architecture at a Glance

The workspace consists of two primary subsystems:
1. **The Core Engine & Dashboard** (root directory & `rufus-dashboard/`): Analyzes listings, computes vector competitor gaps, generates optimized copy, runs causal Difference-in-Differences attribution, and renders client dashboards.
2. **The Acquisition Tool** (`first client/acquisition_tool/`): Outbound marketing automation pipeline that parses weak Amazon listings, enriches contacts via Apollo, drafts custom multi-step cold-email outreach sequences, and manages Apollo sequences.

---

## 2. Boot Sequence: Starting Services

To spin up the platform locally for manual or automated verification, execute these commands in the terminal:

### Step A: Activate and Launch backend
```powershell
# Navigate to backend directory
cd backend

# Activate Python virtual environment (if needed)
# ..\backend-venv\Scripts\Activate.ps1

# Launch FastAPI development server
uvicorn main:app --host 0.0.0.0 --port 8000
```
*Verify startup by hitting the health check endpoint: `GET http://localhost:8000/`.*

### Step B: Launch Next.js Dashboard
```powershell
# Navigate to dashboard directory
cd rufus-dashboard

# Launch Next.js Dev Server
npm run dev
```
*Verify visual representation by opening `http://localhost:3000` in the browser.*

---

## 3. Daily Operations Runbook

### Operation 1: Run Funnel Optimization on a Listing ASIN
To trigger the end-to-end TOFU/MOFU/BOFU rewrite and DiD modeling:

```powershell
# Run the assistant command
python .agents/skills/marketing-funnel-assistant/scripts/marketing_assistant.py <ASIN> --keywords "term1, term2" --audience "gym goers" --location "backpack"
```
*Outputs are generated beautifully at `reports/<ASIN>_marketing_funnel_report.md`.*

### Operation 2: Run Outbound Prospecting (Acquisition Funnel)
To run Funnel A (Amazon listing scraper → Rufus score → Apollo lookup → personalized draft email):

```powershell
# Navigate to first client tools
cd "first client"

# Run cold email generation command
python acquisition_tool/main.py draft-emails --limit=5
```

### Operation 3: Inspect SQLite Vector Cache
To inspect dimensions, counts, and contents of cached embeddings:

```powershell
sqlite3 backend/embedding_cache.db "SELECT count(*), dimensions FROM embedding_cache GROUP BY dimensions;"
```

---

## 4. Troubleshooting Playbook

### A. SQLite Database is Locked
* **Cause:** Multiple concurrent connections trying to write on cache sqlite.
* **Resolution:** The caching layer uses a persistent thread-safe threadpool connection pooling pattern. If locking occurs, stop the backend uvicorn service, wait 5 seconds, delete `backend/embedding_cache.db` to flush, and restart.

### B. Missing label.tsx Component in Next.js
* **Cause:** Visual import fail on compilation.
* **Resolution:** We have fully created the standard Next.js-compatible `rufus-dashboard/src/components/ui/label.tsx` matching shadcn specifications.

### C. Supabase Not Syncing Prospects
* **Cause:** Missing local environment settings.
* **Resolution:** Ensure `SUPABASE_URL` and `SUPABASE_KEY` are placed in `backend/.env`. The backend has been optimized to handle missing keys gracefully with mock fallbacks without crashing.
