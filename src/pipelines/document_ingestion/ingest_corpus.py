"""
CampusGrid AI: Regulatory Document Ingestion Pipeline
Loads markdown corpus files from backend/rag/corpus/tariffs, chunks them into DocumentClauses,
generates embeddings, and indexes them into VectorStore and BM25SearchEngine.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.infrastructure.retrieval.sparse_bm25 import BM25SearchEngine
from src.domain.entities.rag import DocumentClause
from src.pipelines.document_ingestion.chunker import RegulatoryDocumentChunker


class DocumentIngestionPipeline:
    """Manages parsing, embedding generation, and indexing of regulatory policies."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        bm25_engine: Optional[BM25SearchEngine] = None,
        chunker: Optional[RegulatoryDocumentChunker] = None
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.bm25_engine = bm25_engine or BM25SearchEngine()
        self.chunker = chunker or RegulatoryDocumentChunker()

    def ingest_directory(self, dir_path: str) -> Dict[str, Any]:
        """Ingests all .md files in the given directory into vector and keyword stores."""
        target_dir = Path(dir_path)
        if not target_dir.exists() or not target_dir.is_dir():
            return {"status": "error", "message": f"Directory not found: {dir_path}", "clause_count": 0}

        md_files = list(target_dir.glob("*.md"))
        all_clauses: List[DocumentClause] = []
        clause_id_counter = 1

        for file_path in sorted(md_files):
            try:
                content = file_path.read_text(encoding="utf-8")
                clauses = self.chunker.parse_markdown(content, default_source=file_path.stem)
                for c in clauses:
                    c.id = clause_id_counter
                    clause_id_counter += 1
                    all_clauses.append(c)
            except Exception as e:
                print(f"[Ingestion Error] Failed reading {file_path}: {e}")

        if not all_clauses:
            return {"status": "empty", "message": "No clauses extracted from directory", "clause_count": 0}

        # Generate embeddings
        texts = [c.content for c in all_clauses]
        vectors = self.embedding_provider.embed_documents(texts)
        for c, v in zip(all_clauses, vectors):
            c.embedding = v

        # Index into stores
        self.vector_store.add_documents(all_clauses)
        self.bm25_engine.index_documents(all_clauses)

        return {
            "status": "success",
            "files_processed": [f.name for f in md_files],
            "total_clauses_ingested": len(all_clauses),
            "sources": list(set(c.source_document for c in all_clauses))
        }

    def ingest_raw_text(
        self,
        text: str,
        source_document: str,
        effective_date: str = "2024-01-01"
    ) -> Dict[str, Any]:
        """Ingests a raw text or markdown snippet directly."""
        clauses = self.chunker.parse_markdown(text, default_source=source_document)
        if not clauses:
            return {"status": "error", "message": "No valid clauses could be parsed from text"}

        start_id = self.vector_store.count() + 1
        for idx, c in enumerate(clauses):
            c.id = start_id + idx
            if not c.source_document or c.source_document == "Regulatory Document":
                c.source_document = source_document
            c.effective_date = effective_date

        texts = [c.content for c in clauses]
        vectors = self.embedding_provider.embed_documents(texts)
        for c, v in zip(clauses, vectors):
            c.embedding = v

        self.vector_store.add_documents(clauses)
        self.bm25_engine.index_documents(clauses)

        return {
            "status": "success",
            "clauses_added": len(clauses),
            "source_document": source_document
        }
