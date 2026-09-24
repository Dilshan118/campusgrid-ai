"""
CampusGrid AI: In-Memory Vector Store
Lightweight vector store implementing exact cosine similarity search.
Enables offline development, testing, and zero-dependency deployments.
"""

import math
from typing import List, Dict, Any, Optional
from src.domain.interfaces.vector_store import VectorStore, VectorSearchResult
from src.domain.entities.rag import DocumentClause

class MemoryVectorStore(VectorStore):
    """In-memory cosine similarity vector database."""

    def __init__(self):
        self._documents: Dict[str, DocumentClause] = {}
        self._counter = 1

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    def add_documents(self, documents: List[DocumentClause]) -> List[str]:
        ids = []
        for doc in documents:
            if doc.id is None:
                doc.id = self._counter
                self._counter += 1
            doc_id = str(doc.id)
            self._documents[doc_id] = doc
            ids.append(doc_id)
        return ids

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        results = []
        for doc_id, doc in self._documents.items():
            if not doc.embedding:
                continue

            # Check optional filter
            if filter_metadata:
                match = True
                for k, v in filter_metadata.items():
                    if getattr(doc, k, None) != v:
                        match = False
                        break
                if not match:
                    continue

            sim = self._cosine_similarity(query_vector, doc.embedding)
            results.append(VectorSearchResult(clause=doc, similarity=sim, distance=1.0 - sim))

        # Sort descending by similarity
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def delete(self, document_ids: List[str]) -> bool:
        for d_id in document_ids:
            self._documents.pop(d_id, None)
        return True

    def count(self) -> int:
        return len(self._documents)

    def list_documents(self) -> List[DocumentClause]:
        return [doc.model_copy(update={"embedding": None}) for doc in self._documents.values()]
