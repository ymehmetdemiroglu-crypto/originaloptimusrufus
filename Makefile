# =============================================================================
# Optimus Rufus — Monorepo Task Runner
# =============================================================================

.PHONY: dev-backend dev-frontend dev-calc test deploy clean help

help:
	@echo "Optimus Rufus Command Reference:"
	@echo "  make dev-backend   - Run FastAPI backend development server"
	@echo "  make dev-frontend  - Run Next.js dashboard development server"
	@echo "  make dev-calc      - Run Vite ROI calculator development server"
	@echo "  make dev           - Spin up all development services concurrently (needs concurrently npm pkg)"
	@echo "  make test          - Run backend pytest suite"
	@echo "  make deploy        - Run production deployment script"
	@echo "  make clean         - Clear pycache, build, and test caches"

dev-backend:
	cd backend && python main.py

dev-frontend:
	cd rufus-dashboard && npm run dev

dev-calc:
	cd rufus-calculator && npm run dev

test:
	cd backend && pytest

deploy:
	chmod +x deploy.sh && ./deploy.sh

clean:
	rm -rf .pytest_cache backend/.pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
