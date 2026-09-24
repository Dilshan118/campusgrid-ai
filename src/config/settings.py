"""
CampusGrid AI: Modular Configuration Management
Organized hierarchical settings using Pydantic Settings v2.
Allows switching any infrastructure provider (LLM, Embeddings, Vector Store, Database, Cache, Reranker)
via environment variables with zero code modifications.
"""

import os
from functools import lru_cache
from typing import Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The JWT secret shipped in .env.example. Accepted for local development only.
DEFAULT_JWT_SECRET = "campusgrid_super_secret_jwt_key_replace_in_production_32b"

# Slices that can be swapped for their reference baseline (see REFERENCE_BASELINE_AGENTS).
BASELINE_AGENT_KEYS = {"agent1", "agent2", "agent4"}

class LLMSettings(BaseModel):
    provider: str = Field(default="mock", description="'litellm', 'openai', 'gemini', 'anthropic', 'groq', 'ollama', 'mock'")
    model: str = Field(default="gemini/gemini-1.5-flash", description="Model identifier")
    temperature: float = 0.2
    max_tokens: int = 1500
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

class EmbeddingSettings(BaseModel):
    provider: str = Field(default="auto", description="'auto', 'sentence_transformers', 'mock'")
    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    dimension: int = 384

class VectorStoreSettings(BaseModel):
    provider: str = Field(default="memory", description="'memory', 'pgvector', 'chroma'")
    top_k: int = 2
    persist_dir: str = "backend/data/storage/chroma_db"

class DatabaseSettings(BaseModel):
    provider: str = Field(default="in_memory", description="'in_memory', 'postgres'")
    database_url: str = Field(
        default="postgresql://campusgrid_user:campusgrid_secure_password@localhost:5432/campusgrid_db"
    )
    pool_size: int = 10
    max_overflow: int = 20

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

class CacheSettings(BaseModel):
    provider: str = Field(default="memory", description="'memory', 'redis'")
    ttl_seconds: int = 300
    redis_url: Optional[str] = None

class RerankerSettings(BaseModel):
    strategy: str = Field(default="rrf", description="'rrf', 'cross_encoder', 'passthrough'")
    rrf_k: int = 60

class SecuritySettings(BaseModel):
    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    max_request_body_bytes: int = 1_048_576
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 5

class PhysicsSettings(BaseModel):
    comfort_min_temp_c: float = 21.0
    comfort_max_temp_c: float = 25.5
    battery_min_soc: float = 0.20
    battery_max_soc: float = 0.90
    battery_capacity_kwh: float = 500.0
    battery_max_power_kw: float = 100.0
    building_c_in: float = 50.0      # Thermal capacitance (kWh / °C)
    building_r_vent: float = 2.5     # Thermal resistance (°C / kW)

class WeatherSettings(BaseModel):
    provider: str = "open-meteo"
    openweather_api_key: Optional[str] = None
    campus_latitude: float = 6.9147
    campus_longitude: float = 79.9733

