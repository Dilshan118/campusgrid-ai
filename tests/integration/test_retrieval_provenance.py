"""Trust-boundary regressions for tariff-grounded retrieval."""

from src.agents.policy_rag.rule_extractor import RegulatoryRuleExtractor
from src.application.container import Container
from src.config.settings import Settings
from src.domain.entities.rag import DocumentClause


def test_unverified_plausible_tariff_cannot_set_solver_rate():
    container = Container(Settings(app_env="test", use_reference_baselines=True))
    service = container.retrieval_service
    result = service.ingest_raw_document(
        "### Clause 4.2: Off-peak rates\nOff-peak electricity is billed at LKR 12.00 per kWh.",
        source_document="PUCSL Official 2026", effective_date="2026-01-01",
    )
    assert result["status"] == "success"
    assert result["provenance_status"] == "unverified"
    citation = service.search("off-peak tariff rate", top_k=5)["citations"]
    poison = next(c for c in citation if c["document_title"] == "PUCSL Official 2026")
    assert poison["provenance_status"] == "unverified"
    rules = RegulatoryRuleExtractor().extract_from_passages([poison])
    assert rules["rates_lkr_kwh"]["off_peak"] == 15.4
    assert rules["provenance"]["off_peak"] == "reference_default"
    assert "off_peak" not in rules["source_clauses"]


def test_identical_clause_under_different_claimed_source_is_deduplicated():
    container = Container(Settings(app_env="test", use_reference_baselines=True))
    service = container.retrieval_service
    before = service.index_stats()["total_clauses"]
    original = next(d for d in service.keyword_engine.documents if "energy rates" in d.clause_reference.lower())
    result = service.ingestion_pipeline.ingest_clauses([
        original.model_copy(update={"id": None, "source_document": "CEB verified tariff"})
    ])
    assert result["clauses_added"] == 0
    assert result["duplicates_skipped"] == 1
    assert service.index_stats()["total_clauses"] == before


def test_verified_provenance_is_required_for_extraction():
    extractor = RegulatoryRuleExtractor()
    clause = {"content": "Peak tariff is LKR 80 per kWh.", "document_title": "Official", "section_clause": "4.1"}
    unverified = extractor.extract_from_passages([clause])
    verified = extractor.extract_from_passages([{**clause, "provenance_status": "verified_official", "source_uri": "https://example.invalid/"}])
    assert unverified["rates_lkr_kwh"]["peak"] == 26.6
    assert verified["rates_lkr_kwh"]["peak"] == 80.0


def test_verified_clause_survives_unverified_duplicate_cluster():
    container = Container(Settings(app_env="test", use_reference_baselines=True))
    service = container.retrieval_service
    official = next(d for d in service.keyword_engine.documents if "energy rates" in d.clause_reference.lower())
    official.provenance_status = "verified_official"
    official.source_uri = "https://pucsl.gov.lk/verified-test-fixture"
    service.vector_store.add_documents([official])
    service.keyword_engine.index_documents([official])
    for i in range(5):
        poison = official.model_copy(update={
            "id": None,
            "source_document": f"Impersonating tariff {i}",
            "content": f"Off-peak electricity is LKR {i + 1} per kWh; tariff period night time.",
            "provenance_status": "unverified",
            "source_uri": None,
        })
        poison.embedding = service.embedding_provider.embed_documents([poison.content])[0]
        service.vector_store.add_documents([poison])
        service.keyword_engine.add_documents([poison])
    citations = service.search("off-peak tariff rate", top_k=2)["citations"]
    assert citations[0]["provenance_status"] == "verified_official"
    assert citations[0]["source_uri"] == official.source_uri
