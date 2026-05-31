---
name: rufus-cosmos-optimization-implementation
description: "Use when implementing, refining, or auditing the backend components of the Rufus/COSMO optimization engine. Triggers: Gemini embedding integration, SQLite vector caching, Matryoshka dimension truncation, Rainforest/SP-API catalog ingestion, lexical keyword safety filters, Q&A seeding, causal attribution A/B test modeling."
metadata:
  author: Antigravity Agent
  version: "1.1.0"
---

# Rufus & COSMO Backend Implementation Skill

This skill outlines the engineering principles, mathematical formulations, and software design patterns required to implement and operate the upgraded **Rufus/COSMO Listing Optimization Engine**.

---

## 1. Local Runbook: Operating the Engine

As an AI coding agent, you can start, stop, and audit the backend services directly using standard CLI tool commands.

### A. Starting the FastAPI Server
To launch the backend API in the background or for testing:

```powershell
# Navigate and launch server using Uvicorn
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### B. Running the Test Suite
The backend contains a suite of automated unit tests in the `tests/` package. Verify all calculations pass before submitting changes:

```powershell
# Run the pytest suite from the backend directory
cd backend
python -m pytest tests/ -v
```

### C. Inspecting the Embedding Cache
To view the cached vector surface area and ensure hit-rates are optimal:

```powershell
# Query cached rows count
sqlite3 backend/embedding_cache.db "SELECT count(*), dimensions FROM embedding_cache GROUP BY dimensions;"
```

---

## 2. High-Fidelity Embedding & Cost-Optimized Caching

Google's `gemini-embedding-001` provides state-of-the-art semantic representation but must be managed carefully to minimize API latency and token billing overhead.

### A. Matryoshka Representation Learning (MRL) Truncation
Matryoshka embeddings pack the most critical semantic details into the early dimensions of the vector. To safely truncate a 3072-dimensional vector down to a lower dimension (e.g., 768) without losing comparative accuracy:
1. **Truncate:** Slice the array down to the target dimension range.
2. **Re-normalize:** Re-scale the truncated vector so that its L2 norm equals exactly $1.0$.

$$\vec{v}_{\text{reduced}} = \frac{\vec{v}_{[:d]}}{\|\vec{v}_{[:d]}\|_2}$$

```python
import numpy as np

def reduce_dimensions(embedding: np.ndarray, target_dims: int) -> np.ndarray:
    """Truncate and L2-normalize an embedding vector for fast cosine similarity."""
    if target_dims >= len(embedding):
        return embedding
    reduced = embedding[:target_dims]
    norm = np.linalg.norm(reduced)
    if norm > 0:
        reduced = reduced / norm
    return reduced
```

### B. Thread-Safe Persistent Caching
To prevent locking issues during asynchronous concurrent requests, the cache database uses a persistent SQLite connection with thread-safety guards:

```sql
CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,
    text_content TEXT NOT NULL,
    task_type TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hash_dims ON embedding_cache (text_hash, dimensions);
```

---

## 3. Lexical Keyword Preservation Filter

Rufus requires conversational, natural-language structures, but the traditional search engine (A9/A10) relies on absolute keyword densities. We must enforce a **strict validation gate** to protect existing indexing.

### A. Core Strategy: The Preservation Gate
For every proposed listing rewrite:
1. Parse the client's high-traffic search terms.
2. Use case-insensitive word boundary regex matching to ensure that high-volume keywords are **fully preserved** inside the optimized text.
3. Compute a **Lexical Safety Score** indicating the percentage of organic search value retained.

$$S_{\text{lexical}} = \frac{\sum_{k \in K_{\text{preserved}}} V_k}{\sum_{k \in K_{\text{target}}} V_k}$$

Where $V_k$ is the monthly search volume of keyword $k$. Any optimization with $S_{\text{lexical}} < 0.95$ must be automatically **BLOCKED** or flagged for manual override.

---

## 4. Causal Attribution A/B Test Modeling

To defend premium monthly retainers, we must mathematically isolate Rufus-driven sales lift from normal seasonality or PPC fluctuations using time-series **Causal Inference**.

### A. Difference-in-Differences (DiD) Estimation
Configure an A/B test matching an optimized ASIN (Treatment Group) against a highly correlated, non-optimized ASIN (Control Group) over identical pre-intervention ($t_{\text{pre}}$) and post-intervention ($t_{\text{post}}$) durations.

$$\text{Attributed Lift} = (\bar{Y}_{\text{treat}, \text{post}} - \bar{Y}_{\text{treat}, \text{pre}}) - (\bar{Y}_{\text{control}, \text{post}} - \bar{Y}_{\text{control}, \text{pre}})$$

Where $Y$ represents the unit session percentage (conversion rate) of the products.

---

## 5. Component Dependency Architecture

```
main.py (FastAPI Routing)
 └── core/embedding_engine.py (SQLite Caching & reduced dimensions)
 └── analysis/cosmo_mapper.py (Centroid definitions & slot extraction)
 └── analysis/competitor_analyzer.py (HDBSCAN clustering & Lexical gate)
 └── analysis/attribution.py (Binomial Wald variance DiD model)
 └── data/store.py (Thread-safe in-memory database)
```
