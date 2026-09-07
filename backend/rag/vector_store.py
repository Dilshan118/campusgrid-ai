"""
Backwards compatibility shim for TariffKnowledgeEngine.
Delegates to the modular RetrievalService and VectorStore.
"""

from typing import List, Dict, Any
from src.application.container import get_container

class TariffKnowledgeEngine:
    def __init__(self, persist_dir: str = "backend/data/storage/chroma_db"):
        self.container = get_container()
        self.retrieval_service = self.container.retrieval_service

    def index_corpus(self, document_chunks: List[Dict[str, Any]]):
        pass

    def hybrid_search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        res = self.retrieval_service.search(query=query, top_k=top_k)
        return res.get("citations", [])

__all__ = ["TariffKnowledgeEngine"]
