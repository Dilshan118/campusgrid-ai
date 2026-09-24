# CampusGrid AI — Team Lead Review & Integration Report

**Date:** 24 September 2026 · **Branch:** `feat/lead-system-implementation` · **Author:** Team Lead

This report compares what the project documents promise with what the code does today, records what
the Team Lead fixed in the Lead-owned slice, and lists the changes still needed from each member —
as suggestions, because the Lead does not edit other members' files (`TEAM_GUIDES/OWNERSHIP.md`).

The companion document [`SYSTEM_USER_FLOW_AND_UIUX_SPEC.md`](SYSTEM_USER_FLOW_AND_UIUX_SPEC.md)
describes the dashboard to build on top of this backend.

---

## 1. Summary

- **The pipeline now works end to end and is safe to demo:** a signed-in operator asks a question,
  four agents run, the tariff comes from retrieved regulation clauses, the plan waits in an approval
  queue, and only a facility manager can approve it. Every step is in a tamper-evident audit trail.
- **The biggest gaps found were in the Lead slice** and are fixed: authentication was not enforced,
  the human approval step did not exist, input sanitization silently did nothing, analytics returned
  invented numbers, and Agent 3's rates could be read wrongly or poisoned.
- **The biggest remaining gaps are Agent 2's physics (Member 3) and Agent 4's fact-checker and
  fairness tiers (Member 4).** Until Agent 2 is implemented, run with `REFERENCE_BASELINE_AGENTS=agent2`.
- **Tests:** 136 pass, 5 skip (Agent 2 physics not written), 1 fails on purpose — Member 2's TC-S2-01
  regression guard, which was written to fail once the Lead fixed their finding (section 5, Member 2).

---

## 2. Does the system match the proposal?

✅ meets the requirement · 🔶 partly · ❌ missing

| Requirement (assignment brief / SRS) | Status | Where it stands |
|---|:--:|---|
| ≥ 2 interacting intelligent agents | ✅ | Four agents plus an orchestrator with typed hand-offs |
| LLM integration | ✅ | Explanation, fact-check, forecast summary, and now intent routing for unclear questions |
| NLP techniques (entity extraction, summarisation) | 🔶 | Rule-based entity extraction backed by the room inventory; Agent 1 summary now wired. spaCy NER is still not used. |
| Information retrieval (hybrid RAG) | ✅ | Dense + BM25 + RRF; 30-query benchmark: Recall@2 = 1.00, MRR = 0.93 with real embeddings |
| Web analytics (query clustering, funnel, A/B test) | ✅ | All four modules computed from real events. Clustering groups by NLP intent — the SRS says TF-IDF + K-Means (see D-4) |
| Security (JWT, RBAC, sanitization) | ✅ | Enforced on every route; lockout, logout/revocation, hashed passwords, body-size limit |
| Security (mTLS, HTTPS) | ❌ | Claimed in the SRS; not implemented. HTTPS belongs to deployment (see D-4) |
| Communication protocols (REST, MCP) | 🔶 | REST per agent ✅. **MCP is not implemented anywhere** (Member 3) |
| Human-in-the-loop approval | ✅ | Was missing entirely; now a pending queue, approve/reject with rules, signed decisions |
| Responsible AI — explainability | ✅ | Plain-English explanation with citations, plus a numbers-only concise version |
| Responsible AI — faithfulness check | 🔶 | Runs, but **fails open**: if the checker's reply cannot be read it reports "faithful" (Member 4) |
| Responsible AI — fairness tiers | ❌ | Room→tier classification exists; the solver does not enforce tiers yet (Member 4, D-1 to D-3) |
| Responsible AI — differential privacy | ✅ | Member 2's Laplace export is now what the historical API returns |
| Digital twin (2R2C thermal, battery SOC) | ❌ | Member 3's physics raises `NotImplementedError`; the demo uses the reference baseline |
| Deterministic safety limits (21.0–25.5 °C, 20–90 % SOC) | 🔶 | Solver respects SOC; comfort limits are now passed from settings, but Agent 2 still hard-codes them |
| Tamper-evident audit trail | ✅ | SHA-256 hash chain + database trigger blocking UPDATE/DELETE + verify endpoint |
| Dashboard | 🔶 | Prototype only; full spec written, not yet built |

