"""
CampusGrid AI: ChromaDB Vector Store Adapter
Connects to a local persistent or in-memory ChromaDB instance.
"""

from typing import List, Dict, Any, Optional
from src.domain.interfaces.vector_store import VectorStore, VectorSearchResult
from src.domain.entities.rag import DocumentClause
from src.domain.exceptions.base import VectorStoreException

class ChromaStore(VectorStore):
    """ChromaDB vector store adapter."""

    def __init__(self, persist_dir: str = "backend/data/storage/chroma_db"):
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self.persist_dir)
                self._collection = self._client.get_or_create_collection(
                    name="campusgrid_policy_clauses",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                raise VectorStoreException(
                    message=f"Failed to initialize ChromaDB: {str(e)}",
                    provider_name="chromadb"
                ) from e
        return self._collection

    def add_documents(self, documents: List[DocumentClause]) -> List[str]:
        col = self._get_collection()
        ids = []
        embeddings = []
        metadatas = []
        documents_text = []

        for idx, doc in enumerate(documents):
            doc_id = str(doc.id or f"doc_{idx}")
            ids.append(doc_id)
            embeddings.append(doc.embedding or [])
            metadatas.append({
                "source_document": doc.source_document,
                "clause_reference": doc.clause_reference,
                "section_title": doc.section_title or "",
                "effective_date": doc.effective_date or ""
            })
            documents_text.append(doc.content)

        col.add(
            ids=ids,
            embeddings=embeddings if all(len(e) > 0 for e in embeddings) else None,
            metadatas=metadatas,
            documents=documents_text
        )
        return ids

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        col = self._get_collection()
        where_filter = filter_metadata if filter_metadata else None

        res = col.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter
        )

        results = []
        if res and res["ids"] and len(res["ids"][0]) > 0:
            for i in range(len(res["ids"][0])):
                doc_id = res["ids"][0][i]
                meta = res["metadatas"][0][i]
                content = res["documents"][0][i]
                distance = res["distances"][0][i] if "distances" in res and res["distances"] else 0.0
                similarity = 1.0 - distance

                clause = DocumentClause(
                    id=int(doc_id) if doc_id.isdigit() else None,
                    source_document=meta.get("source_document", "Unknown"),
                    clause_reference=meta.get("clause_reference", "Section"),
                    section_title=meta.get("section_title"),
                    content=content,
                    effective_date=meta.get("effective_date")
                )
                results.append(VectorSearchResult(clause=clause, similarity=similarity, distance=distance))

        return results

    def delete(self, document_ids: List[str]) -> bool:
        col = self._get_collection()
        col.delete(ids=document_ids)
        return True

    def count(self) -> int:
        col = self._get_collection()
        return col.count()

    def list_documents(self) -> List[DocumentClause]:
        col = self._get_collection()
        res = col.get(include=["metadatas", "documents"])
        docs = []
        for doc_id, meta, content in zip(res.get("ids", []), res.get("metadatas", []), res.get("documents", [])):
            docs.append(DocumentClause(
                id=int(doc_id) if str(doc_id).isdigit() else None,
                source_document=meta.get("source_document", "Unknown"),
                clause_reference=meta.get("clause_reference", "Section"),
                section_title=meta.get("section_title"),
                content=content,
                effective_date=meta.get("effective_date") or None,
            ))
        return docs
