"""
CampusGrid AI: Dependency Injection Composition Root
Central container wiring all providers, repositories, tools, agents, and orchestrators based on configuration.
Guarantees strict separation of concerns and facilitates zero-code provider switching.
"""

import logging
from typing import Any, Dict, List, Optional
from src.config.settings import Settings, get_settings
from src.domain.interfaces.llm import LLMProvider
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.vector_store import VectorStore
from src.domain.interfaces.cache import CacheProvider
from src.domain.interfaces.reranker import Reranker
from src.domain.interfaces.repositories import (
    RoomRepository,
    TimetableRepository,
    MeterHistoryRepository,
    AuditLogRepository,
    AnalyticsEventRepository,
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
    InMemoryAnalyticsEventRepository,
    PostgresRoomRepository,
    PostgresTimetableRepository,
    PostgresMeterHistoryRepository,
    PostgresAuditLogRepository,
    PostgresAnalyticsEventRepository,
)
from src.infrastructure.retrieval import BM25SearchEngine, RRFReranker, PassthroughReranker
from src.infrastructure.tools.registry import ToolRegistry
from src.infrastructure.tools.weather_tool import WeatherTool
from src.infrastructure.tools.simulation_tool import SimulationTool
from src.pipelines.document_ingestion.ingest_corpus import DocumentIngestionPipeline
from src.application.services.retrieval_service import RetrievalService
from src.application.services.audit_service import AuditService
from src.application.services.analytics_service import AnalyticsService
from src.agents.telemetry.agent import TelemetryForecastingAgent
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.policy_rag.agent import PolicyRAGAgent
from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
from src.agents.coordinator.agent import CampusGridOrchestrator
from src.agents.coordinator.nlp_parser import NLPQueryParser
from src.agents.coordinator.intent_router import LLMIntentRouter
from src.agents.telemetry.forecaster import DemandForecaster
from src.agents.digital_twin.thermal_model import BuildingThermalTwin
from src.agents.digital_twin.battery_dynamics import BatteryDynamicsModel
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.domain.entities.telemetry import TelemetryInterval
from src.domain.entities.optimization import OptimizationInput
from src.infrastructure.reference_baselines import (
    BaselineDemandForecaster,
    BaselineBuildingThermalTwin,
    BaselineBatteryDynamicsModel,
    BaselineCampusMicrogridOptimizer,
)

logger = logging.getLogger("campusgrid.container")


# Tiny inputs that let the container tell "not written yet" (NotImplementedError) apart from working
# code at startup. Any other exception means the code exists; it is left in place and fails loudly
# at request time rather than being hidden behind a baseline.
def _probe_forecaster(forecaster):
    interval = TelemetryInterval(time_slot="12:00", base_load_kw=400.0, solar_gen_kw=100.0, outdoor_temp_c=30.0,
                                 grid_tariff_lkr_kwh=30.0, zone_occupancy_count=50)
    forecaster.predict([interval], [30.0], [50])


def _probe_thermal(twin):
    twin.simulate(initial_temp_c=24.0, ambient_temps=[28.0], occupant_counts=[0], hvac_power_kw=[0.0])


def _probe_battery(battery):
    battery.simulate_soc_trajectory(250.0, [0.0], [0.0])


def _probe_optimizer(optimizer):
    optimizer.solve(OptimizationInput(time_slots=["00:00", "00:30"], base_load_kw=[100.0, 100.0],
                                      solar_gen_kw=[0.0, 0.0], grid_tariff_lkr_kwh=[15.0, 15.0]))


def _implemented(probe, target) -> bool:
    try:
        probe(target)
    except NotImplementedError:
        return False
    except Exception as exc:  # implemented but unhappy with the probe input — keep member code
        logger.debug("Startup probe of %s raised %s; keeping member implementation.", type(target).__name__, exc)
    return True


