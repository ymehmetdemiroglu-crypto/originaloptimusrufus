# 🚀 Optimus Rufus

> AI-powered Amazon listing optimization engine with COSMO/Rufus intelligence and causal attribution A/B modeling.

Optimus Rufus is an agency-grade toolchain designed to analyze, score, and optimize Amazon product detail pages against Amazon's latest COSMO semantic graph algorithms and Rufus conversational shopping assistant rules.

---

## 🏗 System Architecture

```
                                 ┌────────────────────────┐
                                 │     Next.js Portal     │
                                 │   (rufus-dashboard)    │
                                 └───────────┬────────────┘
                                             │ REST API
                                             ▼
┌────────────────────────┐       ┌────────────────────────┐
│  Acquisition Tool CLI  ├──────►│    FastAPI Backend     ├──────► Supabase DB
│   (outbound agent)     │       │        (backend)       │        (prospects, etc.)
└────────────────────────┘       └───────────┬────────────┘
                                             │
                                             ▼
                                  Google Gemini / LLMs
                                (COSMO Semantic Parsing)
```

- **[backend](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/backend)**: Python FastAPI web service containing embedding caches, Lexical keyword safety filters, COSMO relation mapping, and Difference-in-Differences causal A/B testing models.
- **[rufus-dashboard](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/rufus-dashboard)**: Next.js management dashboard built with Tailwind CSS, Recharts, and Shadcn UI.
- **[acquisition-tool](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/acquisition-tool)**: Outbound lead scraping, score auditing, and prospecting tool integrated with Apollo and Apify.
- **[rufus-calculator](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/rufus-calculator)**: Interactive customer ROI and pricing positioning calculator built with React/Vite.
- **[docs](file:///c:/Users/hp/OneDrive/Desktop/optimus%20rufus/docs)**: Centralized workspace documentation including specifications, architectural diagrams, and generated client reports.

---

## 📦 Directory Overview

```
optimus-rufus/
├── .agents/                # AI agent skills & guidelines
├── docs/                   # Centralized system documentation
│   ├── specs/              # Technical specs & plans
│   ├── images/             # Architecture charts & positioning graphs
│   └── reports/            # Generated marketing reports
├── backend/                # FastAPI Python backend
├── rufus-dashboard/        # Next.js frontend app
├── acquisition-tool/       # Outbound pipeline & scraper
├── rufus-calculator/       # Interactive client ROI tool
├── Makefile                # Monorepo command runner
└── docker-compose.yml      # Multi-container production deployment
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (npm)
- Docker & Docker Compose

### Local Development Setup

#### 1. Setup Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Configure API keys
python main.py
```
Backend runs at `http://localhost:8000`.

#### 2. Setup Dashboard
```bash
cd rufus-dashboard
npm install
npm run dev
```
Dashboard runs at `http://localhost:3000`.

#### 3. Setup Calculator
```bash
cd rufus-calculator
npm install
npm run dev
```
Calculator runs at `http://localhost:5173`.

---

## 🐋 Production Deployment (Docker Compose)

The entire Optimus Rufus stack (FastAPI backend, Next.js frontend, outbound worker, and Caddy reverse proxy with automatic SSL) is configured to deploy with Docker Compose.

```bash
# 1. Edit environment variables
cp .env.example .env

# 2. Run deploy script (UFW Firewall, Docker dependencies, Health Checks)
./deploy.sh
```

---

## 📄 License

Proprietary. All Rights Reserved. Optimus Rufus © 2026.
