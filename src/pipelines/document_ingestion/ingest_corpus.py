"""
CampusGrid AI: Regulatory Document Ingestion Pipeline
Loads corpus files (Markdown, plain text, PDF) from backend/rag/corpus/tariffs, chunks them into
DocumentClauses, screens them, embeds them, and indexes them into the VectorStore and the
keyword (BM25) index.

Re-running ingestion is safe: a clause already indexed under the same
(source_document, clause_reference) is skipped, not duplicated.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.keyword_search import KeywordSearchEngine
from src.domain.entities.rag import DocumentClause
from src.pipelines.document_ingestion.chunker import RegulatoryDocumentChunker
from src.pipelines.document_ingestion.screening import ClauseScreener

logger = logging.getLogger("campusgrid.ingestion")

SUPPORTED_SUFFIXES = (".md", ".txt", ".pdf")


def _clause_key(clause: DocumentClause) -> str:
    return f"{clause.source_document.strip().lower()}|{clause.clause_reference.strip().lower()}"


class DocumentIngestionPipeline:
    """Manages parsing, screening, embedding generation, and indexing of regulatory policies."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        keyword_engine: KeywordSearchEngine,
        chunker: Optional[RegulatoryDocumentChunker] = None,
        screener: Optional[ClauseScreener] = None,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.keyword_engine = keyword_engine
        self.chunker = chunker or RegulatoryDocumentChunker()
        self.screener = screener or ClauseScreener()

    # ------------------------------------------------------------------

    def ingest_directory(self, dir_path: str) -> Dict[str, Any]:
        """Ingests every supported document in the given directory."""
        target_dir = Path(dir_path)
        if not target_dir.exists() or not target_dir.is_dir():
            return {"status": "error", "message": f"Directory not found: {dir_path}", "total_clauses_ingested": 0}

        files = sorted(p for p in target_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
        all_clauses: List[DocumentClause] = []
        file_errors: List[Dict[str, str]] = []

        for file_path in files:
            try:
                all_clauses.extend(self._parse_file(file_path))
            except Exception as e:
                logger.warning("Failed reading %s: %s", file_path, e)
                file_errors.append({"file": file_path.name, "error": type(e).__name__})

        if not all_clauses:
            return {
                "status": "empty",
                "message": "No clauses extracted from directory",
                "total_clauses_ingested": 0,
                "file_errors": file_errors,
            }

        result = self._index(all_clauses)
        return {
            "status": "success",
            "files_processed": [f.name for f in files],
            "total_clauses_ingested": result["clauses_added"],
            "duplicates_skipped": result["duplicates_skipped"],
            "rejected_clauses": result["rejected_clauses"],
            "file_errors": file_errors,
            "sources": sorted({c.source_document for c in all_clauses}),
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

        for c in clauses:
            if not c.source_document or c.source_document == "Regulatory Document":
                c.source_document = source_document
            c.effective_date = effective_date

        result = self._index(clauses)
        added = result["clauses_added"]
        status = "success" if added else ("duplicate" if result["duplicates_skipped"] else "rejected")
        return {
            "status": status,
            "clauses_added": added,
            "duplicates_skipped": result["duplicates_skipped"],
            "rejected_clauses": result["rejected_clauses"],
            "source_document": source_document,
            "message": None if added else "No new clauses were indexed; see duplicates_skipped / rejected_clauses.",
        }

    def ingest_clauses(self, clauses: List[DocumentClause]) -> Dict[str, Any]:
        """Indexes already-parsed clauses (screened and de-duplicated like any other source)."""
        return self._index(clauses)

    # ------------------------------------------------------------------

    def _parse_file(self, file_path: Path) -> List[DocumentClause]:
        suffix = file_path.suffix.lower()
        if suffix == ".md":
            return self.chunker.parse_markdown(file_path.read_text(encoding="utf-8"), default_source=file_path.stem)
        if suffix == ".txt":
            return self.chunker.parse_plain_text(file_path.read_text(encoding="utf-8"), source_document=file_path.stem)
        # .pdf — pypdf ships with the `rag` extra; without it PDFs are reported, not silently skipped.
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        text = "\f".join(page.extract_text() or "" for page in reader.pages)
        title = (reader.metadata.title if reader.metadata and reader.metadata.title else None) or file_path.stem
        return self.chunker.parse_plain_text(text, source_document=title)

    def _index(self, clauses: List[DocumentClause]) -> Dict[str, Any]:
        accepted, rejected = self.screener.screen(clauses)

        existing_docs = self.keyword_engine.documents
        existing_keys = {_clause_key(d) for d in existing_docs}
        new_clauses: List[DocumentClause] = []
        duplicates = 0
        for c in accepted:
            key = _clause_key(c)
            if key in existing_keys:
                duplicates += 1
                continue
            existing_keys.add(key)
            new_clauses.append(c)

        if new_clauses:
            next_id = max((d.id or 0 for d in existing_docs), default=0) + 1
            for offset, c in enumerate(new_clauses):
                c.id = next_id + offset

            vectors = self.embedding_provider.embed_documents([c.content for c in new_clauses])
            for c, v in zip(new_clauses, vectors):
                c.embedding = v

            stored_ids = self.vector_store.add_documents(new_clauses)
            # Persistent stores assign their own IDs; keep the keyword index in step with them.
            for c, stored_id in zip(new_clauses, stored_ids):
                if str(stored_id).isdigit():
                    c.id = int(stored_id)
            self.keyword_engine.add_documents([c.model_copy(update={"embedding": None}) for c in new_clauses])

        if rejected:
            logger.warning("Ingestion quarantined %d clause(s): %s", len(rejected), rejected)

        return {"clauses_added": len(new_clauses), "duplicates_skipped": duplicates, "rejected_clauses": rejected}
