"""
Unit tests for VectorStore abstraction and MemoryVectorStore.
"""

from src.infrastructure.vector_store.memory_store import MemoryVectorStore
from src.domain.entities.rag import DocumentClause

def test_memory_vector_store_add_and_search():
    store = MemoryVectorStore()

    doc1 = DocumentClause(
        id=1,
        source_document="PUCSL GP-2",
        clause_reference="Clause 4.1",
        content="Peak rate is 58 LKR per kWh.",
        embedding=[1.0, 0.0, 0.0]
    )
    doc2 = DocumentClause(
        id=2,
        source_document="ASHRAE-55",
        clause_reference="Section 5.3",
        content="Comfort temperature range is 21.0 to 25.5 C.",
        embedding=[0.0, 1.0, 0.0]
    )

    ids = store.add_documents([doc1, doc2])
    assert len(ids) == 2
    assert store.count() == 2

    # Query matching doc1
    results = store.similarity_search(query_vector=[0.95, 0.05, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0].clause.clause_reference == "Clause 4.1"
    assert results[0].similarity > 0.9

def test_memory_vector_store_delete():
    store = MemoryVectorStore()
    doc = DocumentClause(
        id=10,
        source_document="Test",
        clause_reference="1.0",
        content="Test content",
        embedding=[0.5, 0.5]
    )
    store.add_documents([doc])
    assert store.count() == 1

    store.delete(["10"])
    assert store.count() == 0
