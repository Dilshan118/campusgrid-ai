# CampusGrid AI: Complete Codebase and Workflow Walkthrough

**Review date:** 2026-09-30  
**Scope:** React frontend, FastAPI routes, agents, application services, infrastructure providers, storage, ingestion/training pipelines, compatibility layer, tests, and deployment files.  
**Method:** This document follows the executable code. It does not treat a screen label or design document as proof that a feature is implemented.

## Executive conclusion

CampusGrid AI is a **campus energy planning and decision-support application**. An operator or facility manager can ask a natural-language question, inspect a demand/solar forecast, simulate room comfort, search regulations, or request a battery dispatch plan. For a full dispatch request, the backend coordinates four agents:

1. Agent 1 produces a half-hourly campus demand and solar forecast.
2. Agent 2 simulates one room's thermal comfort.
3. Agent 3 retrieves tariff and comfort clauses and deterministically extracts numeric rules.
4. Agent 4 solves a battery-only MILP and asks an LLM to explain the solver result.

The recommendation is written to an append-only audit trail and waits for a facility manager to approve or reject it.

The most important fact for a new developer is this:

> **Approval does not execute the plan.** There is no BMS, inverter, BACnet, Modbus, job-dispatch, or actuator integration. Approval appends an audit decision. An approved plan can be downloaded as a plain-text checklist and must be carried out manually.

The application is therefore a useful coursework/demo implementation of forecasting, simulation, RAG, optimization, XAI, approval, analytics, and auditing, but it is not yet a production campus energy-management system.

### Implementation labels used below

- **Implemented:** There is an executable frontend-to-backend path with real application logic.
- **Implemented with fallback/demo data:** The path works, but may use seeded, synthetic, or offline fallback data.
- **Presentation only:** The UI represents a stage or capability that is not actually streamed or executed.
- **Missing:** No working end-to-end implementation exists.

---

## 1. Project purpose

### 1.1 The problem it is trying to solve

The system tries to help a university reduce daily electricity cost and peak demand without violating classroom comfort constraints. It combines five kinds of information:

- campus meter history;
- weather and timetable/occupancy information;
- a room thermal model;
- electricity tariffs and comfort regulations;
- a battery optimization model.

It converts those inputs into a reviewable recommendation with citations, warnings, projected savings, a battery schedule, and an audit record.

### 1.2 The real end-to-end purpose

The actual code supports this outcome:

> A staff member asks for a forecast, simulation, regulation lookup, or battery plan; the system calculates and explains the result; a facility manager records an approval/rejection decision; staff manually carry out any approved schedule outside CampusGrid.

It does **not** close the loop by observing whether the approved schedule was executed or whether the predicted saving occurred.

### 1.3 Major source-code areas

| Area | Responsibility | Main location |
|---|---|---|
| React dashboard | Pages, charts, forms, permission-aware navigation, API calls | [`frontend/src`](../frontend/src) |
| HTTP API | Authentication, route-level role checks, request/response handling | [`src/api`](../src/api) |
| Orchestration | Intent classification and selective agent execution | [`src/agents/coordinator`](../src/agents/coordinator) |
| Agent 1 | Telemetry, weather, timetable, forecasting, DP export | [`src/agents/telemetry`](../src/agents/telemetry) |
| Agent 2 | Thermal twin, battery dynamics, what-if simulation, MCP tool | [`src/agents/digital_twin`](../src/agents/digital_twin) |
| Agent 3 | Hybrid retrieval and deterministic rule extraction | [`src/agents/policy_rag`](../src/agents/policy_rag) |
| Agent 4 | Battery MILP, LLM explanation, faithfulness checking | [`src/agents/dispatch_explanation`](../src/agents/dispatch_explanation) |
| Application services | Retrieval, approvals/audit, analytics | [`src/application/services`](../src/application/services) |
| Infrastructure | PostgreSQL, pgvector/Chroma/memory, embeddings, LLMs, cache, weather | [`src/infrastructure`](../src/infrastructure) |
| Offline pipelines | Document ingestion and forecast training | [`src/pipelines`](../src/pipelines) |
| Legacy compatibility | Old imports delegating to `src`; not the main architecture | [`backend`](../backend) |
| Database bootstrap | Tables, seed rooms/timetables, pgvector, append-only trigger | [`backend/data/init.sql`](../backend/data/init.sql) |

The central dependency-injection composition root is [`src/application/container.py`](../src/application/container.py). It selects providers from environment settings and wires repositories, services, tools, agents, and the orchestrator.

---

## 2. Roles and permissions

### 2.1 Roles actually implemented

The backend implements exactly three roles in [`src/api/routes/auth.py`](../src/api/routes/auth.py) and [`src/api/middleware/auth.py`](../src/api/middleware/auth.py):

| Role | Practical meaning | Can create plans | Can approve/reject | Can ingest regulations | Can view analytics | Can view system status |
|---|---|---:|---:|---:|---:|---:|
| `FACILITY_MANAGER` | Full-access decision maker | Yes | Yes | Yes | Yes | Yes |
| `OPERATOR` | Day-to-day planning user | Yes | No | No | No | No |
| `ENERGY_AUDITOR` | Read-only compliance reviewer | No | No | No | Yes | No |

### 2.2 Exact permission matrix returned to the frontend

| Permission | Facility manager | Operator | Energy auditor | Meaning in the UI |
|---|:---:|:---:|:---:|---|
| `orchestrator:query` | Yes | Yes | No | Ask CampusGrid |
| `simulation:run` | Yes | Yes | No | What-if simulator |
| `optimizer:run` | Yes | Yes | No | New dispatch plan |
| `telemetry:read` | Yes | Yes | No | Forecast and historical overlay |
| `rag:search` | Yes | Yes | Yes | Regulation search/library read |
| `rag:ingest` | Yes | No | No | Add or re-index regulations |
| `audit:read` | Yes | Yes | Yes | Approvals, plan review, audit records |
| `audit:approve` | Yes | No | No | Approve/reject controls |
| `analytics:read` | Yes | No | Yes | Analytics and audit-chain verification |
| `system:read` | Yes | No | No | System Status page |

### 2.3 How access control works

There are two layers:

1. **Frontend convenience layer.** [`frontend/src/App.jsx`](../frontend/src/App.jsx) assigns a permission to each route, while [`frontend/src/components/Layout.jsx`](../frontend/src/components/Layout.jsx) filters navigation items and hides buttons. This improves usability but is not the security boundary.
2. **Backend security layer.** Every protected route uses `Depends(require_roles(...))`. The bearer JWT is verified for signature, issuer, expiry, role, and revocation before the role is compared with the route's allowed role group. Missing/invalid tokens receive 401; valid but disallowed roles receive 403.

The backend authorizes by the `role` claim, not by trusting a client-supplied permission list. The acting `user_id` for queries, decisions, and analytics also comes from the verified token, not the request body.

