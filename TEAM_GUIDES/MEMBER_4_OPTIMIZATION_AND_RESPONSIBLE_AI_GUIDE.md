# Developer 3 — Optimisation, XAI & Responsible AI

**Member:** Member 4 · **Agent:** Agent 4 — Dispatch and Explanation
**Security audit:** Student 3 — Responsible AI, Bias & Faithfulness (80 marks report + 20 marks viva)
**Branch:** `feature/dev3-milp-optimization`
**Ownership:** see [`OWNERSHIP.md`](OWNERSHIP.md) — it is authoritative

---

## 1. Your job, in plain English

You are the **campus financial optimiser**, and you own the part that has to be right.

Sri Lankan electricity is cheap at night (about LKR 15/kWh), normal during the day (LKR 30),
and brutal during the evening peak (LKR 58). On top of that the utility charges a penalty based
on the **single highest 15-minute spike** in the entire month — one bad afternoon can set
30–50% of the bill.

Your job is to work out mathematically when the battery should charge and when it should
discharge, so the bill comes out as low as possible — while never breaking a safety rule.

Then you make the system **explain that decision honestly** to a human, and prove it did not
make anything up.

> Your agent is the only one that decides real physical setpoints. That is why the numbers come
> from a solver and never from a language model. The LLM explains your answer; it never
> produces it. This separation is the strongest safety argument the whole project has — expect
> to be asked about it at the viva.

---

## 2. What to build

### 2.1 The solver — `src/agents/dispatch_explanation/milp_solver.py`

Implement `solve()` with PuLP over 48 half-hour intervals. Decide how much power to import,
how much to charge, and how much to discharge, minimising energy cost plus the peak penalty.

Rules that must hold at every interval: supply meets demand; the battery stays between 20% and
90%; it never charges or discharges faster than 100 kW.

Your class already inherits `MicrogridOptimizerInterface` — keep that.

### 2.2 Make it a genuine MILP

The reference version uses only continuous variables, which makes it a **linear program, not a
mixed-integer one**. Add a binary variable per interval forcing the battery to either charge or
discharge but never both at once.

> This is about five lines, and it matters. "Where are your integer variables?" is an obvious
> viva question, and right now the honest answer is "there aren't any." Fix that early.

### 2.3 Fairness guardrails — new file `tier_guardrails.py`

Some places must never lose power. Build the room-to-tier mapping and enforce it in the solver:

| Tier | Facilities | Policy |
|---|---|---|
| **Tier 0** | Research labs, medical rooms, server rooms | **Never curtailed** — a hard mathematical constraint |
| **Tier 1** | Lecture halls, libraries, offices | May flex ±1.5°C during peak hours |
| **Tier 2** | EV chargers, pumps, ornamental lighting | Fully curtailable, shift to cheap hours |

Tier 0 must be impossible to cut — not "unlikely", *impossible*, enforced as a constraint. This
is the Responsible AI fairness requirement in the brief, and it is your own audit topic.

### 2.4 Report which limits are binding

When the solver finishes, work out which constraints stopped it saving more money — battery too
small? discharge rate too low? — and return that list. This is what makes the recommendation
explainable rather than a black box.

### 2.5 Fix a real safety bug — `faithfulness.py`

Right now, when the fact-checking step fails to parse the language model's reply, it returns
`is_faithful: true, confidence 0.95`. In other words: **when the check fails, it reports
success.** An unverifiable explanation is currently marked verified.

Make it **fail closed** — if it could not check, the answer is "not faithful", not "fine".

Then strengthen the check itself: pull every number out of the generated explanation and compare
it against the actual solver output. If a figure appears that the solver never produced, reject
the explanation.

> This one bug is worth real marks. It sits exactly where the brief asks for explainability and
> transparency, and finding and fixing it is a genuine Responsible AI contribution you can
> describe in your report.

### 2.6 The explanation itself — `xai_explainer.py`

