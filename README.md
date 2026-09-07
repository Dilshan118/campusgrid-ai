# CampusGrid AI: Autonomous Multi-Agent Campus Microgrid EMS & Digital Twin

**Course Code:** IT 3041 – Information Retrieval and Web Analytics (IRWA)  
**Academic Lead:** Mr. Samadhi Chathuranga Rathnayake  
**Preferred GitHub Repository Name:** `campusgrid-ai`  
**System Version:** Production v4.2  

> ### 👉 New to this project? Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) first.
> It is the complete guide in plain English: what we are building, how the four agents work,
> which technologies we use and why, what is already done, what each team member is responsible
> for, the week-by-week plan, and how we work day to day.
> This README covers only installing and running the system.

---

## 1. Project Overview
**CampusGrid AI** is a distributed multi-agent cyber-physical energy management platform engineered specifically for university campuses and large institutional facilities. 

It solves the **15-minute peak demand penalty trap** under Ceylon Electricity Board (CEB) / LECO industrial tariffs (such as **PUCSL GP-2** and **Industrial I-2**) by orchestrating rooftop solar PV, battery storage (BESS), and smart HVAC precooling through mathematical optimization (MILP), physics-based 2R2C thermal modeling, and grounded Explainable AI (XAI).

```
                  THE 4-AGENT SEQUENTIAL PIPELINE
    [ User Query ] ──► [ Central Orchestrator: deterministic Python pipeline ]
                              │
                              ▼
    [ Agent 1: Telemetry & Forecasting ] ────Forecast────► [ Agent 2: Digital Twin Simulation ]
                                                                      │
                                                                 Feasibility
                                                                      ▼
    [ Agent 4: Dispatch & Explanation ] ◄───Constraints─── [ Agent 3: Policy & Info Retrieval ]
           │
           ▼
    [ Human Facility Manager Approval Queue (React Web Dashboard) ]
```

---

## 2. Technology Stack & Key Frameworks

Items marked **(planned)** are on the roadmap but not yet in the codebase. Everything else
is implemented and covered by the test suite.

* **Frontend:** React 18 Single Page Application, Vite, Tailwind CSS, Lucide React, Recharts.
* **Backend Gateway:** FastAPI + Uvicorn. Each agent is reachable over its own REST endpoint.
* **Orchestration:** Deterministic sequential Python pipeline with typed hand-offs between
  agents. Intent parsing is rule-based today; **spaCy `en_core_web_sm` NER and LLM intent
  routing are planned.** LangGraph was evaluated and deliberately not adopted — the pipeline
  has no cycles or conditional graph state, so it would add dependency weight without value.
* **Database & Vector Search:** **Neon Serverless PostgreSQL 16** with the `pgvector` extension —
  relational tables and embeddings in one engine. ChromaDB and an in-memory store are also
  available as drop-in adapters.
* **Information Retrieval:** Hybrid search — dense vector similarity plus Okapi BM25 keyword
  matching, merged with Reciprocal Rank Fusion (k=60).
* **Mathematical Optimizer:** Deterministic Mixed-Integer Linear Programming with `PuLP` and
  the CBC solver, over 48 half-hour intervals.
* **Physics Digital Twin:** Continuous 2-Resistance 2-Capacitance (2R2C) thermal network.
* **Pluggable LLM Manager:** LiteLLM provider factory supporting Google Gemini, OpenAI, Claude,
  Groq and Ollama — plus a deterministic mock provider for offline CI — switchable by one
  environment variable with zero code changes.

---

## 3. Quickstart & Installation Guide

### Prerequisites
* **Node.js:** v18.x or v20.x
* **Python:** v3.10 or newer (matches `requires-python` in `pyproject.toml`)
* **Git**

---

### Step 1: Environment Configuration
Copy the template configuration to create your local `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in:
1. `DATABASE_URL`: Your Neon Serverless PostgreSQL connection string (`postgresql://user:pass@ep-xyz-pooler...neon.tech/neondb?sslmode=require`).
2. `GEMINI_API_KEY`: Your Google Gemini API key (or OpenAI / Groq key).

---

### Step 2: Backend Setup
1. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies. `pyproject.toml` is the single source of dependency truth:
   ```bash
   pip install -e ".[all]"        # what every team member should run
   ```
   Lighter installs are available if you do not need the heavy extras:
   | Command | Gives you |
   |---|---|
   | `pip install -e ".[dev]"` | API + full test suite on mock providers (fast, no torch) |
   | `pip install -e ".[postgres]"` | adds the Neon / PostgreSQL driver |
   | `pip install -e ".[rag]"` | adds real sentence-transformers embeddings and PDF ingestion |
   | `pip install -e ".[ml]"` | adds LightGBM / scikit-learn / scipy for forecasting and physics fitting |

3. Verify the install before touching anything else:
   ```bash
   pytest tests/ -v
   ```

4. **Optional — connect a real database.** The app defaults to `DATABASE_PROVIDER=in_memory`
   and needs no database at all. To use Neon or local PostgreSQL, apply the schema first:
   ```bash
   psql "$DATABASE_URL" -f backend/data/init.sql
   ```
   > Applying `init.sql` is **required**. `init_db()` only creates the `vector` and
   > `uuid-ossp` extensions — it defines no tables, because the project has no SQLModel
   > table classes. Skipping this step leaves you with an empty schema and confusing
   > runtime errors.

5. Start the FastAPI development server:
   ```bash
   uvicorn src.api.main:app --reload --port 8000
   ```
   * Interactive Swagger documentation: `http://localhost:8000/docs`
   * `uvicorn backend.main:app` still works — it is a compatibility shim re-exporting the same app.

