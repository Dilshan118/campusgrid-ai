# Student 4 Security Audit: Retrieval, Tool and MCP Security

**Project:** CampusGrid AI (IT 3041 IRWA)
**Auditor:** Member 3, Developer 2 (Digital Twin)
**Scope:** the RAG ingestion and retrieval path, the vector store, the digital-twin simulation tool and the MCP tool server.
**Test suite:** `tests/red_team_security_audits/test_student4_retrieval_mcp_security.py` (15 executable cases)
**Environment:** Python 3.14.0, FastAPI 0.141.1, pytest 9.1.1, Windows 11. Branch `feature/dev2-digital-twin-physics`, audited on top of commit `03f172a` plus the mitigations described in section 6.
**Scoring:** CVSS v3.1 base scores, computed with the FIRST specification formula.

> Screenshots: add a screenshot of the `pytest -v` run (section 8) and of the MCP rejection responses before submission. The terminal output itself is saved in `pytest_run.log`, and each case's recorded result is in `evidence/<test_id>.json`.

---

## 1. Summary

Each case sends a real attack at the real production classes (`RetrievalService`, `DocumentIngestionPipeline`, `MemoryVectorStore`, `SimulationTool`, `MCPToolServer`) and asserts on what actually came back. No "actual behaviour" text is written by hand. It is built from the live return values and saved as evidence at run time.

