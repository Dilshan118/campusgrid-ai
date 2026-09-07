# Developer 1 — Data, Machine Learning & Privacy

**Member:** Member 2 · **Agent:** Agent 1 — Telemetry and Forecasting
**Security audit:** Student 2 — Privacy and Data Leakage (80 marks report + 20 marks viva)
**Branch:** `feature/dev1-telemetry-forecasting`
**Ownership:** see [`OWNERSHIP.md`](OWNERSHIP.md) — it is authoritative

---

## 1. Your job, in plain English

You are the **campus energy forecaster**.

Every day the university burns electricity on lecture halls, labs, computers and air
conditioning, while rooftop solar panels generate some of it back. Your job is to look at
three things — what the campus used before, how hot tomorrow will be, and how many students
are timetabled into each room — and predict **tomorrow's electricity, half hour by half hour**.

Everything downstream depends on your numbers. The physics simulation uses your temperatures,
and the battery optimiser uses your demand figures. If your numbers are wrong, the whole
system is wrong.

Separately, as **Student 2**, you attack the system to prove nobody can spy on students or
work out which lab equipment is running just by staring at power meter readings.

---

## 2. What to build

### 2.1 The forecaster — `src/agents/telemetry/forecaster.py`

Implement `predict()`. It receives past meter intervals, a temperature series and occupancy
counts, and returns a `PowerForecast` containing 48 demand values, 48 solar values, upper and
lower confidence bounds, and a list of intervals where demand looks abnormally high.

Your class already inherits `DemandForecasterInterface` — keep that. It is what lets the team
lead swap your model in and out without touching any other file.

### 2.2 A real weather feed — `src/infrastructure/tools/weather_tool.py`

Today this returns the same 48 hardcoded temperatures no matter what date you ask for.
Replace it with a real **Open-Meteo** call for the campus coordinates already in settings —
free, no API key needed. Cache the result, and fall back to the built-in curve if the network
is unavailable so tests never depend on the internet.

### 2.3 Real database access — the meter and timetable repositories

Right now the system reads from a 48-row CSV **even when it is configured to use PostgreSQL**,
because the Postgres versions of these two repositories do not exist yet. Write them:

- `src/infrastructure/database/repositories/meter_history_repository.py`
- `src/infrastructure/database/repositories/timetable_repository.py`

The `meter_history` table in `backend/data/init.sql` now mirrors the `TelemetryInterval`
entity field-for-field, so no translation layer is needed. Ask the team lead for the Neon
connection string.

### 2.4 Real training data

The repository has exactly one synthetic day. Get at least **90 days** of half-hourly campus
data. The recommended source is **Building Data Genome 2 (BDG2)**, the open ASHRAE benchmark.
If you generate data synthetically instead, that is acceptable — but write your assumptions
down in a README next to the data file. An examiner will ask where the data came from.

### 2.5 Train an actual model — `src/pipelines/periodic_retraining/train_forecaster.py`

Load the historical data, build features (hour of day, day of week, outdoor temperature,
occupancy), train a LightGBM or scikit-learn regressor, measure **RMSE and MAE** on a 20% test
split, and save the model.

Then compare it against the simple rule-based baseline in
`src/infrastructure/reference_baselines/baseline_forecaster.py`.

> **That comparison is your headline result.** "My model scores X, the baseline scores Y" is
> what you present and defend. Write the numbers down as soon as you have them.

### 2.6 NEW — a plain-English forecast summary

After producing the numbers, make **one LLM call** that writes a two-sentence note explaining
what is unusual about tomorrow. For example:

> *"Tomorrow's demand runs about 12% above a normal Tuesday, driven by a 33°C afternoon and
> two large lectures in the Main Academic Complex between 13:00 and 16:00."*

Use the injected `LLMProvider` — never call an SDK directly. Ask the team lead to wire it in.

**Why this matters:** the assignment brief explicitly names **summarisation** as a required
NLP technique. This is how Agent 1 earns that mark. It is roughly 20 lines.

