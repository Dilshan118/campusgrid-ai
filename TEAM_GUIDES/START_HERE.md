# START HERE — CampusGrid AI

**Everyone on the team reads this first.** It explains what we are building, how the pieces fit
together, what is already done, and exactly what each person does next.

No jargon. If a term needs explaining, it is explained.

| I want to know… | Go to |
|---|---|
| What are we building and why | [Part 1](#part-1--what-we-are-building) |
| How do the four agents actually work | [Part 2](#part-2--how-the-system-works) |
| What is already built | [Part 3](#part-3--where-we-are-right-now) |
| What am *I* responsible for | [Part 4](#part-4--who-does-what) |
| What do I do first, second, third | [Part 5](#part-5--the-build-plan-step-by-step) |
| How do we work together without breaking things | [Part 6](#part-6--how-we-work-day-to-day) |
| When are we finished | [Part 7](#part-7--when-we-are-done) |

---

# Part 1 — What we are building

## The problem, in one paragraph

A Sri Lankan university pays for electricity in two ways. First, for the units it uses. Second —
and this is the painful one — a penalty based on the **single highest 15-minute spike** in the
whole month. If every lecture hall switches its air conditioning on at 2pm on a hot Tuesday, that
one spike can set **30% to 50% of the entire monthly bill**. Universities have solar panels and
big batteries that could flatten that spike, but they run on dumb timers, so the battery is often
empty exactly when it is needed.

## What our system does about it

**CampusGrid AI** is an advisor. A facility manager types a question in normal English, and the
system works out the cheapest safe plan for the campus battery and air conditioning — then
explains its reasoning in plain English with references to the actual electricity regulations.

Three things it deliberately does **not** do:

- It does **not** touch the national grid. It only works behind the university's own meter.
- It does **not** flip any switches. It recommends; a human approves.
- The language model does **not** choose any physical setting. A mathematical solver does that.

> **Remember that last point.** It is the single most important design decision in the project,
> and you will be asked about it in the viva. A language model cannot *guarantee* the battery
> stays above 20% charge — it will happily produce a number that looks sensible and is wrong. So
> the solver decides the numbers, and the language model explains them.

---

# Part 2 — How the system works

## The four agents, in one line each

An **agent** is just a worker with one clear job that can hand its answer to the next worker.

| Agent | Its one job | In plain English |
|---|---|---|
| **Agent 1** — Telemetry | Predict | "Here is how much electricity we will use tomorrow." |
| **Agent 2** — Digital Twin | Check safety | "Here is whether that plan would cook the students." |
| **Agent 3** — Policy Retrieval | Look up rules | "Here is what the electricity regulations actually say." |
| **Agent 4** — Dispatch | Decide and explain | "Here is the plan, what it saves, and why." |

Nobody's job overlaps with anybody else's. That is deliberate — it is how four people work at the
same time without stepping on each other.

## A real request, start to finish

Say the facility manager types:

> *"Cut tomorrow's peak demand penalty and pre-cool Lecture Hall 1 to 23.5°C."*

Here is what happens, in order:

```
   The manager types the question in the web dashboard
                          |
                          v
   The API receives it and hands it to the Orchestrator
                          |
                          v
   ORCHESTRATOR reads the question and pulls out the details:
   room = LH-1,  target = 23.5C,  date = tomorrow,  goal = save money
                          |
                          v
   AGENT 1  "What will tomorrow look like?"
   Reads past meter readings, the weather, and the class timetable.
   Produces 48 half-hourly numbers for electricity demand and solar output.
                          |
                          |  passes: demand, solar, temperatures, how many students
                          v
   AGENT 2  "Would that actually be safe?"
   Runs the building physics. Works out how hot each room gets.
   Checks the battery never drops below 20% or above 90%.
                          |
                          |  passes: indoor temperatures, "is this feasible: yes/no"
                          v
   AGENT 3  "What do the rules say?"
   Searches the electricity tariff documents and comfort standards.
   Finds the exact rates and the exact clauses they come from.
                          |
                          |  passes: LKR 58/kWh at peak, LKR 1100/kVA penalty, + citations
                          v
   AGENT 4  "So what should we do?"
   The solver works out the cheapest safe battery schedule.
   Then the language model writes the explanation.
   Then a SECOND language model call checks every number in that
   explanation against what the solver actually produced.
                          |
                          v
   Everything gets written to the audit log (who asked, what each
   agent said, what was decided) so it can never be disputed later
                          |
                          v
   The manager sees: the plan, the money saved, the plain-English
   reasoning, the regulation citations — and an APPROVE button.
   Nothing happens until they press it.
```

## Where the language model is used, and where it is not

This matters more than any other technical detail in the project.

| The language model **does** this | The language model **never** does this |
|---|---|
| Understands what the manager meant | Decides the battery schedule |
| Decides which agents need to run | Calculates temperatures |
| Writes the plain-English explanation | Invents a tariff rate |
| Fact-checks its own explanation | Touches any physical equipment |
| Summarises why tomorrow looks unusual | Produces any number that must be correct |

Everything in the right-hand column is done by a formula or a solver, because those can be
**proven** correct and give the same answer every time.

## Why we split it into four agents

You could write this as one big program. We did not, for three reasons:

1. **Four people can work at once.** Each agent is a separate folder with a separate owner.
2. **You can test each piece on its own.** If the forecast is wrong, you know exactly where.
3. **The assignment requires it** — at least two interacting intelligent agents. We have four.

## How the agents talk to each other

- **Inside the system:** each agent gets typed input and returns a typed result. The Orchestrator
  passes the results along the chain.
- **From outside:** every agent also has its own web address, so it can be called on its own —
  `/api/telemetry`, `/api/simulation`, `/api/rag`, `/api/optimizer`.
- **To tools:** the physics simulator will be reachable over **MCP** (Model Context Protocol), a
  standard way for an AI system to call an external tool. Developer 2 builds this.

## How we swap any technology out

Every external thing — the language model, the search database, the storage — sits behind an
**interface**. Think of it as a plug socket: the agents plug into the socket and never care
which appliance is on the other end.

That means switching from Google Gemini to OpenAI, or from PostgreSQL to Chroma, is **one line
in a `.env` file** — no code changes anywhere.

> Practical consequence for you: **agents must never import a vendor's library directly.** If
> your code says `import openai`, that is a bug. Ask the Team Lead to wire it in properly.

---

# Part 3 — Where we are right now

## Already working — do not rebuild these

- The whole architecture: interfaces, dependency injection, layering
- The API with 8 endpoints, request tracing, and error handling
- **Hybrid search** (Agent 3): meaning-based search + keyword search, combined and ranked
- The plain-English explainer and the automated fact-checker
- Swappable language model (5 providers) and a fake one for offline testing
- The append-only audit log
- Working "stand-in" versions of everything the three developers are about to build
- 45 tests — **37 pass, 8 skip.** The 8 skips are the parts not written yet.

## Not built yet

| What | Who |
|---|---|
| The demand forecaster | Developer 1 |
| Real weather data (currently the same numbers every day) | Developer 1 |
| Reading meter data from the real database | Developer 1 |
| The room temperature physics | Developer 2 |
| The battery charge physics | Developer 2 |
| Exposing the simulator over MCP | Developer 2 |
| The battery schedule solver | Developer 3 |
| Fairness rules (some rooms must never lose power) | Developer 3 |
| Login and access control | Team Lead |
| Loading the real tariff PDFs into the search index | Team Lead |
| Entity extraction and smart routing | Team Lead |
| Real usage analytics | Team Lead |
| The dashboard screens | Team Lead |

## One thing to know before you start

Set `USE_REFERENCE_BASELINES=true` in your `.env` file and **the entire system runs end to end
right now**, using stand-in versions of the unfinished parts.

This is important: **nobody is ever blocked waiting for anybody else.** Developer 3 can build and
test the solver before Developer 1 has finished the forecaster. Set it back to `false` when you
want to test your own code.

---

# Part 4 — Who does what

Four people. Four completely separate areas. Nobody edits anybody else's files.

| Person | Role | Owns | Individual audit |
|---|---|---|---|
| **Member 1** | Team Lead | The shared foundations, the API, security, Agent 3 (search), the dashboard, and gluing everything together | Student 1 — Prompt injection |
| **Member 2** | Developer 1 — Data & ML | Agent 1: forecasting, weather, database reading, model training | Student 2 — Privacy leaks |
| **Member 3** | Developer 2 — Digital Twin | Agent 2: room physics, battery physics, the MCP tool | Student 4 — Tool & search security |
| **Member 4** | Developer 3 — Optimisation | Agent 4: the solver, fairness rules, explanation checking | Student 3 — Bias & honesty |

**Your detailed instructions are in your own file** — open it, read it fully, then start:

- Developer 1 → [`MEMBER_2_TELEMETRY_AND_PRIVACY_GUIDE.md`](MEMBER_2_TELEMETRY_AND_PRIVACY_GUIDE.md)
- Developer 2 → [`MEMBER_3_DIGITAL_TWIN_AND_PHYSICS_GUIDE.md`](MEMBER_3_DIGITAL_TWIN_AND_PHYSICS_GUIDE.md)
- Developer 3 → [`MEMBER_4_OPTIMIZATION_AND_RESPONSIBLE_AI_GUIDE.md`](MEMBER_4_OPTIMIZATION_AND_RESPONSIBLE_AI_GUIDE.md)
- Team Lead → [`00_TEAM_LEAD_PLAYBOOK.md`](00_TEAM_LEAD_PLAYBOOK.md)

**Exactly which files belong to whom** is in [`OWNERSHIP.md`](OWNERSHIP.md). That file is the
final word — check it before you commit anything.

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

# Part 5 — The build plan, step by step

Four weeks. Do the steps in order. Inside each step, all four people work at the same time.

## Step 0 — Foundations ✅ DONE

The Team Lead has already done this. The architecture is set, the interfaces are frozen, the
tests pass from a clean copy, and the setup instructions are correct.

**Nobody starts before this is done. It is done. You can start.**

## Step 1 — Week 1: make your part work at all

Get something working end to end, even if it is rough. Do not polish yet.

| Person | This week |
|---|---|
| **Developer 1** | Write the forecaster so it returns 48 sensible numbers. Test it. |
| **Developer 2** | Write the room physics and battery physics. Prove a room with 100 students gets warmer. |
| **Developer 3** | Write the solver. Get it returning "Optimal" with the battery inside safe limits. |
| **Team Lead** | Add login. Switch on real meaning-based search. Load the real tariff documents. |

**End of week checkpoint (Team Lead runs this):** turn `USE_REFERENCE_BASELINES` off and confirm
the whole system still runs with everybody's real code.

## Step 2 — Week 2: make it real

Replace the fake data with real data.

| Person | This week |
|---|---|
| **Developer 1** | Read from the real database. Call the real weather service. Get 90 days of real data. Train an actual model and write down how much better it is than the simple version. |
| **Developer 2** | Stop guessing the physics constants — calculate them from data. Delete the duplicate copies of the physics. |
| **Developer 3** | Add the fairness rules. Fix the honesty checker so it fails safely. Add the integer variables to the solver. |
| **Team Lead** | Get the cloud database working properly. Build the list of test questions so we can measure how good the search is. Make analytics real. |

**End of week checkpoint:** the whole system runs on the real cloud database with a real language
model, using real tariff documents.

## Step 3 — Week 3: depth, then stop

| Person | This week |
|---|---|
| **Developer 1** | Add the privacy protection. Add the plain-English forecast summary. |
| **Developer 2** | Build the three what-if scenarios. Expose the simulator over MCP. |
| **Developer 3** | Build the fairness proof tests (swap dorm and office, show the result is the same). |
| **Team Lead** | Make the search results actually reach the solver. Build the dashboard screens. Calculate the search quality scores. |

> **End of week 3 is FEATURE FREEZE.** After this, no new features. Anything unfinished gets
> written up as "future work" — which is a perfectly good answer in a report.

## Step 4 — Week 4, first half: the security audits

Everybody does their own 15 test cases. **This happens now and not earlier**, because you need a
working system to attack.

> ### ⚠️ The most important instruction in this document
>
> The example security tests currently in the repository are **fake**. They write down a made-up
> "what happened" and then check that the paragraph has the right headings. No attack is ever
> actually run.
>
> **Do not copy them.** Send the real attack at the running system, capture what really came
> back, and put that real output in your report.
>
> Each of these reports is worth 80 marks. Made-up evidence is a marks risk and an academic
> integrity risk. Real evidence — including "I attacked it and it held up" — scores properly.

## Step 5 — Week 4, second half: submission

- Final report (30 marks) — the SRS in `docs/` is the raw material
- Gen AI video, 3–5 minutes (25 marks)
- Clean repository with a good README (5 marks) — already done
- Viva practice (20 marks) — see the Q&A section in the master SRS

## What depends on what

- **Everything** depends on Step 0. Done.
- **Developer 2** needs Developer 1's temperatures. Use the stand-ins until they arrive.
- **Developer 3** needs Developer 1's forecast and Developer 2's safety check. Same — use stand-ins.
- **The Team Lead** needs everybody, which is why integration happens weekly and not at the end.
- **The security audits** need a working system. That is why they are in week 4.

---

# Part 6 — How we work day to day

## Getting set up (once)

```bash
git clone <repo>
cd "IRWA project"
python3 -m venv venv && source venv/bin/activate
pip install -e ".[all]"
cp .env.example .env
pytest tests/ -v          # you should see 37 passed
```

If those 37 tests do not pass, stop and tell the Team Lead. Do not start working.

## Every day

```bash
git checkout your-branch
git pull --rebase origin main     # do this EVERY morning
```

Pulling every morning means conflicts are one line. Leaving it a week means losing an afternoon.

## Three rules that prevent almost every problem

1. **Never edit a file you do not own.** Check [`OWNERSHIP.md`](OWNERSHIP.md) if unsure.
2. **Never edit `container.py` or `settings.py`.** If you need something connected up, open an
   issue called `WIRE: <your class> into container` and the Team Lead does it. These two files
   are where merge conflicts come from.
3. **Run `pytest tests/` before you push.** If it is red, do not push.

## Tell the team this every day — five lines

```
What I finished:
What I'm doing today:
What is blocked:
What files I changed:
What I need from someone else:
```

If "what files I changed" lists a file you do not own, say so straight away.

## When you get stuck

- **Blocked on someone else's code?** You are not. Set `USE_REFERENCE_BASELINES=true`.
- **Need a setting or a library?** Ask the Team Lead. Do not add it yourself.
- **Your test fails and you cannot see why?** There is a working version of your algorithm in
  `src/infrastructure/reference_baselines/` — read it. Do not edit it, and do not copy it word
  for word, because you have to defend your own code in the viva.

---

# Part 7 — When we are done

## Each developer is done when

- Your own tests pass with **no skips**
- Your part works with real data, not the stand-in
- You can state your own result in one sentence — "my model scores X, the simple version scores Y"
- Your 15 security tests **actually run** and record what really happened
- `pytest tests/` is fully green

## The project is done when

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

## The one sentence to build the video and viva around

> *"Four specialised agents, each with the right kind of brain for its job. The language model
> understands the question, decides which agents to run, and explains the answer. The solver
> decides the numbers, because those have to be provably safe. And a human approves before
> anything moves."*

---

## Where everything else lives

| File | What is in it |
|---|---|
| [`OWNERSHIP.md`](OWNERSHIP.md) | Exactly which files belong to whom — **the final word** |
| Your own `MEMBER_*.md` | Your detailed instructions and copy-paste prompts |
| [`../README.md`](../README.md) | Installing and running the system |
| [`../docs/README.md`](../docs/README.md) | Guide to the specification documents |
| [`../docs/CAMPUSGRID_AI_SIMPLIFIED_SRS_AND_SYSTEM_GUIDE.md`](../docs/CAMPUSGRID_AI_SIMPLIFIED_SRS_AND_SYSTEM_GUIDE.md) | The full technical specification |
| [`../docs/04_COURSEWORK_SPECIFICATIONS_AND_RUBRICS.md`](../docs/04_COURSEWORK_SPECIFICATIONS_AND_RUBRICS.md) | What we are graded on |

*Last checked against the code on 7 September 2026. If you change how the system works, update
this file in the same commit.*
