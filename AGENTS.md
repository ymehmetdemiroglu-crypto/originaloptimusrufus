# 🤖 AI Agent Developer Guide (AGENTS.md)

Welcome, agent! This guide helps you navigate, maintain, and expand the **Optimus Rufus** codebase safely, cleanly, and efficiently.

---

## 🧭 Codebase Map

| Subdirectory | Key Tech | Description & Entrypoints |
|--------------|----------|---------------------------|
| `backend/` | FastAPI, Pydantic | **Core logic service**. Entrypoint: [main.py](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/backend/main.py). All schemas are in `models.py`. Integrates SQLite cache db (`embedding_cache.db`), RAG embeddings, and Difference-in-Differences causal estimation. |
| `rufus-dashboard/` | Next.js, Shadcn UI | **Admin and control UI**. Pages are situated under `src/app/`. Components are structured under `src/components/ui/`. Integrates Supabase SSR auth client. |
| `acquisition-tool/` | Python, Click CLI | **Scraper and cold outreach engine**. Entrypoint: [main.py](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/acquisition-tool/main.py) (CLI commands). Contains pipeline runners, Apify Reddit & Amazon scrapers, and Apollo sequence integrations. |
| `rufus-calculator/` | React, Vite | **Interactive ROI pricing tool**. Entrypoint: `src/main.jsx`. Contains styling at `src/index.css` and main layout at `src/App.jsx`. |
| `.agents/` | Markdown Skills | **AI skill manuals**. Read `skills/<skill_name>/SKILL.md` before executing complex backend modifications. |

---

## 🔗 Key System Integrations

### 1. In-Memory Catalog Store
- Located in [backend/data/store.py](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/backend/data/store.py).
- Serves as the primary operational database for in-flight listings, competitor ASIN arrays, and simulated conversion logs.
- Flushes directly into local memory. Avoid long CPU blocking operations inside the store!

### 2. Lexical & Semantic Safety Filters
- **Lexical Filter**: Compares listing terms against `acquisition-tool/rules/banned_phrases.json` or target keywords inside competitor analyzer services.
- **Semantic Filter**: Calculates cosine similarity against raw embeddings to flag drift percentage before deploying rewritten copy.

### 3. Difference-in-Differences (DiD) Causal Model
- Implemented in [backend/analysis/attribution.py](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/backend/analysis/attribution.py).
- Subtracts natural conversion trends (isolated using control ASIN traffic histories) from treatment ASIN metrics to confirm exact attributed uplift percent.

---

## 🛠 Operational Runbook

### 1. Starting Development Services
Use the root level `Makefile` commands to spin up environments:
```bash
make dev-backend   # Launches FastAPI dev server with auto-reload (port 8000)
make dev-frontend  # Launches Next.js dev server (port 3000)
make dev-calc      # Launches Vite calculator (port 5173)
```

### 2. running Tests
Always run the pytest suite before submitting any changes to `backend/`:
```bash
make test          # Executes all backend tests in backend/tests/
```

### 3. CLI Scraping & Prospecting
Run Click CLI options directly inside `acquisition-tool/`:
```bash
python main.py scrape-amazon --category=supplements --limit=20
python main.py enrich-contacts
python main.py draft-emails --limit=10
```

---

## 📌 Coding Rules & Best Practices

1. **Maintain Cache Integrity**: Keep SQLite cache `embedding_cache.db` in `backend/core` gitignored. Never hardcode absolute file paths; use `Path(__file__)` or relative calculations.
2. **Handle Path Manipulation Cleanly**: Always preserve `sys.path.append(str(acq_path))` patterns at backend startup to keep imports between `acquisition-tool` and `backend` seamless.
3. **No Direct Production Database Schema Alterations**: Write sql migration scripts inside [backend/migrations](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/backend/migrations) and test them using sandbox Supabase environments first.