### 2.4 Authentication that exists versus authentication that is implied

**Implemented:**

- three hard-coded demo accounts with PBKDF2 password hashes;
- signed HS256 JWT access tokens;
- five-failure/five-minute login throttling;
- logout token revocation;
- session restoration through `GET /api/auth/me`;
- token storage in browser `sessionStorage`, so it is scoped to the tab session;
- automatic logout/redirect on any authenticated 401 response.

**Not implemented:**

- a users table;
- account creation, deletion, password reset, or an administrator page;
- university SSO/OIDC/SAML;
- persistent/distributed lockouts or token revocation for multi-instance deployments;
- refresh tokens or device/session management.

The login-page sentence “Accounts are created by an administrator” is therefore aspirational. No account-administration workflow exists.

### 2.5 How the roles interact

1. An **operator** or **facility manager** creates a recommendation through Ask CampusGrid or New Dispatch Plan.
2. All three roles can read the resulting recommendation because all have `audit:read` in the current design.
3. Only a **facility manager** can approve or reject it.
4. An **energy auditor** can inspect the plan, decision, citations, agent outputs, and audit-chain integrity, but cannot change the plan or decision.
5. After approval, operational staff use the downloaded checklist and an external BMS to carry out the schedule manually.

There is no explicit assignment, notification, hand-off, or acknowledgement record for the person who performs that final manual work.

---

## 3. Complete real user workflows

The natural-language entry point is [`POST /api/orchestrator/query`](../src/api/routes/orchestrator.py). The orchestrator in [`src/agents/coordinator/agent.py`](../src/agents/coordinator/agent.py) first parses the question and chooses one of five actions. It does **not** always run all four agents.

### 3.1 Intent understanding

[`src/agents/coordinator/nlp_parser.py`](../src/agents/coordinator/nlp_parser.py) deterministically extracts:

- action/intent;
- date;
- room and building;
- requested setpoint;
- ambient-temperature change;
- occupancy multiplier;
- prompt-injection/security flags;
- assumptions such as a default room/date or clamped temperature.

If rule-based confidence is below `0.6`, [`src/agents/coordinator/intent_router.py`](../src/agents/coordinator/intent_router.py) asks the configured LLM to choose one label from a closed list. The LLM cannot supply a temperature, room, date, or physical limit; those stay deterministic.

### 3.2 Policy/regulation lookup

**Example:** “What is the GP-2 peak rate?”

1. Parser chooses `policy_lookup`.
2. Only Agent 3 runs.
3. Hybrid retrieval returns up to three clauses.
4. Deterministic regex/range/order rules extract tariff/comfort figures.
5. A `policy_lookup` audit record is appended with status `not_required`.
6. The frontend displays the cited clauses and extracted figures.

No human approval is required because this path only returns information.

### 3.3 Forecast request

**Example:** “Show tomorrow's forecast.”

1. Parser chooses `telemetry_status`.
2. Agent 1 loads a historical profile, obtains weather, and reads the selected room's timetable.
3. It predicts 48 half-hour demand/solar values and confidence bounds.
4. It optionally asks the LLM for a two-sentence forecast summary.
5. A `forecast_review` audit record is appended.
6. The frontend displays the chart, peak, peak time, and anomaly count.

No approval is required.

### 3.4 What-if simulation request

**Example:** “What if tomorrow is 3 C hotter in LH-1?”

1. Parser chooses `what_if_simulation`.
2. Agent 1 supplies weather and room occupancy inputs.
3. Occupancy is capped at the room's configured capacity.
4. Agent 2 perturbs the inputs, generates an HVAC thermostat schedule, runs the 2R2C thermal model, and counts intervals outside 21.0-25.5 C.
5. It also returns an idle-battery SOC trajectory unless a battery plan is supplied.
6. A `what_if_simulation` audit record is appended.
7. The frontend shows indoor/outdoor temperature and offers “Plan for this scenario.”

No approval is required because the simulation changes nothing.

### 3.5 Full dispatch-planning request

**Example:** “Plan tomorrow's battery schedule for LH-1 to reduce the evening peak.”

1. Parser chooses `optimize_dispatch` and records defaults/assumptions.
2. Agent 3 starts in a worker thread because regulation retrieval does not depend on the forecast.
3. Agent 1 runs on the request thread:
   - load meter history for the target date, or seed fallback;
   - call Open-Meteo, or use a deterministic offline curve;
   - read the room timetable;
   - predict 48 half-hour campus demand and solar values;
   - create an LLM forecast summary.
4. The orchestrator caps Agent 1's room occupancy at configured capacity.
5. Agent 2 runs the room thermal simulation using the requested/default setpoint and reports a comfort verdict.
6. Agent 3 searches the user's question and four additional constraint queries so the solver receives peak/day/off-peak tariff rates, tariff windows, maximum-demand charge, and comfort citations.
7. The orchestrator converts the retrieved tariff rules into a 48-slot price profile.
8. Agent 4 builds an `OptimizationInput` and solves a battery dispatch MILP:
   - grid import, battery charge, discharge, SOC, peak-grid, and charge-mode variables;
   - SOC and charge/discharge power limits;
   - no simultaneous charging/discharging;
   - power balance for each half-hour;
   - end-of-day SOC at least equal to starting SOC;
   - objective of daily energy cost plus 1/30 of the monthly maximum-demand charge.
9. Agent 4 asks the LLM for a plain-language explanation. If the LLM fails, it uses a deterministic solver-only template.
10. A second LLM call and a deterministic numeric checker audit the explanation. A failure produces a warning rather than silently certifying the text.
11. The orchestrator assembles solver data, sources, tariff provenance, comfort verdict, warnings, target, battery limits, assumptions, and baseline grid profile.
12. A signed `dispatch_recommendation` audit record is appended with `approval_status=pending`.
13. The API returns `ready_for_operator_approval` (the name is historical; only a facility manager can decide it).
14. The frontend opens Plan Review.
15. A facility manager approves or rejects:
    - warnings must be explicitly acknowledged before approval;
    - rejection requires notes;
    - plans older than 24 hours cannot be decided;
    - a second decision is rejected.
16. The system appends a separate `approval_decision` audit record. It never edits the recommendation row.
17. If approved, the user can download a text execution checklist.
18. Execution is manual and external to the application.

### 3.6 Out-of-scope request

If the parser finds no relevant energy/comfort/regulation intent, no domain agent runs. The system appends an `out_of_scope_query` record and returns a scope explanation plus suggested valid questions.

---

## 4. Dashboards and features

Routes are defined in [`frontend/src/App.jsx`](../frontend/src/App.jsx). API calls are centralized in [`frontend/src/api/client.js`](../frontend/src/api/client.js).

### 4.1 Login

