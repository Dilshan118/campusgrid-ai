
# Team Lead Playbook (Member 1 - Project Leader)

**Project:** CampusGrid AI (Smart Campus Microgrid Energy Management System)
**Course:** IT 3041 – Information Retrieval and Web Analytics (IRWA)
**Your Role:** Team Lead & Chief Architect (Member 1)

---

## 1. Executive Summary & Architecture Status

As Team Lead, you have established a **100% production-ready Clean Architecture foundation**:

- **Domain Layer (`src/domain/`)**: Pure business entities, abstract interfaces, and domain exceptions.
- **Infrastructure Layer (`src/infrastructure/`)**: Swappable adapters for LLMs (LiteLLM/Gemini/OpenAI), Embeddings, Vector Stores (Chroma/PgVector/Memory), Relational DB (Postgres/In-Memory), Caching, and Observability tracing.
- **Central DI Container (`src/application/container.py`)**: Assembles all components with zero vendor lock-in.
- **REST API Gateway (`src/api/`)**: 8 FastAPI domain routers (`health`, `orchestrator`, `telemetry`, `simulation`, `optimizer`, `rag`, `analytics`, `audit`).
- **Your Agent Domain (Agent 3 - Policy RAG)**: Fully implemented hybrid dense + BM25 + Reciprocal Rank Fusion search engine with Sri Lankan utility tariff rule extraction.
- **Your Red Team Audit (Student 1)**: Prompt Injection, Jailbreak analysis, and delimiter collision testing.

Your 3 teammates now have **completely isolated, conflict-free sandboxes** to build their domains.

---

## 2. Team Responsibility Matrix

```
+──────────────┬────────────────────────────┬─────────────────────────────┬───────────────────────────+
| Member       | Core System Domain         | Assigned Code Sandbox       | 80-Mark Security Audit    |
+──────────────┼────────────────────────────┼─────────────────────────────┼───────────────────────────+
| Member 1     | Team Lead, API, Hybrid RAG,| src/api/, src/application/, | Student 1: Prompt         |
| (You)        | Orchestrator, Frontend UI  | src/agents/policy_rag/      | Injection & Jailbreaking  |
+──────────────┼────────────────────────────┼─────────────────────────────┼───────────────────────────+
| Member 2     | Telemetry, Load/Solar      | src/agents/telemetry/       | Student 2: Privacy, NILM  |
|              | Forecasting, ML Retraining | src/pipelines/retraining/   | & Data Leakage            |
+──────────────┼────────────────────────────┼─────────────────────────────┼───────────────────────────+
| Member 3     | Digital Twin, 2R2C Thermal | src/agents/digital_twin/    | Student 4: Retrieval, MCP |
|              | Physics, Battery Dynamics  | src/infrastructure/tools/   | & Physical Bounds Abuse   |
+──────────────┼────────────────────────────┼─────────────────────────────┼───────────────────────────+
| Member 4     | MILP Optimization Solver,  | src/agents/dispatch_        | Student 3: Responsible    |
|              | Peak Shaving, XAI          |   explanation/milp_solver.py| AI, Bias & Hallucination  |
+──────────────┼────────────────────────────┼─────────────────────────────┼───────────────────────────+
```

---

## 3. The Zero-Conflict Git Workflow

To ensure zero git merge conflicts between teammates:

### Rule 1: Dedicated Branches

Each teammate must create and work exclusively on their own branch:

- Member 2: `git checkout -b feature/member2-telemetry-forecasting`
- Member 3: `git checkout -b feature/member3-digital-twin-physics`
- Member 4: `git checkout -b feature/member4-milp-optimization`

### Rule 2: Strict File Ownership

No member is allowed to touch another member's files:

- **Member 2** only touches `src/agents/telemetry/` and `tests/unit/test_member2_telemetry.py`.
- **Member 3** only touches `src/agents/digital_twin/` and `tests/unit/test_member3_digital_twin.py`.
- **Member 4** only touches `src/agents/dispatch_explanation/milp_solver.py` and `tests/unit/test_member4_milp_solver.py`.
- **You (Member 1)** manage `src/api/`, `src/application/container.py`, and `frontend/`.

### Rule 3: Pull Request Verification Checklist

Before approving any teammate's Pull Request into `main`:

1. Run their personal unit test:
   ```bash
   pytest tests/unit/test_memberX_....py -v
   ```
2. Run their security audit test:
   ```bash
   pytest tests/red_team_security_audits/test_studentX_....py -v
   ```
3. Run the full test suite to make sure nothing broke:
   ```bash
   pytest tests/ -v
   ```

---

## 4. How to Guide Your Teammates

Send each teammate their respective guide in `TEAM_GUIDES/`:

1. Send `TEAM_GUIDES/MEMBER_2_TELEMETRY_AND_PRIVACY_GUIDE.md` to **Member 2**.
2. Send `TEAM_GUIDES/MEMBER_3_DIGITAL_TWIN_AND_PHYSICS_GUIDE.md` to **Member 3**.
3. Send `TEAM_GUIDES/MEMBER_4_OPTIMIZATION_AND_RESPONSIBLE_AI_GUIDE.md` to **Member 4**.

Each guide contains:

- A non-technical, plain-English explanation of their real-world goal.
- Exactly which 2-3 files belong to them.
- A **ready-to-use copy-paste prompt for Claude Code** so they can generate their code immediately without feeling lost.
- The exact terminal command they run to verify their code turns green.
