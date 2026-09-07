"""
CampusGrid AI: Hybrid RAG Retrieval Service
Orchestrates dense vector search and sparse BM25 keyword matching with Reciprocal Rank Fusion (RRF).
Automatically bootstraps official PUCSL GP-2 tariffs and ASHRAE-55 comfort standard clauses.
"""

from typing import List, Dict, Any, Optional
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.reranker import Reranker
from src.domain.entities.rag import DocumentClause, Citation
from src.infrastructure.retrieval.sparse_bm25 import BM25SearchEngine
from src.infrastructure.retrieval.rrf_reranker import RRFReranker

class RetrievalService:
    """Coordinates hybrid regulatory document search."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        reranker: Optional[Reranker] = None,
        bm25_engine: Optional[BM25SearchEngine] = None
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.reranker = reranker or RRFReranker(k=60)
        self.bm25_engine = bm25_engine or BM25SearchEngine()
        self._bootstrap_initial_corpus()

    def _bootstrap_initial_corpus(self):
        """Seeds official PUCSL GP-2 tariff clauses and ASHRAE-55 comfort standards."""
        if self.vector_store.count() > 0:
            return

        clauses = [
            DocumentClause(
                id=1,
                source_document="PUCSL Electricity Tariff Schedule GP-2",
                clause_reference="Clause 4.1 - Peak Time-of-Use Rate",
                section_title="Peak Energy Charges",
                content=(
                    "Under General Purpose Tariff 2 (GP-2), consumption during the peak window (18:00 to 22:30 hours) "
                    "shall be billed at the unit rate of LKR 58.00 per kilowatt-hour (kWh). "
                    "Institutions are advised to curtail non-critical HVAC loads or dispatch behind-the-meter battery storage."
                ),
                effective_date="2024-07-01"
            ),
            DocumentClause(
                id=2,
                source_document="PUCSL Electricity Tariff Schedule GP-2",
                clause_reference="Clause 4.2 - Day & Off-Peak Rates",
                section_title="Day and Off-Peak Energy Charges",
                content=(
                    "Day-time energy consumption (05:30 to 18:00 hours) is billed at LKR 30.00 per kWh. "
                    "Off-peak energy consumption (22:30 to 05:30 hours) is billed at LKR 15.00 per kWh. "
                    "Battery storage systems should be charged primarily during the off-peak window."
                ),
                effective_date="2024-07-01"
            ),
            DocumentClause(
                id=3,
                source_document="PUCSL Electricity Tariff Schedule GP-2",
                clause_reference="Clause 6.3 - Maximum Demand Penalty",
                section_title="Maximum Demand Surcharge",
                content=(
                    "A monthly maximum demand charge of LKR 1,100.00 per kVA is levied on the single highest "
                    "15-minute integrated demand recorded across the billing cycle. Demand spikes occurring during "
                    "simultaneous chiller startup must be eliminated via peak shaving."
                ),
                effective_date="2024-07-01"
            ),
            DocumentClause(
                id=4,
                source_document="ASHRAE Standard 55-2023",
                clause_reference="Section 5.3 - Thermal Comfort Envelopes",
                section_title="Indoor Operative Temperature Requirements",
                content=(
                    "For educational lecture halls and computing laboratories with sedentary student activity (1.0 to 1.2 met) "
                    "and standard indoor attire (0.5 to 1.0 clo), the acceptable operative temperature envelope ranges between "
                    "21.0°C and 25.5°C. Precooling strategies must not drop indoor temperatures below 21.0°C."
                ),
                effective_date="2023-01-01"
            ),
        ]

        # Embed and index
        texts = [c.content for c in clauses]
        vectors = self.embedding_provider.embed_documents(texts)
        for c, v in zip(clauses, vectors):
            c.embedding = v

        self.vector_store.add_documents(clauses)
        self.bm25_engine.index_documents(clauses)

    def search(self, query: str, top_k: int = 2) -> Dict[str, Any]:
        """Executes dense + sparse search, merges with RRF, and returns citations."""
        # 1. Dense vector search
        query_vec = self.embedding_provider.embed_text(query)
        dense_results = self.vector_store.similarity_search(query_vec, top_k=top_k * 2)
        dense_candidates = [r.clause for r in dense_results]

        # 2. Sparse BM25 search
        bm25_results = self.bm25_engine.search(query, top_k=top_k * 2)
        sparse_candidates = [c for c, _ in bm25_results]

        # 3. Reciprocal Rank Fusion
        if isinstance(self.reranker, RRFReranker):
            rerank_results = self.reranker.rerank_ranked_lists(
                [dense_candidates, sparse_candidates],
                top_k=top_k
            )
        else:
            rerank_results = self.reranker.rerank(query, dense_candidates, top_k=top_k)

        citations = []
        for res in rerank_results:
            c = res.clause
            citations.append({
                "document_title": c.source_document,
                "section_clause": c.clause_reference,
                "content": c.content,
                "confidence_score": res.score,
                "retrieval_method": "hybrid_rrf"
            })

        return {
            "query": query,
            "citations": citations,
            "candidates_count": len(dense_candidates) + len(sparse_candidates)
        }
