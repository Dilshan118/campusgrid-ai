"""
CampusGrid AI: Hybrid RAG Retrieval Service
Orchestrates dense vector search and sparse BM25 keyword matching with Reciprocal Rank Fusion (RRF).
Automatically bootstraps official PUCSL GP-2 tariffs and ASHRAE-55 comfort standard clauses.

All retrieval components are injected by the DI container, so this service depends only on
domain interfaces (VectorStore, EmbeddingProvider, KeywordSearchEngine, Reranker).
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.keyword_search import KeywordSearchEngine
from src.domain.interfaces.reranker import Reranker
from src.domain.entities.rag import DocumentClause

logger = logging.getLogger("campusgrid.retrieval")

# Last-resort seed used only when the corpus directory yields no clauses at all.
_FALLBACK_CLAUSES = [
    DocumentClause(
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


def _doc_key(clause: DocumentClause) -> str:
    return f"{clause.source_document}_{clause.clause_reference}"


class RetrievalService:
    """Coordinates hybrid regulatory document search and ingestion."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        keyword_engine: KeywordSearchEngine,
        reranker: Reranker,
        ingestion_pipeline: Any,
        corpus_dir: Optional[str] = None
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.keyword_engine = keyword_engine
        self.reranker = reranker
        self.ingestion_pipeline = ingestion_pipeline
        self.corpus_dir = corpus_dir or "backend/rag/corpus/tariffs"
        self._bootstrap_initial_corpus()

    @property
    def bm25_engine(self) -> KeywordSearchEngine:
        """Backwards-compatible name used by tests/benchmark_ir_quality.py."""
        return self.keyword_engine

    @property
    def dense_enabled(self) -> bool:
        return getattr(self.embedding_provider, "is_semantic", True)

    def _bootstrap_initial_corpus(self):
        """Makes both indexes consistent on startup.

        A persistent vector store (pgvector, Chroma) survives restarts but the keyword index
        is in memory, so it is rebuilt from the stored clauses first. The corpus directory is
        then (re-)ingested; clauses already indexed are skipped, so new files are picked up
        without duplicating old ones.
        """
        if self.vector_store.count() > 0:
            try:
                self.keyword_engine.index_documents(self.vector_store.list_documents())
            except NotImplementedError:
                logger.warning("%s cannot list documents; keyword index starts empty.", type(self.vector_store).__name__)

        corpus_path = Path(self.corpus_dir)
        if corpus_path.exists():
            self.ingestion_pipeline.ingest_directory(str(corpus_path))

        if not self.keyword_engine.documents:
            logger.warning("Corpus directory '%s' yielded no clauses; indexing the built-in fallback clauses.", self.corpus_dir)
            self.ingestion_pipeline.ingest_clauses([c.model_copy() for c in _FALLBACK_CLAUSES])

    def search(self, query: str, top_k: int = 2) -> Dict[str, Any]:
        """Executes dense + sparse search, merges with RRF, and returns citations."""
        # 1. Dense vector search (skipped when the embeddings carry no meaning)
        dense_candidates: List[DocumentClause] = []
        if self.dense_enabled:
            query_vec = self.embedding_provider.embed_text(query)
            dense_candidates = [r.clause for r in self.vector_store.similarity_search(query_vec, top_k=top_k * 2)]

        # 2. Sparse BM25 search
        sparse_candidates = [c for c, _ in self.keyword_engine.search(query, top_k=top_k * 2)]

        # 3. Fusion
        ranked_lists = [dense_candidates, sparse_candidates] if dense_candidates else [sparse_candidates]
        if hasattr(self.reranker, "rerank_ranked_lists"):
            rerank_results = self.reranker.rerank_ranked_lists(ranked_lists, top_k=top_k)
        else:
            rerank_results = self.reranker.rerank(query, dense_candidates + sparse_candidates, top_k=top_k)

        dense_keys = {_doc_key(c) for c in dense_candidates}
        sparse_keys = {_doc_key(c) for c in sparse_candidates}
        method = "hybrid_rrf" if dense_candidates else "sparse_bm25"

        citations = []
        for res in rerank_results:
            c = res.clause
            key = _doc_key(c)
            citations.append({
                "rank": res.rank,
                "clause_id": c.id,
                "document_title": c.source_document,
                "section_clause": c.clause_reference,
                "section_title": c.section_title,
                "effective_date": c.effective_date,
                "content": c.content,
                "confidence_score": res.score,
                "retrieval_method": method,
                "matched_by": [m for m, keys in (("semantic", dense_keys), ("keyword", sparse_keys)) if key in keys],
            })

        return {
            "query": query,
            "citations": citations,
            "candidates_count": len(dense_candidates) + len(sparse_candidates),
            "dense_search_enabled": bool(dense_candidates) or self.dense_enabled,
        }

    def ingest_raw_document(
        self,
        text: str,
        source_document: str = "Regulatory Document",
        effective_date: str = "2024-01-01"
    ) -> Dict[str, Any]:
        """Ingests a raw policy text or markdown snippet into the active vector and keyword stores."""
        return self.ingestion_pipeline.ingest_raw_text(
            text=text,
            source_document=source_document,
            effective_date=effective_date
        )

    def ingest_corpus_directory(self) -> Dict[str, Any]:
        return self.ingestion_pipeline.ingest_directory(self.corpus_dir)

    def index_stats(self) -> Dict[str, Any]:
        docs = self.keyword_engine.documents
        by_source: Dict[str, int] = {}
        for d in docs:
            by_source[d.source_document] = by_source.get(d.source_document, 0) + 1
        return {
            "total_clauses": len(docs),
            "vector_store_count": self.vector_store.count(),
            "documents": [{"source_document": k, "clauses": v} for k, v in sorted(by_source.items())],
            "dense_search_enabled": self.dense_enabled,
        }
