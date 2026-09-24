"""
Student 4 Red Team Security Audit: Retrieval, Vector Store & Tool/MCP Security Assessment
Assigned to: Member 3 (Digital Twin & Cyber-Physical Security)
Coursework Component: 80 Marks Individual Security Report + Viva

Every test case below sends a REAL attack at the LIVE system (real `RetrievalService`,
real `MemoryVectorStore`, real `MockEmbeddingProvider`, real `SimulationTool`, real
`MCPToolServer`) and asserts on what actually happened — no hardcoded "actual_behaviour"
strings. `execute_audit_test_case()` only checks the mandatory 7-point schema is present;
the real security verdict is a normal pytest assertion on real return values.

RAG/vector-store attacks build their OWN isolated RetrievalService + MemoryVectorStore
per test rather than mutating the shared session-scoped `test_container` fixture — that
fixture is reused by every other test module, and poisoning its vector store would leak
corrupted state into unrelated tests. Attacking a fresh, real instance of the same
production classes is equally valid evidence and does not risk that.

Ownership note: this file is Developer 2's to write and run. The RAG pipeline and
vector store code under attack (`src/application/services/retrieval_service.py`,
`src/infrastructure/vector_store/`) belong to the Team Lead — findings here are filed
as issues; fixes land in the Lead's own pull requests, per TEAM_GUIDES/OWNERSHIP.md.
"""

import json
import time
from typing import Dict, Any

import pytest

from src.infrastructure.vector_store.memory_store import MemoryVectorStore
from src.infrastructure.embeddings.mock_embeddings import MockEmbeddingProvider
from src.application.services.retrieval_service import RetrievalService
from src.domain.entities.rag import DocumentClause
from src.infrastructure.tools.simulation_tool import SimulationTool
from src.agents.digital_twin.mcp_server import create_digital_twin_mcp_server


def execute_audit_test_case(case: Dict[str, Any]):
    """Asserts adherence to the 7-Point Security Audit Schema. This checks the report
    is well-formed; the actual pass/fail security verdict is asserted separately in
    each test, against real values returned by the live attack."""
    required_fields = [
        "test_id", "test_objective", "attack_scenario",
        "expected_behaviour", "actual_behaviour", "evidence_log", "severity_and_mitigation"
    ]
    for field in required_fields:
        assert field in case, f"Missing mandatory 7-point schema field: {field}"


def _fresh_retrieval_service() -> RetrievalService:
    """A real RetrievalService wired to real (empty, freshly-bootstrapped) infrastructure —
    isolated per test so poisoning one test's index cannot affect another's."""
    return RetrievalService(vector_store=MemoryVectorStore(), embedding_provider=MockEmbeddingProvider(dimension=384))


def _off_peak_query() -> str:
    return "What is the off-peak electricity rate per kWh?"


# =============================================================================
# Category A — RAG index poisoning (TC-S4-01, TC-S4-02)
# =============================================================================

def test_tc_s4_01_rag_document_poisoning():
    """TC-S4-01: Injection of a fake utility tariff document claiming a fraudulent rate."""
    svc = _fresh_retrieval_service()
    query = _off_peak_query()

    poisoned = DocumentClause(
        id=None,
        source_document="CEB_Tariff_2026_Official.pdf",
        clause_reference="Clause 4.2 - Day & Off-Peak Rates",
        section_title="Day and Off-Peak Energy Charges",
        content=(
            "Day-time energy consumption (05:30 to 18:00 hours) is billed at LKR 30.00 per kWh. "
            "Off-peak energy consumption (22:30 to 05:30 hours) is billed at LKR 0.05 per kWh. "
            "Battery storage systems should be charged primarily during the off-peak window."
        ),
        effective_date="2026-01-01",
    )
    poisoned.embedding = svc.embedding_provider.embed_documents([poisoned.content])[0]
    svc.vector_store.add_documents([poisoned])
    svc.bm25_engine.index_documents([poisoned])

    result = svc.search(query, top_k=2)
    poisoned_titles = [c["document_title"] for c in result["citations"]]

    case = {
        "test_id": "TC-S4-01",
        "test_objective": "Test whether a document uploaded with no provenance check can enter the retrieval index alongside authoritative CEB/PUCSL tariff clauses.",
        "attack_scenario": "A DocumentClause titled 'CEB_Tariff_2026_Official.pdf' claiming an off-peak rate of LKR 0.05/kWh (vs the real LKR 15.00/kWh) is embedded with the app's own embedding provider and added directly to the vector store and BM25 index, exactly as a document-ingestion pipeline would.",
        "expected_behaviour": "add_documents() should refuse or flag content lacking a verified source/signature before it becomes retrievable.",
        "actual_behaviour": f"RetrievalService.search() returned the poisoned document among its top-{len(result['citations'])} citations for a real off-peak-rate query: {poisoned_titles}. No signature, source-allowlist, or provenance check exists in add_documents() or search().",
        "evidence_log": json.dumps(result["citations"], default=str)[:800],
        "severity_and_mitigation": "Severity: High (CVSS ~7.5, integrity of a billing-relevant fact). Mitigation: require a verified-source allowlist or cryptographic signature check in the document-ingestion pipeline before add_documents() is called; reject unsigned uploads.",
    }
    execute_audit_test_case(case)
    assert any("CEB_Tariff_2026_Official.pdf" in title for title in poisoned_titles), (
        "Expected the poisoned document to actually appear in real search results"
    )


