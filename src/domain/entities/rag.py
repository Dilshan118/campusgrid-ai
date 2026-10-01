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
    # Never inferred from a filename/title. Only a trusted ingestion verifier may set
    # verified_official; current public uploads and bundled fixtures remain unverified.
    provenance_status: str = "unverified"
    source_uri: Optional[str] = None
    content_sha256: Optional[str] = None
    source_sha256: Optional[str] = None
