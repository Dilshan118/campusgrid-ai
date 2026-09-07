"""
CampusGrid AI: Reciprocal Rank Fusion (RRF) Reranker
Combines dense semantic rankings and sparse BM25 lexical rankings into an optimal unified order.
"""

from typing import List, Dict, Tuple
from src.domain.interfaces.reranker import Reranker, RerankResult
from src.domain.entities.rag import DocumentClause

class RRFReranker(Reranker):
    """Reciprocal Rank Fusion Reranker implementing Reranker interface."""

    def __init__(self, k: int = 60):
        self.k = k

    def rerank_ranked_lists(
        self,
        ranked_lists: List[List[DocumentClause]],
        top_k: int = 2
    ) -> List[RerankResult]:
        """
        Fuses multiple ranked candidate lists using RRF score:
        RRF(d) = SUM_m [ 1 / (k + rank_m(d)) ]
        """
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, DocumentClause] = {}

        for rank_list in ranked_lists:
            for rank_idx, doc in enumerate(rank_list):
                doc_key = f"{doc.source_document}_{doc.clause_reference}"
                doc_map[doc_key] = doc
                rank = rank_idx + 1
                rrf_scores[doc_key] = rrf_scores.get(doc_key, 0.0) + (1.0 / (self.k + rank))

        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

        results = []
        for i, key in enumerate(sorted_keys[:top_k]):
            results.append(RerankResult(
                clause=doc_map[key],
                score=round(rrf_scores[key], 6),
                rank=i + 1
            ))
        return results

    def rerank(self, query: str, candidates: List[DocumentClause], top_k: int = 2) -> List[RerankResult]:
        # Single list passthrough
        return self.rerank_ranked_lists([candidates], top_k=top_k)