- **Frontend:** [`frontend/src/pages/LoginPage.jsx`](../frontend/src/pages/LoginPage.jsx)
- **Users:** Everyone before authentication.
- **API:** `POST /api/auth/login`, then `GET /api/auth/me` when restoring a session.
- **Action/result:** Valid demo credentials return JWT, profile, role, permissions, and expiry. The user is sent to the role's home page.
- **Demo aspect:** Development builds reveal three demo account credentials in an expandable panel.

### 4.2 Overview

- **Frontend:** [`frontend/src/pages/OverviewPage.jsx`](../frontend/src/pages/OverviewPage.jsx)
- **Users:** All roles, with different content.
- **Planner view (manager/operator):** Pending-plan count, tomorrow's LH-1 forecast, last approved plan, demand chart, and quick actions.
- **Auditor view:** Hash-chain integrity, plans approved with warnings this month, and recent decisions.
- **APIs:** `/api/audit/pending`, `/api/telemetry/forecast`, `/api/audit/logs`, `/api/audit/verify`.
- **Important behavior:** The planner overview always forecasts `LH-1`; it is not a configurable campus summary.

### 4.3 Ask CampusGrid

- **Frontend:** [`frontend/src/pages/AskPage.jsx`](../frontend/src/pages/AskPage.jsx)
- **Users:** Facility manager and operator.
- **API:** `POST /api/orchestrator/query`.
- **Actions:** Ask plain-English questions; optionally override ambient temperature and occupancy; open results and recent questions from this browser session.
- **Backend:** NLP parser, optional LLM intent router, then only the agent branch required by the intent.
- **After a dispatch:** A pending plan is created and Plan Review can be opened.
- **Presentation-only detail:** The five progress steps are a timer animation. The backend does not stream per-agent progress, so the active step is not real server state.
- **Storage:** The last eight questions/results are kept in `sessionStorage`, not a server-side conversation history.

### 4.4 What-if Simulator

- **Frontend:** [`frontend/src/pages/WhatIfPage.jsx`](../frontend/src/pages/WhatIfPage.jsx)
- **Users:** Facility manager and operator.
- **API:** `POST /api/simulation/what-if`; `GET /api/campus/rooms`.
- **Actions:** Choose room/date, starting indoor temperature, outdoor-temperature delta, and occupancy multiplier.
- **Backend:** Weather tool + meter history occupancy + Agent 2 thermal model.
- **Result:** 48 half-hour temperature points, comfort violations, source/fallback notice, room-capacity notice.
- **After action:** “Plan for this scenario” pre-fills Ask CampusGrid; it does not pass an immutable simulation object or link the eventual plan to the simulation record.

### 4.5 Forecast

- **Frontend:** [`frontend/src/pages/ForecastPage.jsx`](../frontend/src/pages/ForecastPage.jsx)
- **Users:** Facility manager and operator.
- **APIs:** `GET /api/telemetry/forecast`, `GET /api/telemetry/historical`, `GET /api/campus/rooms`.
- **Actions:** Select date and room; optionally overlay a historical profile.
- **Backend:** Agent 1 and the differential-privacy export path.
- **Result:** Demand, solar, uncertainty bands, peak, anomaly count, optional LLM summary.
- **Caveat:** With no database rows for the selected date, “historical” is the same seeded fallback day with fresh-process-cached DP noise, not a true comparable historical day.

### 4.6 Approvals

- **Frontend:** [`frontend/src/pages/ApprovalsPage.jsx`](../frontend/src/pages/ApprovalsPage.jsx)
- **Users:** All roles can read; only facility manager can decide.
- **APIs:** `GET /api/audit/pending`, `GET /api/audit/logs`.
- **Actions:** Switch pending/all, filter warnings, show plans created by the current user, refresh, open/re-run plans.
- **Result:** The current effective state is derived from a separate decision row or 24-hour expiry.
- **Limitation:** The UI fetches at most 100 rows and then filters in the browser. There is no pagination.

### 4.7 New Dispatch Plan

- **Frontend:** [`frontend/src/pages/NewPlanPage.jsx`](../frontend/src/pages/NewPlanPage.jsx)
- **Users:** Facility manager and operator.
- **API:** `POST /api/optimizer/dispatch`.
- **Actions:** Select date/room and battery capacity, charge rate, discharge rate, and starting SOC.
- **Backend:** The endpoint forces the complete orchestrator pipeline; it is not a direct solver-only call.
- **After action:** A pending recommendation is created and the UI navigates to Plan Review.
- **Misleading UI:** The banner says the current optimizer still applies campus battery defaults until Agent 4 reads the fields. Agent 4 now does read and use these per-request fields, so that warning is stale.

### 4.8 Plan Review

- **Frontend:** [`frontend/src/pages/PlanReviewPage.jsx`](../frontend/src/pages/PlanReviewPage.jsx)
- **Users:** All roles can read; facility manager decides.
- **APIs:** `GET /api/audit/logs/{id}`, `POST /api/audit/approve`, analytics-event endpoint.
- **Content:** Savings, peak reduction, explanation variant, faithfulness badge, warnings, battery/grid charts, binding limits, tariff provenance, comfort verdict, sources, decision history.
- **Approval rules:** Manager only; warning acknowledgement required; rejection notes required; plan must be pending and younger than 24 hours.
- **After approval:** A text checklist is generated entirely in the browser from stored solver output. It is not sent to an execution service.

### 4.9 Regulation Search

- **Frontend:** [`frontend/src/pages/RegulationsSearchPage.jsx`](../frontend/src/pages/RegulationsSearchPage.jsx)
- **Users:** All roles.
- **API:** `POST /api/rag/search` plus interaction analytics.
- **Actions:** Search, choose top 1-5 results, expand a clause.
- **Backend:** Agent 3 -> RetrievalService -> dense search when semantic embeddings are active + BM25 -> RRF.
- **Result:** Citation cards include document, clause, effective date, content, matched-by labels, and fusion score.
- **Fallback:** The page reports “Keyword matching only” when mock/non-semantic embeddings disable dense retrieval.

### 4.10 Regulation Library

- **Frontend:** [`frontend/src/pages/LibraryPage.jsx`](../frontend/src/pages/LibraryPage.jsx)
- **Users:** All roles can list; facility manager can ingest/re-index.
- **APIs:** `GET /api/rag/documents`, `POST /api/rag/ingest`.
- **Actions:** List indexed sources, paste Markdown/text, set source title/effective date, re-index the server corpus directory.
- **Backend:** Chunk -> screen/quarantine -> embed -> vector store -> BM25 index -> audit record.
- **Limitation:** There is no multipart PDF/TXT upload UI. Files must already exist in the server corpus folder before re-indexing.

### 4.11 Audit & Compliance

