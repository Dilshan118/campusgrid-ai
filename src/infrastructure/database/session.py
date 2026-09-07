"""
CampusGrid AI: Database Session Manager
Configures SQLAlchemy / SQLModel engine and session generation with Neon pooler support.
"""

from typing import Generator, Optional
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from src.domain.interfaces.database import DatabaseSessionManager
from src.config.settings import DatabaseSettings

class SQLDatabaseSessionManager(DatabaseSessionManager):
    """Manages SQLAlchemy / SQLModel connection engines and sessions."""

    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.engine = create_engine(
            settings.database_url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_pre_ping=True,
        )

    def init_database(self) -> None:
        """Creates pgvector extension and executes SQLModel table creation."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                conn.commit()
            SQLModel.metadata.create_all(self.engine)
        except Exception:
            # Tolerant if extensions fail (e.g. SQLite test database)
            SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            yield session
