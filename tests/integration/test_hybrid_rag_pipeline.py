"""
Integration test for Hybrid RAG Pipeline: Dense Vector + Sparse BM25 + Reciprocal Rank Fusion.
"""

def test_hybrid_rag_end_to_end(test_container):
    service = test_container.retrieval_service

    # Query for peak tariff rates
    result = service.search(query="peak tariff hours and CEB rates in LKR", top_k=2)

    assert "citations" in result
    assert len(result["citations"]) >= 1

    first_citation = result["citations"][0]
    assert "GP-2" in first_citation["document_title"]
    assert "Peak" in first_citation["section_clause"]
    assert first_citation["retrieval_method"] == "hybrid_rrf"
    assert first_citation["confidence_score"] > 0.0
