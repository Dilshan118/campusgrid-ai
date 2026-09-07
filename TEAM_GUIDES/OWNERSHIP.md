# Code Ownership Matrix — AUTHORITATIVE

**This file is the single source of truth for who owns what.**

Earlier ownership tables exist in `docs/CAMPUSGRID_AI_MASTER_ARCHITECTURAL_BLUEPRINT_AND_SRS.md`
(§12.1) and `docs/CAMPUSGRID_AI_SIMPLIFIED_SRS_AND_SYSTEM_GUIDE.md` (View 7). They
**contradict each other and this file**. Those two documents are coursework submissions and
are kept as-submitted for the record — but where they disagree with this file, **this file wins**.
Do not take a work assignment from them.

---

## Roles

| Member | Role | Slice | Individual audit |
|---|---|---|---|
| Member 1 | **Team Lead & Architect** | Contracts, DI, API, security, orchestrator, Agent 3 RAG, ingestion, analytics, frontend, integration | Student 1 — Prompt Injection & Jailbreak |
| Member 2 | **Developer 1 — Data & ML** | Agent 1 end-to-end: meter/timetable repositories, weather API, forecaster, retraining | Student 2 — Privacy & Data Leakage |
| Member 3 | **Developer 2 — Digital Twin** | Agent 2 end-to-end: 2R2C thermal, battery SOC, simulation tool, what-if | Student 4 — Retrieval, Tool & MCP Security |
| Member 4 | **Developer 3 — Optimization & Responsible AI** | Agent 4 end-to-end: MILP, tier guardrails, XAI, faithfulness | Student 3 — Responsible AI, Bias & Faithfulness |

---

## File ownership

**OWNER** = sole editor. **support** = consumes it, may request changes, must not edit.
**request** = open an issue; the Team Lead makes the edit.

| Area | Lead | Dev 1 | Dev 2 | Dev 3 |
|---|:--:|:--:|:--:|:--:|
| `src/domain/**` — interfaces + entities | **OWNER** | support | support | support |
| `src/config/settings.py` | **OWNER** | request | request | request |
| `src/application/container.py` | **OWNER** | request | request | request |
| `src/api/**` — routes, middleware, auth | **OWNER** | support | support | support |
| `src/agents/base/**`, `coordinator/**` | **OWNER** | — | — | — |
| `src/agents/policy_rag/**`, `services/retrieval_service.py` | **OWNER** | — | *attacks only* | — |
| `src/infrastructure/{llm,embeddings,vector_store,retrieval,cache,observability}/**` | **OWNER** | — | — | — |
| `src/infrastructure/tools/__init__.py`, `registry.py` | **OWNER** | — | — | — |
| `src/pipelines/document_ingestion/**` | **OWNER** | — | — | — |
| `src/prompts/**` | **OWNER** | — | — | request |
| `frontend/**` | **OWNER** | — | — | — |
| `src/infrastructure/database/repositories/room_repository.py` | **OWNER** | — | — | — |
| `src/infrastructure/database/repositories/audit_log_repository.py` | **OWNER** | — | — | — |
| `src/agents/telemetry/**` | support | **OWNER** | — | — |
| `.../repositories/timetable_repository.py` | support | **OWNER** | — | — |
| `.../repositories/meter_history_repository.py` | support | **OWNER** | — | — |
| `src/infrastructure/tools/weather_tool.py` | support | **OWNER** | — | — |
| `src/pipelines/periodic_retraining/**` | support | **OWNER** | — | — |
| `src/agents/digital_twin/**` | support | — | **OWNER** | — |
| `src/infrastructure/tools/simulation_tool.py` | support | — | **OWNER** | — |
| `src/agents/dispatch_explanation/**` | support | — | — | **OWNER** |
| `src/infrastructure/reference_baselines/**` | **OWNER** · frozen | read | read | read |
| `tests/conftest.py`, `tests/integration/**` | **OWNER** | support | support | support |
| `tests/unit/test_member2_*` | — | **OWNER** | — | — |
| `tests/unit/test_member3_*` | — | — | **OWNER** | — |
| `tests/unit/test_member4_*` | — | — | — | **OWNER** |
| `red_team/test_student1_*` (prompt injection) | **OWNER** | — | — | — |
| `red_team/test_student2_*` (privacy) | — | **OWNER** | — | — |
| `red_team/test_student4_*` (retrieval & tools) | — | — | **OWNER** | — |
| `red_team/test_student3_*` (responsible AI) | — | — | — | **OWNER** |
| `docs/**`, `README.md`, `.env.example`, `pyproject.toml` | **OWNER** | — | — | — |

---

## The five collision points, and how they are split

1. **`src/infrastructure/tools/`** — Dev 1 owns `weather_tool.py`, Dev 2 owns
   `simulation_tool.py`. The Lead owns `__init__.py` and `registry.py`; neither
   developer edits those two.

2. **Repositories** — split one file per entity. Dev 1 owns timetable and meter history;
   the Lead owns room and audit log. Nobody shares a repository module any more.

3. **`src/agents/dispatch_explanation/`** — Dev 3 owns the **whole folder**, including
   `xai_explainer.py`, because their audit is about XAI faithfulness. The Lead owns
   `src/prompts/**`; Dev 3 requests template changes rather than editing them.

4. **RAG security testing** — Dev 2's audit covers RAG index poisoning and vector-store
   DoS, but that code belongs to the Lead. Dev 2 may **attack** it and **report** findings;
   **fixes land in the Lead's pull requests**. Attacker and defender being different people
   is normal in red-teaming.

5. **`container.py` and `settings.py`** — everyone eventually needs a line in these.
   **Request-only.** Open an issue titled `WIRE: <class> into container` and the Lead makes
   the edit. This single rule prevents most merge conflicts on this codebase.

---

## Rules that apply to everybody

- **Never commit a file you do not own.** Check this table if unsure.
- **Rebase on `main` every morning** (`git pull --rebase origin main`). Daily rebases give
  one-line conflicts; weekly ones cost afternoons.
- **No `src/infrastructure` import inside `src/agents`, `src/application` or `src/domain`.**
  Agents depend on interfaces; only the container and factories know concrete vendors.
  A pull request that violates this is rejected.
- **Output shapes are contracts.** Changing what your agent returns breaks whoever consumes
  it — that needs Lead sign-off and an announcement to everyone.
- **Blocked? You still are not waiting.** Set `USE_REFERENCE_BASELINES=true` and the whole
  pipeline runs with working stand-ins for the other slices.

---

## Branches

```
main                    ← protected, always green, only the Lead merges
 └── v0-baseline         ← tag everyone branches from
      ├── feat/dev1-telemetry-forecasting
      ├── feat/dev2-digital-twin-physics
      ├── feat/dev3-milp-optimization
      └── feat/lead-<topic>
```

## Daily report — five lines, async is fine

```
What I finished:
What I'm doing today:
What is blocked:
What files I changed:
What I need from someone else:
```

If "what files I changed" ever lists a file you do not own, flag it that day.