- **Frontend:** [`frontend/src/pages/AuditPage.jsx`](../frontend/src/pages/AuditPage.jsx)
- **Users:** All roles can read. Manager and auditor can run chain verification.
- **APIs:** `GET /api/audit/logs`, `GET /api/audit/logs/{id}`, `GET /api/audit/verify`.
- **Actions:** Filter type/status on the server; filter user/date in the browser; inspect a record drawer; inspect each agent's stored output; navigate between recommendation and decision; export the currently loaded rows as CSV.
- **Result:** The page exposes the audit record's SHA-256 chain fields and effective approval state.
- **Limitation:** CSV export covers only the currently loaded maximum 100 rows, not a complete database export.

### 4.12 Analytics

- **Frontend:** [`frontend/src/pages/AnalyticsPage.jsx`](../frontend/src/pages/AnalyticsPage.jsx)
- **Users:** Facility manager and energy auditor.
- **API:** `GET /api/analytics/summary`; browser events use `POST /api/analytics/event`.
- **Modules:** Acceptance funnel, explanation A/B test, intent grouping/top words, citation first-click MRR.
- **Actual data:** Calculated from stored analytics events; not hard-coded chart numbers.
- **Important qualification:** “Query clusters” are groups by the parser's existing intent label plus word counts. There is no embedding/topic-clustering algorithm.
- **A/B rule:** User ID hashes deterministically to concise-first or cited-first. Statistical significance is withheld until both arms have at least 30 decisions.

### 4.13 System Status

- **Frontend:** [`frontend/src/pages/SystemStatusPage.jsx`](../frontend/src/pages/SystemStatusPage.jsx)
- **Users:** Facility manager only.
- **API:** public `GET /api/health`.
- **Content:** Active Python provider class names, dense-search state, version, and whether agents 1/2/4 use member code or a reference baseline.
- **Limitation:** “online” is returned if the endpoint executes; it does not actively test database, LLM, embedding, weather, or vector-store availability.

### 4.14 MCP endpoint (no dashboard page)

- **Backend:** [`src/api/routes/mcp.py`](../src/api/routes/mcp.py) and [`src/agents/digital_twin/mcp_server.py`](../src/agents/digital_twin/mcp_server.py)
- **Users:** Planner roles through authenticated HTTP.
- **Protocol:** Minimal JSON-RPC `initialize`, `ping`, `tools/list`, and `tools/call`.
- **Tools:** Weather and thermal simulation are registered by the container.
- **Caveat:** It is an HTTP endpoint carrying MCP-like JSON-RPC, not the full official MCP SDK/transport stack, and has no message-level signature.

---

## 5. Data flow

### 5.1 Common request path

1. A React page calls a method in [`frontend/src/api/client.js`](../frontend/src/api/client.js).
2. `fetch` sends JSON and a bearer JWT to FastAPI.
3. Sanitization and request-tracing middleware process the request.
4. JWT/role dependencies authenticate and authorize it.
5. The route obtains the singleton [`Container`](../src/application/container.py).
6. The route calls an agent or application service.
7. Repositories/providers access PostgreSQL, pgvector/Chroma/memory, weather, embeddings, or an LLM.
8. The route wraps data in the common API response shape.
9. The API client unwraps `payload.data`; errors become `ApiError` objects.
10. React renders results and may send non-blocking analytics events.

### 5.2 Storage actually used

The environment can select in-memory or PostgreSQL implementations. The current `.env` selects **PostgreSQL + pgvector**, **Groq LLM**, **Google embeddings (768 dimensions)**, **memory cache**, **RRF**, and **Open-Meteo**. Secrets are intentionally not reproduced here. `/api/health` is the reliable runtime check of the provider classes that successfully loaded.

PostgreSQL schema in [`backend/data/init.sql`](../backend/data/init.sql):

| Table | Purpose |
|---|---|
| `rooms` | Room inventory and capacity |
| `timetables` | Expected occupancy by room/day/time |
| `meter_history` | Historical half-hour meter/weather/tariff/occupancy rows |
| `document_clauses` | Regulation chunks and pgvector embeddings |
| `audit_log_store` | Append-only recommendations, lookups, simulations, ingestions, and decisions |
| `analytics_events` | Query, display, explanation, citation, and decision interaction events |

There is no users table, execution-jobs table, equipment table, live telemetry queue, model registry, or notification table.

### 5.3 Forecast data flow

`ForecastPage` or orchestrator  
-> `/api/telemetry/forecast` or Agent 1 inside orchestrator  
-> `MeterHistoryRepository.get_historical_profile(date)`  
-> PostgreSQL rows or one 48-row CSV seed fallback  
-> `WeatherTool.execute(date)`  
-> Open-Meteo or deterministic offline curve  
-> `TimetableRepository.get_schedule_for_day()`  
-> `DemandForecaster.predict()`  
-> optional LLM summary  
-> API/chart/audit record.

The room picker does **not** produce a room-level electricity forecast. Demand is campus-wide; the selected room mainly determines the timetable/occupancy supplied to the thermal twin.

### 5.4 Dispatch data flow

`AskPage`/`NewPlanPage`  
-> orchestrator route  
-> parser/intent router  
-> Agent 1 forecast + Agent 2 room comfort + Agent 3 regulations  
-> tariff-profile builder  
-> Agent 4 battery MILP  
-> LLM explanation + faithfulness verifier  
-> `AuditLogRepository.log_transaction()`  
-> pending Plan Review  
-> manager decision  
-> separate audit decision row  
-> browser-generated manual checklist.

---

## 6. AI and RAG workflow

### 6.1 Where AI/LLMs are actually used

LLMs are used for four bounded tasks:

1. low-confidence intent routing;
2. a two-sentence forecast summary;
3. dispatch-plan explanation;
4. explanation faithfulness audit.

The numeric forecast, thermal equations, tariff extraction, tariff profile, optimization, approval rules, and audit signatures are deterministic code. The LLM does not write to hardware.

### 6.2 RAG ingestion

The default corpus folder is [`backend/rag/corpus/tariffs`](../backend/rag/corpus/tariffs), currently containing one PUCSL GP-2 Markdown document and one ASHRAE-55 Markdown document.

[`src/pipelines/document_ingestion/ingest_corpus.py`](../src/pipelines/document_ingestion/ingest_corpus.py) performs:

1. Read `.md`, `.txt`, or `.pdf` files.
2. Split Markdown headings or plain/PDF clause headings into `DocumentClause` objects.
3. Remove repeated page furniture from extracted PDFs.
4. Screen clauses for empty/oversized content, prompt-injection patterns, implausible figures, tariff-order violations, and inverted comfort bounds.
5. Deduplicate by normalized `source_document + clause_reference`.
6. Generate embeddings for accepted clause content.
7. Store text/metadata/vectors in the selected vector store.
8. Add embedding-free copies to the in-process BM25 index.

Rejected clauses are returned to the uploader and not indexed. A successful ingestion also creates a `knowledge_ingestion` audit record.

### 6.3 Vector storage and retrieval

Selectable vector stores:

- `memory`: process-local cosine search;
- `pgvector`: persistent PostgreSQL `document_clauses` table;
- `chroma`: persistent local Chroma directory.

