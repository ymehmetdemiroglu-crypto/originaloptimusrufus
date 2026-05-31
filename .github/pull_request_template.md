# Optimus Rufus Pull Request Quality Gate

## Checklist for Reviewers & Authors

### 🧼 Code Quality & Style (Idea 1 & 2)
- [ ] No new lint warnings exist. Standardize by running `ruff check` in python, or `npm run lint` in JS directories.
- [ ] Code is fully type-annotated. Run `mypy` or `npm run build` to verify type safety.
- [ ] No hardcoded absolute file paths. Dynamic paths must use `Path(__file__)`.

### 🚀 Caching & Thread Safety (Idea 11)
- [ ] Vector calculations are memoized or hit Tier-1 local SQLite cache database.
- [ ] Heavy vector and embedding queries are offloaded using thread pools (`asyncio.to_thread`) to avoid blocking FastAPI's event loop.
- [ ] No potential thread-lock or database locks introduced by concurrent background scraper workers.

### 🧪 Tests & Coverage (Idea 5, 6, 7 & 25)
- [ ] Unit tests added for any new service or calculation models (pytest / vitest).
- [ ] Invariants and edge cases checked with Hypothesis property-based testing if applicable.
- [ ] Overall code coverage of the modified component is >80%.
- [ ] Repetitive mock data extracted to conftest.py fixtures.

### 🔒 Security & Dependency Verification (Idea 21 & 29)
- [ ] No secrets, api keys, or database credentials hardcoded. All values loaded securely from environment variables.
- [ ] Startup configuration checks implemented to fail-fast if environment parameters are malformed or missing.
- [ ] SQL execution pathways parameterized or protected against injection.
- [ ] New packages added explicitly to requirements.txt or package.json.
