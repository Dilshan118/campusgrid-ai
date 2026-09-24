# CampusGrid AI — Complete System & Team Guide

**Read this first. It is the only document you need to start work.**

Everything about what we are building, how the system works, what technology goes where, what is
built, what is missing, who does what, and the order we build it in.

Written in plain English. Verified against the actual code on **7 September 2026**.

| I want to know… | Go to |
|---|---|
| What are we building and why | [Section 1](#1-what-the-system-does) |
| How do the four agents work | [Section 2](#2-the-four-agents) |
| How do they talk to each other | [Section 3](#3-how-the-agents-talk-to-each-other) |
| What happens when someone asks a question | [Section 4](#4-how-data-flows-from-start-to-finish) |
| What technology are we using, and why | [Sections 5–7](#5-the-technology-map) |
| What is already built | [Section 8](#8-what-is-built-and-what-is-missing) |
| What is broken and needs fixing | [Section 9](#9-problems-to-fix-before-continuing) |
| What am **I** responsible for | [Sections 10–13](#10-team-lead--member-1) |
| How do I set up and work day to day | [Section 15](#15-how-we-work-day-to-day) |
| What order do we build things in | [Section 14](#14-the-finished-system-and-the-order-we-build-it) |

> **The other two documents.** [`../TEAM_GUIDES/OWNERSHIP.md`](../TEAM_GUIDES/OWNERSHIP.md) is the
> file-by-file "may I edit this?" table — check it before you commit. Your own
> `TEAM_GUIDES/MEMBER_*.md` file has your detailed instructions and copy-paste prompts.

---

## Contents

**Part A — The system**
1. [What the system does](#1-what-the-system-does)
2. [The four agents and what each is responsible for](#2-the-four-agents)
3. [How the agents talk to each other](#3-how-the-agents-talk-to-each-other)
4. [How data flows from start to finish](#4-how-data-flows-from-start-to-finish)

**Part B — The technology**
5. [The technology map](#5-the-technology-map)
6. [Where each technology fits and why](#6-where-each-technology-fits-and-why)
7. [How the pieces plug together in our code](#7-how-the-pieces-plug-together-in-our-code)

**Part C — Reality check**
8. [What is built and what is missing](#8-what-is-built-and-what-is-missing)
9. [Problems to fix before continuing](#9-problems-to-fix-before-continuing)

**Part D — The team**
10. [Team Lead](#10-team-lead--member-1)
11. [Developer 1 — Data & Forecasting](#11-developer-1--data--forecasting)
12. [Developer 2 — Physics & Simulation](#12-developer-2--physics--simulation)
13. [Developer 3 — Optimisation & Responsible AI](#13-developer-3--optimisation--responsible-ai)
14. [The finished system, and the order we build it](#14-the-finished-system-and-the-order-we-build-it)

**Part E — Working together**
15. [How we work day to day](#15-how-we-work-day-to-day)

---
---

# PART A — THE SYSTEM

## 1. What the system does

### The problem

A Sri Lankan university pays its electricity bill in two parts:

1. **The units it uses** — normal metered consumption.
2. **A penalty based on the single highest 15-minute spike in the whole month.**

That second part is the killer. If every lecture hall switches on its air conditioning at 2pm on
a hot Tuesday, the campus draws a huge amount of power for fifteen minutes. That one spike can
set **30% to 50% of the entire monthly bill**, even though the campus was quiet the rest of the
time.

Universities already own the equipment to prevent this — solar panels and a large battery — but
those run on simple timers. The battery often sits empty exactly when it is needed most.

### What we built

**CampusGrid AI is an advisor, not an autopilot.**

A facility manager types a question in ordinary English. The system predicts tomorrow's
electricity, checks what the buildings can physically tolerate, looks up the real electricity
regulations, then calculates the cheapest safe plan for the battery and the air conditioning —
and explains its reasoning in plain English, citing the actual regulation clauses.

### Three deliberate limits

| The system does NOT | Why |
|---|---|
| Touch the national grid | It works only behind the university's own meter |
| Flip any switch by itself | A human reviews and approves every recommendation |
| Let the language model pick any physical setting | A language model cannot *guarantee* the battery stays above 20% — a solver can |

> **That third limit is the most important design decision in the whole project.** The solver
> decides the numbers; the language model explains them. Expect to be asked about it in the viva.

---

## 2. The four agents

An **agent** is a worker with one clear job that hands its answer to the next worker. Nobody's
job overlaps — that is what lets four people build this at the same time.

### Agent 1 — Telemetry and Forecasting
**Owner: Developer 1** · `src/agents/telemetry/`

**Responsible for:** predicting the future. Nothing else.

It reads past meter readings, tomorrow's weather, and the class timetable, then produces 48
half-hourly numbers for electricity demand and 48 for solar generation, each with a confidence
range, plus a list of intervals that look abnormally high.

**Hard boundary:** it predicts only. It never chooses an action or a schedule.

### Agent 2 — Digital Twin Simulation
**Owner: Developer 2** · `src/agents/digital_twin/`

**Responsible for:** checking whether a plan is physically safe.

It runs a simplified physics model of a building — how heat leaks through walls, how much heat
students give off, how much the air conditioning removes — and works out the indoor temperature
at every interval. It also tracks the battery's charge level and flags any moment it would leave
the safe 20%–90% band.

It answers *"would this plan cook the students or damage the battery?"*

**Hard boundary:** it simulates only. It never picks the final schedule.

### Agent 3 — Policy and Information Retrieval
**Owner: Team Lead** · `src/agents/policy_rag/`

**Responsible for:** finding out what the rules actually say.

It searches the electricity tariff documents and the thermal comfort standards, and returns the
exact rates — peak LKR 58/kWh, the LKR 1,100/kVA demand penalty, the 21.0–25.5°C comfort band —
together with the specific clause each figure came from.

This is the **Information Retrieval** module the assignment requires, and it is currently the
strongest part of the system.

**Hard boundary:** it reports rules only. It never decides schedules.

### Agent 4 — Dispatch and Explanation
**Owner: Developer 3** · `src/agents/dispatch_explanation/`

**Responsible for:** making the decision, then justifying it honestly.

It combines the forecast (Agent 1), the safety verdict (Agent 2) and the regulations (Agent 3),
then solves a mathematical optimisation problem across 48 intervals to find the cheapest battery
schedule that breaks no rules. Then a language model writes the plain-English justification, and
**a second language model call checks every number in that justification against what the solver
actually produced.**

**Hard boundary:** it recommends. A human approves before anything is actuated.

### The Orchestrator
**Owner: Team Lead** · `src/agents/coordinator/`

Not an agent so much as the manager. It reads the question, pulls out the details (which room,
what date, what temperature), decides which agents need to run, runs them in order, and assembles
the final answer. It also writes everything to the audit log.

### Why we split it into four agents

You could write this as one big program. We did not, for three reasons:

1. **Four people can work at once.** Each agent is a separate folder with a separate owner.
2. **You can test each piece on its own.** If the forecast is wrong, you know exactly where.
3. **The assignment requires it** — at least two interacting intelligent agents. We have four.

---

## 3. How the agents talk to each other

Three different communication mechanisms, each for a different purpose. The assignment
specifically asks about this, so it is worth understanding clearly.

### Inside the system — typed hand-offs

Every agent inherits from a shared base class (`src/agents/base/agent.py`). Calling
`agent.execute(input)` always returns the same shape:

```
AgentExecutionResult
├── agent_name          which agent produced this
├── success             did it work
├── data                the actual answer
├── error               what went wrong, if anything
├── execution_time_ms   how long it took
└── citations           any sources it used
```

That uniform shape is why the Orchestrator can chain agents together without special-casing each
one, and why timing, logging and error handling are written once instead of four times.

### From outside — REST over HTTP

Every agent also has its own web address, so it can be called independently:

| Endpoint | Which agent | What it does |
|---|---|---|
| `POST /api/orchestrator/query` | all four | the full pipeline |
| `GET /api/telemetry/forecast` | Agent 1 | just the forecast |
| `POST /api/simulation/what-if` | Agent 2 | just a physics scenario |
| `POST /api/rag/search` | Agent 3 | just a regulation lookup |
| `POST /api/optimizer/dispatch` | Agent 4 | just the solver |
| `GET /api/audit/logs` | — | the decision history |
| `POST /api/analytics/event` | — | usage tracking |
| `GET /api/health` | — | which providers are active |

### To external tools — MCP *(planned, Developer 2)*

**MCP (Model Context Protocol)** is a standard way for an AI system to call an external tool with
a defined schema. The physics simulator will be exposed this way, so the tool boundary is real
rather than just a Python function call. This is what lets us claim the protocol requirement
honestly.

---

## 4. How data flows from start to finish

A real request: *"Cut tomorrow's peak demand penalty and pre-cool Lecture Hall 1 to 23.5°C."*

```
  MANAGER types the question into the dashboard
        |
        v
  API receives it  ──  POST /api/orchestrator/query
        |             (checks who you are — planned)
        v
  ORCHESTRATOR extracts the details
        room = LH-1 · target = 23.5C · date = tomorrow · goal = save money
        |
        v
  ┌─ AGENT 1 ─ "What will tomorrow look like?" ─────────────────────┐
  │  reads:  past meter readings (database)                          │
  │          tomorrow's weather (external service)                   │
  │          who is timetabled where (database)                      │
  │  gives:  48 demand numbers · 48 solar numbers · confidence range │
  └──────────────────────────────┬───────────────────────────────────┘
                                 │ temperatures + student counts
                                 v
  ┌─ AGENT 2 ─ "Would that be safe?" ───────────────────────────────┐
  │  runs:   building heat physics · battery charge physics          │
  │  gives:  48 indoor temperatures · safe or not · any violations   │
  └──────────────────────────────┬───────────────────────────────────┘
                                 │ feasibility verdict
                                 v
  ┌─ AGENT 3 ─ "What do the rules say?" ────────────────────────────┐
  │  turns the question into numbers a computer can compare          │
  │  searches BOTH by meaning AND by exact keyword                   │
  │  merges the two result lists into one ranking                    │
  │  gives:  tariff rates + the exact clauses they came from          │
  └──────────────────────────────┬───────────────────────────────────┘
                                 │ rates + citations
                                 v
  ┌─ AGENT 4 ─ "So what should we do?" ─────────────────────────────┐
  │  SOLVER  works out the cheapest safe battery schedule            │
  │  LLM     writes the plain-English justification                  │
  │  LLM     fact-checks that justification against the solver log   │
  │  gives:  the schedule · money saved · reasoning · honesty score  │
  └──────────────────────────────┬───────────────────────────────────┘
                                 v
  AUDIT LOG — who asked, what each agent said, what was decided
              (append-only, so it can never be quietly rewritten)
                                 |
                                 v
  MANAGER sees the plan, the savings, the reasoning, the citations
          and an APPROVE button. Nothing happens until they press it.
```

### The offline pipelines

Two background jobs that run on a schedule, not during a request:

```
  DOCUMENT INGESTION  (Team Lead — not built yet)
  tariff PDFs → strip page furniture → split into clauses
              → turn each clause into numbers → store in the database

  MODEL RETRAINING  (Developer 1 — not built yet)
  months of past readings → build features → train the forecasting model
                          → save it → Agent 1 picks it up
```

---
---

# PART B — THE TECHNOLOGY

## 5. The technology map

| Layer | What we use | Status |
|---|---|---|
| Dashboard | React 18, Vite, Tailwind, Recharts | shell only |
| Web server | FastAPI + Uvicorn | working |
| Login & permissions | JWT tokens, 3 roles, per-route checks | working |
| Understanding questions | rule-based entities + LLM intent router for unclear queries; spaCy NER planned | working |
| Language model | LiteLLM → Gemini / OpenAI / Claude / Groq / Ollama | working |
| Turning text into numbers | sentence-transformers (`all-MiniLM-L6-v2`) | working (on in `.env.example`) |
| Meaning-based search | pgvector inside PostgreSQL | built, untested live |
| Keyword search | Okapi BM25, written by hand | working |
| Combining search results | Reciprocal Rank Fusion | working |
| Normal database | Neon PostgreSQL 16 | wired (all repositories) |
| Maths solver | PuLP with the CBC engine | reference version only |
| Building physics | 2R2C thermal model | reference version only |
| Forecasting model | LightGBM or scikit-learn | **missing** |
| Tool protocol | MCP | **missing** |
| Testing | pytest — 142 tests | working |

---

## 6. Where each technology fits and why

This is the section to read carefully. It answers "why is this here and what does it actually do."

### The language model (LLM)

**What it is:** a model that understands and writes human language.

**Where we use it — exactly two places today,** both in Agent 4:
- `xai_explainer.py` — writes the plain-English justification
- `faithfulness.py` — checks that justification for invented numbers

**Where we should also use it (planned):**
- The Orchestrator, to work out what the manager actually wants and which agents to run
- Agent 1, to write a short "why is tomorrow unusual" summary
- Agent 3, to rewrite a vague question into better search terms

**Why we do not fine-tune it.** Fine-tuning means retraining the model on your own data. We have
almost no data, the task is explanation rather than specialist knowledge, and fine-tuning would
lock us to one vendor. We use an off-the-shelf model through a swappable adapter instead.

**How it stays swappable:** every agent talks to an interface called `LLMProvider`. Changing
from Gemini to OpenAI is one line in a `.env` file. There is also a fake provider that returns
fixed answers, so tests run in under two seconds with no API cost.

### Embeddings

**What they are:** a way of turning a sentence into a long list of numbers, arranged so that
sentences with similar *meaning* end up with similar numbers. That is what makes it possible to
search by meaning rather than by exact words.

**What we embed:** regulation text only — tariff clauses and comfort standards.

**What we deliberately never embed:** meter readings, student data, timetables. Electricity
consumption data never reaches the language model at all. That is a genuine privacy property and
worth stating out loud in the report.

> ### ⚠️ The most impactful single line in the whole project
>
> `EMBEDDING_PROVIDER` currently defaults to `mock`. The mock generates numbers from a hash of
> the text — fast and repeatable, which is what automated tests want, but **carrying no meaning
> at all.** Right now, meaning-based search returns effectively random results and only the
> keyword search is doing real work.
>
> Switch it to `sentence_transformers` before any demo, evaluation or screenshot.

### Vector database

**What it is:** a database that can answer "find me the stored items whose numbers are closest to
these numbers" — which is how meaning-based search works.

**What we use:** `pgvector`, an extension that runs *inside* PostgreSQL. That is a good choice
because normal tables and search vectors live in the same database — one connection, one backup,
no synchronisation problems.

Two alternatives are already built and switchable: ChromaDB, and a simple in-memory store used
for testing.

**One thing to know:** the number of values per embedding (384) is fixed in the database schema.
Switching to a bigger model means changing that column and re-indexing everything. It is not
free.

### The normal database

**What it is:** ordinary tables — rooms, timetables, meter history, the audit log.

**What we use:** Neon PostgreSQL 16 — cloud-hosted, so all four of us connect to the same
database with no local install.

**Current state:** rooms and the audit log read from PostgreSQL. Meter history and timetables
**silently fall back to a spreadsheet file** even when configured for PostgreSQL, because those
two adapters have not been written yet. That is Developer 1's job.

### RAG (Retrieval-Augmented Generation)

**What it means in plain English:** instead of hoping the language model happens to know the Sri
Lankan electricity tariff, we look the tariff up in real documents first, and hand those exact
passages to the model along with the question. The model then answers using material we
retrieved, not from memory. That is what stops it inventing rates.

**Our version is "hybrid", which means we search two ways at once:**

```
  Question: "what is the peak rate?"
        |
        ├─── BY MEANING ────  turn the question into numbers,
        │                     find clauses with similar numbers
        │                     → good at "expensive evening electricity"
        │
        └─── BY KEYWORD ────  Okapi BM25 exact word matching
                              → good at "GP-2", "LKR 58.00", "Clause 4.2"
                  |
                  v
        Both lists merged by Reciprocal Rank Fusion:
        anything ranked highly by either method rises to the top
                  |
                  v
        Top 2 clauses handed to Agent 4, with citations
```

We search both ways because each fails where the other succeeds. Meaning-based search is poor at
exact codes like `GP-2 Section 4.2`; keyword search is poor at "ways to keep students cool".

**Honest current state:** the machinery is real and working, but the searchable corpus is **four
clauses typed directly into a Python file.** There is no ingestion pipeline yet. Until real tariff
PDFs are loaded, this is a demonstration rather than a working knowledge base.

### Machine learning models

Worth being clear about, because the amount of ML here is smaller than people assume.

| Model | What it does | Should we train it? |
|---|---|---|
| Demand forecaster | predicts tomorrow's electricity | **Yes** — real data, small, explainable |
| 2R2C constants | how fast a building heats up | **Yes** — fit from measurements instead of guessing |
| Anomaly detector | flags unusual consumption | Optional, cheap |
| Language model | understanding and explaining | **No** — use off the shelf |
| Embedding model | text into numbers | **No** — use off the shelf |
| Entity extraction | pull room names and dates out | **No** — use spaCy plus simple rules |

**Perspective:** the total mathematical core of this system is under 200 lines — a forecast
formula, a temperature formula, a battery formula and one solver call. The language and search
side is roughly twice that. **This is an LLM and information-retrieval project that contains some
maths, not a machine-learning project.**

### The maths solver

**What it is:** you describe your goal ("spend the least money") and your rules ("battery between
20% and 90%", "never exceed 100 kW"), and the solver finds the mathematically best answer.

**Why not just ask the language model?** Because the solver *proves* its answer obeys every rule.
A language model produces something plausible. When the answer controls real equipment, plausible
is not good enough.

---

## 7. How the pieces plug together in our code

### The core idea — plug sockets

Every external technology sits behind an **interface**. Think of it as a plug socket: the agents
plug in and never know or care which appliance is on the other end.

```
   AGENTS  ──plug into──►  INTERFACES  ◄──filled by──  REAL TECHNOLOGY
   (business logic)         (contracts)                 (vendors)

   Agent 4 needs to             LLMProvider              LiteLLM → Gemini
   write an explanation                                  or the fake one for tests

   Agent 3 needs to             VectorStore              pgvector
   search by meaning                                     or Chroma, or in-memory

   Agent 1 needs                MeterHistoryRepository   PostgreSQL
   past readings                                         or the spreadsheet file
```

**Why it matters:** switching database, language model or search engine is one line in `.env`.
Nothing in the business logic changes.

**The rule this creates, and it is not negotiable:** if a file inside `src/agents/`,
`src/application/` or `src/domain/` imports a vendor library directly — `import openai`,
`import chromadb` — that is a bug and the pull request gets rejected. Only the container and the
factories are allowed to know vendor names.

### Where everything is decided — one file

`src/application/container.py` reads the settings and builds the whole system: picks the language
model, picks the database, builds the four agents, wires them into the Orchestrator.

**This is the only place the real technologies are chosen.** It is also the file most likely to
cause merge conflicts, which is why **only the Team Lead edits it.** Everyone else opens an issue
titled `WIRE: <my class> into container`.

### The switches, and which actually work

| Setting in `.env` | Options | Wired up? |
|---|---|---|
| `LLM_PROVIDER` | mock · gemini · openai · anthropic · groq · ollama | ✅ yes |
| `EMBEDDING_PROVIDER` | mock · sentence_transformers | ✅ yes (`.env.example` uses real embeddings; mock disables the dense leg) |
| `VECTOR_STORE_PROVIDER` | memory · pgvector · chroma | ✅ yes |
| `DATABASE_PROVIDER` | in_memory · postgres | ✅ yes — all five repositories, incl. analytics |
| `CACHE_PROVIDER` | memory · redis | 🔶 memory only, and nothing uses the cache |
| `RERANKER_STRATEGY` | rrf · passthrough | ✅ yes — `cross_encoder` stops startup with a clear error |
| `WEATHER_PROVIDER` | open-meteo | ✅ validated — anything else stops startup |
| `USE_REFERENCE_BASELINES` | true · false | ✅ yes — this is the "nobody is blocked" switch |
| `REFERENCE_BASELINE_AGENTS` | any of agent1, agent2, agent4 | ✅ yes — baseline only the unfinished slices |

### The stand-in system — why nobody waits

`src/infrastructure/reference_baselines/` contains working versions of everything the three
developers are building. Set `USE_REFERENCE_BASELINES=true` and the whole system runs end to end
today.

That is the mechanism that makes genuine parallel work possible: Developer 3 can build and test
the solver against a real forecast before Developer 1 has written one.

**Read them for reference. Never edit them. Do not copy them word for word** — you have to defend
your own code in the viva.

---
---

# PART C — REALITY CHECK

## 8. What is built and what is missing

### Built and working — do not rebuild

- The full architecture: interfaces, dependency injection, clean layering
- 20 interfaces covering every external technology
- 8 API endpoints with request tracing and error handling
- **Hybrid search** — meaning + keyword + rank fusion (Agent 3's core)
- The plain-English explainer and the automated fact-checker
- Swappable language model across 5 vendors plus an offline fake
- Append-only audit log
- Working stand-ins for all three developers' work
- 142 tests: **136 pass, 5 skip, 1 intentional fail.** The skips are Agent 2's unwritten physics; the
  failure is TC-S2-01, a guard Member 2 wrote to fail once the Lead fixed their finding (see
  `docs/TEAM_LEAD_REVIEW_AND_INTEGRATION_REPORT.md`).

### Missing

| What | Owner | Why it matters |
|---|---|---|
| Demand forecaster | Developer 1 | Agent 1 does nothing without it |
| Real weather data | Developer 1 | Returns identical numbers every day |
| PostgreSQL meter + timetable adapters | Developer 1 | Agent 1 never reads the real database |
| Trained forecasting model + real dataset | Developer 1 | No result to report or defend |
| Room temperature physics | Developer 2 | Agent 2 does nothing without it |
| Battery charge physics | Developer 2 | Safety limits unverified |
| Fitted physics constants | Developer 2 | Currently guessed |
| MCP tool exposure | Developer 2 | Required protocol, currently just a function |
| The solver | Developer 3 | Agent 4 does nothing without it |
| Integer variables in the solver | Developer 3 | Without them it is not truly a MILP |
| Fairness tier rules | Developer 3 | Required Responsible AI element |
| ~~Login and permissions~~ | Team Lead | **Done** — JWT, 3 roles, lockout, logout |
| ~~Document ingestion~~ | Team Lead | **Done** — Markdown/TXT/PDF, screening, de-duplication |
| Entity extraction + smart routing | Team Lead | **Done** except spaCy (rule entities + LLM router) |
| ~~Real analytics~~ | Team Lead | **Done** — funnel, A/B z-test, intent clusters, MRR |
| Dashboard screens | Team Lead | Spec written: `docs/SYSTEM_USER_FLOW_AND_UIUX_SPEC.md` |
| ~~Search quality measurement~~ | Team Lead | **Done** — 30-query benchmark, in the test suite |

---

## 9. Problems to fix before continuing

Found by reading the code. Ordered by how much they matter.

> **Status on 24 September 2026:** #3, #4 and #5 are fixed (Team Lead). #1, #6, #7 and #9 are still
> open and belong to their owners. #2 is done for Students 1 and 2. The current, complete list of open
> items per member and the cross-member integration issues is in
> [`TEAM_LEAD_REVIEW_AND_INTEGRATION_REPORT.md`](TEAM_LEAD_REVIEW_AND_INTEGRATION_REPORT.md).

### Serious

**1. The fact-checker fails in the wrong direction.**
`src/agents/dispatch_explanation/faithfulness.py` — when it cannot read the model's reply, it
returns "verified, 95% confident." A check that failed reports success. *Developer 3 fixes this;
it should fail closed.*

**2. The security tests do not test anything.**
The examples in `tests/red_team_security_audits/` build a paragraph containing a made-up "what
happened", then check the paragraph has the right headings. **No attack is ever run.** Each of
these reports is worth 80 marks. *Everyone rewrites their own to run real attacks, in week 4.*

**3. Agent 3's work never reaches Agent 4.**
Two separate faults. The rule extractor ignores the text it is given and returns fixed constants.
And the Orchestrator passes Agent 4 the tariff numbers from the meter history rather than the
ones Agent 3 retrieved. **So the search results are currently decorative** — in an information
retrieval course. *Team Lead fixes.*

**4. Meaning-based search is switched off.**
`EMBEDDING_PROVIDER=mock` means dense search compares hashes. *One line. Team Lead.*

### Worth fixing

**5. Two settings do nothing.** `RERANKER_STRATEGY` and `WEATHER_PROVIDER` are read but never
used. Either wire them or remove them — configuration that lies is worse than none.

**6. The safety limits are defined in three places.** The comfort band 21.0–25.5°C appears in
`shared/constants.py`, in the settings, and typed directly into two files. Three sources of truth
for a safety guardrail will eventually disagree. *Developer 2 consolidates.*

**7. The physics exists in three copies.** Fix one and the others silently disagree.
*Developer 2 collapses to one.*

**8. Dead code.** `src/application/use_cases/` is imported by nothing. `PolicySearchEngineInterface`
is implemented by nothing. `MultiAgentState` is never used. The tool registry is built and never
consulted. The cache is created and caches nothing. Harmless, but it misleads a reader.

**9. The solver has no integer variables.** It is currently a linear program, not a
mixed-integer one. "Where are your integer variables?" is an obvious viva question.
*Developer 3 — about five lines.*

---
---

# PART D — THE TEAM

Four people, four separate areas, no overlap. File-by-file detail is in
[`../TEAM_GUIDES/OWNERSHIP.md`](../TEAM_GUIDES/OWNERSHIP.md).

## What each person hands to the others

This is the only part where you depend on each other, so agree it once and do not change it
without telling the Team Lead.

```
  TEAM LEAD gives everyone ......... the interfaces (the "shape" your code must fit)
                                     and wires your work into the system

  DEVELOPER 1 gives ................ 48 demand numbers, 48 solar numbers   -> Developer 3
                                     48 temperatures, 48 student counts    -> Developer 2
                                     48 tariff prices                      -> Developer 3

  DEVELOPER 2 gives ................ 48 indoor temperatures                -> Team Lead
                                     "is this safe: yes/no"                -> Developer 3
                                     battery charge levels                 -> Developer 3

  TEAM LEAD (Agent 3) gives ........ tariff rates + citations              -> Developer 3

  DEVELOPER 3 gives ................ the schedule, the savings, the plan   -> Team Lead
                                     the honesty check result              -> Team Lead
```

---

## 10. Team Lead — Member 1

### Responsible for
The shared foundations everyone else depends on, plus everything nobody else owns: the
interfaces, the dependency container, the settings, the API, security, Agent 3, the offline
ingestion, the analytics, the dashboard — and gluing it all together.

You also own the two files most likely to cause conflict (`container.py`, `settings.py`), which
is why they are request-only for everybody else.

### Must implement
1. **Login and permissions** — JWT tokens, role checks, input sanitisation. *(required by the brief)*
2. **Document ingestion** — real tariff PDFs → split into clauses → embedded → stored. This turns
   the RAG from a demo into a real system.
3. **Turn on real embeddings** — one line, then verify search quality actually changes.
4. **Entity extraction and smart routing** — spaCy pulls out room/date/rate; the language model
   decides which agents to run. *(this is what makes the system genuinely "agentic")*
5. **Connect Agent 3 to Agent 4** — retrieved rates must reach the solver.
6. **Real analytics** — persisted events, query grouping, an acceptance funnel, an A/B test.
7. **A search quality test set** — 30–50 question-and-correct-clause pairs, so you can report
   real IR scores.
8. **Dashboard screens** — overview, what-if, optimiser, knowledge base, analytics, audit.

### Must NOT
Write anyone else's algorithm. Your job is to unblock, review and integrate. If you find yourself
implementing the forecaster, something has gone wrong.

### Must deliver to the team
- The interfaces (done)
- Container wiring, within a day of being asked
- The database connection string
- Tariff rates and citations, from Agent 3 to Developer 3

### Complete when
Someone can log in, ask a question in the dashboard, and get an answer built from real documents
in a real database, with real search scores to report — and all four slices are merged and green.

---

## 11. Developer 1 — Data & Forecasting

**Member 2** · Agent 1 · Security audit: privacy and data leakage

### Responsible for
Everything to do with **getting data in and predicting the future**. You are the start of the
chain — if your numbers are wrong, everything downstream is wrong.

### Must implement
1. **The forecaster** (`src/agents/telemetry/forecaster.py`) — 48 demand values, 48 solar values,
   confidence bounds, anomaly flags.
2. **Real weather** (`weather_tool.py`) — call Open-Meteo, cache it, fall back offline. It
   currently returns identical numbers for every date.
3. **PostgreSQL adapters** for meter history and timetables — the two that silently fall back to
   a spreadsheet today.
4. **A real dataset** — at least 90 days of half-hourly data. Building Data Genome 2 is the
   recommended source. If you generate it instead, write your assumptions down.
5. **A trained model** — LightGBM or scikit-learn, measured with RMSE and MAE, compared against
   the simple baseline. **That comparison is your headline result.**
6. **A plain-English forecast summary** — one language model call explaining why tomorrow is
   unusual. *(this earns the "summarisation" mark)*
7. **Privacy noise** on meter readings.
8. **15 real security tests** on privacy and data leakage.

### Must NOT
Touch the physics, the solver, the search, the API, the dashboard, `container.py` or
`settings.py`. Do not edit the reference baselines.

### Must deliver
| Output | To whom |
|---|---|
| 48 demand + 48 solar values, bounds, anomalies | Developer 3 |
| 48 temperatures + 48 student counts | Developer 2 |
| 48 tariff values | Developer 3 |
| Forecast summary text | Team Lead |

These shapes are contracts. Changing them breaks other people — tell the Team Lead first.

### Complete when
- Your tests pass with **no skips**
- A forecast comes from PostgreSQL, not the spreadsheet
- The weather tool gives different answers for different dates
- You can state your RMSE and MAE and how they beat the baseline
- All 15 security tests really run
- `pytest tests/` is green

---

## 12. Developer 2 — Physics & Simulation

**Member 3** · Agent 2 · Security audit: tool and search security

### Responsible for
**Proving a plan is physically safe** before anyone acts on it. You are the safety check between
prediction and decision.

### Must implement
1. **Room temperature physics** (`thermal_model.py`) — step through 48 intervals: students give
   off heat, heat leaks through walls, air conditioning removes it.
2. **Battery physics** (`battery_dynamics.py`) — charge level over time, energy lost as heat,
   count every breach of the 20%–90% band.
3. **Fit the physics constants from data** instead of guessing 50.0 and 2.5.
   **This is your headline result** — how much more accurate is the fitted model?
4. **Delete the duplicate physics** — it exists in three places. Make the simulation tool call
   your model. Exactly one copy must remain.
5. **Consolidate the safety limits** — read 21.0/25.5 from settings, not typed into files.
6. **Three what-if scenarios** — heatwave, crowd surge, solar dropout.
7. **Expose the simulator over MCP.** *(this is how the project claims the protocol requirement,
   and it is also your own audit topic — you cannot credibly test tool security against a plain
   function call)*
8. **15 real security tests** on tool spoofing, index poisoning and search denial-of-service.

### Must NOT
Touch forecasting, the solver, the API or the dashboard. **You may attack the search code but
never edit it** — it belongs to the Team Lead. File an issue; fixes land in their pull requests.

### Must deliver
| Output | To whom |
|---|---|
| 48 indoor temperatures | Team Lead |
| Safe or not, plus violation count | Developer 3 |
| Battery charge trajectory | Developer 3 |

### Complete when
- Your tests pass with **no skips**
- A room with 100 students and no cooling **measurably warms up** — the physics behaves, not
  merely runs
- Exactly one copy of the physics exists
- You can state your fitted constants and the accuracy improvement
- The simulator is reachable over MCP and **rejects impossible inputs** like −15°C
- All 15 security tests really run
- `pytest tests/` is green

---

## 13. Developer 3 — Optimisation & Responsible AI

**Member 4** · Agent 4 · Security audit: bias and honesty

### Responsible for
**Making the actual decision, and making the system honest about it.** Yours is the only agent
that produces real physical setpoints — which is why they come from a solver and never from a
language model.

### Must implement
1. **The solver** (`milp_solver.py`) — 48 intervals, minimise cost plus the peak penalty, respect
   supply-meets-demand, the 20%–90% battery band and the 100 kW rate limit.
2. **Add integer variables** — a binary per interval so the battery either charges or discharges,
   never both. Without this it is not truly a MILP.
3. **Fairness tiers** (`tier_guardrails.py`) — Tier 0 (labs, medical, servers) can *never* be cut,
   enforced as a hard constraint; Tier 1 can flex ±1.5°C; Tier 2 is fully curtailable.
4. **Report binding limits** — which constraint stopped it saving more?
5. **Fix the fact-checker** — make it fail closed, then have it extract every number from the
   explanation and compare against the solver output.
6. **15 real security tests** on hallucinated rates, load-shedding bias and explanation honesty.
   A strong test: run the solver twice with dormitory and office labels swapped and show the
   result is symmetric.

### Must NOT
Touch forecasting, physics, search, the API or the dashboard. You own your whole folder including
the explainer — but the **prompt templates belong to the Team Lead**; request changes.

### Must deliver
| Output | To whom |
|---|---|
| Full schedule, costs, savings, peak before/after, binding limits | Team Lead |
| Honesty verdict for every explanation | Team Lead |

### Complete when
- Your tests pass with **no skips**
- Solver returns "Optimal" and the battery **never** leaves 20%–90%
- Real integer variables exist and you can point to them
- Tier 0 rooms **cannot** be cut, with a test proving it
- The fact-checker **rejects** an explanation containing a wrong number, with a test proving it
- All 15 security tests really run
- `pytest tests/` is green

---

## 14. The finished system, and the order we build it

### What "finished" looks like

A facility manager opens the dashboard and logs in. They type *"tomorrow looks hot — what should
we do about the peak charge?"* in ordinary English.

The system works out what they are asking, runs only the agents that question needs, predicts
tomorrow's electricity from real campus data, checks the buildings stay comfortable, looks up the
real Sri Lankan tariff rules from real documents, calculates the cheapest safe battery schedule,
and explains its reasoning in plain English with clickable citations — after checking its own
explanation for invented numbers.

The manager sees the plan, the money saved, the reasoning and the sources, and presses **Approve**.
Every step is written to a log that cannot be quietly rewritten.

Behind it: any language model can be swapped in with one line. Every number that matters comes
from a solver that can prove it followed the rules. And critical facilities can never be cut,
because that is written into the mathematics.

### Build order

```
  STEP 0 ── FOUNDATIONS ─────────────────────────────── ✅ DONE
    Architecture, interfaces, tests green from a clean copy.
    Everything below depends on this.

  STEP 1 ── WEEK 1 ── MAKE EACH PART WORK AT ALL ────── all four in parallel
    Dev 1  forecaster returns sensible numbers
    Dev 2  physics runs and behaves correctly
    Dev 3  solver returns Optimal within safe limits
    Lead   login · real embeddings · ingest real tariff documents
    ► CHECKPOINT: turn the stand-ins off, confirm it still runs

  STEP 2 ── WEEK 2 ── MAKE IT REAL ─────────────────── all four in parallel
    Dev 1  real database · real weather · 90 days of data · trained model
    Dev 2  fit the constants · delete duplicate physics
    Dev 3  fairness tiers · fix the fact-checker · integer variables
    Lead   cloud database live · search test set · real analytics
    ► CHECKPOINT: real data, real database, real language model, end to end

  STEP 3 ── WEEK 3 ── DEPTH, THEN STOP ─────────────── all four in parallel
    Dev 1  privacy noise · forecast summary
    Dev 2  what-if scenarios · MCP tool
    Dev 3  fairness proof tests
    Lead   connect Agent 3 to Agent 4 · dashboard · search scores
    ► FEATURE FREEZE at the end of this week

  STEP 4 ── WEEK 4a ── SECURITY AUDITS ─────────────── all four, individually
    15 real attacks each, against the integrated system.
    This comes AFTER integration because you need something to attack.

  STEP 5 ── WEEK 4b ── SUBMISSION
    Report · video · repository · viva practice
```

### What depends on what

- **Everything** depends on Step 0. It is done.
- **Developer 2** needs Developer 1's temperatures → use the stand-ins meanwhile.
- **Developer 3** needs Developer 1's forecast and Developer 2's verdict → same.
- **The Team Lead** needs everybody, which is why integration is weekly and not at the end.
- **The security audits** need a working system → that is why they are last.

**Nobody is ever blocked.** `USE_REFERENCE_BASELINES=true` runs the whole system with working
stand-ins for whatever is not finished.

### The project is done when

The assignment asks for specific things. Here is where we stand:

| The assignment asks for | Where we are |
|---|---|
| At least 2 interacting agents | ✅ we have 4 |
| One or more language models | ✅ working |
| NLP techniques (entity extraction, summarising) | ⬜ Team Lead + Developer 1 |
| An information retrieval module | ✅ our strongest part |
| Security (login, input checking) | ⬜ Team Lead |
| Defined communication protocols | 🔶 web endpoints done, MCP is Developer 2 |
| Fairness | ⬜ Developer 3 |
| Explainability and transparency | ✅ working |
| Protecting user data | 🔶 meter data never reaches the language model — Developer 1 adds the rest |
| A commercialisation plan | ✅ written |
| A clean repository with a good README | ✅ done |

Three gaps and two half-finished items. That is a to-do list, not a problem.

### The sentence to build the video and viva around

> *"Four specialised agents, each with the right kind of brain for its job. The language model
> understands the question, decides which agents to run, and explains the answer. The solver
> decides the numbers, because those have to be provably safe. And a human approves before
> anything moves."*

---

---
---

# PART E — WORKING TOGETHER

## 15. How we work day to day

### Getting set up (once)

```bash
git clone <repo>
cd "IRWA project"
python3 -m venv venv && source venv/bin/activate
pip install -e ".[all]"
cp .env.example .env
pytest tests/ -v          # 136 passed, 5 skipped (Agent 2 physics), 1 known fail (TC-S2-01)
```

If those 37 tests do not pass, stop and tell the Team Lead. Do not start working.

### Every day

```bash
git checkout your-branch
git pull --rebase origin main     # do this EVERY morning
```

Pulling every morning means conflicts are one line. Leaving it a week means losing an afternoon.

### Three rules that prevent almost every problem

1. **Never edit a file you do not own.** Check [`../TEAM_GUIDES/OWNERSHIP.md`](../TEAM_GUIDES/OWNERSHIP.md) if unsure.
2. **Never edit `container.py` or `settings.py`.** If you need something connected up, open an
   issue called `WIRE: <your class> into container` and the Team Lead does it. These two files
   are where merge conflicts come from.
3. **Run `pytest tests/` before you push.** If it is red, do not push.

### Tell the team this every day — five lines

```
What I finished:
What I'm doing today:
What is blocked:
What files I changed:
What I need from someone else:
```

If "what files I changed" lists a file you do not own, say so straight away.

### When you get stuck

- **Blocked on someone else's code?** You are not. Set `USE_REFERENCE_BASELINES=true`.
- **Need a setting or a library?** Ask the Team Lead. Do not add it yourself.
- **Your test fails and you cannot see why?** There is a working version of your algorithm in
  `src/infrastructure/reference_baselines/` — read it. Do not edit it, and do not copy it word
  for word, because you have to defend your own code in the viva.

---

---

*Verified against the codebase on 7 September 2026. If you change how the system works, update
this document in the same commit.*