---

## 3. What the Team Lead fixed

| # | Problem found | Why it mattered | Fix |
|---|---|---|---|
| L-1 | Requests with **no token were treated as a facility manager**; no route checked roles | Anyone could read the audit trail or run plans | Every route declares its roles; missing/invalid token → 401, wrong role → 403 |
| L-2 | A failed login returned **400**, not 401 | Clients could not tell bad input from bad credentials | Security errors carry their real status (401/403/409/413/429) |
| L-3 | Demo passwords in **plain text**; no brute-force protection; no logout | Weak, and an audit finding | PBKDF2 hashes, 5-attempt lockout, token revocation on logout |
| L-4 | The audit trail recorded the `user_id` **sent in the request body** | Anyone could attribute a plan to someone else | The user always comes from the verified token |
| L-5 | **Sanitization middleware did nothing** — Starlette replays the original body, so null bytes and zero-width characters reached the agents | The Student 1 audit relied on it | Rewritten as pure ASGI middleware; plus a 1 MB body limit and control-character check on query parameters |
| L-6 | **No approval step existed**; the frontend called `/api/audit/approve`, which returned 404 | The core "human approves" promise was not met | Pending queue, approve/reject, reasons required, warnings must be acknowledged, 24 h expiry, one decision per plan |
| L-7 | Policy lookups and simulations were logged as **"human approved"** | The audit trail said something untrue | Separate record types and statuses; approval is its own appended record |
| L-8 | Audit trail was "append-only" by convention only | Edits would go unnoticed | Hash chain, DB trigger, `GET /api/audit/verify` |
| L-9 | Rule extractor read **"off-peak … LKR 15" as the peak rate** when Clause 4.2 came first, and never matched "day-time electricity consumption" | Wrong tariff into the solver | Sentence-level extraction that checks off-peak before peak |
| L-10 | A poisoned clause could **set the peak rate to LKR 0.00** | Indirect prompt injection reaching the maths | Plausibility check against a reference PUCSL table; rejects out-of-range values, with warnings |
| L-11 | Agent 3 searched only with the user's words, so tariff figures **silently fell back to constants** | "RAG feeds the solver" was often untrue | Dedicated constraint retrieval; each figure reports whether it was retrieved and from which clause |
| L-12 | Ingesting one document **wiped the keyword index**; re-ingesting **duplicated** clauses; after a restart with pgvector the keyword index was **empty** | Search quality broke after normal use | Incremental BM25, de-duplication, rebuild from the vector store on startup |
| L-13 | Uploads were open to everyone and unscreened | RAG index poisoning (Student 4's topic) | Manager-only; clauses with instruction-like text or implausible figures are quarantined and reported; uploads are audited |
| L-14 | Mock embeddings are random, so hybrid search was **worse than keyword search alone** (MRR 0.61 vs 0.94) | Misleading scores in tests and demos | Dense leg skipped when embeddings carry no meaning; `.env.example` now uses real embeddings |
| L-15 | Analytics **returned hard-coded numbers** (85 %, "variant A") from an in-memory list | Web analytics is a graded module | Persisted events; funnel, A/B test with a two-proportion z-test, intent clusters, citation MRR. Queries and decisions are logged by the server so the browser cannot forge them |
| L-16 | "Forecast only" questions ran the whole pipeline; out-of-scope questions ran it too | Wasted work and confusing results | Five intents, each running only the agents it needs; LLM router for unclear questions, restricted to an allow-list |
| L-17 | "Tomorrow" was hard-coded to 2026-09-07; rooms were a hard-coded list of four (one of which does not exist) | Wrong dates in live use | Relative dates and weekdays; rooms from the room repository; every assumption reported back |
| L-18 | Setpoints between 18 and 30 °C were accepted though the comfort band is 21.0–25.5 °C | A guardrail gap | Clamped to the band from settings, with a note |
| L-19 | The API always sent `perturb_*` defaults, so **"+3 °C heatwave" in the question was ignored** | What-if via the API did not work | Only explicit slider values override the question text |
| L-20 | The orchestrator read `is_feasible`, but Agent 2 returns `is_thermal_feasible` | **Every plan was reported as thermally feasible** | Reads Agent 2's key; comfort violations become plan warnings |
| L-21 | `/api/optimizer/dispatch` used meter-history tariffs and ignored its own inputs, and was never audited | A second, unapproved planning path | It now runs the full pipeline and creates a pending plan |
| L-22 | `USE_REFERENCE_BASELINES` was all-or-nothing | To run Agent 2's baseline, Members 2's and 4's finished code was switched off too | `REFERENCE_BASELINE_AGENTS=agent2` baselines only the unfinished slice |
| L-23 | Member 2's **Postgres meter and timetable repositories** and **forecast summary** existed but were never wired | Agent 1 never read the database; no summary appeared | Wired in the container |
| L-24 | `RERANKER_STRATEGY`, `WEATHER_PROVIDER` and `EMBEDDING_PROVIDER=openai` were accepted but did nothing | Configuration that lies | Implemented or rejected at startup with a clear message |
| L-25 | The application layer imported infrastructure classes directly (against the project's own rule) | Architecture violation in the Lead's own code | Keyword-search interface; everything injected by the container |
| L-26 | Errors could return internal exception text; validation errors echoed the submitted input | Information disclosure | One error envelope for every endpoint, no internals |
| L-27 | The IR benchmark was not part of the test suite | Retrieval regressions went unnoticed | Added as a collected test |

Student 1 red-team tests were updated so their assertions actually run (three of them read fields
from the wrong place and could never fail), and TC-S1-06 / TC-S1-14 now test the new defences.

### Lead items still open

| Item | Note |
|---|---|
| Build the dashboard from the UI/UX spec | Spec section 12 lists what the prototype must change |
| spaCy NER | Optional. Rules + room inventory cover the entities; spaCy is not installed. Decide whether to add it or remove the claim |
| Post-solve comfort verification | Needs Members 3 and 4 first (issue I-1) |
| Live PostgreSQL run | Re-run `backend/data/init.sql` (new audit columns, trigger, `analytics_events` table); Postgres paths are not covered by tests |
| Unused parts | Cache provider, tool registry and `MultiAgentState` are still never used |

---

## 4. Suggestions for each member

These are requests, not edits. Each item names the file so you can find it quickly.

### Member 2 — Agent 1, Telemetry & Forecasting

1. **Update TC-S2-01** (`tests/red_team_security_audits/test_student2_privacy_leakage.py`).
   Your mitigation — route `/api/telemetry/historical` through `get_privacy_protected_export()` — is
   now in place, so the guard fails as you designed. Flip the final assertion to check the fix
   (`not identical_readings`), and record before/after evidence in your report. The response also
   carries the header `X-Privacy-Mechanism: laplace;epsilon=1.0`.
2. **Check the trained forecaster's scale.** For the seed day, the historical peak is 860 kW and the
   baseline forecaster predicts 954 kW, but the trained model predicts about **2,180 kW**. Every plan's
   peak and savings figure depends on this. Check feature units (occupancy counts reach 1,500) and
   report RMSE on the seed day next to the baseline.
3. **`day_of_week=1` is hard-coded** in `src/agents/telemetry/agent.py`. Derive it from the target
   date so Friday uses Friday's timetable.
4. `InMemoryMeterHistoryRepository.get_historical_profile()` ignores the date (same 48 rows for every
   day). Either select the matching day from your 90-day dataset or document the limitation.
5. Agent 1's `tariffs_lkr_kwh` output is no longer used — the orchestrator now takes tariffs from
   Agent 3. Keep it only if you label it "historical billed tariff".
6. Seven to ten of 48 intervals are flagged as anomalies on an ordinary day; consider calibrating the
   threshold so an anomaly means something to the operator.

### Member 3 — Agent 2, Digital Twin

1. **Implement `BuildingThermalTwin.simulate()` and `BatteryDynamicsModel.simulate_soc_trajectory()`**
   (the 5 skipped tests). The demo runs on the baseline until then.
2. **Stop hard-coding 21.0 / 25.5 °C** in `src/agents/digital_twin/agent.py` (lines ~60 and ~71). The
   orchestrator and the what-if route now send `comfort_min_c` and `comfort_max_c` from settings.
3. **Use `target_setpoint_c`** (now sent by the orchestrator). Today Agent 2 treats the setpoint as the
   starting temperature and applies a fixed 35/5 kW cooling curve, which produces about 25 comfort
   violations for *every* plan — so every plan carries a warning the manager must acknowledge. A simple
   thermostat model (cool towards the setpoint within the HVAC limit) would fix this.
4. **Accept a schedule to verify** (`hvac_power_kw` and/or a battery charge/discharge series) and return
   an SOC trajectory with violation count, so the plan can be re-checked after the solver runs (I-1).
5. **Collapse the duplicate physics:** `src/infrastructure/tools/simulation_tool.py` has its own copy.
   Make the tool call your twin so there is exactly one model.
6. **Expose the simulator over MCP.** This is how the project meets the protocol requirement and it is
   your own audit topic. Ask the Lead to add the MCP dependency to `pyproject.toml`.
7. Standardise the feasibility key (`is_thermal_feasible` in the agent vs `is_feasible` in the tool).
   The orchestrator accepts both for now.
8. WIRE-3 from Agent 4: publish `kw_saved_per_degree_c` so Tier 1 flexibility can be modelled.
9. Student 4 audit: the RAG attack surface changed (uploads are manager-only, suspicious clauses are
   quarantined, duplicates skipped, rates range-checked). Re-run your poisoning tests against it; any
   bypass you find is a good finding — report it and the fix lands in the Lead's PR.
10. Remove the duplicate `BuildingThermalTwin` import in `agent.py`.

### Member 4 — Agent 4, Dispatch & Responsible AI

1. **Make the fact-checker fail closed** (`src/agents/dispatch_explanation/faithfulness.py`). When the
   checker's reply is not valid JSON it currently returns `is_faithful: true, confidence: 0.95`. Return
   `is_faithful: false` instead, and add a deterministic check: extract every number from the
   explanation and match it against the solver output and the cited rates. The UI shows a red badge and
   the approval step requires acknowledgement when this fails, so it matters.
2. **Read the inputs the pipeline now sends** in `agent.py` `_run()` and put them on `OptimizationInput`
   (the fields already exist):
   `max_demand_penalty_lkr_kva` → `peak_demand_penalty_lkr_kva`;
   `battery_capacity_kwh`, `max_charge_rate_kw`, `max_discharge_rate_kw`, `initial_soc_ratio`.
   Today the dispatch form's battery settings have no effect, and a revised demand charge in the
   regulations never reaches the solver.
3. **Use `feasibility_verdict`**: when it is false, say so in the explanation rather than describing the
   plan as comfortable.
4. **Tier enforcement.** WIRE-1 (tier load fields) and WIRE-4 (`max_grid_import_kw`) are accepted: the
   fields are on `OptimizationInput`. Build the constraints once D-1 to D-3 are decided; your
   implementation order in `AGENT4_WIRE_REQUESTS.md` is right.
5. Keep explanations plain text (no Markdown links or images); the dashboard renders them as text.
6. Student 3 audit: the dorm/office symmetry test needs the tier-aware solver; plan for it after item 4.

---

## 5. Integration issues between members

| ID | Issue | Effect today | Resolution | Owners |
|---|---|---|---|---|
| **I-1** | Comfort is checked **before** the solver runs, against a default cooling curve, not the plan's own pre-cooling | The comfort verdict is not about the recommended plan; every plan shows a warning | Agent 4 outputs its HVAC/pre-cool schedule; Agent 2 accepts it; the orchestrator adds a "verify plan" step after Agent 4 | M4 → M3 → Lead |
| **I-2** | Agent 4 ignores the demand charge, battery settings and feasibility verdict it receives | Form inputs and retrieved demand charge have no effect | Member 4 item 2–3 | M4 |
| **I-3** | Forecast peak ~2.5× the historical profile | Inflated peaks and savings in every plan | Member 2 item 2 | M2 |
| **I-4** | Comfort limits defined in settings, constants, and hard-coded in Agent 2 | Three sources of truth for a safety rule | Settings are passed in; Agent 2 must read them | M3 |
| **I-5** | `is_thermal_feasible` vs `is_feasible` | Plans were silently marked feasible | Lead reads both now; Member 3 standardises | M3, Lead ✅ |
| **I-6** | Room categories in the room inventory ("Auditorium", "Computer Lab") are not in Agent 4's tier map | Tier classification would raise an error for real rooms | Decision D-2, then the Lead updates the room data | Lead + M4 |
| **I-7** | No per-tier load exists anywhere | Tier constraints have nothing to act on | Decision D-1 | Lead + M2 + M4 |
| **I-8** | Default config crashed every plan while Agent 2 is unimplemented, and the only fix disabled Members 2 and 4 too | Broken demos, or hidden work | `REFERENCE_BASELINE_AGENTS=agent2` in `.env.example` | Lead ✅ |
| **I-9** | TC-S2-01 asserts the old vulnerability | One red test | Member 2 item 1 | M2 |
| **I-10** | The frontend prototype auto-logs in as admin, stores passwords, sends stale fields | Unsafe and now partly incompatible | Rebuild per UI/UX spec section 12 | Lead |
| **I-11** | MCP is claimed but absent | Protocol requirement unmet | Member 3 item 6 | M3 |
| **I-12** | `day_of_week` fixed at 1 | Wrong occupancy on other days | Member 2 item 3 | M2 |

---

## 6. Decisions the team needs to make

| ID | Question | Recommendation |
|---|---|---|
| **D-1** | Where do per-tier loads come from? (WIRE-2) | No sub-metering exists, so use a **documented synthetic split**: each room's category share of campus load from the room inventory. Label it synthetic in code, report and viva. |
| **D-2** | Which tier are "Auditorium" and "Computer Lab"? | **Tier 1** for both (teaching spaces). Keep Tier 0 for research labs, medical rooms and server rooms. The Lead then adds a `tier_category` to each room. |
| **D-3** | Must curtailed Tier 2 energy be recovered within the same day? | **Yes** — shift, don't drop, within the 48-interval horizon. Easier to defend and to test. |
| **D-4** | The SRS claims things the code does not do: TF-IDF + K-Means clustering, mTLS, WebSockets, an *encrypted* audit store | Either implement or reword before the report. Suggested wording: intent-based query clustering; HTTPS at deployment; REST only; hash-chained append-only audit store on encrypted-at-rest Neon storage. |

---

## 7. How to verify

```bash
pytest tests/ -q                      # 136 passed, 5 skipped, 1 known failure (TC-S2-01)
python tests/benchmark_ir_quality.py  # prints the IR table (use EMBEDDING_PROVIDER=sentence_transformers)
uvicorn src.api.main:app --reload     # then GET /api/health → agent_slices, dense_search_enabled
```

The live end-to-end check used for this report: operator logs in → asks "Tomorrow looks hot — precool
Lecture Hall 1 to 23.5 °C and cut the peak demand charge" → plan created with all tariff figures marked
`retrieved` from Clauses 4.1, 4.2 and 6.3 → operator approval attempt returns 403 → manager approval
without acknowledging the comfort warning returns 409 → with acknowledgement returns 200 → audit
verification reports the chain valid.