Selectable embeddings:

- Google/Gemini embedding API;
- sentence-transformers;
- deterministic mock vectors.

Mock vectors are explicitly marked non-semantic. When mock embeddings are active, dense retrieval is skipped and search becomes BM25-only.

Search in [`src/application/services/retrieval_service.py`](../src/application/services/retrieval_service.py):

1. Embed the query and retrieve up to `2 * top_k` dense candidates when semantic embeddings are available.
2. Retrieve up to `2 * top_k` BM25 candidates.
3. Fuse ranked lists with Reciprocal Rank Fusion, or use the configured passthrough strategy.
4. Return citation objects with rank, source, clause, effective date, content, method, matched-by legs, and fusion score.
5. Cache the result using an index-versioned key; any ingestion increments the version.

### 6.4 How RAG affects a dispatch plan

Agent 3 first searches the user's wording, then performs four fixed constraint searches for the tariff windows/rates, maximum-demand charge, and comfort envelope. [`src/agents/policy_rag/rule_extractor.py`](../src/agents/policy_rag/rule_extractor.py) extracts values sentence by sentence, validates plausible ranges and ordering, and records which clause supplied each value.

Those rates become the actual 48-slot tariff vector passed to Agent 4. Missing or rejected values fall back to reference constants and create warnings. Citations and provenance are stored with the plan and shown to the reviewer.

The LLM does not perform tariff extraction. This is a strong safety property: regulation text grounds the numbers, but deterministic code decides which numbers are accepted.

### 6.5 Provider swapping

[`src/config/settings.py`](../src/config/settings.py) and the factories under [`src/infrastructure`](../src/infrastructure) make providers configurable without changing agent code:

- LLM: mock, generic LiteLLM, OpenAI, Gemini, Anthropic, Groq, Ollama;
- embeddings: auto, sentence-transformers, Google/Gemini, mock;
- vector store: memory, pgvector, Chroma;
- database: in-memory or PostgreSQL;
- retrieval fusion: RRF or passthrough;
- cache: memory only in the current implementation;
- weather: Open-Meteo only.

Changing embedding dimension requires a matching pgvector column and complete re-index. This is currently a manual operational step, not an automated migration.

---

## 7. Planning and approval workflow

### 7.1 What is automatic

- request sanitization and security-flag detection;
- intent classification and entity extraction;
- forecast/weather/timetable retrieval;
- room-capacity capping;
- thermal simulation;
- regulation retrieval and rule extraction;
- tariff-profile construction;
- battery MILP solve;
- explanation generation/fallback;
- explanation faithfulness checking;
- warning generation;
- recommendation/audit-record creation;
- plan expiry calculation;
- analytics-event recording.

### 7.2 What requires a human

- deciding whether warnings and assumptions are acceptable;
- approving or rejecting a pending recommendation;
- supplying rejection notes;
- acknowledging warnings before approval;
- transferring the approved schedule into the real BMS/inverter controls;
- confirming that execution happened;
- handling deviations and comparing actual savings with the prediction.

The last three items have no CampusGrid workflow or data model yet.

### 7.3 Approval invariants enforced by the backend

[`src/application/services/audit_service.py`](../src/application/services/audit_service.py) enforces:

- only `dispatch_recommendation` records with pending status can be decided;
- only facility-manager routes can call the decision service;
- only one decision per recommendation;
- no decision after 24 hours;
- rejection requires a reason;
- warnings must be acknowledged before approval;
- approval/rejection creates a new row rather than mutating the recommendation.

PostgreSQL additionally uses a partial unique index for one decision per recommendation. Application locks handle same-process races, and the database constraint handles cross-process races.

### 7.4 What the solver really plans

The MILP in [`src/agents/dispatch_explanation/milp_solver.py`](../src/agents/dispatch_explanation/milp_solver.py) plans **battery charge/discharge only**. It does not optimize HVAC setpoints, room loads, flexible load tiers, EV charging, pumps, or equipment switching.

Agent 2's HVAC schedule is used to judge a requested room setpoint before the battery solve, but that HVAC power is not added to or controlled by Agent 4's objective. Therefore the phrase “battery/HVAC dispatch plan” overstates the implemented solver.

---

## 8. Audit and compliance

### 8.1 Why the page exists

The audit page provides traceability for questions, automated reasoning, recommendations, knowledge changes, and human decisions. It lets an auditor answer:

- who asked or decided;
- what question was asked;
- which agents ran and what they returned;
- which assumptions, rules, solver result, warnings, and explanation were stored;
- whether and when a manager approved/rejected;
- whether stored rows still match the hash chain.

### 8.2 Events recorded in the audit trail

| Record type | Created by | Approval needed |
|---|---|---:|
| `dispatch_recommendation` | Full orchestrator pipeline | Yes |
| `approval_decision` | Facility-manager approve/reject action | No; it is the decision |
| `policy_lookup` | Ask CampusGrid policy branch | No |
| `what_if_simulation` | Ask CampusGrid simulation branch | No |
| `forecast_review` | Ask CampusGrid forecast branch | No |
| `out_of_scope_query` | Out-of-scope branch | No |
| `knowledge_ingestion` | Manager ingest/re-index action | No |

Direct `/api/simulation/what-if` and `/api/telemetry/forecast` calls do **not** create audit rows. The same operations invoked through Ask CampusGrid do. This means “every simulation/forecast is audited” is not true across all entry points.

### 8.3 Hash-chain mechanics

Each `AuditRecord` hashes canonical row content plus the previous row's hash with SHA-256. PostgreSQL uses a trigger to reject ordinary updates/deletes. Verification reads records in order and recomputes the chain.

This is **tamper-evident**, not a cryptographic digital signature/non-repudiation system. There is no secret signing key or external anchor; a sufficiently privileged database administrator who can bypass the trigger could rewrite rows and recompute the entire chain. UI wording such as “signed” should be understood as “hash chained.”

### 8.4 Audit versus analytics

These are separate stores:

- audit rows are decision/evidence records and are hash chained;
- analytics events measure UI behavior and are not part of that chain.

Server code records query submissions, regulation searches, and approve/reject events. Browser code records recommendation shown, explanation opened, and citation clicked. Browser events are useful product analytics, not authoritative compliance evidence.

---

## 9. Implementation map