> The LLM writes the *sentence*. It must never produce the *numbers* — those come from your
> forecaster. If the LLM invents a figure, that is a hallucination and Student 3's audit will
> catch it.

### 2.7 Privacy protection

Add optional differential-privacy noise to meter readings before they leave your layer. This
is both a Responsible AI requirement in the brief and the core subject of your own audit.

---

## 3. Your security audit — 15 real test cases

File: `tests/red_team_security_audits/test_student2_privacy_leakage.py`

Cover: student and staff schedule de-anonymisation, sub-meter appliance disaggregation (NILM),
cross-campus data leakage, differential-privacy noise verification, markdown/URL exfiltration,
and prompt-based extraction of raw database records.

Every case uses the mandatory 7-point schema: test ID, objective, attack scenario, expected
behaviour, actual behaviour, evidence, severity and mitigation.

> ### ⚠️ Read this before you write a single test
>
> The two example tests currently in that file are **wrong** and must not be copied. They
> build a dictionary of hardcoded strings — including a made-up "actual behaviour" — and then
> assert the dictionary has seven keys. No attack is ever executed. The `test_container`
> fixture is passed in and never used.
>
> **Your tests must actually run.** Call the real API or the real container, send the real
> attack, capture the real response, and assert on what really came back. Then paste that real
> output into your report as evidence.
>
> Invented evidence in an 80-mark security report is both a marks risk and an academic
> integrity risk. Schedule these for **week 4, after integration** — you need a working system
> to attack.

---

## 4. Files you own

```
src/agents/telemetry/
src/infrastructure/tools/weather_tool.py
src/infrastructure/database/repositories/meter_history_repository.py
src/infrastructure/database/repositories/timetable_repository.py
src/pipelines/periodic_retraining/
tests/unit/test_member2_telemetry.py
tests/red_team_security_audits/test_student2_privacy_leakage.py
your dataset files + their README
```

## 5. Do not modify

```
src/domain/                                  the shared contracts — ask the lead
src/application/container.py                 request wiring, do not edit
src/config/settings.py                       request settings, do not edit
src/agents/digital_twin/  dispatch_explanation/  policy_rag/  coordinator/
src/infrastructure/tools/simulation_tool.py, __init__.py, registry.py
src/infrastructure/reference_baselines/      read for reference, never edit
src/api/    frontend/
```

Need a class wired into the container, or a new setting? Open an issue titled
`WIRE: <class> into container`. The team lead makes that edit. This one rule prevents most
merge conflicts on this project.

---

## 6. What you depend on, and what you owe

**From the team lead:** the `DemandForecasterInterface` you implement (already in place), the
Neon connection string, an injected `LLMProvider` for your summary, and container wiring.

**You must provide — these shapes are contracts, do not change them without telling the lead:**

| Output | Used by |
|---|---|
| `PowerForecast` — 48 each of demand, solar, lower bound, upper bound, anomaly indices | Developer 3 (solver input) |
| 48 ambient temperatures | Developer 2 (physics input) |
| 48 occupancy counts | Developer 2 (physics input) |
| 48 tariff values | Developer 3 (cost objective) |
| Plain-English forecast summary | Team Lead (dashboard) |

**Blocked waiting on someone?** You are not. Set `USE_REFERENCE_BASELINES=true` in your `.env`
and the whole pipeline runs with working stand-ins for everyone else's work.

---

## 7. Done means

- [ ] `pytest tests/unit/test_member2_telemetry.py` passes with **no skips**
- [ ] A forecast comes out of **PostgreSQL**, not the CSV fallback
- [ ] The weather tool returns **different values for different dates**
- [ ] You can state your model's RMSE and MAE, and how they beat the baseline
- [ ] The forecast summary reads naturally and contains no number the model didn't produce
- [ ] All 15 security tests **execute real attacks** and record real observed behaviour
- [ ] `pytest tests/` fully green

```bash
pytest tests/unit/test_member2_telemetry.py -v
pytest tests/red_team_security_audits/test_student2_privacy_leakage.py -v
pytest tests/ -v
```
