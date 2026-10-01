"""
Backwards compatibility shim for TariffKnowledgeEngine.
Delegates to the modular RetrievalService and VectorStore.

Deprecated: new code should use `get_container().retrieval_service` directly.
"""

import warnings
from typing import List, Dict, Any
from src.application.container import get_container
from src.domain.entities.rag import DocumentClause


class TariffKnowledgeEngine:
    def __init__(self, persist_dir: str = "backend/data/storage/chroma_db"):
        warnings.warn(
            "backend.rag.vector_store.TariffKnowledgeEngine is deprecated; use the container's retrieval_service.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.container = get_container()
        self.retrieval_service = self.container.retrieval_service

    def index_corpus(self, document_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Indexes pre-chunked clauses with the same screening and de-duplication as the corpus
        directory. Each chunk needs `content` plus a source and clause reference (the old
        `document_title` / `section_clause` key names are accepted)."""
        clauses = [
            DocumentClause(
                source_document=chunk.get("source_document") or chunk.get("document_title") or "Regulatory Document",
                clause_reference=chunk.get("clause_reference") or chunk.get("section_clause") or f"Section {i + 1}",
                section_title=chunk.get("section_title"),
                content=chunk["content"],
                effective_date=chunk.get("effective_date"),
            )
            for i, chunk in enumerate(document_chunks)
        ]
        return self.retrieval_service.ingest_clauses(clauses)

    def hybrid_search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        res = self.retrieval_service.search(query=query, top_k=top_k)
        return res.get("citations", [])

__all__ = ["TariffKnowledgeEngine"]