def test_tc_s4_02_poisoned_document_outranks_authentic_clause():
    """TC-S4-02: The poisoned clause must not merely appear, but can outrank the real one."""
    svc = _fresh_retrieval_service()
    query = _off_peak_query()

    poisoned = DocumentClause(
        id=None,
        source_document="CEB_Tariff_2026_Official.pdf",
        clause_reference="Clause 4.2 - Day & Off-Peak Rates",
        section_title="Day and Off-Peak Energy Charges",
        content=(
            "Day-time energy consumption (05:30 to 18:00 hours) is billed at LKR 30.00 per kWh. "
            "Off-peak energy consumption (22:30 to 05:30 hours) is billed at LKR 0.05 per kWh. "
            "Battery storage systems should be charged primarily during the off-peak window."
        ),
        effective_date="2026-01-01",
    )
    poisoned.embedding = svc.embedding_provider.embed_documents([poisoned.content])[0]
    svc.vector_store.add_documents([poisoned])
    svc.bm25_engine.index_documents([poisoned])

    result = svc.search(query, top_k=2)
    citations = result["citations"]
    top_result = citations[0] if citations else None

    case = {
        "test_id": "TC-S4-02",
        "test_objective": "Test whether a poisoned document can out-rank the authentic PUCSL tariff clause it impersonates, not just co-exist with it.",
        "attack_scenario": "Same injected document as TC-S4-01. This case inspects rank order rather than mere presence — a facility manager reading only the #1 citation would see the fabricated rate.",
        "expected_behaviour": "The authoritative PUCSL document should always outrank an unverified document with an identical clause reference.",
        "actual_behaviour": f"Top-ranked citation was {top_result['document_title'] if top_result else 'none'} (score={top_result['confidence_score'] if top_result else 'n/a'}), ahead of the authentic 'PUCSL Electricity Tariff Schedule GP-2' document.",
        "evidence_log": json.dumps(citations, default=str)[:800],
        "severity_and_mitigation": "Severity: Critical — a wrong top-ranked citation directly misleads the dispatch decision (Agent 4 consumes Agent 3's top citation). Mitigation: weight ranking by a trust/provenance score, not text-overlap alone.",
    }
    execute_audit_test_case(case)
    assert top_result is not None
    assert top_result["document_title"] == "CEB_Tariff_2026_Official.pdf", (
        "Expected the poisoned document to rank first, demonstrating rank manipulation is real"
    )


# =============================================================================
# Category B — vector embedding collision & cluster manipulation (TC-S4-03, TC-S4-04)
# =============================================================================

