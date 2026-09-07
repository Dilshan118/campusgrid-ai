# CampusGrid AI: Master System Architecture, Requirements Specification & Implementation Guide

**Document Identifier:** CG-SRS-OFFICIAL-ALIGN-2026-V2.0  
**Project Title:** CampusGrid AI — Multi-Agent Campus Energy Decision Support System & Cyber-Physical Digital Twin  
**Course Code:** IT 3041 – Information Retrieval and Web Analytics (IRWA)  
**Academic Lead:** Mr. Samadhi Chathuranga Rathnayake  
**Official Blueprint Reference:** `CampusGrid AI — system architecture and technology stack` (Unified Architectural Standard)  

---

## Document Navigation Guide (Focused Views)
To make this document practical for different engineering and academic needs, it is divided into **7 Dedicated Views**:
1. [View 1: Executive Overview & The Real-World Domain Problem](#view-1-executive-overview--the-real-world-domain-problem)
2. [View 2: System Architecture & Decoupled Topology (Official Diagram Alignment)](#view-2-system-architecture--decoupled-topology-official-diagram-alignment)
3. [View 3: The 4 Agents & Central Orchestrator Pipeline](#view-3-the-4-agents--central-orchestrator-pipeline)
4. [View 4: Technology Stack & Unified Data Storage Architecture](#view-4-technology-stack--unified-data-storage-architecture)
5. [View 5: Offline Ingestion & Periodic Retraining Pipelines](#view-5-offline-ingestion--periodic-retraining-pipelines)
6. [View 6: Scalable Codebase Hierarchy & Implementation Skeleton](#view-6-scalable-codebase-hierarchy--implementation-skeleton)
7. [View 7: Team Delegation & 60-Test Security Audit Matrix](#view-7-team-delegation--60-test-security-audit-matrix)

---

# View 1: Executive Overview & The Real-World Domain Problem

### 1.1 What is CampusGrid AI?
**CampusGrid AI** is an autonomous, multi-agent cyber-physical decision support platform designed specifically for university campuses and large institutional facilities. It assists campus facility directors and financial bursars in eliminating multi-million rupee electricity bill surcharges.

### 1.2 The 15-Minute Peak Demand Penalty Trap
Commercial consumers in Sri Lanka (under Ceylon Electricity Board / LECO **PUCSL GP-2** and **Industrial I-2** tariffs) pay electricity bills based on two metrics:
1. **Energy Charge ($\text{LKR / kWh}$):** The total cumulative kilowatt-hours of energy used across the month.
2. **Maximum Demand Surcharge ($\text{LKR / kVA}$):** A severe penalty determined solely by the **single highest 15-minute peak spike** recorded across the entire month.

```
                  THE 15-MINUTE PEAK DEMAND PENALTY TRAP
    Power (kW)
        ^
    900 |                  / \  <-- 15-Minute Chiller Surge at 14:00
        |                 /   \     (Locks in 30% - 50% of the ENTIRE monthly bill!)
    600 |  --------------/     \-----------------------------------------------
        |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    300 |  Baseline Campus Load Profile
        |______________________________________________________________________> Time
        00:00   04:00   08:00   12:00   14:00   16:00   18:00   20:00   24:00
```

* **The Operational Crisis:** If multiple lecture halls power on central air conditioning chillers simultaneously at 2:00 PM on a hot day, power surges for just 15 minutes. That single spike locks in a maximum demand surcharge that accounts for **30% to 50% of the university's monthly electricity bill**.
* **The Battery Storage Dilemma:** Universities install rooftop solar panels and Battery Energy Storage Systems (BESS), but run them on uncoordinated, dumb timers. The battery discharges during cheap morning hours and sits completely empty when the expensive evening peak hits (LKR 58.00/kWh between 18:00 and 22:30).

### 1.3 The Human-in-the-Loop Co-Pilot Philosophy
CampusGrid AI operates strictly behind the university meter. It does **not** control the national utility grid. It acts as an advisory co-pilot:
* Mathematical equations and thermal physics are solved deterministically by computational engines.
* The system recommends optimal battery charge/discharge schedules and precooling setpoints.
* **A human facility manager reviews, verifies, and approves every action before anything is physically actuated.**

---

# View 2: System Architecture & Decoupled Topology (Official Diagram Alignment)

The architecture adheres 100% to the official system specification: **Four specialized agents, one central orchestrator, communicating via REST + JSON over HTTPS, backed by unified PostgreSQL with pgvector.**

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
│                                 CAMPUSGRID AI SYSTEM ARCHITECTURE                                │
+──────────────────────────────────────────────────────────────────────────────────────────────────+
│                                                                                                  │
│   [ CLIENT APPLICATION ]                                                                         │
│   Web Dashboard (React 18 SPA: Vite + Tailwind CSS + Lucide + Recharts)                          │
│   - Natural-language what-if query, recommendation view, approval queue                          │
│                                                                                                  │
│                                           │  HTTPS                                               │
│                                           ▼                                                      │
│                                                                                                  │
│   [ ACCESS AND SECURITY LAYER ]                                                                  │
│   HTTPS · Authentication · Authorization                                                         │
│   - Authentication establishes who the user is; authorization and RBAC decide what they see      │
│   - HTTPS / TLS on every request between client, orchestrator, and agents; request payloads safe │
│   - Every query, agent message, decision, and approval written to the audit log store            │
│                                                                                                  │
│                                           │  REST · JSON                                         │
│                                           ▼                                                      │
│                                                                                                  │
│   [ ORCHESTRATOR ]                                                                               │
│   Deterministic sequential Python pipeline with typed hand-offs                                  │
│   - NLP converts user query into structured fields: action, date, building, room, target         │
│   - Routes to the agents the intent requires; handles sequencing and shared state                │
│   - Receives schedule and explanation back from Agent 4 and returns grounded answer to client    │
│                                                                                                  │
│             │                                 │ REST call to each agent   │                      │
│             ▼                                 ▼                           ▼                      │
│                                                                                                  │
│   [ THE FOUR SPECIALIZED SMART AGENTS ]                                                          │
│   +─────────────────────────+                 +─────────────────────────+                        │
│   | Agent 1 – Telemetry     |                 | Agent 2 – Digital Twin  |                        │
│   | and Forecasting         | ────forecast───►| Simulation              |                        │
│   | (ML · data)             |                 | (physics · simulation)  |                        │
│   +────────────┬────────────+                 +────────────┬────────────+                        │
│                │                                           │                                     │
│                │                                           │ feasibility                         │
│                │                                           ▼                                     │
│   +────────────┴────────────+                 +─────────────────────────+                        │
│   | Agent 3 – Policy and    |                 | Agent 4 – Dispatch      |                        │
│   | Information Retrieval   | ──constraints──►| and Explanation         |                        │
│   | (IR · NLP · RAG)        |                 | (LLM · optimization)    |                        │
│   +────────────┬────────────+                 +────────────┬────────────+                        │
│                │                                           │                                     │
│                ▼                                           ▼                                     │
│                                                                                                  │
│   [ DATA STORES, SIMULATION & EXTERNAL SERVICES ]                                                │
│   +-------------------------+                 +-------------------------+                        │
│   | PostgreSQL & pgvector   |                 | Simulation Platform     |                        │
│   | - Rooms, timetables,    |                 | (2R2C physics model     |                        │
│   |   meter history         |                 |  reached via MCP tool)  |                        │
│   | - Policy/tariff vectors |                 +-------------------------+                        │
│   +-------------------------+                 +-------------------------+                        │
│   +-------------------------+                 | LLM API (External)      |                        │
│   | Weather Service         |                 | & Audit Log Store       |                        │
│   | (Hourly campus forecast)|                 | (Encrypted append-only) |                        │
│   +-------------------------+                 +-------------------------+                        │
│                                                                                                  │
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

### Architectural Communication Directives
1. **Network Isolation:** Agents sit on the internal backend network and are **not** publicly exposed.
2. **Standard Inter-Agent Protocol:** Communication between the Orchestrator and all Agents uses **REST API + JSON over HTTPS** with payload signature validation.
3. **Model Context Protocol (MCP):** Used for agent-to-tool invocations, specifically between Agent 2 and the **Simulation Platform** runtime.
4. **Agent-to-Agent (A2A):** Documented as an optional future expansion standard for multi-vendor institutional federation, not required for core autonomy.

---

# View 3: The 4 Agents & Central Orchestrator Pipeline

The core intelligence is structured into four distinct agent competencies plus the central orchestrator. Information flows sequentially from forecasting to simulation, constraint extraction, and final dispatch.

```
                               THE 4-AGENT DATA PIPELINE
    [ User Query ]
          │
          ▼
   [ Orchestrator ] ──NLP Parse──► (action, date, building, room, target)
          │
          ▼
   [ Agent 1: Telemetry & Forecasting ]
          │
          ├─────► [ Emits Demand & Solar PV Forecast with Confidence Bands ]
          ▼
   [ Agent 2: Digital Twin Simulation ]
          │
          ├─────► [ Computes 2R2C Building Thermal Dynamics & Feasibility Envelope ]
          ▼
   [ Agent 3: Policy & Information Retrieval ]
          │
          ├─────► [ Retrieves PUCSL GP-2 Tariffs & ASHRAE-55 Comfort Constraints ]
          ▼
   [ Agent 4: Dispatch and Explanation ]
          │
          ├─────► [ Solves 48-Period MILP Optimization + Generates Plain-English XAI ]
          ▼
   [ Human Facility Manager Approval Queue ]
```

---

### 1. Central Orchestrator (Deterministic Python Pipeline)
* **Core Competency:** Conversational routing and workflow state management.
* **Responsibilities:**
  * Uses explicit NLP to parse user inputs into structured parameter fields (`action`, `date`, `building`, `room`, `target_temp`).
    Rule-based today; **spaCy `en_core_web_sm` NER is planned.**
  * Routes to the agents a given intent requires, in a fixed, auditable order.
    **LLM-driven intent routing is planned.** A graph framework (LangGraph) was evaluated and
    deliberately not adopted: the pipeline has no cycles and no conditional graph state.
  * Receives the final schedule and plain-language explanation from Agent 4 and returns the grounded answer to the client dashboard.

---

### 2. Agent 1 – Telemetry and Forecasting (ML · Data)
* **Core Competency:** Machine learning load prediction and time-series sensor ingestion.
* **Responsibilities:**
  * Reads meter logs, room capacities, course schedules, and occupancy records from **PostgreSQL**.
  * Pulls external hourly weather forecast data for campus coordinates (cached with local persistence fallback).
  * Forecasts day-ahead electricity demand (kW) and rooftop solar PV generation.
  * Flags abnormal consumption against the expected historical baseline (threshold-based today; **Isolation Forest planned**).
  * Emits demand and PV profiles with calibrated confidence bands.
* **Strict Operational Boundary:** **Predicts only — it does NOT choose an action or schedule.**

---

### 3. Agent 2 – Digital Twin Simulation (Physics · Simulation)
* **Core Competency:** Cyber-physical simulation and thermal feasibility validation.
* **Responsibilities:**
  * Represents campus building energy behavior using a continuous 2-Resistance 2-Capacitance (2R2C) Equivalent Thermal Network physics model.
  * Runs "What-If" scenarios: sudden ambient heatwaves ($+4^\circ\text{C}$), student crowd surges ($100\text{ W}$ heat per human body), and solar drop-offs.
  * Evaluates battery electrochemical State-of-Charge ($20\% \le SOC \le 90\%$) and ASHRAE-55 indoor comfort boundaries ($21.0^\circ\text{C} \le T_{\text{in}} \le 25.5^\circ\text{C}$).
  * Re-verifies a candidate schedule before it is recommended to the human manager.
  * Interfaces with the simulation runtime via **Model Context Protocol (MCP) tool calls**.
* **Strict Operational Boundary:** **Simulates only — it does NOT pick the final schedule.**

---

### 4. Agent 3 – Policy and Information Retrieval (IR · NLP · RAG)
* **Core Competency:** Hybrid regulatory search and constraint extraction.
* **Responsibilities:**
  * Executes keyword (lexical), semantic (vector), and hybrid search over campus documents.
  * Indexes PUCSL tariff schedules (GP-2, Industrial I-2) and ASHRAE-55 comfort standards inside **pgvector**.
  * Employs Named Entity Recognition (NER) to extract exact tariff rates (Day: LKR 30.00, Peak: LKR 58.00, Off-Peak: LKR 15.00), kVA maximum demand penalty thresholds, and time blocks.
  * Returns applicable regulatory rules and constraints with verified document and clause citations.
* **Strict Operational Boundary:** **Reports rules only — it does NOT decide schedules.**

---

### 5. Agent 4 – Dispatch and Explanation (LLM · Optimization)
* **Core Competency:** Mathematical cost minimization and plain-language justification.
* **Responsibilities:**
  * Combines the load forecast (from Agent 1), the physical feasibility envelope (from Agent 2), and the regulatory constraints (from Agent 3).
  * Formulates and solves a 48-period Mixed-Integer Linear Program (MILP) using `PuLP` with the `CBC` solver engine.
  * Eliminates the 15-minute peak demand penalty through battery peak-shaving and smart chiller pre-cooling.
  * Identifies which physical or financial constraints are binding on the chosen schedule.
  * Synthesizes a plain-English Explainable AI (XAI) justification grounded strictly in solver logs and retrieved citations.
* **Strict Operational Boundary:** **Recommends schedules; a human must approve before anything is actuated. Zero LLM writes to physical registers.**

---

# View 4: Technology Stack & Unified Data Storage Architecture

Every technology choice is aligned with the official system specification to deliver enterprise-grade performance without needless complexity:

```
+──────────────────────────┬─────────────────────────────┬─────────────────────────────────────────+
│ Architectural Layer      │ Selected Technology         │ Technical Role & Justification          │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Client Application       │ React 18 + Vite             │ Single Page Application (SPA) providing │
│                          │ Tailwind CSS + Recharts     │ sub-50ms reactive microgrid dashboards  │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Access & Security Layer  │ FastAPI + PyJWT             │ TLS/HTTPS encryption, OAuth 2.0 / JWT   │
│                          │ Pydantic v2 Validators      │ auth, RBAC authorization, AST sanitize  │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Orchestration Layer      │ Sequential Python pipeline  │ Deterministic agent sequencing with     │
│                          │ spaCy en_core_web_sm (plan) │ typed hand-offs; NLP field extraction   │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Relational Database      │ PostgreSQL 16               │ Stores structured campus data: rooms,   │
│                          │ (via SQLModel / psycopg2)   │ timetables, buildings, meter history    │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Vector Search Database   │ pgvector Extension          │ Runs inside PostgreSQL: vector search   │
│                          │ (sentence-transformers)     │ over tariff & policy document clauses   │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Simulation Platform      │ Python 2R2C Grey-Box Twin   │ Continuous differential equation solver │
│                          │ FastMCP Protocol Adapter    │ reached via Model Context Protocol (MCP)│
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Optimization Solver      │ PuLP with CBC Solver        │ Open-source MILP solver; solves the     │
│                          │                             │ 48-interval problem in well under 1s    │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ External LLM API         │ Google Gemini / LiteLLM     │ High-speed structured reasoning; never  │
│                          │                             │ receives raw high-frequency meter data  │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ Audit & Log Store        │ PostgreSQL Encrypted Store  │ Append-only table logging queries, agent│
│                          │                             │ messages, decisions, and human approvals│
+──────────────────────────┴─────────────────────────────┴─────────────────────────────────────────+
```

### The Unified Database: Neon Serverless PostgreSQL with pgvector
CampusGrid AI uses **Neon Serverless PostgreSQL** as its primary database. Neon provides fully managed cloud PostgreSQL with native `pgvector` support, connection pooling, and SSL encryption:
* **No Local Database Installation Needed:** All 4 team members connect to the exact same cloud database using a standard Neon connection string (`DATABASE_URL=postgresql://user:pass@ep-xyz-pooler...neon.tech/neondb?sslmode=require`).
* **Relational + Vector in One Place:** Campus structured tables (rooms, timetables, meter logs) and RAG vector embeddings (`embedding vector(384)`) reside in the **same database engine**.
* **Zero Synchronization Lag:** Changes to tariff vectors or sensor records are committed in single atomic transactions.

---

### Pluggable Zero-Code LLM Architecture (LiteLLM Factory)
To prevent vendor lock-in and allow instant switching between models without rewriting agent code, the system implements an abstracted **Pluggable LLM Manager** (`backend/core/llm_manager.py`):
* **Zero Code Changes:** Switching from Google Gemini to OpenAI, Anthropic Claude, Groq, or local Ollama requires changing only **one line in `.env`**:
  * `LLM_PROVIDER=gemini` $\rightarrow$ calls `gemini/gemini-1.5-flash`
  * `LLM_PROVIDER=openai` $\rightarrow$ calls `openai/gpt-4o-mini`
  * `LLM_PROVIDER=anthropic` $\rightarrow$ calls `anthropic/claude-3-5-sonnet-20240620`
  * `LLM_PROVIDER=groq` $\rightarrow$ calls `groq/llama-3.1-70b-versatile`
  * `LLM_PROVIDER=ollama` $\rightarrow$ calls `ollama/llama3` (local, free, zero cost)
* **Unified Agent Interface:** All agents invoke the singleton `llm = get_llm(); llm.generate(messages=...)`, completely isolated from model-specific client SDKs.

---

### Centralized Environment Variables & API Keys Reference
All secrets and operational parameters are managed separately in `.env` (configured via `backend/core/config.py`):

```
+──────────────────────────┬─────────────────────────────┬─────────────────────────────────────────+
│ Environment Variable     │ Example / Default Value     │ Operational Purpose                     │
+──────────────────────────┼─────────────────────────────┼─────────────────────────────────────────+
│ `DATABASE_URL`           │ `postgresql://user:pass@...`│ Neon Serverless PostgreSQL connection   │
│ `LLM_PROVIDER`           │ `gemini`                    │ Active LLM provider switch              │
│ `LLM_MODEL`              │ `gemini/gemini-1.5-flash`   │ Active model identifier                 │
│ `GEMINI_API_KEY`         │ `AIzaSy...`                 │ Google Gemini API credentials           │
│ `OPENAI_API_KEY`         │ `sk-proj-...`               │ OpenAI API credentials                  │
│ `ANTHROPIC_API_KEY`      │ `sk-ant-...`                │ Anthropic Claude API credentials        │
│ `GROQ_API_KEY`           │ `gsk_...`                   │ Groq Cloud API credentials              │
│ `WEATHER_PROVIDER`       │ `open-meteo`                │ Weather service (free, no key needed)   │
│ `JWT_SECRET_KEY`         │ `32_byte_hex_string`        │ Token signing for Access & Security     │
│ `EMBEDDING_MODEL`        │ `all-MiniLM-L6-v2`          │ Sentence-transformers embedding model   │
│ `COMFORT_MIN_TEMP_C`     │ `21.0`                      │ ASHRAE-55 lower comfort hard limit      │
│ `COMFORT_MAX_TEMP_C`     │ `25.5`                      │ ASHRAE-55 upper comfort hard limit      │
│ `BATTERY_MIN_SOC`        │ `0.20`                      │ Battery electrochemical lower guardrail │
│ `BATTERY_MAX_SOC`        │ `0.90`                      │ Battery electrochemical upper guardrail │
+──────────────────────────┴─────────────────────────────┴─────────────────────────────────────────+
```

---

# View 5: Offline Ingestion & Periodic Retraining Pipelines

The system architecture specifies two dedicated offline background pipelines that keep regulatory documents and predictive models continuously accurate:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
│                                    TWO OFFLINE PIPELINES                                         │
+──────────────────────────────────────────────────────────────────────────────────────────────────+
│                                                                                                  │
│  [ PIPELINE 1: OFFLINE DOCUMENT INGESTION ]                                                      │
│  (Triggered once during setup, and again whenever a tariff or university policy is revised)      │
│                                                                                                  │
│   +─────────────────────+     +─────────────────────+     +─────────────────────+                │
│   | Source Documents    | ──► | Text Extraction     | ──► | Clause Chunking     |                │
│   | - PUCSL Tariffs     |     | - Drops headers     |     | - Splits by clause  |                │
│   | - ASHRAE Standards  |     |   and page furniture|     |   or section        |                │
│   +─────────────────────+     +─────────────────────+     +──────────┬──────────+                │
│                                                                      │                           │
│                                                                      ▼                           │
│                               +─────────────────────+     +─────────────────────+                │
│                               | Loads into          | ◄── | Embedding Model     |                │
│                               | pgvector Table      |     | - Computes vectors  |                │
│                               +─────────────────────+     |   and keyword index |                │
│                                                           +─────────────────────+                │
│                                                                                                  │
│ ──────────────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                                  │
│  [ PIPELINE 2: OFFLINE PERIODIC RETRAINING ]                                                     │
│  (Triggered weekly/monthly to update predictive models and physical building coefficients)       │
│                                                                                                  │
│   +───────────────────────────────────+                   +───────────────────────────────────+  │
│   | Historical Archive                | ────────────────► | Retrain and Re-Fit                |  │
│   | - Accumulated sub-meter telemetry |                   | - LightGBM demand forecaster      |  │
│   | - Historical weather logs         |                   | - 2R2C thermal resistance ($R$)   |  │
│   | - Past semester timetables        |                   |   and capacitance ($C$) parameters│  │
│   +───────────────────────────────────+                   +─────────────────┬─────────────────+  │
│                                                                             │                    │
│                                                                             ▼                    │
│                                                   +───────────────────────────────────────────+  │
│                                                   | Updated Models Returned to Agents 1 & 2   |  │
│                                                   +───────────────────────────────────────────+  │
│                                                                                                  │
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

# View 6: Scalable Codebase Hierarchy & Implementation Skeleton

To prevent developer collisions during Git pull requests, the codebase is partitioned into distinct module boundaries matching the official architecture:

```
campusgrid-ai/
├── pyproject.toml                              # SINGLE source of dependency truth (+ extras)
├── .env.example                                # Every provider switch, documented
├── Dockerfile · docker-compose.yml             # Backend image · local pgvector
│
├── src/                                        # ◀── THE APPLICATION (Clean Architecture)
│   │
│   ├── domain/                                 # Pure business core — zero vendor imports
│   │   ├── entities/                           # TelemetryInterval, OptimizationResult, DocumentClause…
│   │   ├── interfaces/                         # ALL abstract contracts (ports)
│   │   │   ├── llm.py  embeddings.py  vector_store.py  repositories.py
│   │   │   ├── cache.py  reranker.py  tool.py  database.py
│   │   │   ├── forecaster.py                   # Agent 1 contract        (Developer 1)
│   │   │   ├── thermal_twin.py                 # Agent 2 contracts       (Developer 2)
│   │   │   ├── policy_extractor.py             # Agent 3 contracts       (Team Lead)
│   │   │   └── optimizer.py                    # Agent 4 contracts       (Developer 3)
│   │   └── exceptions/                         # Structured domain exception hierarchy
│   │
│   ├── application/
│   │   ├── container.py                        # DI composition root — LEAD ONLY, request wiring
│   │   └── services/                           # RetrievalService, AuditService
│   │
│   ├── agents/                                 # The 4 agents + central coordinator
│   │   ├── base/                               # BaseAgent: timing, tracing, error isolation
│   │   ├── coordinator/                        # Deterministic pipeline + NLP query parser
│   │   ├── telemetry/                          # AGENT 1 — forecaster            (Developer 1)
│   │   ├── digital_twin/                       # AGENT 2 — 2R2C thermal, battery (Developer 2)
│   │   ├── policy_rag/                         # AGENT 3 — hybrid RAG            (Team Lead)
│   │   └── dispatch_explanation/               # AGENT 4 — MILP, XAI, faithfulness (Developer 3)
│   │
│   ├── infrastructure/                         # Swappable adapters — the only vendor-aware code
│   │   ├── llm/                                # LiteLLM (Gemini/OpenAI/Claude/Groq/Ollama) + mock
│   │   ├── embeddings/                         # SentenceTransformers + deterministic mock
│   │   ├── vector_store/                       # pgvector · Chroma · in-memory
│   │   ├── retrieval/                          # Okapi BM25 + Reciprocal Rank Fusion
│   │   ├── database/
│   │   │   ├── session.py                      # SQLAlchemy / Neon engine
│   │   │   └── repositories/                   # ONE FILE PER ENTITY (prevents merge conflicts)
│   │   │       ├── room_repository.py          # Team Lead
│   │   │       ├── audit_log_repository.py     # Team Lead
│   │   │       ├── timetable_repository.py     # Developer 1
│   │   │       └── meter_history_repository.py # Developer 1
│   │   ├── tools/                              # weather_tool (Dev 1) · simulation_tool (Dev 2)
│   │   ├── reference_baselines/                # Working stand-ins — FROZEN, read-only
│   │   ├── cache/                              # TTL in-memory cache provider
│   │   └── observability/                      # Structured tracer, correlation IDs
│   │
│   ├── api/                                    # FastAPI gateway
│   │   ├── main.py                             # App, CORS, exception handlers, lifespan
│   │   ├── routes/                             # health · orchestrator · telemetry · simulation
│   │   │                                       # optimizer · rag · analytics · audit
│   │   ├── middleware/                         # Request tracing, error handling
│   │   └── dependencies/                       # Container injection
│   │
│   ├── config/settings.py                      # All provider switches — LEAD ONLY
│   ├── prompts/                                # Externalised prompt templates (Team Lead)
│   ├── pipelines/periodic_retraining/          # Offline model training (Developer 1)
│   ├── schemas/                                # Public request/response DTOs
│   └── shared/                                 # Constants, datetime helpers
│
├── backend/                                    # Compatibility shims → re-export from src/
│   └── data/
│       ├── init.sql                            # PostgreSQL DDL + pgvector schema
│       └── seeds/sample_campus_seed.csv        # 48-interval benchmark dataset
│
├── frontend/                                   # React 18 + Vite SPA (Team Lead)
├── docs/                                       # Coursework specifications & SRS
├── TEAM_GUIDES/                                # Role briefs + authoritative OWNERSHIP.md
└── tests/
    ├── unit/  integration/                     # 45 tests
    └── red_team_security_audits/               # 4 × 15-case individual audits
```

---

# View 7: Team Delegation & 60-Test Security Audit Matrix

> **Note for developers:** the delegation table below is an early draft that predates the
> `src/` Clean Architecture refactor, and it references `backend/` paths that are now
> compatibility shims. It is retained here as-submitted for the coursework record.
> **For actual file ownership, use [`TEAM_GUIDES/OWNERSHIP.md`](../TEAM_GUIDES/OWNERSHIP.md)**,
> which is the authoritative source and wins wherever the two disagree.

Each of the four development team members owns a distinct, un-conflicted operational slice, with the Team Lead taking on the interface, orchestration, and retrieval modules, and the other three members leading the specialized engineering domains:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
│                                  TEAM DELEGATION & AUDIT MATRIX                                  │
+──────────┬─────────────────────────────┬─────────────────────────────────┬───────────────────────+
│ Member   │ Engineering Workstream      │ Primary Codebase Ownership      │ Security Audit Focus  │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 1 │ Project Lead, Full-Stack UI,│ `frontend/`,                    │ Student 1:            │
│ (You /   │ Central Orchestrator, Web   │ `backend/security/`,            │ Prompt Injection,     │
│  Lead)   │ Analytics Suite & Agent 3   │ `backend/orchestrator/`,        │ Jailbreak Analysis &  │
│          │ (Policy & IR pgvector RAG)  │ `backend/agents/agent3_.../`,   │ System Prompt Defense │
│          │ + Ingestion Pipeline        │ `backend/pipelines/ingestion/`  │                       │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 2 │ Machine Learning & Campus   │ `backend/agents/`               │ Student 2:            │
│ (Team-   │ Telemetry Lead              │ `agent1_telemetry_forecasting/`,│ Privacy & Data Leakage│
│  mate A) │ - Agent 1: Telemetry & ML   │ `backend/pipelines/retraining/` │ Assessment (NILM &    │
│          │ - Neon meter/timetable read │                                 │ Differential Privacy) │
│          │ - Weather API & 24h forecast│                                 │                       │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 3 │ Cyber-Physical Digital Twin │ `backend/agents/`               │ Student 4:            │
│ (Team-   │ & Building Physics Lead     │ `agent2_digital_twin/`          │ Infrastructure, MCP   │
│  mate B) │ - Agent 2: Digital Twin Sim │                                 │ Interception & Network│
│          │ - 2R2C thermal equations    │                                 │ Protocol Security     │
│          │ - Battery SOC & degradation │                                 │                       │
│          │ - What-If perturbation sim  │                                 │                       │
│          │ - Simulation MCP tool call  │                                 │                       │
+──────────┼─────────────────────────────┼─────────────────────────────────┼───────────────────────+
│ Member 4 │ Mathematical Optimization & │ `backend/agents/`               │ Student 3:            │
│ (Team-   │ Responsible AI Lead         │ `agent4_dispatch_explanation/`, │ Responsible AI, Bias  │
│  mate C) │ - Agent 4: Dispatch Solver  │ `backend/security/audit_store.py│ & Faithfulness        │
│          │ - PuLP 48-interval MILP math│                                 │ Assessment (Dorm vs   │
│          │ - Tier-0 life safety locks  │                                 │ Office Fair Shedding) │
│          │ - XAI faithfulness checker  │                                 │                       │
+──────────┴─────────────────────────────┴─────────────────────────────────┴───────────────────────+
```

### Individual 80-Mark Security Audit Responsibilities:
* **Student 1 (Member 1 / You):** Probes the Client Dashboard and Central Orchestrator for direct prompt injection, system prompt extraction, roleplay jailbreaks, delimiter collisions, and multilingual token smuggling.
* **Student 2 (Member 2 / Teammate A):** Evaluates Agent 1 and Neon PostgreSQL meter data for Non-Intrusive Load Monitoring (NILM) disaggregation, student schedule reconstruction, and verifies calibrated differential privacy noise ($\epsilon=1.0$).
* **Student 3 (Member 4 / Teammate C):** Evaluates Agent 4 for systematic load-shedding bias between student dorms and faculty offices, tariff rate hallucination, screen-reader accessibility, and automated XAI faithfulness checks.
* **Student 4 (Member 3 / Teammate B):** Tests Agent 2's simulation runtime, unencrypted MCP tool interception, BACnet/IP packet spoofing, and vector store denial-of-service resilience.

---

## Conclusion
This specification establishes a clean, modern, and academically verified architecture. It aligns 100% with the official blueprint, guarantees that all group deliverables and individual security audits achieve top marks, and provides your development team with a structured, conflict-free roadmap.
