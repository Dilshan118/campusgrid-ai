# CampusGrid AI: Autonomous Multi-Agent Campus Microgrid EMS & Digital Twin

**Course Code:** IT 3041 – Information Retrieval and Web Analytics (IRWA)  
**Academic Lead:** Mr. Samadhi Chathuranga Rathnayake  
**Preferred GitHub Repository Name:** `campusgrid-ai`  
**System Version:** Production v4.2  

---

## 1. Project Overview
**CampusGrid AI** is a distributed multi-agent cyber-physical energy management platform engineered specifically for university campuses and large institutional facilities. 

It solves the **15-minute peak demand penalty trap** under Ceylon Electricity Board (CEB) / LECO industrial tariffs (such as **PUCSL GP-2** and **Industrial I-2**) by orchestrating rooftop solar PV, battery storage (BESS), and smart HVAC precooling through mathematical optimization (MILP), physics-based 2R2C thermal modeling, and grounded Explainable AI (XAI).

```
                  THE 4-AGENT SEQUENTIAL PIPELINE
    [ User Query ] ──► [ Central Orchestrator: Python / LangGraph ]
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

* **Frontend:** React 18 Single Page Application (SPA), Vite, Tailwind CSS, Lucide React, Recharts.
* **Backend Gateway:** FastAPI (Asynchronous Python Web Framework), Uvicorn, WebSockets.
* **Orchestration:** LangGraph State Machine, spaCy (`en_core_web_sm`) explicit Named Entity Recognition.
* **Database & Vector Search:** **Neon Serverless PostgreSQL 16** with native `pgvector` extension.
* **Mathematical Optimizer:** Deterministic Mixed-Integer Linear Programming (MILP) with `PuLP` and `HiGHS`.
* **Physics Digital Twin:** Continuous 2-Resistance 2-Capacitance (2R2C) Equivalent Thermal Network.
* **Pluggable LLM Manager:** LiteLLM provider factory supporting Google Gemini, OpenAI, Claude, Groq, and Ollama with zero code changes.

---

## 3. Quickstart & Installation Guide

### Prerequisites
* **Node.js:** v18.x or v20.x
* **Python:** v3.11 or newer
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
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Initialize the database schema (connects to Neon and creates `vector` extension and tables):
   ```bash
   python -c "from backend.core.database import init_db; init_db(); print('Database initialized successfully!')"
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   * Interactive Swagger Documentation available at: `http://localhost:8000/docs`

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

```
campusgrid-ai/
├── README.md                                   # Root project documentation
├── .env.example                                # Environment variable blueprint
├── docker-compose.yml                          # Optional local PostgreSQL + pgvector container
│
├── frontend/                                   # React 18 Single Page Application
│   ├── package.json                            # Frontend dependencies
│   ├── vite.config.js                          # Build configuration and backend proxy
│   ├── tailwind.config.js                      # Dark-mode styling configuration
│   └── src/
│       ├── App.jsx                             # Multi-view dashboard shell
│       ├── components/                         # UI cards, charts, and drawers
│       └── pages/                              # Overview, Twin, Optimizer, Analytics views
│
├── backend/                                    # FastAPI Backend & Agent Core
│   ├── main.py                                 # Server entry point with CORS & router mount
│   ├── requirements.txt                        # Pinned backend dependencies
│   │
│   ├── security/                               # Access & Security Layer (Auth, RBAC, Audit Store)
│   ├── orchestrator/                           # Central LangGraph state machine & spaCy NER
│   │
│   ├── agents/                                 # The 4 Specialized Agents
│   │   ├── agent1_telemetry_forecasting/       # Agent 1 (ML · Data)
│   │   ├── agent2_digital_twin/                # Agent 2 (Physics · Simulation / MCP)
│   │   ├── agent3_policy_rag/                  # Agent 3 (IR · NLP · RAG / pgvector)
│   │   └── agent4_dispatch_explanation/        # Agent 4 (LLM · MILP Optimization)
│   │
│   ├── pipelines/                              # Offline Pipelines
│   │   ├── document_ingestion/                 # PDF extraction & pgvector indexer
│   │   └── periodic_retraining/                # Historical model refitting scripts
│   │
│   ├── core/                                   # Config, Database, and Pydantic Contracts
│   │   ├── config.py                           # Settings manager with Neon & LLM support
│   │   ├── database.py                         # SQLModel engine with pgvector
│   │   ├── llm_manager.py                      # Zero-code pluggable LLM provider switch
│   │   └── contracts/                          # Immutable Pydantic v2 schemas
│   │
│   └── data/
│       ├── init.sql                            # PostgreSQL tables & pgvector DDL
│       └── seeds/sample_campus_seed.csv        # 48-period campus benchmark dataset
│
├── docs/                                       # Coursework Specifications & Architecture
│   ├── CAMPUSGRID_AI_SIMPLIFIED_SRS_AND_SYSTEM_GUIDE.md
│   ├── CAMPUSGRID_AI_FULL_MARKING_RUBRIC_EVALUATION.md
│   ├── CAMPUSGRID_AI_MASTER_ARCHITECTURAL_BLUEPRINT_AND_SRS.md
│   └── 04_COURSEWORK_SPECIFICATIONS_AND_RUBRICS.md
│
└── tests/
    ├── unit/                                   # Unit test suite
    └── red_team_security_audits/               # 60-Test Red Team Security Audit Harness
```

---

## 5. Team Delegation Matrix

```
+──────────┬─────────────────────────────┬─────────────────────────────────┬───────────────────────+
│ Member   │ Engineering Workstream      │ Codebase Ownership              │ Security Audit Focus  │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 1 │ Project Lead, Full-Stack UI,│ `frontend/`,                    │ Student 1:            │
│ (Lead)   │ Orchestrator, Web Analytics │ `backend/security/`,            │ Prompt Injection &    │
│          │ & Agent 3 (Policy RAG)      │ `backend/orchestrator/`,        │ Jailbreak Analysis    │
│          │ + Ingestion Pipeline        │ `backend/agents/agent3_.../`    │                       │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 2 │ ML & Telemetry Lead         │ `backend/agents/`               │ Student 2:            │
│ (Team A) │ - Agent 1: Telemetry & ML   │ `agent1_telemetry_forecasting/`,│ Privacy & Data Leakage│
│          │ - Weather API & 24h forecast│ `backend/pipelines/retraining/` │ (NILM & Diff Privacy) │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 3 │ Digital Twin & Physics Lead │ `backend/agents/`               │ Student 4:            │
│ (Team B) │ - Agent 2: Digital Twin Sim │ `agent2_digital_twin/`          │ Infrastructure & MCP  │
│          │ - 2R2C thermal equations    │                                 │ Interception Security │
│          │ - What-If perturbation sim  │                                 │                       │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 4 │ Optimization & AI Lead      │ `backend/agents/`               │ Student 3:            │
│ (Team C) │ - Agent 4: Dispatch Solver  │ `agent4_dispatch_explanation/`, │ Responsible AI, Bias  │
│          │ - PuLP 48-interval MILP math│ `backend/security/audit_store.py│ & Faithfulness        │
+──────────┴─────────────────────────────┴─────────────────────────────────┴───────────────────────+
```

---

## 6. License & Academic Attribution
Developed as part of **IT 3041 – Information Retrieval and Web Analytics (IRWA)** at the Sri Lanka Institute of Information Technology (SLIIT).  
All rights reserved © 2026 CampusGrid AI Team.
