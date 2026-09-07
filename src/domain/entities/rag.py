"""
CampusGrid AI: RAG Domain Entities
Entities for document clauses, embeddings, search results, and citations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class DocumentClause(BaseModel):
    """A single regulatory clause or standard section."""
    id: Optional[int] = None
    source_document: str = Field(..., description="e.g. PUCSL Tariff Schedule GP-2 or ASHRAE-55")
    clause_reference: str = Field(..., description="e.g. Clause 4.2 or Section 5.3")
    section_title: Optional[str] = None
    content: str
    effective_date: Optional[str] = None
    embedding: Optional[List[float]] = None

class Citation(BaseModel):
    """Verified regulatory citation presented in XAI explanations."""
    document_title: str
    section_clause: str
    content: str
    confidence_score: float
    retrieval_method: str = "hybrid_rrf"

class SearchPassage(BaseModel):
    """Result of vector or keyword retrieval."""
    clause: DocumentClause
    score: float
    retrieval_type: str = "dense"  # "dense", "sparse_bm25", "hybrid_rrf"
