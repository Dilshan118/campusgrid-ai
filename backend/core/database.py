"""
CampusGrid AI: Database Connection & Session Manager
Configures SQLAlchemy & SQLModel engine with native support for Neon Serverless
PostgreSQL and the pgvector extension.
"""

from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from backend.core.config import get_settings

settings = get_settings()

# Engine creation with connection pooling for Neon / PostgreSQL
# Note: Neon works best with standard connection pooling or Neon's pgbouncer pooler URL
engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Crucial for serverless databases that sleep
)

def init_db():
    """
    Initializes PostgreSQL extensions (vector) and creates all SQLModel tables.
    Safe to run repeatedly on startup.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    with Session(engine) as session:
        yield session
