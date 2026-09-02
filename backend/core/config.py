"""
CampusGrid AI: Core Configuration Manager
Loads environment variables using Pydantic Settings with strict typing,
Neon PostgreSQL compatibility, and pluggable LLM provider support.
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class Settings(BaseSettings):
    # 1. Database (Neon Serverless PostgreSQL + pgvector)
    database_url: str = Field(
        default="postgresql://campusgrid_user:campusgrid_secure_password@localhost:5432/campusgrid_db",
        description="PostgreSQL connection string (supports Neon with sslmode=require)"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # 2. Pluggable LLM Switch
    llm_provider: str = Field(default="gemini", description="'gemini', 'openai', 'anthropic', 'groq', 'ollama'")
    llm_model: str = Field(default="gemini/gemini-1.5-flash", description="Model identifier")
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1500

    # 3. Provider API Keys
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # 4. Weather API
    weather_provider: str = "open-meteo"
    openweather_api_key: Optional[str] = None
    campus_latitude: float = 6.9147
    campus_longitude: float = 79.9733

    # 5. Security & JWT
    jwt_secret_key: str = "campusgrid_super_secret_jwt_key_replace_in_production_32b"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # 6. RAG & Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    rag_top_k: int = 2

    # 7. Deterministic Physical Safety Bounds
    comfort_min_temp_c: float = 21.0
    comfort_max_temp_c: float = 25.5
    battery_min_soc: float = 0.20
    battery_max_soc: float = 0.90
    battery_capacity_kwh: float = 500.0
    battery_max_power_kw: float = 100.0

    # 8. Server & Client
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    @validator("database_url", pre=True)
    def normalize_database_url(cls, v: str) -> str:
        """Neon sometimes gives postgres:// instead of postgresql://. Normalize it."""
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton configuration instance."""
    return Settings()