class Settings(BaseSettings):
    """Root Application Settings with nested modular domain configurations."""
    app_env: str = Field(default="development", description="'development', 'production', 'test'")
    app_name: str = "CampusGrid AI"
    app_version: str = "4.2.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # Flat environment variable mappings
    llm_provider: str = "mock"
    llm_model: str = "gemini/gemini-1.5-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1500
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # 'auto' uses sentence-transformers when it is installed and its model loads, otherwise the mock.
    embedding_provider: str = "auto"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    rag_top_k: int = 2

    vector_store_provider: str = "memory"
    database_provider: str = "in_memory"
    database_url: str = "postgresql://campusgrid_user:campusgrid_secure_password@localhost:5432/campusgrid_db"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    cache_provider: str = "memory"
    reranker_strategy: str = "rrf"

    weather_provider: str = "open-meteo"
    openweather_api_key: Optional[str] = None
    campus_latitude: float = 6.9147
    campus_longitude: float = 79.9733

    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    max_request_body_bytes: int = 1_048_576
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 5

    comfort_min_temp_c: float = 21.0
    comfort_max_temp_c: float = 25.5
    battery_min_soc: float = 0.20
    battery_max_soc: float = 0.90
    battery_capacity_kwh: float = 500.0
    battery_max_power_kw: float = 100.0
    use_reference_baselines: bool = Field(
        default=False,
        description="When True, container falls back to reference baseline algorithms for agents 1, 2, 4"
    )
    auto_baseline_fallback: bool = Field(
        default=True,
        description=(
            "When a member slice still raises NotImplementedError, wire its reference baseline instead "
            "and report it in /api/health, so a default install always runs end to end."
        )
    )
    reference_baseline_agents: str = Field(
        default="",
        description=(
            "Comma-separated subset of 'agent1,agent2,agent4' to run on reference baselines while "
            "the others run member code. Ignored when USE_REFERENCE_BASELINES=true (all three)."
        )
    )

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret_key == DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be changed from the .env.example default in production.")
        unknown = self.baseline_agents - BASELINE_AGENT_KEYS
        if unknown:
            raise ValueError(
                f"REFERENCE_BASELINE_AGENTS contains unknown entries {sorted(unknown)}; "
                f"allowed: {sorted(BASELINE_AGENT_KEYS)}"
            )
        return self

    @property
    def baseline_agents(self) -> Set[str]:
        """The agent slices that should be wired to their reference baseline."""
        if self.use_reference_baselines:
            return set(BASELINE_AGENT_KEYS)
        return {a.strip().lower() for a in self.reference_baseline_agents.split(",") if a.strip()}

    @property
    def llm(self) -> LLMSettings:
        return LLMSettings(
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
            gemini_api_key=self.gemini_api_key,
            openai_api_key=self.openai_api_key,
            anthropic_api_key=self.anthropic_api_key,
            groq_api_key=self.groq_api_key,
        )

    @property
    def embeddings(self) -> EmbeddingSettings:
        provider = self.embedding_provider
        if provider == "auto" and self.app_env == "test":
            provider = "mock"  # tests stay hermetic and fast unless they ask for a real model
        return EmbeddingSettings(
            provider=provider,
            model=self.embedding_model,
            dimension=self.embedding_dimension,
        )

    @property
    def vector_store(self) -> VectorStoreSettings:
        return VectorStoreSettings(
            provider=self.vector_store_provider,
            top_k=self.rag_top_k,
        )

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            provider=self.database_provider,
            database_url=self.database_url,
            pool_size=self.database_pool_size,
            max_overflow=self.database_max_overflow,
        )

    @property
    def cache(self) -> CacheSettings:
        return CacheSettings(
            provider=self.cache_provider,
        )

    @property
    def reranker(self) -> RerankerSettings:
        return RerankerSettings(
            strategy=self.reranker_strategy,
        )

    @property
    def security(self) -> SecuritySettings:
        return SecuritySettings(
            jwt_secret_key=self.jwt_secret_key,
            jwt_algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            max_request_body_bytes=self.max_request_body_bytes,
            login_max_failed_attempts=self.login_max_failed_attempts,
            login_lockout_minutes=self.login_lockout_minutes,
        )

    @property
    def physics(self) -> PhysicsSettings:
        return PhysicsSettings(
            comfort_min_temp_c=self.comfort_min_temp_c,
            comfort_max_temp_c=self.comfort_max_temp_c,
            battery_min_soc=self.battery_min_soc,
            battery_max_soc=self.battery_max_soc,
            battery_capacity_kwh=self.battery_capacity_kwh,
            battery_max_power_kw=self.battery_max_power_kw,
        )

    @property
    def weather(self) -> WeatherSettings:
        return WeatherSettings(
            provider=self.weather_provider,
            openweather_api_key=self.openweather_api_key,
            campus_latitude=self.campus_latitude,
            campus_longitude=self.campus_longitude,
        )

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Returns cached singleton configuration instance."""
    return Settings()