---

### Step 3: Frontend Setup
1. Open a new terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   npm install
   ```
2. Start the Vite React development server:
   ```bash
   npm run dev
   ```
3. Open your browser at `http://localhost:5173`.

---

## 4. Codebase Architecture

The application lives in **`src/`**, organised as Clean Architecture. Dependencies point
inward only: `api → application → domain`, with `infrastructure` plugged in at the edges.
Agents depend on **interfaces**, never on a vendor — only the DI container and the
factories know which concrete provider is active.

```
campusgrid-ai/
├── pyproject.toml                              # SINGLE source of dependency truth
├── .env.example                                # Every provider switch, documented
├── Dockerfile · docker-compose.yml             # Backend image · local pgvector
│
├── src/                                        # ◀── THE APPLICATION
│   │
│   ├── domain/                                 # Pure business core — zero vendor imports
│   │   ├── entities/                           # TelemetryInterval, OptimizationResult, …
│   │   ├── interfaces/                         # ALL abstract contracts (ports)
│   │   │   ├── llm.py  embeddings.py  vector_store.py  repositories.py
│   │   │   ├── cache.py  reranker.py  tool.py  database.py
│   │   │   ├── forecaster.py                   # Agent 1 contract   (Developer 1)
│   │   │   ├── thermal_twin.py                 # Agent 2 contracts  (Developer 2)
│   │   │   ├── policy_extractor.py             # Agent 3 contracts  (Team Lead)
│   │   │   └── optimizer.py                    # Agent 4 contracts  (Developer 3)
│   │   └── exceptions/                         # Structured domain exception hierarchy
│   │
│   ├── application/
│   │   ├── container.py                        # DI composition root — LEAD ONLY
│   │   └── services/                           # RetrievalService, AuditService
│   │
│   ├── agents/                                 # The 4 agents + coordinator
│   │   ├── base/                               # BaseAgent: timing, tracing, error isolation
│   │   ├── coordinator/                        # Deterministic pipeline + NLP parser
│   │   ├── telemetry/                          # Agent 1 — Developer 1
│   │   ├── digital_twin/                       # Agent 2 — Developer 2
│   │   ├── policy_rag/                         # Agent 3 — Team Lead
│   │   └── dispatch_explanation/               # Agent 4 — Developer 3
│   │
│   ├── infrastructure/                         # Swappable adapters (the only vendor code)
│   │   ├── llm/                                # LiteLLM (Gemini/OpenAI/Claude/Groq/Ollama) + mock
│   │   ├── embeddings/                         # SentenceTransformers + mock
│   │   ├── vector_store/                       # pgvector · Chroma · in-memory
│   │   ├── retrieval/                          # Okapi BM25 + Reciprocal Rank Fusion
│   │   ├── database/repositories/              # One file per entity — see ownership below
│   │   ├── tools/                              # Weather (Dev 1) · Simulation (Dev 2)
│   │   ├── reference_baselines/                # Working stand-ins — FROZEN, read-only
│   │   ├── cache/  observability/
│   │
│   ├── api/                                    # FastAPI gateway — 8 routers + middleware
│   ├── config/settings.py                      # All provider switches — LEAD ONLY
│   ├── prompts/                                # Externalised prompt templates
│   ├── pipelines/periodic_retraining/          # Offline model training (Developer 1)
│   ├── schemas/                                # Public request/response DTOs
│   └── shared/                                 # Constants, datetime helpers
│
├── backend/                                    # Compatibility shims → re-export from src/
│   └── data/                                   # init.sql schema + 48-interval seed CSV
│
├── frontend/                                   # React 18 + Vite SPA (Team Lead)
├── docs/                                       # Coursework specifications & SRS
├── TEAM_GUIDES/                                # Role briefs + authoritative ownership matrix
└── tests/
    ├── unit/  integration/                     # 45 tests
    └── red_team_security_audits/               # 4 × 15-case individual audits
```

---

## 5. Team Delegation

> **Authoritative file ownership lives in [`TEAM_GUIDES/OWNERSHIP.md`](TEAM_GUIDES/OWNERSHIP.md).**
> Read it before your first commit. Ownership tables inside `docs/` are earlier drafts kept
> as-submitted for the coursework record; where they disagree, `OWNERSHIP.md` wins.

| Member | Role | Owns | Individual audit |
|---|---|---|---|
| **Member 1** | Team Lead & Architect | `src/domain/`, `src/api/`, `src/application/container.py`, `src/config/`, Agent 3 Policy RAG, ingestion, analytics, `frontend/` | Student 1 — Prompt Injection & Jailbreak |
| **Member 2** | Developer 1 — Data & ML | `src/agents/telemetry/`, meter + timetable repositories, `weather_tool.py`, retraining pipeline | Student 2 — Privacy & Data Leakage |
| **Member 3** | Developer 2 — Digital Twin | `src/agents/digital_twin/`, `simulation_tool.py` | Student 4 — Retrieval, Tool & MCP Security |
| **Member 4** | Developer 3 — Optimization & Responsible AI | `src/agents/dispatch_explanation/` (whole folder) | Student 3 — Responsible AI, Bias & Faithfulness |

**Three rules that prevent almost every merge conflict here:**

1. Never commit a file you do not own.
2. `container.py` and `settings.py` are **request-only** — open an issue, the Lead edits.
3. Rebase on `main` every morning.
```

---

## 6. License & Academic Attribution
Developed as part of **IT 3041 – Information Retrieval and Web Analytics (IRWA)** at the Sri Lanka Institute of Information Technology (SLIIT).  
All rights reserved © 2026 CampusGrid AI Team.