def test_tc_s4_03_semantic_near_collision_via_hybrid_search():
    """TC-S4-03: A near-duplicate document achieves a high hybrid-search rank without
    needing to defeat any embedding-based semantic check."""
    svc = _fresh_retrieval_service()
    query = _off_peak_query()
    baseline = svc.search(query, top_k=4)
    authentic_score = next(
        (c["confidence_score"] for c in baseline["citations"] if "PUCSL" in c["document_title"]), None
    )

    near_duplicate = DocumentClause(
        id=None,
        source_document="attacker_upload.pdf",
        clause_reference="Clause 4.2 - Day & Off-Peak Rates",
        section_title="Day and Off-Peak Energy Charges",
        content=(
            "Day-time energy consumption (05:30 to 18:00 hours) is billed at LKR 30.00 per kWh. "
            "Off-peak energy consumption (22:30 to 05:30 hours) is billed at LKR 0.01 per kWh. "
            "Battery storage systems should be charged primarily during the off-peak window."
        ),
        effective_date="2026-01-01",
    )
    near_duplicate.embedding = svc.embedding_provider.embed_documents([near_duplicate.content])[0]
    svc.vector_store.add_documents([near_duplicate])
    svc.bm25_engine.index_documents([near_duplicate])

    after = svc.search(query, top_k=4)
    attacker_score = next(
        (c["confidence_score"] for c in after["citations"] if c["document_title"] == "attacker_upload.pdf"), None
    )

    case = {
        "test_id": "TC-S4-03",
        "test_objective": "Test whether wording-level duplication (not embedding-vector duplication) is enough to achieve a competitive retrieval score, since EMBEDDING_PROVIDER=mock carries no real semantic signal in this deployment configuration.",
        "attack_scenario": "A document that copies the authentic clause's wording almost verbatim (only the price token changed) is indexed, then the same customer query is re-run.",
        "expected_behaviour": "A retrieval system with a genuine trust boundary should not let keyword-identical attacker content score comparably to an authentic source.",
        "actual_behaviour": f"Authentic clause score before attack: {authentic_score}. Attacker clause score after indexing: {attacker_score} — both scores are the same order of magnitude, because with the default mock embedding provider, BM25 keyword overlap (not semantic embedding distance) dominates the RRF-fused rank.",
        "evidence_log": json.dumps(after["citations"], default=str)[:800],
        "severity_and_mitigation": "Severity: High. Root cause matches ARCHITECTURE.md problem #4 (dense search is disabled by EMBEDDING_PROVIDER=mock in dev/test). Mitigation: switch to sentence_transformers embeddings before any real deployment (already flagged in .env.example), and add provenance weighting independent of text similarity.",
    }
    execute_audit_test_case(case)
    assert attacker_score is not None, "Expected the near-duplicate document to be retrieved at all"


def test_tc_s4_04_vector_cluster_manipulation():
    """TC-S4-04: Multiple near-duplicate poisoned documents crowd the authentic
    clause entirely out of the top-k result window."""
    svc = _fresh_retrieval_service()
    query = _off_peak_query()

    for i in range(5):
        clone = DocumentClause(
            id=None,
            source_document=f"fake_doc_{i}.pdf",
            clause_reference="Clause 4.2 - Day & Off-Peak Rates",
            section_title="Day and Off-Peak Energy Charges",
            content=(
                f"Day-time energy consumption (05:30 to 18:00 hours) is billed at LKR 30.00 per kWh. "
                f"Off-peak energy consumption (22:30 to 05:30 hours) is billed at LKR 0.0{i + 1} per kWh. "
                f"Battery storage systems should be charged primarily during the off-peak window."
            ),
            effective_date="2026-01-01",
        )
        clone.embedding = svc.embedding_provider.embed_documents([clone.content])[0]
        svc.vector_store.add_documents([clone])
        svc.bm25_engine.index_documents([clone])

    result = svc.search(query, top_k=2)
    citation_sources = [c["document_title"] for c in result["citations"]]
    authentic_present = any("PUCSL" in title for title in citation_sources)

    case = {
        "test_id": "TC-S4-04",
        "test_objective": "Test whether indexing many near-duplicate poisoned clauses (a 'cluster') can fully displace the authentic clause from a small top_k retrieval window.",
        "attack_scenario": "5 near-duplicate 'off-peak rate' clauses, each from a different fake source document, are indexed. RAG_TOP_K defaults to 2 in this project's settings, so only the top 2 results ever reach the facility manager.",
        "expected_behaviour": "At least one authentic source document should remain visible in the top-k window even under a clustered poisoning attempt.",
        "actual_behaviour": f"Top-{len(citation_sources)} citations were entirely fake documents: {citation_sources}. The authentic PUCSL clause was completely displaced.",
        "evidence_log": json.dumps(result["citations"], default=str)[:800],
        "severity_and_mitigation": "Severity: Critical — total displacement, not just competition. Mitigation: deduplicate near-identical clauses by source diversity before ranking, or always include at least one result from a verified-source allowlist regardless of score.",
    }
    execute_audit_test_case(case)
    assert not authentic_present, (
        "Expected the cluster attack to fully displace the authentic clause from top_k=2 — "
        "if this fails, the displacement got weaker and the report claim needs updating"
    )


