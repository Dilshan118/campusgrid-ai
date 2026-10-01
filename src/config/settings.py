"""
CampusGrid AI: Modular Configuration Management
Organized hierarchical settings using Pydantic Settings v2.
Allows switching any infrastructure provider (LLM, Embeddings, Vector Store, Database, Cache, Reranker)
via environment variables with zero code modifications.
"""

import logging
import os
import secrets
from functools import lru_cache
from typing import Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("campusgrid.config")

# The JWT secret shipped in .env.example. Never used to sign tokens: outside production it is
# swapped for a random per-process key, and production refuses to start with it.
DEFAULT_JWT_SECRET = "campusgrid_super_secret_jwt_key_replace_in_production_32b"
MIN_JWT_SECRET_CHARS = 32

# Gemini 1.5 models are retired and no longer in LiteLLM's model catalogue.
DEFAULT_LLM_MODEL = "gemini/gemini-3.5-flash"

# Slices that can be swapped for their reference baseline (see REFERENCE_BASELINE_AGENTS).
BASELINE_AGENT_KEYS = {"agent1", "agent2", "agent4"}

class LLMSettings(BaseModel):
    provider: str = Field(default="mock", description="'litellm', 'openai', 'gemini', 'anthropic', 'groq', 'ollama', 'mock'")
    model: str = Field(default=DEFAULT_LLM_MODEL, description="LiteLLM model identifier, e.g. 'gemini/<model>'")
    temperature: float = 0.2
    max_tokens: int = 1500
    timeout_seconds: float = 30.0
    num_retries: int = 2
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

class EmbeddingSettings(BaseModel):
    provider: str = Field(default="auto", description="'auto', 'sentence_transformers', 'google', 'gemini', 'mock'")
    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    dimension: int = 384
    api_key: Optional[str] = None

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
    # 2R2C building thermal model (SRS section 6.1). Uncalibrated defaults except c_in / r_vent.
    building_c_in: float = 50.0      # Indoor air + furnishings thermal capacitance (kWh / °C)
    building_r_vent: float = 2.5     # Ventilation / infiltration resistance, indoor <-> outdoor (°C / kW)
    building_c_wall: float = 200.0   # Building envelope (wall) thermal capacitance (kWh / °C)
    building_r_in: float = 2.0       # Wall surface <-> indoor air resistance (°C / kW)
    building_r_out: float = 6.0      # Wall <-> outdoor air resistance (°C / kW)
    hvac_max_cooling_kw: float = 35.0  # Rated cooling of one zone's chiller share (kW thermal)

