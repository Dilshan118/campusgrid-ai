"""
CampusGrid AI: Dependency Injection Composition Root
Central container wiring all providers, repositories, tools, agents, and orchestrators based on configuration.
Guarantees strict separation of concerns and facilitates zero-code provider switching.
"""

from typing import Optional
from src.config.settings import Settings, get_settings
from src.domain.interfaces.llm import LLMProvider
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.cache import CacheProvider
from src.domain.interfaces.repositories import (
    RoomRepository,
    TimetableRepository,
    MeterHistoryRepository,
    AuditLogRepository,
)
from src.infrastructure.llm.factory import LLMProviderFactory
from src.infrastructure.embeddings.factory import EmbeddingProviderFactory
from src.infrastructure.vector_store.factory import VectorStoreFactory
from src.infrastructure.cache.factory import CacheProviderFactory
from src.infrastructure.database.session import SQLDatabaseSessionManager
from src.infrastructure.database.repositories import (
    InMemoryRoomRepository,
    InMemoryTimetableRepository,
    InMemoryMeterHistoryRepository,
    InMemoryAuditLogRepository,
    PostgresRoomRepository,
    PostgresAuditLogRepository,
)
from src.infrastructure.tools.registry import ToolRegistry
from src.infrastructure.tools.weather_tool import WeatherTool
from src.infrastructure.tools.simulation_tool import SimulationTool
from src.application.services.retrieval_service import RetrievalService
from src.application.services.audit_service import AuditService
from src.agents.telemetry.agent import TelemetryForecastingAgent
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.policy_rag.agent import PolicyRAGAgent
from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
from src.agents.coordinator.agent import CampusGridOrchestrator
from src.infrastructure.reference_baselines import (
    BaselineDemandForecaster,
    BaselineBuildingThermalTwin,
    BaselineBatteryDynamicsModel,
    BaselineCampusMicrogridOptimizer,
)

class Container:
    """Application Composition Root & Dependency Injection Container."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

        # 1. Core Providers
        self.llm_provider: LLMProvider = LLMProviderFactory.create(self.settings.llm)
        self.embedding_provider: EmbeddingProvider = EmbeddingProviderFactory.create(self.settings.embeddings)
        self.cache_provider: CacheProvider = CacheProviderFactory.create(self.settings.cache)

        # 2. Database & Repositories
        if self.settings.database.provider == "postgres":
            self.session_manager = SQLDatabaseSessionManager(self.settings.database)
            self.room_repo: RoomRepository = PostgresRoomRepository(self.session_manager.engine)
            self.timetable_repo: TimetableRepository = InMemoryTimetableRepository()
            self.meter_repo: MeterHistoryRepository = InMemoryMeterHistoryRepository()
            self.audit_repo: AuditLogRepository = PostgresAuditLogRepository(self.session_manager.engine)
            self.vector_store: VectorStore = VectorStoreFactory.create(
                self.settings.vector_store,
                engine=self.session_manager.engine
            )
        else:
            self.session_manager = None
            self.room_repo: RoomRepository = InMemoryRoomRepository()
            self.timetable_repo: TimetableRepository = InMemoryTimetableRepository()
            self.meter_repo: MeterHistoryRepository = InMemoryMeterHistoryRepository()
            self.audit_repo: AuditLogRepository = InMemoryAuditLogRepository()
            self.vector_store: VectorStore = VectorStoreFactory.create(self.settings.vector_store)

        # 3. Tools & MCP Platform
        self.weather_tool = WeatherTool(
            latitude=self.settings.weather.campus_latitude,
            longitude=self.settings.weather.campus_longitude
        )
        self.simulation_tool = SimulationTool(
            c_in=self.settings.physics.building_c_in,
            r_vent=self.settings.physics.building_r_vent
        )
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(self.weather_tool)
        self.tool_registry.register(self.simulation_tool)

        # 4. Application Services
        self.retrieval_service = RetrievalService(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider
        )
        self.audit_service = AuditService(audit_repo=self.audit_repo)

        # 5. Specialized Domain Agents
        # If use_reference_baselines is enabled (e.g. for CI / Team Lead integration testing),
        # the container wires reference baselines. Otherwise, it uses the live member scaffolds.
        if self.settings.use_reference_baselines:
            self.agent1_telemetry = TelemetryForecastingAgent(
                meter_repo=self.meter_repo,
                timetable_repo=self.timetable_repo,
                weather_tool=self.weather_tool,
                forecaster=BaselineDemandForecaster()
            )
            self.agent2_twin = DigitalTwinAgent(
                simulation_tool=self.simulation_tool,
                thermal_twin=BaselineBuildingThermalTwin(
                    c_in=self.settings.physics.building_c_in,
                    r_vent=self.settings.physics.building_r_vent
                ),
                battery_dynamics=BaselineBatteryDynamicsModel(
                    capacity_kwh=self.settings.physics.battery_capacity_kwh,
                    max_power_kw=self.settings.physics.battery_max_power_kw,
                    min_soc_pct=self.settings.physics.battery_min_soc,
                    max_soc_pct=self.settings.physics.battery_max_soc
                )
            )
            self.agent4_dispatch = DispatchExplanationAgent(
                llm_provider=self.llm_provider,
                optimizer=BaselineCampusMicrogridOptimizer(
                    battery_cap_kwh=self.settings.physics.battery_capacity_kwh,
                    max_kw=self.settings.physics.battery_max_power_kw
                )
            )
        else:
            self.agent1_telemetry = TelemetryForecastingAgent(
                meter_repo=self.meter_repo,
                timetable_repo=self.timetable_repo,
                weather_tool=self.weather_tool
            )
            self.agent2_twin = DigitalTwinAgent(
                simulation_tool=self.simulation_tool
            )
            self.agent4_dispatch = DispatchExplanationAgent(
                llm_provider=self.llm_provider
            )

        self.agent3_rag = PolicyRAGAgent(
            retrieval_service=self.retrieval_service
        )

        # 6. Central Orchestrator
        self.orchestrator = CampusGridOrchestrator(
            agent1_telemetry=self.agent1_telemetry,
            agent2_twin=self.agent2_twin,
            agent3_rag=self.agent3_rag,
            agent4_dispatch=self.agent4_dispatch,
            audit_repo=self.audit_repo
        )

_container_instance: Optional[Container] = None

def get_container(settings: Optional[Settings] = None) -> Container:
    """Returns application singleton DI container."""
    global _container_instance
    if _container_instance is None or settings is not None:
        _container_instance = Container(settings)
    return _container_instance
