"""
CampusGrid AI: PostgreSQL / Neon pgvector Vector Store Adapter
Executes native cosine distance search using the '<=>' pgvector operator.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
from src.domain.interfaces.vector_store import VectorStore, VectorSearchResult
from src.domain.entities.rag import DocumentClause
from src.domain.exceptions.base import VectorStoreException

class PgVectorStore(VectorStore):
    """PostgreSQL pgvector database adapter."""

    def __init__(self, engine):
        self.engine = engine

    def add_documents(self, documents: List[DocumentClause]) -> List[str]:
        inserted_ids = []
        try:
            with self.engine.begin() as conn:
                for doc in documents:
                    res = conn.execute(
                        text("""
                            INSERT INTO document_clauses
                            (source_document, clause_reference, section_title, content, effective_date, embedding)
                            VALUES (:source, :clause_ref, :sec_title, :content, :eff_date, :embedding)
                            RETURNING id;
                        """),
                        {
                            "source": doc.source_document,
                            "clause_ref": doc.clause_reference,
                            "sec_title": doc.section_title or "",
                            "content": doc.content,
                            "eff_date": doc.effective_date,
                            "embedding": str(doc.embedding) if doc.embedding else None
                        }
                    )
                    row = res.fetchone()
                    if row:
                        inserted_ids.append(str(row[0]))
            return inserted_ids
        except Exception as e:
            raise VectorStoreException(
                message=f"Failed to insert documents into pgvector: {str(e)}",
                provider_name="pgvector",
                details={"original_error": str(e)}
            ) from e

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        try:
            vec_str = "[" + ",".join(str(x) for x in query_vector) + "]"
            where_clause = ""
            params: Dict[str, Any] = {"query_vec": vec_str, "top_k": top_k}

            if filter_metadata and "source_document" in filter_metadata:
                where_clause = "WHERE source_document = :source_doc"
                params["source_doc"] = filter_metadata["source_document"]

            query = f"""
                SELECT id, source_document, clause_reference, section_title, content, effective_date,
                       1 - (embedding <=> :query_vec) AS similarity
                FROM document_clauses
                {where_clause}
                ORDER BY embedding <=> :query_vec
                LIMIT :top_k;
            """

            results = []
            with self.engine.connect() as conn:
                rows = conn.execute(text(query), params).fetchall()
                for r in rows:
                    clause = DocumentClause(
                        id=r[0],
                        source_document=r[1],
                        clause_reference=r[2],
                        section_title=r[3],
                        content=r[4],
                        effective_date=str(r[5]) if r[5] else None
                    )
                    sim = float(r[6]) if r[6] is not None else 0.0
                    results.append(VectorSearchResult(clause=clause, similarity=sim, distance=1.0 - sim))
            return results
        except Exception as e:
            raise VectorStoreException(
                message=f"pgvector similarity search failed: {str(e)}",
                provider_name="pgvector",
                details={"original_error": str(e)}
            ) from e

    def delete(self, document_ids: List[str]) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM document_clauses WHERE id = ANY(:ids);"),
                    {"ids": [int(i) for i in document_ids]}
                )
            return True
        except Exception as e:
            raise VectorStoreException(
                message=f"Failed to delete documents from pgvector: {str(e)}",
                provider_name="pgvector"
            ) from e

    def count(self) -> int:
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text("SELECT COUNT(*) FROM document_clauses;")).scalar()
                return int(res or 0)
        except Exception:
            return 0