class LoadFlexibilitySettings(BaseModel):
    """How the campus demand forecast is split into load tiers for the optimizer.

    There is no sub-metering, so the split is an assumption stated on every plan: the
    air-conditioning share of campus demand (Tier 1), how far each half-hour of it may move
    (energy-neutral pre-cooling; 0 disables HVAC flexibility), and the site power factor.
    Tier 2 (shiftable pumps / EV chargers) is entered per plan on the dispatch form."""
    hvac_load_share: float = Field(default=0.40, ge=0.0, le=0.9)
    hvac_flex_ratio: float = Field(default=0.10, ge=0.0, le=0.5)
    power_factor: float = Field(default=1.0, gt=0.5, le=1.0)
    max_grid_import_kw: Optional[float] = Field(default=None, gt=0)

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

    # Public pilot inquiry email. Secrets are supplied only through the deployment environment.
    pilot_smtp_host: Optional[str] = None
    pilot_smtp_port: int = 587
    pilot_smtp_username: Optional[str] = None
    pilot_smtp_password: Optional[str] = None
    pilot_smtp_starttls: bool = True
    pilot_email_from: Optional[str] = None
    pilot_email_recipient: str = "amasha.weerasuriya003@gmail.com"
    pilot_email_timeout_seconds: float = 10.0

    # Flat environment variable mappings
    llm_provider: str = "mock"
    llm_model: str = DEFAULT_LLM_MODEL
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1500
    llm_timeout_seconds: float = 30.0
    llm_num_retries: int = 2
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
    # HMAC key for the audit hash chain (SEC-09). Keep it out of the database's reach; required in production.
    audit_signing_key: Optional[str] = None
    # Rows written before the key was configured (plain SHA-256). Set once, to the row count at the
    # moment the key is introduced; any other unkeyed row fails verification. 0 for a new database.
    audit_legacy_unkeyed_rows: int = 0
    # SEC-05: when true, the manager who requested a plan cannot approve it (four-eyes rule).
    # Off by default because the demo build has a single FACILITY_MANAGER account.
    require_separate_approver: bool = False
    # Per-user limit on the expensive planning endpoints (LLM + solver), requests per minute. 0 disables.
    planner_rate_limit_per_minute: int = 30

    comfort_min_temp_c: float = 21.0
    comfort_max_temp_c: float = 25.5
    battery_min_soc: float = 0.20
    battery_max_soc: float = 0.90
    battery_capacity_kwh: float = 500.0
    battery_max_power_kw: float = 100.0
    building_c_in: float = 50.0
    building_r_vent: float = 2.5
    building_c_wall: float = 200.0
    building_r_in: float = 2.0
    building_r_out: float = 6.0
    hvac_max_cooling_kw: float = 35.0
    campus_hvac_load_share: float = 0.40
    hvac_flex_ratio: float = 0.10
    site_power_factor: float = 1.0
    max_grid_import_kw: Optional[float] = None
    regulation_review_required: bool = Field(
        default=True,
        description=(
            "New regulation text must go through POST /api/rag/submissions and a second reviewer before it is "
            "indexed. False re-enables immediate indexing through POST /api/rag/ingest (tests, local corpus work)."
        ),
    )
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

    def __init__(self, **values):
        super().__init__(**values)
        if self.app_env == "test":
            if "vector_store_provider" not in values:
                self.vector_store_provider = "memory"
            if "database_provider" not in values:
                self.database_provider = "in_memory"
            if "llm_provider" not in values:
                self.llm_provider = "mock"
            if "embedding_provider" not in values:
                self.embedding_provider = "mock"
            if "planner_rate_limit_per_minute" not in values:
                self.planner_rate_limit_per_minute = 0  # the suite fires many requests per user

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret_key == DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be changed from the .env.example default in production.")
        if self.app_env == "production" and len(self.jwt_secret_key) < MIN_JWT_SECRET_CHARS:
            raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_CHARS} characters in production.")
        if self.app_env == "production" and len(self.audit_signing_key or "") < MIN_JWT_SECRET_CHARS:
            raise ValueError(
                f"AUDIT_SIGNING_KEY must be set (at least {MIN_JWT_SECRET_CHARS} characters) in production, "
                "otherwise anyone with database write access can rewrite the audit trail undetected."
            )
        if self.jwt_secret_key == DEFAULT_JWT_SECRET:
            # SEC-02: the default is public (it is in the repository), so anyone could sign a
            # FACILITY_MANAGER token with it. Outside production it is replaced by a random
            # per-process key: nothing is ever signed with the public value. Set JWT_SECRET_KEY
            # to keep sessions across restarts.
            logger.warning("JWT_SECRET_KEY is the public example value; using a random per-process key instead.")
            self.jwt_secret_key = secrets.token_urlsafe(48)
        unknown = self.baseline_agents - BASELINE_AGENT_KEYS
        if unknown:
            raise ValueError(
                f"REFERENCE_BASELINE_AGENTS contains unknown entries {sorted(unknown)}; "
                f"allowed: {sorted(BASELINE_AGENT_KEYS)}"
            )
        return self

    @property
    def audit_signing_key_bytes(self) -> Optional[bytes]:
        return self.audit_signing_key.encode("utf-8") if self.audit_signing_key else None

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
            timeout_seconds=self.llm_timeout_seconds,
            num_retries=self.llm_num_retries,
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
            api_key=self.gemini_api_key,
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
            building_c_in=self.building_c_in,
            building_r_vent=self.building_r_vent,
            building_c_wall=self.building_c_wall,
            building_r_in=self.building_r_in,
            building_r_out=self.building_r_out,
            hvac_max_cooling_kw=self.hvac_max_cooling_kw,
        )

    @property
    def load_flexibility(self) -> LoadFlexibilitySettings:
        return LoadFlexibilitySettings(
            hvac_load_share=self.campus_hvac_load_share,
            hvac_flex_ratio=self.hvac_flex_ratio,
            power_factor=self.site_power_factor,
            max_grid_import_kw=self.max_grid_import_kw,
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