def _build_reranker(strategy: str, rrf_k: int) -> Reranker:
    strategy = (strategy or "rrf").lower().strip()
    if strategy == "rrf":
        return RRFReranker(k=rrf_k)
    if strategy == "passthrough":
        return PassthroughReranker()
    raise ValueError(
        f"RERANKER_STRATEGY='{strategy}' is not implemented. Use 'rrf' or 'passthrough' "
        "(cross-encoder reranking was evaluated and deferred — see docs/README.md)."
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
            engine = self.session_manager.engine
            self.room_repo: RoomRepository = PostgresRoomRepository(engine)
            self.timetable_repo: TimetableRepository = PostgresTimetableRepository(engine)
            self.meter_repo: MeterHistoryRepository = PostgresMeterHistoryRepository(engine)
            self.audit_repo: AuditLogRepository = PostgresAuditLogRepository(engine)
            self.analytics_repo: AnalyticsEventRepository = PostgresAnalyticsEventRepository(engine)
            self.vector_store: VectorStore = VectorStoreFactory.create(self.settings.vector_store, engine=engine)
        else:
            self.session_manager = None
            self.room_repo = InMemoryRoomRepository()
            self.timetable_repo = InMemoryTimetableRepository()
            self.meter_repo = InMemoryMeterHistoryRepository()
            self.audit_repo = InMemoryAuditLogRepository()
            self.analytics_repo = InMemoryAnalyticsEventRepository()
            self.vector_store = VectorStoreFactory.create(self.settings.vector_store)

        # 3. Tools & MCP Platform
        if (self.settings.weather.provider or "").lower() != "open-meteo":
            raise ValueError(
                f"WEATHER_PROVIDER='{self.settings.weather.provider}' is not implemented; only 'open-meteo' is supported."
            )
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
        self.keyword_engine = BM25SearchEngine()
        self.reranker = _build_reranker(self.settings.reranker.strategy, self.settings.reranker.rrf_k)
        self.ingestion_pipeline = DocumentIngestionPipeline(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            keyword_engine=self.keyword_engine,
        )
        self.retrieval_service = RetrievalService(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            keyword_engine=self.keyword_engine,
            reranker=self.reranker,
            ingestion_pipeline=self.ingestion_pipeline,
            cache=self.cache_provider,
        )
        self.audit_service = AuditService(audit_repo=self.audit_repo)
        self.analytics_service = AnalyticsService(event_repo=self.analytics_repo)

        # 5. Specialized Domain Agents
        # Each of agents 1, 2 and 4 runs member code unless it is listed in the baseline set
        # (USE_REFERENCE_BASELINES=true selects all three; REFERENCE_BASELINE_AGENTS picks some),
        # so a finished slice is never replaced just because another slice is unfinished.
        # With AUTO_BASELINE_FALLBACK (default on), a slice whose member code still raises
        # NotImplementedError is swapped for its baseline at startup and reported in /api/health.
        physics = self.settings.physics
        self.baseline_agents = set(self.settings.baseline_agents)
        self.slice_notes: Dict[str, str] = {a: "configured" for a in self.baseline_agents}

        forecaster = self._forecaster(baseline="agent1" in self.baseline_agents)
        thermal_twin, battery = self._twin_models(baseline="agent2" in self.baseline_agents)
        optimizer = self._optimizer(baseline="agent4" in self.baseline_agents)

        if self.settings.auto_baseline_fallback:
            if "agent1" not in self.baseline_agents and not _implemented(_probe_forecaster, forecaster):
                forecaster = self._forecaster(baseline=True)
                self._mark_auto("agent1")
            if "agent2" not in self.baseline_agents and not (
                _implemented(_probe_thermal, thermal_twin) and _implemented(_probe_battery, battery)
            ):
                thermal_twin, battery = self._twin_models(baseline=True)
                self._mark_auto("agent2")
            if "agent4" not in self.baseline_agents and not _implemented(_probe_optimizer, optimizer):
                optimizer = self._optimizer(baseline=True)
                self._mark_auto("agent4")

        self.agent1_telemetry = TelemetryForecastingAgent(
            meter_repo=self.meter_repo,
            timetable_repo=self.timetable_repo,
            weather_tool=self.weather_tool,
            forecaster=forecaster,
            llm_provider=self.llm_provider,
        )
        self.agent2_twin = DigitalTwinAgent(
            simulation_tool=self.simulation_tool,
            thermal_twin=thermal_twin,
            battery_dynamics=battery,
        )
        self.agent4_dispatch = DispatchExplanationAgent(
            llm_provider=self.llm_provider,
            optimizer=optimizer,
        )

        self.agent3_rag = PolicyRAGAgent(
            retrieval_service=self.retrieval_service
        )

        # 6. Central Orchestrator
        self.nlp_parser = NLPQueryParser(
            rooms=self._room_inventory(),
            comfort_min_c=physics.comfort_min_temp_c,
            comfort_max_c=physics.comfort_max_temp_c,
        )
        self.orchestrator = CampusGridOrchestrator(
            agent1_telemetry=self.agent1_telemetry,
            agent2_twin=self.agent2_twin,
            agent3_rag=self.agent3_rag,
            agent4_dispatch=self.agent4_dispatch,
            audit_repo=self.audit_repo,
            nlp_parser=self.nlp_parser,
            intent_router=LLMIntentRouter(llm_provider=self.llm_provider),
            comfort_min_c=physics.comfort_min_temp_c,
            comfort_max_c=physics.comfort_max_temp_c,
            battery_limits={
                "capacity_kwh": physics.battery_capacity_kwh,
                "min_soc_kwh": physics.battery_capacity_kwh * physics.battery_min_soc,
                "max_soc_kwh": physics.battery_capacity_kwh * physics.battery_max_soc,
                "max_power_kw": physics.battery_max_power_kw,
            },
        )

    def nlp_parser_rooms(self) -> List[Dict[str, Any]]:
        """Room inventory as the NLP parser knows it (what the dashboard offers in pickers)."""
        return [
            {k: room.get(k) for k in ("room_id", "building_name", "room_type", "max_capacity")}
            for room in self.nlp_parser.rooms.values()
        ]

    def _room_inventory(self) -> Optional[List[Dict[str, Any]]]:
        try:
            return self.room_repo.list_all() or None
        except Exception as e:  # database unreachable at startup: parser uses its seed inventory
            logger.warning("Room inventory unavailable (%s); NLP parser falls back to the seed rooms.", type(e).__name__)
            return None

    # -- slice construction (member code or reference baseline, always from settings) --------

    def _forecaster(self, baseline: bool):
        return BaselineDemandForecaster() if baseline else DemandForecaster()

    def _twin_models(self, baseline: bool):
        p = self.settings.physics
        if baseline:
            return (
                BaselineBuildingThermalTwin(c_in=p.building_c_in, r_vent=p.building_r_vent),
                BaselineBatteryDynamicsModel(capacity_kwh=p.battery_capacity_kwh, max_power_kw=p.battery_max_power_kw,
                                             min_soc_pct=p.battery_min_soc, max_soc_pct=p.battery_max_soc),
            )
        return (
            BuildingThermalTwin(c_in=p.building_c_in, r_vent=p.building_r_vent),
            BatteryDynamicsModel(capacity_kwh=p.battery_capacity_kwh, max_power_kw=p.battery_max_power_kw,
                                 min_soc_pct=p.battery_min_soc, max_soc_pct=p.battery_max_soc),
        )

    def _optimizer(self, baseline: bool):
        p = self.settings.physics
        if baseline:
            return BaselineCampusMicrogridOptimizer(battery_cap_kwh=p.battery_capacity_kwh, max_kw=p.battery_max_power_kw)
        return CampusMicrogridOptimizer(battery_cap_kwh=p.battery_capacity_kwh, max_kw=p.battery_max_power_kw)

    def _mark_auto(self, agent_key: str) -> None:
        self.baseline_agents.add(agent_key)
        self.slice_notes[agent_key] = "auto: member code not implemented yet"
        logger.warning("%s member code is not implemented yet; running its reference baseline.", agent_key)

    def slice_status(self) -> Dict[str, str]:
        """Which implementation each agent slice is running — reported by /api/health."""
        def status(key: str) -> str:
            if key not in self.baseline_agents:
                return "member_implementation"
            return "reference_baseline_auto" if self.slice_notes.get(key, "").startswith("auto") else "reference_baseline"
        return {
            "agent1_telemetry": status("agent1"),
            "agent2_digital_twin": status("agent2"),
            "agent3_policy_rag": "member_implementation",
            "agent4_dispatch": status("agent4"),
        }


_container_instance: Optional[Container] = None

def get_container(settings: Optional[Settings] = None) -> Container:
    """Returns application singleton DI container."""
    global _container_instance
    if _container_instance is None or settings is not None:
        _container_instance = Container(settings)
    return _container_instance
