"""
CampusGrid AI: Domain Interfaces Module Root
Exposes all foundational and domain-specific ML interfaces.
"""

from src.domain.interfaces.llm import LLMProvider, LLMMessage, LLMResponse
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.vector_store import VectorStore, VectorSearchResult
from src.domain.interfaces.database import DatabaseSessionManager
from src.domain.interfaces.repositories import (
    RoomRepository,
    TimetableRepository,
    MeterHistoryRepository,
    AuditLogRepository,
    AnalyticsEventRepository,
)
from src.domain.interfaces.cache import CacheProvider
from src.domain.interfaces.reranker import Reranker, RerankResult
from src.domain.interfaces.keyword_search import KeywordSearchEngine
from src.domain.interfaces.tool import Tool, ToolResult

# 4 Specialized ML Agent Interfaces
from src.domain.interfaces.forecaster import DemandForecasterInterface, ForecasterTrainerInterface
from src.domain.interfaces.thermal_twin import BuildingThermalTwinInterface, BatteryDynamicsInterface
from src.domain.interfaces.policy_extractor import RegulatoryRuleExtractorInterface, PolicySearchEngineInterface
from src.domain.interfaces.optimizer import (
    MicrogridOptimizerInterface,
    XAIExplainerInterface,
    FaithfulnessVerifierInterface,
)

__all__ = [
    # Core Infrastructure Interfaces
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "EmbeddingProvider",
    "VectorStore",
    "VectorSearchResult",
    "DatabaseSessionManager",
    "RoomRepository",
    "TimetableRepository",
    "MeterHistoryRepository",
    "AuditLogRepository",
    "AnalyticsEventRepository",
    "CacheProvider",
    "Reranker",
    "RerankResult",
    "KeywordSearchEngine",
    "Tool",
    "ToolResult",
    # 4 ML Domain Interfaces
    "DemandForecasterInterface",
    "ForecasterTrainerInterface",
    "BuildingThermalTwinInterface",
    "BatteryDynamicsInterface",
    "RegulatoryRuleExtractorInterface",
    "PolicySearchEngineInterface",
    "MicrogridOptimizerInterface",
    "XAIExplainerInterface",
    "FaithfulnessVerifierInterface",
]
