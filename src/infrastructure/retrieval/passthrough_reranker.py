"""
CampusGrid AI: Passthrough Reranker
Keeps the retrievers' own order (dense hits first, then sparse hits not already listed).
Selected with RERANKER_STRATEGY=passthrough, mainly as an ablation baseline against RRF.
"""

from typing import List
from src.domain.interfaces.reranker import Reranker, RerankResult
from src.domain.entities.rag import DocumentClause


class PassthroughReranker(Reranker):
    """Concatenates ranked lists in order, removing duplicates, without re-scoring."""

    def rerank_ranked_lists(self, ranked_lists: List[List[DocumentClause]], top_k: int = 2) -> List[RerankResult]:
        seen = set()
        merged: List[DocumentClause] = []
        for ranked in ranked_lists:
            for doc in ranked:
                key = f"{doc.source_document}_{doc.clause_reference}"
                if key not in seen:
                    seen.add(key)
                    merged.append(doc)
        return [
            RerankResult(clause=doc, score=round(1.0 / (i + 1), 6), rank=i + 1)
            for i, doc in enumerate(merged[:top_k])
        ]

    def rerank(self, query: str, candidates: List[DocumentClause], top_k: int = 2) -> List[RerankResult]:
        return self.rerank_ranked_lists([candidates], top_k=top_k)