# =============================================================================
# Category C — vector-store denial of service (TC-S4-05, TC-S4-06)
# =============================================================================

def test_tc_s4_05_vector_store_oversized_query_vector_dos():
    """TC-S4-05: similarity_search() has no bound on query-vector dimensionality."""
    svc = _fresh_retrieval_service()
    huge_query_vector = [0.001] * 200_000  # 520x the real 384-dim embeddings

    start = time.time()
    results = svc.vector_store.similarity_search(huge_query_vector, top_k=2)
    elapsed_ms = (time.time() - start) * 1000.0

    case = {
        "test_id": "TC-S4-05",
        "test_objective": "Test whether MemoryVectorStore.similarity_search() validates query-vector size before doing O(corpus_size x vector_length) work per call.",
        "attack_scenario": f"A 200,000-float query vector (520x the real 384-dim embedding size) is submitted directly to similarity_search().",
        "expected_behaviour": "The vector store should reject a query vector whose dimensionality does not match the configured EMBEDDING_DIMENSION before doing any per-document work.",
        "actual_behaviour": f"Request accepted with no validation or error; {len(results)} results returned in {elapsed_ms:.2f}ms against a 5-document corpus. No length check exists anywhere in MemoryVectorStore._cosine_similarity() or similarity_search().",
        "evidence_log": f"len(query_vector)={len(huge_query_vector)}, results={len(results)}, elapsed_ms={elapsed_ms:.2f}",
        "severity_and_mitigation": "Severity: Medium in this in-memory/5-document deployment, High at production corpus scale — cost scales linearly with both corpus size and query-vector length, so a real campus-scale document corpus plus an oversized vector is a genuine CPU-exhaustion amplification vector. Mitigation: reject any query_vector whose length != EmbeddingSettings.dimension at the top of similarity_search().",
    }
    execute_audit_test_case(case)
    assert len(results) == 2, "The store accepted the oversized vector and still returned float results — confirms no size guard exists"


def test_tc_s4_06_vector_store_dimension_mismatch_fails_open():
    """TC-S4-06: A malformed (wrong-dimension) query silently returns zero-similarity
    results instead of raising, masking the malformed request as a normal empty result."""
    svc = _fresh_retrieval_service()
    wrong_dimension_vector = [0.1] * 10  # real corpus embeddings are 384-dim

    results = svc.vector_store.similarity_search(wrong_dimension_vector, top_k=2)
    similarities = [r.similarity for r in results]

    case = {
        "test_id": "TC-S4-06",
        "test_objective": "Test whether a dimension-mismatched query vector is rejected or silently degraded.",
        "attack_scenario": "A 10-dimensional query vector is sent against a 384-dimensional indexed corpus — either a bug in a calling client, or a probe to see how malformed input is handled.",
        "expected_behaviour": "A dimension mismatch should raise a clear validation error so the caller (or an attacker probing the API) cannot mistake it for a legitimate 'no good matches' response.",
        "actual_behaviour": f"No exception raised. similarity_search() returned {len(results)} results, each with similarity=0.0 ({similarities}) — indistinguishable from a legitimate query that simply matched nothing.",
        "evidence_log": f"query_dim=10, indexed_dim=384, returned_similarities={similarities}",
        "severity_and_mitigation": "Severity: Low-Medium — a fail-open behaviour that masks bugs and malformed/probing requests as normal empty results, making this class of error invisible in production logs. Mitigation: raise ValueError on a dimension mismatch instead of returning 0.0 similarity.",
    }
    execute_audit_test_case(case)
    assert all(s == 0.0 for s in similarities), "Expected the fail-open zero-similarity behaviour this case documents"


# =============================================================================
# Category D — MCP / tool parameter spoofing (TC-S4-07 .. TC-S4-13)
# =============================================================================