| Feature/page | Frontend | API | Backend/service | Storage/provider | Result |
|---|---|---|---|---|---|
| Login | `LoginPage.jsx`, `AuthContext.jsx` | `POST /api/auth/login`, `GET /api/auth/me` | auth route/JWT middleware | Hard-coded demo users; in-process throttle/revocation | Session, role, permissions |
| Overview | `OverviewPage.jsx` | forecast, pending, logs, verify | Agent 1, AuditService | meter/weather/audit DB | Role-specific summary |
| Ask CampusGrid | `AskPage.jsx` | `POST /api/orchestrator/query` | NLP parser, optional LLM router, orchestrator | Agents/providers + audit + analytics | Intent-specific response |
| What-if | `WhatIfPage.jsx` | `POST /api/simulation/what-if` | WeatherTool, Agent 2 | weather, meter/timetable repos | Comfort trajectory |
| Forecast | `ForecastPage.jsx` | telemetry forecast/historical | Agent 1, privacy module | meter DB/seed, weather, LLM | Forecast + noisy history |
| Approvals | `ApprovalsPage.jsx` | audit pending/logs | AuditService | audit store | Pending/all plan list |
| New plan | `NewPlanPage.jsx` | `POST /api/optimizer/dispatch` | Forced full orchestrator | all four agents + audit | Pending dispatch plan |
| Plan review | `PlanReviewPage.jsx` | audit record/approve | AuditService | audit store + analytics | Explain/review/decide/checklist |
| Regulation search | `RegulationsSearchPage.jsx` | `POST /api/rag/search` | Agent 3/RetrievalService | embeddings, vector DB, BM25, cache | Ranked citations/rules |
| Regulation library | `LibraryPage.jsx` | RAG documents/ingest | ingestion pipeline | corpus, vector DB, BM25, audit | Index list/ingestion report |
| Audit | `AuditPage.jsx` | audit logs/verify | AuditService | audit store | Evidence, chain verification, CSV |
| Analytics | `AnalyticsPage.jsx` | analytics summary/event | AnalyticsService | analytics-events repo | Funnel, A/B, intent groups, MRR |
| System status | `SystemStatusPage.jsx` | public health | Container introspection | active provider objects | Provider/agent status |
| MCP tools | No page | `POST /api/mcp` | MCPToolServer/ToolRegistry | in-process tools | JSON-RPC tool result |

---

## 10. What is real, what is fallback, and what is missing

### 10.1 Fully implemented application logic

- role-checked FastAPI routes;
- selective multi-agent orchestration;
- deterministic entity extraction and safety flags;
- a real PuLP/CBC mixed-integer battery optimizer;
- 2R2C thermal simulation and battery dynamics;
- hybrid BM25/vector retrieval with RRF;
- regulation chunking, screening, embedding, indexing, and citations;
- LLM explanation plus deterministic and LLM faithfulness checks;
- pending/approve/reject/expire workflow;
- append-only decision records and hash-chain verification;
- interaction analytics and A/B calculation;
- React pages wired to actual APIs.

### 10.2 Demo/fallback data and models

- only three seed rooms;
- a small Monday timetable;
- one 48-interval seed meter day reused for dates with no database data;
- a synthetic 90-day training dataset;
- a linear JSON forecast artifact at runtime, or a formula fallback;
- solar prediction based on historical seed solar adjusted by temperature;
- synthetic thermal calibration data and partially uncalibrated wall constants;
- only two default regulation documents;
- Open-Meteo with a deterministic offline weather curve;
- three hard-coded demo users;
- mock LLM/embedding/reference-agent fallbacks available by configuration.

### 10.3 Missing operational system pieces

- live meter/timetable/occupancy ingestion pipeline;
- equipment inventory and current equipment state;
- BMS/battery/inverter execution adapter;
- execution job/status/acknowledgement workflow;
- post-execution telemetry reconciliation and realized-savings calculation;
- production identity/user administration;
- notification/assignment workflow;
- full regulation document lifecycle and trust/provenance controls;
- production frontend deployment configuration.

---

## 11. Problems and risks found in the code

### 11.1 Critical workflow gaps

#### A. There is no execution/dispatch integration

The system stops after approval and a browser-generated checklist. There is no persistent execution job, command signing, BMS adapter, device acknowledgement, rollback, or “executed/failed/cancelled” state.

**Develop:** An explicitly separate execution subsystem only if the project is meant to control equipment. It should consume approved immutable plan IDs, require final human confirmation, use device-specific adapters, enforce rate/SOC/setpoint guardrails again, record acknowledgements, and append execution/audit events. If the assignment intends advisory-only behavior, make “manual execution is the terminal state” explicit everywhere and remove autonomous wording.

#### B. Comfort simulation and dispatch optimization are not coupled

Agent 2 calculates an HVAC schedule and comfort verdict before Agent 4, but Agent 4 optimizes only the battery and never consumes HVAC power as a decision variable. The optimized plan is not re-simulated through Agent 2.

**Develop:** A joint or staged optimization in which HVAC/flexible-load decisions and battery decisions share the same power balance, room comfort constraints, equipment limits, and post-solve validation. A plan should fail closed if the final optimized schedule violates comfort.

#### C. Fairness/load-tier fields exist but are not enforced

`OptimizationInput` contains Tier 0/1/2 load arrays and maximum grid import, but the MILP ignores them. [`tier_guardrails.py`](../src/agents/dispatch_explanation/tier_guardrails.py) explicitly says it is classification-only and is not wired to agents or the solver. The Student 3 fairness audit contains only two schema-presence tests and TODOs, including claims not exercised against the optimizer.

**Develop:** Authoritative room/equipment tier data, tier classification for all inventory values, MILP constraints for non-curtailable critical loads and equitable flexible-load treatment, outcome disparity metrics, and executable red-team tests rather than narrative fixtures.

#### D. A plan labelled for a room is based on campus-wide electric demand

Agent 1 predicts campus demand using campus occupancy. The selected room changes the timetable given to Agent 2, but does not isolate room electrical demand. The resulting battery plan is campus-level while the UI labels it with a room target.

**Develop:** Either make the product explicitly campus-level and treat room as a comfort-check context, or add sub-metered room/building forecasts and a multi-zone power model.

### 11.2 Data and model limitations

#### E. No live telemetry ingestion route or scheduled collector

Repositories can append readings, but no API, stream consumer, ETL job, or scheduler invokes that path. Most dates fall back to the same CSV seed profile.

**Develop:** Authenticated ingestion, validation, timestamp/quality rules, deduplication, missing-data handling, monitoring, and a scheduled/streaming connector to real campus meters and timetable sources.

#### F. Training and serving can choose different model types

The trainer prefers LightGBM when installed and saves a `.joblib`, while the runtime forecaster only loads the linear JSON artifact. Training can report a stronger LightGBM result that production never serves.

**Develop:** One versioned model contract/registry that both trainer and runtime support, with model version, feature schema, evaluation metrics, promotion, rollback, and drift monitoring.

#### G. Forecast and thermal validation are largely synthetic

The 90-day data is generated from a known formula; thermal calibration uses synthetic temperatures; wall constants remain default estimates. Reported accuracy on these datasets does not prove campus performance.

**Develop:** Evaluation on held-out real meter/BMS data, multi-day/season coverage, calibration per building/zone, and explicit uncertainty/quality indicators in the UI.

#### H. Solar dropout is modelled incorrectly

