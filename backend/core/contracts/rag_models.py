"""
CampusGrid AI: Information Retrieval & RAG Contract Models
Defines schemas for tariff policy queries, retrieved passages, and citations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User search query or question")
    top_k: int = Field(default=2, ge=1, le=5, description="Number of passages to return")

class RAGCitation(BaseModel):
    document_title: str
    section_clause: str
    content: str
    confidence_score: float
    retrieval_method: str = Field(default="hybrid_rrf", description="dense, sparse_bm25, or hybrid_rrf")

class RAGQueryResponse(BaseModel):
    query: str
    citations: List[RAGCitation]
    grounded_summary: Optional[str] = None
