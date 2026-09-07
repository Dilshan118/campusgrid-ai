# Developer 2 — Digital Twin, Physics & Tool Security

**Member:** Member 3 · **Agent:** Agent 2 — Digital Twin Simulation
**Security audit:** Student 4 — Retrieval, Vector Store & Tool/MCP Security (80 marks report + 20 marks viva)
**Branch:** `feature/dev2-digital-twin-physics`
**Ownership:** see [`OWNERSHIP.md`](OWNERSHIP.md) — it is authoritative

---

## 1. Your job, in plain English

You are the **cyber-physical engineer**.

Before this system tells anyone to cool a lecture hall or drain a 500 kWh battery, somebody has
to check that the plan is physically safe. That is you.

If it is 33°C outside and 200 students walk into a hall, how fast does the room heat up? Does it
stay inside the comfort band of 21.0°C to 25.5°C that people can actually work in? If the
battery discharges hard through the evening peak, does it drop below the 20% floor that damages
the cells?

You answer those questions with physics, not guesswork. Your feasibility verdict is what makes
the final recommendation trustworthy.

Separately, as **Student 4**, you attack the system's tools and its document search — trying to
send the simulator dangerous commands, and trying to poison the tariff knowledge base.

---

## 2. What to build

### 2.1 The room thermal model — `src/agents/digital_twin/thermal_model.py`

Implement `simulate()`. Step through 48 half-hour intervals. In each one: students give off
heat (about 100 watts each), outside air leaks through the walls in or out, and the air
conditioning removes heat. Return the indoor temperature at every interval.

Your class already inherits `BuildingThermalTwinInterface` — keep that.

### 2.2 The battery model — `src/agents/digital_twin/battery_dynamics.py`

Implement `simulate_soc_trajectory()`. Track the stored energy as it charges and discharges,
account for the roughly 8% lost as heat on a round trip, and count every interval where the
charge level leaves the safe 20%–90% band.

### 2.3 Stop guessing the physics constants

The model currently hardcodes a thermal capacity of `50.0` and a resistance of `2.5`. Those are
guesses. **Fit them from data** using `scipy.optimize.least_squares` against measured indoor
temperatures, and report how much more accurate the fitted model is than the guessed one.

> **This is your headline result.** "Guessed constants gave X error, fitted constants gave Y" is
> what you present. It turns a toy model into a calibrated grey-box, and it is excellent viva
> material.

### 2.4 Delete the duplicate physics

The same equations currently exist in **three** places: your `thermal_model.py`,
`src/infrastructure/tools/simulation_tool.py`, and the reference baseline. That is a bug waiting
to happen — fix one copy and the others silently disagree.

Make `simulation_tool.py` call your model instead of keeping its own copy. After you are done
there must be **exactly one** implementation of the 2R2C equations in the codebase.

### 2.5 Make the safety limits configurable

The numbers `21.0` and `25.5` are typed directly into the code in several places, and there are
three separate definitions of the comfort band across the project. Read them from settings so
they can never disagree. Ask the team lead to expose any setting you need.

### 2.6 Proper what-if scenarios

Build three: a heatwave (+4°C), a crowd surge (double occupancy), and a solar dropout. Each
returns whether the building stays comfortable and, if not, by how much it misses.

### 2.7 NEW — expose the simulator as a real MCP tool

Right now the simulation tool is called as a plain Python function. Expose it over the **Model
Context Protocol** so it becomes a genuine tool call across a defined protocol boundary.

**Why this matters, twice over:**

1. The assignment brief requires **"defined agent communication protocols (e.g. MCP, HTTP,
   sockets)"**. HTTP is already covered by the REST endpoints. Making this a real MCP tool is
   how the project claims MCP honestly instead of just naming it in a diagram.
2. It is **your own audit topic**. You cannot credibly test MCP parameter spoofing and tool
   interception against a tool that is really just a function call.

Keep it behind the existing `Tool` interface so nothing else in the codebase has to change.