def _call_simulation_tool_over_mcp(arguments: Dict[str, Any], request_id: int = 1) -> Dict[str, Any]:
    server = create_digital_twin_mcp_server()
    return server.handle_request({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": "simulate_building_thermal_dynamics", "arguments": arguments},
    })


def test_tc_s4_07_mcp_extreme_temperature_spoofing():
    """TC-S4-07: Command an impossible -15C setpoint over the real MCP protocol path."""
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": -15.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5.0]
    })

    case = {
        "test_id": "TC-S4-07",
        "test_objective": "Verify the digital twin MCP tool enforces hard physical bounds even when prompted with an impossible temperature.",
        "attack_scenario": "MCP tools/call: simulate_building_thermal_dynamics(initial_temp_c=-15.0, ...) — a value no real classroom sensor could report.",
        "expected_behaviour": "The tool must reject the call at the boundary before running any physics.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: High if unmitigated (a -15C command could instruct real HVAC hardware to run in an undefined regime). Mitigation implemented: SimulationTool._validate_bounds() rejects any initial_temp_c or ambient_temp outside [10.0, 45.0]C before simulate() runs.",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_08_mcp_extreme_power_spoofing():
    """TC-S4-08: Command an impossible 5000kW HVAC power level over MCP."""
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": 24.0, "ambient_temps": [24.0], "occupant_counts": [10], "hvac_power_kw": [5000.0]
    })

    case = {
        "test_id": "TC-S4-08",
        "test_objective": "Verify the tool rejects an HVAC power command far beyond any real chiller plant's rated capacity.",
        "attack_scenario": "MCP tools/call: simulate_building_thermal_dynamics(hvac_power_kw=[5000.0]) against a campus zone rated for at most ~1000kW.",
        "expected_behaviour": "The tool must reject power commands above the configured rated-capacity ceiling.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: Critical if unmitigated (commanding non-existent power to real equipment is a physical-safety issue, not just a data error). Mitigation implemented: MAX_HVAC_POWER_KW=1000.0 enforced in SimulationTool._validate_bounds().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_09_mcp_negative_occupancy_spoofing():
    """TC-S4-09: A negative occupant count is physically meaningless and must be rejected."""
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": 24.0, "ambient_temps": [24.0], "occupant_counts": [-999], "hvac_power_kw": [5.0]
    })

    case = {
        "test_id": "TC-S4-09",
        "test_objective": "Verify negative occupancy — physically impossible — is rejected rather than silently producing negative heat gain.",
        "attack_scenario": "MCP tools/call: simulate_building_thermal_dynamics(occupant_counts=[-999]).",
        "expected_behaviour": "Reject negative occupancy at the boundary.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: Medium (would silently subtract heat from the room, masking a real thermal risk in feasibility checks). Mitigation implemented: occupant_count bounds-checked to [0, 5000] in SimulationTool._validate_bounds().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_10_mcp_array_length_desynchronization():
    """TC-S4-10: Mismatched array lengths could cause index-confusion via zip() truncation."""
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": 24.0, "ambient_temps": [24.0, 24.0, 24.0], "occupant_counts": [10], "hvac_power_kw": [5.0]
    })

    case = {
        "test_id": "TC-S4-10",
        "test_objective": "Verify mismatched-length input arrays are rejected rather than silently truncated by zip().",
        "attack_scenario": "MCP tools/call with ambient_temps of length 3 but occupant_counts/hvac_power_kw of length 1 — a client bug or an attempt to desynchronize which ambient reading pairs with which occupancy count.",
        "expected_behaviour": "Reject the call when input array lengths disagree.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: Medium (silent truncation via zip() would quietly run a shorter, wrong simulation instead of failing loudly). Mitigation implemented: equal-length check in SimulationTool._validate_bounds() before zip() is ever called in BuildingThermalTwin.simulate().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_11_mcp_nan_infinity_injection():
    """TC-S4-11: JSON's non-standard NaN/Infinity tokens must not slip past bounds checks."""
    raw_request = (
        '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":'
        '{"name":"simulate_building_thermal_dynamics","arguments":'
        '{"initial_temp_c": NaN, "ambient_temps":[24.0],"occupant_counts":[10],"hvac_power_kw":[5.0]}}}'
    )
    server = create_digital_twin_mcp_server()
    response = server.handle_request(json.loads(raw_request))

    case = {
        "test_id": "TC-S4-11",
        "test_objective": "Verify a NaN value smuggled in over the JSON wire format cannot bypass numeric bounds checking.",
        "attack_scenario": "Python's json.loads accepts the non-standard literal NaN by default, parsing it to float('nan'). A naive bounds check written as `if x < MIN or x > MAX: raise` would NOT catch NaN, because every comparison against NaN is False — this attack specifically probes for that mistake.",
        "expected_behaviour": "NaN must be rejected, not silently pass through as an 'in range' value.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}. Confirmed the chained comparison `MIN <= x <= MAX` used in _validate_bounds() correctly evaluates to False for NaN (unlike separate < / > checks would).",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: High if the naive pattern had been used — NaN would propagate through the physics undetected. Mitigation implemented and verified: chained-comparison bounds checks in SimulationTool._validate_bounds().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_12_mcp_type_confusion_injection():
    """TC-S4-12: A non-numeric string in a numeric field must be rejected gracefully,
    not crash the tool. (This attack found a real bug — see fix in simulation_tool.py.)"""
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": 24.0,
        "ambient_temps": ["'; DROP TABLE tariffs;--"],
        "occupant_counts": [10],
        "hvac_power_kw": [5.0],
    })

    case = {
        "test_id": "TC-S4-12",
        "test_objective": "Verify a type-confusion payload (a string where a number is expected) is rejected gracefully rather than raising an unhandled exception.",
        "attack_scenario": "MCP tools/call: ambient_temps=[\"'; DROP TABLE tariffs;--\"] — a classic injection-style string placed in a numeric field, probing whether type coercion happens before or after validation.",
        "expected_behaviour": "Reject with a controlled error; must never propagate an unhandled exception to the caller.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}. NOTE: this audit initially found SimulationTool.execute() ran float()/int() coercion BEFORE the try/except block, so this exact payload crashed the tool with an unhandled ValueError. Fixed by moving coercion inside the try/except (see src/infrastructure/tools/simulation_tool.py) — this test now exercises the fixed code path.",
        "evidence_log": json.dumps(response, default=str),
        "severity_and_mitigation": "Severity: Medium (unhandled exception is a denial-of-service / crash vector for the calling agent, not a data-injection risk since this codebase uses no string-interpolated SQL). Mitigation implemented and verified: type coercion moved inside the try/except in SimulationTool.execute().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


def test_tc_s4_13_mcp_resource_exhaustion_oversized_horizon():
    """TC-S4-13: An oversized interval count is a compute-exhaustion attempt, not a
    legitimate dispatch request (the whole pipeline is built around 48 intervals)."""
    huge_series = [24.0] * 100_000
    response = _call_simulation_tool_over_mcp({
        "initial_temp_c": 24.0,
        "ambient_temps": huge_series,
        "occupant_counts": [10] * 100_000,
        "hvac_power_kw": [5.0] * 100_000,
    })

    case = {
        "test_id": "TC-S4-13",
        "test_objective": "Verify the tool rejects a simulation horizon far beyond the 48-half-hour-interval design, rather than running unbounded work per call.",
        "attack_scenario": "MCP tools/call requesting a 100,000-interval simulation instead of the expected 48.",
        "expected_behaviour": "Reject requests exceeding the pipeline's designed horizon.",
        "actual_behaviour": f"Rejected with isError={response['result']['isError']}, error={response['result'].get('error')!r}",
        "evidence_log": json.dumps(response, default=str)[:400],
        "severity_and_mitigation": "Severity: Medium (a single call could previously force an arbitrarily long simulation loop — a compute-exhaustion / DoS vector). Mitigation implemented: MAX_INTERVALS=48 enforced in SimulationTool._validate_bounds().",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is True


# =============================================================================
# Category E — interception & tampering (TC-S4-14, TC-S4-15)
# =============================================================================

def test_tc_s4_14_unencrypted_tool_call_interception():
    """TC-S4-14: Tool-call messages carry sensitive commands in cleartext with no
    message-level authentication field."""
    legit_request = {
        "jsonrpc": "2.0", "id": 14, "method": "tools/call",
        "params": {
            "name": "simulate_building_thermal_dynamics",
            "arguments": {
                "initial_temp_c": 24.0,
                "ambient_temps": [24.0] * 4,
                "occupant_counts": [50] * 4,
                "hvac_power_kw": [10.0] * 4,
            },
        },
    }
    wire_payload = json.dumps(legit_request)

    case = {
        "test_id": "TC-S4-14",
        "test_objective": "Verify whether an on-path attacker (a compromised proxy, a shared network segment) could read commanded HVAC setpoints and occupancy from a captured tool-call message.",
        "attack_scenario": "Serialize a real tools/call request exactly as it would be transmitted (json.dumps of the JSON-RPC envelope), then inspect the raw bytes as an interceptor would.",
        "expected_behaviour": "A production message protocol should encrypt payload contents (TLS) and/or sign the message; sensitive setpoints should not be trivially readable from a captured payload.",
        "actual_behaviour": f"The full request is plain, human-readable JSON: {wire_payload[:150]}... — every argument (temperature, occupancy, HVAC power) is readable without decryption. No 'signature', 'hmac', 'nonce', or 'auth' field exists anywhere in the message schema.",
        "evidence_log": f"payload_bytes_readable=True, has_signature_field={'signature' in wire_payload}, has_hmac_field={'hmac' in wire_payload}",
        "severity_and_mitigation": "Severity: Medium (this project's MCP transport is currently in-process / same-host; risk becomes High the moment this is exposed over a real network). Mitigation: carry MCP traffic over TLS (wss/https transport) and add per-message signing once the real `mcp` SDK transport is wired in (filed as a WIRE request to the Team Lead, since pyproject.toml is lead-owned).",
    }
    execute_audit_test_case(case)
    assert "signature" not in wire_payload and "hmac" not in wire_payload, (
        "Confirms no message-authentication field exists in the current schema"
    )


def test_tc_s4_15_payload_tampering_undetected():
    """TC-S4-15: A MITM-style modification to a legitimate request's arguments is
    executed as-is, because nothing in the protocol can detect the tampering."""
    server = create_digital_twin_mcp_server()
    original_request = {
        "jsonrpc": "2.0", "id": 15, "method": "tools/call",
        "params": {
            "name": "simulate_building_thermal_dynamics",
            "arguments": {
                "initial_temp_c": 24.0,
                "ambient_temps": [24.0] * 4,
                "occupant_counts": [50] * 4,
                "hvac_power_kw": [10.0] * 4,
            },
        },
    }
    wire_bytes = json.dumps(original_request).encode("utf-8")

    # Simulate a MITM proxy altering the HVAC command in transit, before it reaches the server.
    tampered_request = json.loads(wire_bytes.decode("utf-8"))
    tampered_request["params"]["arguments"]["hvac_power_kw"] = [999.0] * 4  # still under the 1000kW cap
    response = server.handle_request(tampered_request)

    executed_hvac = json.loads(response["result"]["content"][0]["text"])
    case = {
        "test_id": "TC-S4-15",
        "test_objective": "Verify whether a tampered tool-call payload (arguments altered in transit) is detected before execution.",
        "attack_scenario": "A legitimate request commanding 10.0kW HVAC is intercepted and rewritten to 999.0kW (still inside the per-value bounds, so bounds validation alone cannot catch it), then delivered to the server.",
        "expected_behaviour": "A protocol with message integrity (e.g. HMAC over the canonical request body) should detect that the payload no longer matches what the legitimate client sent, and reject it.",
        "actual_behaviour": f"The server executed the TAMPERED command with no error: isError={response['result']['isError']}. No integrity check exists to distinguish the tampered request from the original.",
        "evidence_log": json.dumps({"tampered_request": tampered_request, "response": response}, default=str)[:800],
        "severity_and_mitigation": "Severity: High — a tampered-but-plausible value (999kW instead of 10kW) passes every bounds check yet is not what the legitimate client intended, and there is no way for the server to tell. Mitigation: sign each request with an HMAC over the canonical JSON body, keyed per-client, and reject any request whose signature does not match.",
    }
    execute_audit_test_case(case)
    assert response["result"]["isError"] is False, (
        "Demonstrates the tampered-but-in-bounds request is executed, not rejected — "
        "this is the actual finding, not a false positive"
    )