Agent 2's `solar_dropout` scenario scales/derates HVAC power availability. It does not reduce the solar generation series that Agent 4 uses.

**Develop:** Scenario inputs that perturb the actual solar forecast and then rerun both power optimization and comfort validation.

#### I. Demand charge is approximated

The regulation describes a monthly 15-minute maximum-demand charge, while the solver uses 30-minute intervals and prices one-thirtieth of the monthly charge as a daily objective. It also treats kW as kVA at unity power factor.

**Develop:** A documented billing-period model using 15-minute demand intervals, existing month-to-date peak, power factor/kVA where available, and a defensible inter-day allocation method.

### 11.3 RAG and regulation risks

#### J. Document trust is incomplete

Screening rejects obvious prompt injection and implausible numbers, but there is no publisher allowlist, signature verification, approval workflow, trust score, supersession status, or effective-date filtering. A manager can add a plausible but false rate that passes numeric bounds.

**Develop:** Source registry, checksum/signature or verified acquisition record, maker-checker approval for new regulations, effective/expiry dates, supersession, rollback, and retrieval ranking/filtering by authority and validity.

#### K. Embedding dimension migration is manual

`document_clauses.embedding` is fixed at `vector(768)` in SQL. Sentence-transformers defaults to 384. The factory only warns for some mismatches; it does not migrate or block all unsafe configurations.

**Develop:** Schema migrations, startup dimension validation against the live column, separate indexes per model/version, and mandatory re-index tooling.

#### L. Google embedding fallback has implementation defects

`src/infrastructure/embeddings/factory.py` calls `os.getenv` without importing `os` when no configured key short-circuits the expression. Also, `GoogleEmbeddingProvider.warm_up()` catches its own error, so the factory's surrounding `try` cannot reliably fall back as its comments claim.

**Develop:** Correct import/error propagation, explicit health check, fail-fast versus fallback policy, and tests for missing/invalid keys and network failure.

#### M. Vector-store boundary validation is incomplete

The red-team tests show the in-memory vector store accepts oversized or wrong-dimension query vectors and degrades to zero-similarity behavior instead of rejecting them.

**Develop:** Exact dimension and finite-number validation at every vector-store adapter boundary.

#### N. File ingestion is only partially exposed

The backend can parse PDF/TXT files from a server directory, but the dashboard only accepts pasted text. There is no uploaded-file quarantine/review experience.

**Develop:** Secure multipart upload, MIME/size checks, malware scanning as appropriate, extracted-text preview, quarantine approval, and immutable source-file retention/hash.

### 11.4 Correctness and code-quality defects

#### O. Agent 1 calls the forecast-summary LLM twice

[`src/agents/telemetry/agent.py`](../src/agents/telemetry/agent.py) contains the same `build_forecast_summary(...)` block twice. This doubles cost/latency and discards the first answer.

**Develop/fix:** Remove the duplicate call and add a call-count regression test.

#### P. Dead duplicated code remains in the orchestrator

[`src/agents/coordinator/agent.py`](../src/agents/coordinator/agent.py) contains an unreachable duplicate block after `_battery_limits_used()` returns.

**Develop/fix:** Delete the unreachable block and add static analysis/linting to catch dead code.

#### Q. New Dispatch Plan contains stale guidance

The page says custom battery fields are not yet used, but Agent 4 and the solver do use them.

**Develop/fix:** Replace the banner with a confirmation of the actual values used and test that the review page matches submitted values.

#### R. Ask progress is simulated, not observed

The browser advances steps every 1.1 seconds without server events. It can imply a stage is running even when the selected branch never uses it.

**Develop:** Server-sent events/WebSocket progress tied to real agent lifecycle, or a neutral indeterminate loader.

#### S. Direct forecast/simulation endpoints bypass the audit trail

The orchestrator versions are audited, but direct `/telemetry/forecast` and `/simulation/what-if` routes are not. This conflicts with broad UI/document claims that every request is recorded.

**Develop:** Decide and document the audit policy, then log all regulated actions consistently or narrow the claims.

#### T. Legacy compatibility code includes an actual stub

Most [`backend`](../backend) Python files delegate to `src`, but `backend/rag/vector_store.py::index_corpus()` is `pass`. Duplicate old contract models can also drift from the domain entities.

**Develop:** Remove unused compatibility APIs after confirming consumers, or make them thin, tested adapters with deprecation notices. Do not maintain two contract sets indefinitely.

### 11.5 Security, privacy, and compliance limitations

#### U. Audit “signatures” are unkeyed hashes

The chain detects ordinary mutation but does not prove who signed a record and can be recomputed by a sufficiently privileged attacker.

**Develop:** HMAC or asymmetric signatures with protected/rotated keys, external timestamp/anchor storage, and verification logs if non-repudiation is required.

#### V. Audit visibility is very broad

All three roles can read all audit records, including question text and, by default, complete per-agent outputs. There is no tenant/building/team scoping or field-level redaction.

**Develop:** Define data classification and least-privilege views. Separate operational, compliance, and sensitive telemetry/query details; add tenant/building scopes if the system expands.

#### W. Differential privacy has no persistent budget accounting

Historical exports add Laplace noise and cache the noisy answer per date/process, which prevents averaging within one process. The cache resets on restart, there is no per-user query budget or composition accounting, and occupancy remains exact.

**Develop:** Persistent privacy-ledger/budget rules, bounded contribution analysis, release versioning, access limits, and a documented threat model.

#### X. Authentication is demo-grade

Users are hard-coded; throttling and revocation are process-local; the default deployment uses one shared JWT secret; there is no MFA/SSO or account lifecycle.

**Develop:** University identity provider integration, persistent authorization data, short-lived tokens/refresh strategy, distributed rate limiting/revocation, MFA according to risk, and secret rotation.

#### Y. MCP transport integrity is incomplete

The route relies on bearer authentication and deployment-level HTTPS. The JSON-RPC message itself has no HMAC/signature/nonce, and tests demonstrate that an in-range command altered in transit cannot be distinguished from the original.

**Develop:** Enforced TLS, trusted proxy configuration, replay protection/message signing if MCP crosses trust boundaries, client identity, and per-tool authorization. mTLS is appropriate for service/device connections.

### 11.6 Architecture and deployment problems

#### Z. Fresh PostgreSQL bootstrap is fragile

Raw tables live in `backend/data/init.sql`, but FastAPI's `init_database()` only calls `SQLModel.metadata.create_all()` and does not execute that SQL. The container constructs RetrievalService and attempts corpus/vector bootstrap before the lifespan calls `init_database()`. Docker Compose works because PostgreSQL runs the mounted script, but a fresh external PostgreSQL/Neon database needs manual setup and can fail before startup initialization.

**Develop:** A real ordered migration system (for example Alembic) run before container construction; migrations should create extensions/tables/indexes/triggers and track schema version.

#### AA. Deployment files do not deploy the complete application