> **Validate every parameter at the tool boundary.** The tool must refuse `-15°C` or `5000 kW`
> outright. Rejecting them is a feature, and it is the mitigation you will write up in your
> report.

---

## 3. Your security audit — 15 real test cases

File: `tests/red_team_security_audits/test_student4_retrieval_mcp_security.py`

Cover: MCP/tool parameter spoofing (commanding impossible temperatures or power levels), RAG
index poisoning (feeding in a fake tariff document claiming electricity costs 0.05 rupees),
vector embedding collision and cluster manipulation, vector-store denial of service with
oversized query vectors, interception of unencrypted tool calls, and payload tampering.

Every case uses the mandatory 7-point schema.

> ### ⚠️ Two things before you start
>
> **First — the existing examples are wrong.** They build a dictionary of hardcoded strings,
> including a made-up "actual behaviour", and assert it has seven keys. No attack ever runs.
> Do not copy that pattern. **Send real attacks at the live system and record what really
> happened.** Invented evidence in an 80-mark report is a marks risk and an integrity risk.
> Schedule these for **week 4, after integration**.
>
> **Second — the document search code belongs to the team lead.** You are expected to *attack*
> it and *report* what you find. You must not *edit* it. File an issue; fixes land in the
> lead's pull requests. Attacker and defender being different people is normal in red-teaming.

---

## 4. Files you own

```
src/agents/digital_twin/
src/infrastructure/tools/simulation_tool.py
tests/unit/test_member3_digital_twin.py
tests/red_team_security_audits/test_student4_retrieval_mcp_security.py
```

## 5. Do not modify

```
src/domain/                                  the shared contracts — ask the lead
src/application/container.py                 request wiring, do not edit
src/config/settings.py                       request settings, do not edit
src/agents/telemetry/  dispatch_explanation/  policy_rag/  coordinator/
src/infrastructure/tools/weather_tool.py, __init__.py, registry.py
src/application/services/retrieval_service.py    attack it in tests, never edit
src/infrastructure/vector_store/                 attack it in tests, never edit
src/infrastructure/reference_baselines/          read for reference, never edit
```

Need something wired in, or a new setting exposed? Open an issue titled
`WIRE: <class> into container`. The team lead makes that edit.

---

## 6. What you depend on, and what you owe

**From the team lead:** the `BuildingThermalTwinInterface` and `BatteryDynamicsInterface` you
implement (already in place), configurable comfort and battery limits, and container wiring.

**From Developer 1:** the 48 ambient temperatures and 48 occupancy counts you simulate against.

**You must provide — these shapes are contracts, do not change them without telling the lead:**

| Output | Used by |
|---|---|
| 48 simulated indoor temperatures | Team Lead (dashboard) |
| `comfort_violations_count` and `is_thermal_feasible` | Developer 3 (feasibility constraint) |
| 48-value battery charge trajectory + violation count | Developer 3, Team Lead |

**Blocked waiting on Developer 1?** You are not. Set `USE_REFERENCE_BASELINES=true` in your
`.env` and you get working stand-in temperatures and occupancy immediately.

---

## 7. Done means

- [ ] `pytest tests/unit/test_member3_digital_twin.py` passes with **no skips**
- [ ] A room with 100 students and no cooling **measurably heats up**; a balanced room stays
      flat — the physics behaves correctly, not merely runs without crashing
- [ ] There is **exactly one** copy of the 2R2C equations in the codebase
- [ ] You can state your fitted R and C values and how much they improved accuracy
- [ ] The simulator is reachable as a real MCP tool and **rejects out-of-range parameters**
- [ ] All 15 security tests **execute real attacks** and record real observed behaviour
- [ ] `pytest tests/` fully green

```bash
pytest tests/unit/test_member3_digital_twin.py -v
pytest tests/red_team_security_audits/test_student4_retrieval_mcp_security.py -v
pytest tests/ -v
```
