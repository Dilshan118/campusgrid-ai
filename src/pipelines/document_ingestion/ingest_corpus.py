"""
CampusGrid AI: Regulatory Document Ingestion Pipeline
Loads corpus files (Markdown, plain text, PDF) from backend/rag/corpus/tariffs, chunks them into
DocumentClauses, screens them, embeds them, and indexes them into the VectorStore and the
keyword (BM25) index.

Re-running ingestion is safe: a clause already indexed under the same
(source_document, clause_reference) is skipped, not duplicated.
"""

import logging
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
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


def _content_key(clause: DocumentClause) -> str:
    normalized = re.sub(r"\s+", " ", clause.content).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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
            # Folder name only: this message reaches API clients and must not reveal server paths.
            return {"status": "error", "message": f"Corpus directory not found: {target_dir.name}", "total_clauses_ingested": 0}

        files = sorted(p for p in target_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
        all_clauses: List[DocumentClause] = []
        file_errors: List[Dict[str, str]] = []
        manifest = self._load_trusted_manifest(target_dir)
        verified_source_count = 0

        for file_path in files:
            try:
                file_bytes = file_path.read_bytes()
                source_digest = hashlib.sha256(file_bytes).hexdigest()
                clauses = self._parse_file(file_path)
                source_record = manifest.get(source_digest)
                if source_record:
                    verified_source_count += 1
                for clause in clauses:
                    clause.source_sha256 = source_digest
                    clause.source_uri = source_record["source_uri"] if source_record else None
                    clause.provenance_status = "verified_official" if source_record else "unverified"
                all_clauses.extend(clauses)
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
            "verified_source_files": verified_source_count,
        }

    @staticmethod
    def _load_trusted_manifest(target_dir: Path) -> Dict[str, Dict[str, str]]:
        """Load hash-pinned, maintainer-reviewed source records; titles alone never qualify."""
        manifest_path = target_dir / "trusted_sources.json"
        if not manifest_path.is_file():
            return {}
        try:
            records = json.loads(manifest_path.read_text(encoding="utf-8")).get("sources", {})
        except (OSError, ValueError, TypeError):
            logger.error("Trusted source manifest is unreadable; corpus files remain unverified.")
            return {}
        trusted: Dict[str, Dict[str, str]] = {}
        for digest, record in records.items():
            if not isinstance(record, dict):
                continue
            uri = str(record.get("source_uri", ""))
            parsed = urlparse(uri)
            if (re.fullmatch(r"[a-f0-9]{64}", digest)
                    and record.get("provenance_status") == "verified_official"
                    and parsed.scheme == "https"
                    and parsed.hostname in {"pucsl.gov.lk", "www.pucsl.gov.lk"}):
                trusted[digest] = record
        return trusted

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
            # An uploader controls both the claimed title and text. Do not let either
            # confer authority; status can only be raised by a future verified importer.
            c.provenance_status = "unverified"
            c.source_uri = None
            c.content_sha256 = _content_key(c)

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
        existing_content = {_content_key(d) for d in existing_docs}
        new_clauses: List[DocumentClause] = []
        duplicates = 0
        for c in accepted:
            key = _clause_key(c)
            digest = _content_key(c)
            c.content_sha256 = digest
            # Bundled files are reference fixtures, not independently authenticated sources.
            if c.provenance_status != "verified_official":
                c.provenance_status = "unverified"
                c.source_uri = None
            if key in existing_keys or digest in existing_content:
                duplicates += 1
                continue
            existing_keys.add(key)
            existing_content.add(digest)
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