| ID | Finding | CVSS 3.1 | Status |
|---|---|---|---|
| TC-S4-01 | Extreme poisoned tariff is blocked at ingestion | 4.5 Medium (before mitigation) | Mitigated (Team Lead's `ClauseScreener`), verified |
| TC-S4-02 | Poisoned tariff inside the plausible range is accepted and retrieved | 4.5 Medium | **Open**, Team Lead's code |
| TC-S4-03 | Near-duplicate wording scores level with the authentic clause | 2.4 Low | **Open**, Team Lead's code |
| TC-S4-04 | Many near-duplicates crowd the top-k window | 4.5 Medium | **Open**, Team Lead's code |
| TC-S4-05 | Vector store accepts an oversized query vector | 2.3 Low | **Open**, Team Lead's code |
| TC-S4-06 | Wrong-dimension query fails open (similarity 0.0, no error) | 2.3 Low | **Open**, Team Lead's code |
| TC-S4-07 | Impossible temperature over MCP | 6.5 Medium (before mitigation) | Mitigated, verified |
| TC-S4-08 | Impossible HVAC power over MCP | 6.5 Medium (before mitigation) | Mitigated, verified |
| TC-S4-09 | Negative occupancy over MCP | 4.3 Medium (before mitigation) | Mitigated, verified |
| TC-S4-10 | Mismatched series lengths truncated silently | 4.3 Medium (before mitigation) | Mitigated in two layers, verified |
| TC-S4-11 | NaN smuggled through JSON | 5.4 Medium (before mitigation) | Mitigated, verified |
| TC-S4-12 | String in a numeric field crashed the tool | 4.3 Medium (before mitigation) | Mitigated, verified |
| TC-S4-13 | 100,000-interval simulation (compute exhaustion) | 6.5 Medium (before mitigation) | Mitigated, verified |
| TC-S4-14 | Tool-call messages readable on the wire | 3.1 Low | Partly mitigated; confidentiality **open** (needs TLS) |
| TC-S4-15 | Tampered or replayed tool calls executed | 5.3 Medium (before mitigation) | Mitigated in code, verified; HTTP endpoint wiring **pending** |

**Headline result.** Before this audit's final mitigation, a tool call rewritten in transit from 10 kW to 999 kW of cooling was executed without error. It passed every bounds check and drove the simulated room to −15.2 °C. A captured request could also be replayed any number of times. With the new message-integrity guard, the same tampered message is rejected with `Rejected: message signature does not match its contents`, and a replay is rejected with `Rejected: message already processed (replay)`. The genuine message still runs.

---

## 2. Threat model and attack surface

### 2.1 Assets
- **Regulatory knowledge base.** Tariff and PUCSL clauses that Agent 3 retrieves and Agent 4 quotes in its dispatch explanations. A wrong tariff here makes every cost figure and savings claim wrong.
- **Digital twin commands and results.** Temperatures, occupancy and HVAC power passed to the simulation tool, plus the feasibility verdicts it returns. These gate whether a dispatch plan is shown as comfortable.
- **Service availability.** The API, the tool server and the retrieval path.

### 2.2 Trust boundaries and entry points

| Entry point | Who can reach it | Boundary crossed |
|---|---|---|
| `POST /api/rag/ingest` | `FACILITY_MANAGER` role only (JWT) | Uploaded text becomes trusted retrieval content |
| `RetrievalService.search()` (via `/api/rag/query` and the orchestrator) | All authenticated roles | Retrieved text flows into LLM prompts and explanations |
| `MemoryVectorStore.similarity_search()` | Internal: any code path that builds a query vector | Vector math on untrusted dimensions |
| `POST /api/mcp` (JSON-RPC `tools/call`) | `FACILITY_MANAGER` and `OPERATOR` (JWT) | Client arguments execute the physics tool |
| Agent-to-tool message link | Any network position between a caller and the tool host | Messages in transit |

### 2.3 Threat actors
1. **Malicious or compromised document uploader.** Holds, or has stolen, a facility-manager login and uploads a doctored tariff sheet (TC-S4-01 to 04).
2. **Compromised planner account or buggy client.** Sends malformed or extreme tool arguments (TC-S4-07 to 13).
3. **On-path attacker.** A compromised proxy or a shared network segment between an agent and the tool server; reads, alters or replays messages (TC-S4-14, 15).
4. **Internal caller with a bad vector.** A bug or probe sending the wrong embedding size (TC-S4-05, 06).

### 2.4 STRIDE mapping

| STRIDE | Where it applies | Cases |
|---|---|---|
| Spoofing | Unsigned tool calls cannot prove which client sent them | TC-S4-15 |
| Tampering | Poisoned documents; arguments altered in transit | TC-S4-01 to 04, TC-S4-15 |
| Repudiation | Replayed calls are indistinguishable from new ones | TC-S4-15 |
| Information disclosure | Setpoints and occupancy readable on the wire | TC-S4-14 |
| Denial of service | Oversized vectors, oversized horizons, crashing inputs | TC-S4-05, 12, 13 |
| Elevation of privilege | Out-of-envelope commands a real plant should never accept | TC-S4-07 to 11 |

---

## 3. Method

- **Real components, isolated state.** RAG attacks build their own `RetrievalService`, wired exactly as `Container` wires it, so poisoning one test's index cannot leak into other tests. MCP attacks go through `MCPToolServer.handle_request()`, the same method `POST /api/mcp` calls.
- **Mandatory seven fields.** Each case records `test_id`, `test_objective`, `attack_scenario`, `expected_behaviour`, `actual_behaviour`, `evidence_log` and `severity_and_mitigation`. The last three are built from live return values.
- **Two separate checks.** `execute_audit_test_case()` checks the record is complete. A normal `assert` on real values decides pass or fail.
- **Evidence export.** Setting `AUDIT_EVIDENCE_DIR` writes each case, with a timestamp, to `<test_id>.json`. The files in `evidence/` come from the run in section 8.
- **Before and after.** For the mitigations added in this audit, the case runs the attack against the unprotected configuration and against the protected one in the same test. Both results are asserted.
- **Scoring.** CVSS v3.1 base metrics. Where an assessor's contextual view differs (for example, "High at production corpus scale"), it is kept in the case text as a *contextual rating*, but the base score is the rating of record.

---

## 4. Test cases

Every case below quotes its recorded `actual_behaviour`. The full JSON, including `evidence_log`, is in `evidence/`.

### Category A: RAG index poisoning

#### TC-S4-01: Extreme fabricated tariff blocked at ingestion
- **Objective:** Check that an absurd tariff figure submitted through the real ingestion path is caught before it becomes retrievable.
- **Attack scenario:** Upload "CEB_Tariff_2026_Official.pdf", which claims an off-peak rate of LKR 0.05/kWh (the real rate is LKR 15.00), through `RetrievalService.ingest_raw_document()`.
- **Expected behaviour:** Rejected before it is embedded or indexed.
- **Actual behaviour:** `status='rejected'`, reason *"implausible regulatory figures: Retrieved off_peak=0.05 is outside the plausible range [2.0, 100.0]"*. `poisoned_present_in_search=False`.
- **Evidence:** `evidence/TC-S4-01.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:U/C:N/I:H/A:N` = **4.5 Medium** before mitigation
- **Root cause (original):** Ingestion trusted document text without checking its figures.
- **Mitigation:** Team Lead's `ClauseScreener` plausibility check in `src/pipelines/document_ingestion/screening.py`. Verified working; no further action.

#### TC-S4-02: Plausible-range poison bypasses screening
- **Objective:** Check whether the screen catches a wrong figure that still sits inside its numeric range.
- **Attack scenario:** Same path as TC-S4-01, but the fake rate is LKR 8.00, a 47% understatement that is still inside [2, 100].
- **Expected behaviour:** Flagged, or held for source verification.
- **Actual behaviour:** `status='success'`. The poisoned document appears in the top_k=2 window a facility manager reads: `['PUCSL Electricity Tariff Schedule GP-2', 'CEB_Tariff_2026_Official.pdf']`, at rank 2 with score 0.016129, comparable to the authentic clause.
- **Evidence:** `evidence/TC-S4-02.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:U/C:N/I:H/A:N` = **4.5 Medium**
- **Root cause:** Plausibility is treated as trust. Nothing checks where a document came from (publisher, signature or hash).
- **Mitigation (recommended to the Team Lead):** An allow-list of verified sources, or a signature/SHA-256 check against the official PDF, before a clause may outrank or sit beside an authentic one.

### Category B: Embedding collision and cluster manipulation

#### TC-S4-03: Near-duplicate wording scores level with the authentic clause
- **Objective:** Check whether copied wording is enough to score as well as the real clause.
- **Attack scenario:** Index a document that copies the authentic clause word for word except for the price, then re-run the customer query.
- **Expected behaviour:** Attacker content should not score comparably to an authentic source.
- **Actual behaviour:** Authentic score 0.016393; attacker score 0.016129, the same order of magnitude. With the mock embedding provider, BM25 keyword overlap dominates the fused rank.
- **Evidence:** `evidence/TC-S4-03.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:U/C:N/I:L/A:N` = **2.4 Low**
- **Root cause:** Ranking uses text similarity only, with no provenance weighting. The dense channel is inactive under `EMBEDDING_PROVIDER=mock`.
- **Mitigation (recommended):** Real embeddings in any deployment, plus a provenance weight independent of text similarity.

#### TC-S4-04: Cluster crowding of the top-k window
- **Objective:** Check whether several plausible fakes can crowd the small window a manager reads.
- **Attack scenario:** Five near-duplicate off-peak clauses (LKR 6–10), each from a different fake source.
- **Expected behaviour:** The authentic source stays visible, and fakes are distinguishable from it.
- **Actual behaviour:** top_k=2 is `['PUCSL Electricity Tariff Schedule GP-2', 'fake_doc_0.pdf']` (1 of 2 fake). top_k=4 is the authentic clause plus `fake_doc_0`, `fake_doc_1` and `fake_doc_2`.
- **Evidence:** `evidence/TC-S4-04.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:U/C:N/I:H/A:N` = **4.5 Medium**
- **Root cause:** No source-diversity or de-duplication step before ranking.
- **Mitigation (recommended):** Collapse near-identical clauses, and always reserve a top-k slot for a verified source.

### Category C: Vector-store denial of service

#### TC-S4-05: Oversized query vector accepted
- **Objective:** Check whether `similarity_search()` validates the query-vector size.
- **Attack scenario:** A 200,000-float query vector, 520 times the real 384 dimensions.
- **Expected behaviour:** Rejected before any per-document work.
- **Actual behaviour:** Accepted with no validation. 1 result was returned in 0.08 ms against a 1-document corpus. No length check exists in `similarity_search()` or `_cosine_similarity()`.
- **Evidence:** `evidence/TC-S4-05.json`
- **CVSS:** `CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:N/I:N/A:L` = **2.3 Low** (contextual rating High at production corpus scale, because cost grows with corpus size times vector length)
- **Root cause:** No dimension guard at the store boundary.
- **Mitigation (recommended):** Reject any `len(query_vector) != EMBEDDING_DIMENSION` at the top of `similarity_search()`.

#### TC-S4-06: Dimension mismatch fails open
- **Objective:** Check whether a wrong-dimension query is rejected or silently degraded.
- **Attack scenario:** A 10-dimension query against a 384-dimension index.
- **Expected behaviour:** A clear validation error.
- **Actual behaviour:** No exception. It returned 1 result with similarity `[0.0]`, which looks exactly like a genuine "no match".
- **Evidence:** `evidence/TC-S4-06.json`
- **CVSS:** `CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N` = **2.3 Low**
- **Root cause:** Cosine similarity returns 0.0 on mismatched lengths instead of raising an error.
- **Mitigation (recommended):** Raise `ValueError` on mismatch (the same guard as TC-S4-05).

### Category D: MCP tool parameter spoofing

All of these go through `MCPToolServer.handle_request()` with a `tools/call` to `simulate_building_thermal_dynamics`. The mitigation is `SimulationTool._validate_bounds()` in `src/infrastructure/tools/simulation_tool.py`, which runs before any physics.

#### TC-S4-07: Impossible temperature
- **Objective:** The tool enforces physical bounds on temperature.
- **Attack scenario:** `initial_temp_c=-15.0`.
- **Expected behaviour:** Rejected at the boundary.
- **Actual behaviour:** `isError=True`, *"initial_temp_c=-15.0 outside physical envelope [10.0, 45.0]"*.
- **Evidence:** `evidence/TC-S4-07.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N` = **6.5 Medium** before mitigation
- **Root cause (original):** Tool arguments reached the physics unchecked.
- **Mitigation:** A [10, 45] °C envelope on every temperature. Verified.

#### TC-S4-08: Impossible HVAC power
- **Objective:** Reject power beyond any real plant's rating.
- **Attack scenario:** `hvac_power_kw=[5000.0]`.
- **Expected behaviour:** Rejected.
- **Actual behaviour:** `isError=True`, *"hvac_power_kw 5000.0 outside rated plant capacity [0, 1000.0]"*.
- **Evidence:** `evidence/TC-S4-08.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N` = **6.5 Medium** before mitigation
- **Root cause and mitigation:** Same as TC-S4-07; `MAX_HVAC_POWER_KW=1000`. Verified.

#### TC-S4-09: Negative occupancy
- **Objective:** Reject physically meaningless occupancy.
- **Attack scenario:** `occupant_counts=[-999]`.
- **Expected behaviour:** Rejected.
- **Actual behaviour:** `isError=True`, *"occupant_count -999 outside plausible zone capacity [0, 5000]"*.
- **Evidence:** `evidence/TC-S4-09.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N` = **4.3 Medium** before mitigation
- **Mitigation:** Occupancy bounds [0, 5000]. Verified.

#### TC-S4-10: Mismatched series lengths (fixed in this audit round)
- **Objective:** Mismatched arrays must be rejected, not silently truncated by `zip()`.
- **Attack scenario:** `ambient_temps` of length 3 with `occupant_counts` and `hvac_power_kw` of length 1. The same input is also sent straight to the physics model, bypassing the tool.
- **Expected behaviour:** Rejected at both layers.
- **Actual behaviour:** Over MCP: *"ambient_temps, occupant_counts and hvac_power_kw must be equal length (got 3, 1, 1)"*. Model called directly: *"Per-interval series must all be the same length; got ambient_temps=3, occupant_counts=1, hvac_power_kw=1."*
- **Evidence:** `evidence/TC-S4-10.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N` = **4.3 Medium** before mitigation
- **Root cause:** Only the tool checked lengths. Every other caller (the agent, calibration, the what-if API, the battery model) reached `zip()` directly, and a 48-interval forecast paired with a 24-interval plan silently became a 24-interval day.
- **Mitigation (new):** `SeriesLengthMismatchError` in `src/agents/digital_twin/validation.py`, raised by `BuildingThermalTwin.simulate()`, `BatteryDynamicsModel.simulate_soc_trajectory()` and `DigitalTwinAgent`. It is both a `DomainException` (clean API error) and a `ValueError` (MCP `INVALID_PARAMS`).
- **Before and after:** Before the fix, the direct model call returned a 1-interval result. After it, the call raises, as the test asserts.

#### TC-S4-11: NaN injection
- **Objective:** A NaN from the JSON wire format must not slip past the bounds checks.
- **Attack scenario:** Raw JSON with `"initial_temp_c": NaN` (Python's parser accepts it).
- **Expected behaviour:** Rejected.
- **Actual behaviour:** `isError=True`, *"initial_temp_c=nan outside physical envelope [10.0, 45.0]"*.
- **Evidence:** `evidence/TC-S4-11.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:L` = **5.4 Medium** before mitigation
- **Root cause of the risk:** `if x < MIN or x > MAX` never fires for NaN.
- **Mitigation:** Chained `MIN <= x <= MAX`, which is False for NaN. Verified.

#### TC-S4-12: Type confusion (a real bug found by this audit)
- **Objective:** A string in a numeric field must fail gracefully.
- **Attack scenario:** `ambient_temps=["'; DROP TABLE tariffs;--"]`.
- **Expected behaviour:** A controlled error, never an unhandled exception.
- **Actual behaviour:** `isError=True`, *"could not convert string to float"*.
- **Evidence:** `evidence/TC-S4-12.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L` = **4.3 Medium** before mitigation
- **Root cause (found by this audit):** `float()`/`int()` coercion ran before the `try` block, so this payload crashed the tool.
- **Mitigation:** Coercion moved inside the `try` block in `SimulationTool.execute()`. There was no SQL-injection risk: the codebase uses no string-built SQL.

#### TC-S4-13: Compute exhaustion through the horizon
- **Objective:** Reject simulation horizons far beyond the design.
- **Attack scenario:** A 100,000-interval simulation.
- **Expected behaviour:** Rejected.
- **Actual behaviour:** `isError=True`, *"100000 intervals requested, exceeds the 48-interval horizon this pipeline is designed for"*.
- **Evidence:** `evidence/TC-S4-13.json`
- **CVSS:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H` = **6.5 Medium** before mitigation
- **Mitigation:** `MAX_INTERVALS=48` in `_validate_bounds()`. Verified.

### Category E: Interception, tampering and replay

#### TC-S4-14: Tool calls readable on the wire
- **Objective:** Can an on-path attacker read setpoints and occupancy from a captured call?
- **Attack scenario:** Serialize a real `tools/call` exactly as transmitted, before and after message signing, and inspect the bytes.
- **Expected behaviour:** Contents encrypted (TLS) and the message signed.
- **Actual behaviour:** Before: plain JSON with no signature field. After signing: the message carries an HMAC-SHA256 signature, nonce and timestamp (`has_signature=True`), but every argument is still readable (`hvac_power_kw visible=True`).
- **Evidence:** `evidence/TC-S4-14.json`
- **CVSS:** `CVSS:3.1/AV:A/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N` = **3.1 Low**
- **Root cause:** The HTTP transport is not encrypted, and the protocol had no integrity field.
- **Mitigation:** Integrity was added by TC-S4-15's fix. Confidentiality is still **open**: it needs HTTPS or mTLS at a reverse proxy, which is deployment work owned by the Team Lead.

#### TC-S4-15: Tampering and replay (fixed in this audit round)
- **Objective:** Detect a payload altered in transit, or a captured payload sent again, before it runs.
- **Attack scenario:** A legitimate 10 kW call is rewritten to 999 kW, which is inside the 1000 kW cap so bounds checks cannot catch it. Separately, a captured call is re-sent. Both attacks run without the guard and with it.
- **Expected behaviour:** The tampered message is rejected, and the same signed message is never executed twice.
- **Actual behaviour:**
  - *Before:* the tampered 999 kW command executed (`isError=False`), driving the simulated room to −15.22 °C, and the captured request executed 3 times out of 3.
  - *After:* tampered → `{'code': -32001, 'message': 'Rejected: message signature does not match its contents'}`; genuine → `isError=False`; replay → `{'code': -32001, 'message': 'Rejected: message already processed (replay)'}`.
- **Evidence:** `evidence/TC-S4-15.json`
- **CVSS:** `CVSS:3.1/AV:A/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:N` = **5.3 Medium** before mitigation
- **Root cause:** JSON-RPC carries no proof of origin or freshness. Bounds checks judge whether a value is possible, not whether it is the value the client sent.
- **Mitigation (new):** `src/agents/digital_twin/mcp_integrity.py`, enforced in `MCPToolServer.handle_request()` before any dispatch:
  - an HMAC-SHA256 over the canonical request (sorted keys, no whitespace), keyed by `key_id` so keys can rotate;
  - a 300-second timestamp window;
  - a single-use nonce, remembered only while its timestamp could still pass;
  - a constant-time signature comparison;
  - a nonce table that is bounded and fails closed when full.

  The block lives in `params._meta`, the place MCP reserves for metadata. Unit tests cover stale and future timestamps, forged and unknown keys, a tampered method, malformed blocks, nonce expiry, a full nonce table, and unsigned notifications.
- **Residual:** The guard is opt-in. `POST /api/mcp` enables it once the Team Lead adds signing keys to `settings.py` and passes a `MessageIntegrityGuard` in `container.py`, both of which are lead-owned files. A request has been raised.

---

## 5. Risk matrix

Likelihood reflects the preconditions each attack needs (role, network position, knowledge). Impact follows the CVSS impact metrics.

| Likelihood ↓ / Impact → | Low | Medium | High |
|---|---|---|---|
| **High** | | | |
| **Medium** | TC-S4-03 | | **TC-S4-02, TC-S4-04** |
| **Low** | TC-S4-05, TC-S4-06, TC-S4-14 | | TC-S4-15 (residual until wired) |

The mitigated and verified cases (TC-S4-01, 07 to 13, and TC-S4-15 in code) sit at **residual Low**. They are left out of the grid.

**Priorities:** (1) provenance checks for regulatory documents (TC-S4-02, 04); (2) wiring MCP signing keys and TLS (TC-S4-15, 14); (3) the vector-store dimension guard (TC-S4-05, 06).

---

## 6. Mitigations and code references

| Case | Change | Location | Owner |
|---|---|---|---|
| TC-S4-07 to 09, 11, 13 | Physical-envelope and horizon bounds | `src/infrastructure/tools/simulation_tool.py` (`_validate_bounds`) | Dev 2 |
| TC-S4-12 | Coercion moved inside `try` | `src/infrastructure/tools/simulation_tool.py` (`execute`) | Dev 2 |
| TC-S4-10 | Length checks in the model, battery and agent | `src/agents/digital_twin/validation.py`, `thermal_model.py`, `battery_dynamics.py`, `agent.py` | Dev 2 |
| TC-S4-15 | HMAC, nonce and timestamp message integrity | `src/agents/digital_twin/mcp_integrity.py`, `mcp_server.py` | Dev 2 |
| TC-S4-01 | Clause plausibility screening | `src/pipelines/document_ingestion/screening.py` | Team Lead |
| TC-S4-02 to 06, 14 | Recommendations filed | see each case | Team Lead |

Commit hashes: *add the hashes of the mitigation commits here once they are pushed.*

---

## 7. Limitations
- **Mock embeddings.** RAG cases use `MockEmbeddingProvider`, as the test configuration does, so the dense channel carries no semantic signal. TC-S4-03's result depends on that. Re-running against real embeddings is recommended.
- **In-process transport.** The tool server runs in-process in the tests; the HTTP route passes the same messages to the same method. TC-S4-14's network exposure is assessed, not captured with a sniffer.
- **Base scores only.** CVSS scores are base scores. Environmental factors (for example, a larger production corpus) are noted as contextual ratings in the cases.

---

## 8. Reproducing the evidence

```bash
# All 15 cases, with a JSON evidence file per case
AUDIT_EVIDENCE_DIR=security_reports/student4_retrieval_tool_mcp/evidence \
  pytest tests/red_team_security_audits/test_student4_retrieval_mcp_security.py -v

# Unit tests for the mitigations (integrity guard, length validation, and more)
pytest tests/unit/test_member3_digital_twin.py -v -k "integrity or mismatched"
```

Recorded run (`pytest_run.log`): **15 passed**.