`docker-compose.yml` starts only PostgreSQL. The Dockerfile builds only the backend and installs the `postgres` extra. There is no frontend container/static build, reverse proxy, TLS, or production orchestration.

**Develop:** Reproducible backend and frontend images, migration job, health/readiness probes, secrets injection, HTTPS/reverse proxy, backups, observability, and environment-specific deployment manifests.

#### AB. Health is descriptive, not diagnostic

`/api/health` returns `online` and class names but does not probe dependencies.

**Develop:** Separate liveness and readiness endpoints; readiness should validate database/schema, vector dimension/index, embedding/LLM configuration, and required corpus availability without making an expensive provider call on every request.

#### AC. In-memory modes lose important state

Audit records, uploaded clauses, analytics, lockouts, and revoked tokens may be process-local depending on configuration. Multi-worker behavior will diverge.

**Develop:** Disallow ephemeral providers in production and validate deployment configuration at startup.

#### AD. Documentation has drifted

Some architecture text still describes `/api/optimizer/dispatch` as “just the solver,” while current code forces the whole orchestrator. Other labels still say “operator approval” although only managers approve.

**Develop:** Generate an API/role matrix from route metadata where possible and include documentation checks in review/CI.

### 11.7 Test and engineering-process gaps

- There is no frontend test dependency or test script in `frontend/package.json`.
- There is no lint/type-check script for the React code.
- Student 3's responsible-AI audit is largely narrative and incomplete.
- Several red-team findings intentionally assert vulnerable behavior, so “tests pass” does not mean “the security issue is fixed.”
- No visible CI workflow enforces backend tests, frontend build/tests, migrations, or IR/model-quality thresholds.
- Analytics, audit, and list endpoints use fixed limits rather than pagination/export jobs.
- The offline retraining script is not scheduled and has no model promotion workflow.

**Develop:** CI with backend unit/integration/security tests, frontend component/E2E/accessibility tests, lint/type checks, migration tests, dependency scanning, IR benchmarks with real semantic embeddings, and model-quality/drift gates.

---

## 12. Recommended development backlog

### Priority 1: Make the current advisory product internally correct

1. Remove the duplicate LLM call and dead orchestrator code.
2. Correct stale UI/document labels and the simulated-progress wording.
3. Make audit coverage consistent for direct forecast/simulation routes.
4. Add pagination and complete export behavior.
5. Fix embedding fallback/dimension validation and introduce database migrations.
6. Add frontend automated tests, accessibility checks, linting, and CI.

**Acceptance outcome:** The existing advisory workflow is truthful, reproducible, deployable, and consistently audited.

### Priority 2: Replace demo data with an operational data foundation

1. Build live meter, weather, timetable, occupancy, and equipment-state ingestion.
2. Add data-quality flags, freshness, lineage, missing-data handling, and monitoring.
3. Train/calibrate on real held-out campus data.
4. Unify model training, versioning, serving, evaluation, drift, and rollback.

**Acceptance outcome:** Forecast and comfort outputs clearly identify fresh real inputs and measured validation quality; fallback data cannot be mistaken for live data.

### Priority 3: Build a genuinely safe multi-resource plan

1. Model HVAC/flexible loads in the optimizer.
2. Enforce grid-import, Tier 0/1/2, comfort, equipment, and fairness constraints.
3. Rerun the final schedule through the thermal and battery twins.
4. Represent 15-minute demand and month-to-date billing state correctly.
5. Add scenario-based uncertainty/robust optimization for weather, demand, and solar.

**Acceptance outcome:** Every action in a plan is part of one coherent power/comfort model and passes deterministic post-solve validation.

### Priority 4: Harden regulation and identity governance

1. Verified-source registry and regulation lifecycle/approval.
2. Effective-date/supersession-aware retrieval.
3. Secure file upload/quarantine/review.
4. University SSO, persistent users/roles/scopes, MFA/rate limiting as required.
5. Keyed audit signing/external anchoring if non-repudiation is a requirement.

**Acceptance outcome:** A reviewer can prove which valid source and authorized identity caused each plan input and decision.

### Priority 5: Add controlled execution only if required

1. Persist an immutable execution job referencing one approved, unexpired plan.
2. Require an explicit final human confirmation and optional two-person rule.
3. Add dry-run/preflight checks and repeat all hard physical limits at the adapter boundary.
4. Use secure BMS/inverter adapters with least-privilege credentials and mTLS where appropriate.
5. Record sent/acknowledged/failed/cancelled/completed states and operator identity.
6. Reconcile actual telemetry against the schedule and calculate realized savings/comfort.
7. Provide emergency stop, rollback, and incident procedures.

**Acceptance outcome:** No LLM directly controls equipment; only an approved deterministic schedule can become a guarded, observable execution job.

---

## 13. One complete end-to-end workflow diagram

```text
OPERATOR or FACILITY MANAGER
        |
        | Ask question / request new plan
        v
React page -> API client -> JWT + backend role check -> input sanitization
        |
        v
Deterministic NLP parser
  | extracts intent, room, date, setpoint, scenario values, assumptions
  | optional LLM label-only router when confidence is low
        |
        +---------------- policy lookup ----------------> Agent 3 RAG -> citations/rules -> audit -> UI
        |
        +---------------- forecast ---------------------> Agent 1 -> forecast -> audit -> UI
        |
        +---------------- what-if ----------------------> Agent 1 -> Agent 2 -> comfort result -> audit -> UI
        |
        +---------------- full dispatch plan -----------------------------------------------+
        |                                                                                   |
        |        +-> Agent 1: meter/seed + weather + timetable -> demand/solar forecast     |
        |        |                                                                          |
        |        +-> Agent 2: room occupancy + 2R2C model -> comfort verdict                |
        |        |                                                                          |
        |        +-> Agent 3: corpus -> embeddings/vector search + BM25 + RRF                |
        |                         -> cited tariff/comfort rules                              |
        |                                                                                   |
        |        Agent 4: retrieved tariff + forecast -> BATTERY-ONLY MILP                   |
        |                         -> LLM explanation -> numeric + LLM faithfulness check     |
        |                                                                                   |
        +-----------------------------> signed/hash-chained pending recommendation ----------+
                                              |
                                              v
                         ALL ROLES MAY READ PLAN AND AUDIT EVIDENCE
                                              |
                                              v
                               FACILITY MANAGER ONLY
                         reviews sources + warnings + assumptions
                                  /                         \
                         reject + reason              approve + acknowledge
                                  \                         /
                                   v                       v
                              separate append-only approval_decision record
                                              |
                                              v
                                approved plan checklist downloaded
                                              |
                                              v
                          HUMAN TEAM MANUALLY ENTERS SCHEDULE IN EXTERNAL BMS
                                              |
                                              v
                     No CampusGrid execution acknowledgement or outcome tracking yet
                                              |
                                              v
                              ENERGY AUDITOR reads records and verifies hash chain
```