Already working: it turns solver numbers plus retrieved tariff citations into plain English for
the facility manager. You own this file. If you need a prompt template changed, ask the team
lead — `src/prompts/` is theirs.

---

## 3. Your security audit — 15 real test cases

File: `tests/red_team_security_audits/test_student3_responsible_ai_bias.py`

Cover: hallucinated tariff rates (does the AI invent prices that were never retrieved?),
systematic load-shedding bias between student dormitories and administrative offices,
disproportionate comfort penalties on general classrooms, XAI faithfulness failures (does the
explanation ever claim savings the solver never produced?), screen-reader accessibility, and
bias against legacy equipment.

Every case uses the mandatory 7-point schema.

**A strong fairness test looks like this:** run the solver twice with the dormitory and office
labels swapped, and show the outcome is symmetric. If it isn't, you have found real algorithmic
bias — and a finding with evidence scores far better than a clean sheet with none.

> ### ⚠️ Read this before you write a single test
>
> The existing examples in that file are **wrong**. They build a dictionary of hardcoded strings
> — including a made-up "actual behaviour" — and assert it has seven keys. No attack is ever
> executed, and the `test_container` fixture is passed in and never used.
>
> **Your tests must really run against the live system** and record what actually happened.
> Invented evidence in an 80-mark report is both a marks risk and an academic integrity risk.
> Schedule these for **week 4, after integration** — you need a working system to attack.

---

## 4. Files you own

```
src/agents/dispatch_explanation/     the WHOLE folder — solver, explainer,
                                     faithfulness, agent, your new tier_guardrails.py
your room-to-tier mapping data file
tests/unit/test_member4_milp_solver.py
tests/red_team_security_audits/test_student3_responsible_ai_bias.py
```

## 5. Do not modify

```
src/domain/                                  the shared contracts — ask the lead
src/application/container.py                 request wiring, do not edit
src/config/settings.py                       request settings, do not edit
src/agents/telemetry/  digital_twin/  policy_rag/  coordinator/
src/prompts/                                 the lead owns the templates — request changes
src/infrastructure/                          all of it
src/infrastructure/reference_baselines/      read for reference, never edit
```

Need something wired in, or a new setting exposed? Open an issue titled
`WIRE: <class> into container`. The team lead makes that edit.

---

## 6. What you depend on, and what you owe

**From the team lead:** the `MicrogridOptimizerInterface` you implement (already in place),
prompt template changes, the tariff rates and citations coming out of the document search, and
container wiring.

**From Developer 1:** 48 forecast demand values, 48 solar values, 48 tariff values.
**From Developer 2:** the thermal feasibility verdict you treat as a constraint.

**You must provide — these shapes are contracts, do not change them without telling the lead:**

| Output | Used by |
|---|---|
| `OptimizationResult` — 48 each of grid import, charge, discharge, state of charge; baseline and optimised cost; savings; peak before and after; solver status; binding constraints | Team Lead (explanation, dashboard, audit log) |
| Faithfulness verdict for every generated explanation | Team Lead (Responsible AI evidence) |

**Blocked waiting on Developers 1 and 2?** You are not. Set `USE_REFERENCE_BASELINES=true` in
your `.env` and you get a working forecast and feasibility verdict immediately.

---

## 7. Done means

- [ ] `pytest tests/unit/test_member4_milp_solver.py` passes with **no skips**
- [ ] Solver returns `Optimal` across all 48 intervals, and the battery **never** leaves the
      20%–90% band in any result
- [ ] The model contains **real integer variables** and you can point to them
- [ ] Tier 0 rooms **cannot** be curtailed, and you have a test proving it
- [ ] The fact-checker **rejects** an explanation containing a wrong number, and you have a test
      proving it
- [ ] All 15 security tests **execute real attacks** and record real observed behaviour
- [ ] `pytest tests/` fully green

```bash
pytest tests/unit/test_member4_milp_solver.py -v
pytest tests/red_team_security_audits/test_student3_responsible_ai_bias.py -v
pytest tests/ -v
```
