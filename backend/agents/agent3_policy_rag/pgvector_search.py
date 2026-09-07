"""
Backwards compatibility shim for PgVectorPolicySearch.
Delegates to the modular RetrievalService and VectorStore.
"""

from typing import List, Dict, Any
from src.application.container import get_container

class PgVectorPolicySearch:
    def __init__(self):
        self.container = get_container()
        self.retrieval_service = self.container.retrieval_service

    def search_similar_clauses(self, query_embedding: List[float], top_k: int = 2) -> List[Dict[str, Any]]:
        res = self.container.vector_store.similarity_search(query_vector=query_embedding, top_k=top_k)
        return [
            {
                "id": r.clause.id,
                "source_document": r.clause.source_document,
                "clause_reference": r.clause.clause_reference,
                "content": r.clause.content,
                "similarity": r.similarity
            }
            for r in res
        ]

__all__ = ["PgVectorPolicySearch"]
