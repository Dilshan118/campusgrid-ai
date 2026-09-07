"""
CampusGrid AI: Central Orchestrator & Multi-Agent Coordinator
Manages the deterministic 4-agent execution pipeline:
User Query -> NLP Parser -> Agent 1 (Forecast) -> Agent 2 (Simulation) -> Agent 3 (RAG) -> Agent 4 (Solver & XAI) -> Audit Store -> Human Approval
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.agents.base.state import MultiAgentState
from src.agents.coordinator.nlp_parser import NLPQueryParser
from src.agents.telemetry.agent import TelemetryForecastingAgent
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.policy_rag.agent import PolicyRAGAgent
from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import AuditRecord
from src.domain.exceptions.base import DomainException


class AgentPipelineError(DomainException):
    """Raised when a step of the sequential 4-agent pipeline fails.

    Raising rather than returning an error dict matters: BaseAgent.execute() converts this
    into AgentExecutionResult(success=False), which the API layer turns into a real HTTP
    error. Returning a dict instead produced a misleading HTTP 200 with the failure buried
    in the response body.
    """

    def __init__(self, agent_label: str, reason: Optional[str]):
        super().__init__(
            message=f"{agent_label} failed: {reason}",
            error_code="AGENT_PIPELINE_FAILED",
            details={"failed_stage": agent_label, "reason": reason},
        )

class CampusGridOrchestrator(BaseAgent):
    """Central multi-agent coordinator implementing the 4-agent pipeline."""

    def __init__(
        self,
        agent1_telemetry: TelemetryForecastingAgent,
        agent2_twin: DigitalTwinAgent,
        agent3_rag: PolicyRAGAgent,
        agent4_dispatch: DispatchExplanationAgent,
        audit_repo: AuditLogRepository,
        nlp_parser: Optional[NLPQueryParser] = None
    ):
        super().__init__(
            name="Central Orchestrator",
            description="Coordinates multi-agent microgrid execution across forecasting, simulation, RAG, and solver."
        )
        self.agent1 = agent1_telemetry
        self.agent2 = agent2_twin
        self.agent3 = agent3_rag
        self.agent4 = agent4_dispatch
        self.audit_repo = audit_repo
        self.nlp_parser = nlp_parser or NLPQueryParser()

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_query = input_data.get("query", "Optimize 24h battery schedule to minimize peak demand charge.")
        user_id = input_data.get("user_id", "operator_facility_manager")
        session_id = input_data.get("session_id", str(uuid.uuid4()))

        # 1. NLP Parameter Extraction
        parsed = self.nlp_parser.parse(user_query)

        # 2. Step 1: Agent 1 (Telemetry & Forecasting)
        a1_res = self.agent1.execute({
            "date": parsed["date"],
            "room": parsed["room"],
            "building": parsed["building"]
        })
        if not a1_res.success:
            raise AgentPipelineError("Agent 1 (Telemetry & Forecasting)", a1_res.error)

        # 3. Step 2: Agent 2 (Digital Twin Simulation)
        a2_res = self.agent2.execute({
            "initial_temp_c": parsed.get("target_temp_c", 24.0),
            "ambient_temperatures_c": a1_res.data.get("ambient_temperatures_c", []),
            "occupancy_counts": a1_res.data.get("occupancy_counts", []),
            "perturb_temp_delta_c": float(input_data.get("perturb_temp_delta_c", 0.0)),
            "perturb_occ_multiplier": float(input_data.get("perturb_occ_multiplier", 1.0))
        })
        if not a2_res.success:
            raise AgentPipelineError("Agent 2 (Digital Twin Simulation)", a2_res.error)

        # 4. Step 3: Agent 3 (Policy & Information Retrieval RAG)
        a3_res = self.agent3.execute({
            "query": user_query,
            "top_k": 2
        })
        if not a3_res.success:
            raise AgentPipelineError("Agent 3 (Policy & Information Retrieval)", a3_res.error)

        # 5. Step 4: Agent 4 (Dispatch & Explanation)
        a4_res = self.agent4.execute({
            "time_slots": a1_res.data.get("time_slots", []),
            "forecast_demand_kw": a1_res.data.get("forecast_demand_kw", []),
            "forecast_solar_kw": a1_res.data.get("forecast_solar_kw", []),
            "tariffs_lkr_kwh": a1_res.data.get("tariffs_lkr_kwh", []),
            "citations": a3_res.data.get("citations", []),
            "user_query": user_query
        })
        if not a4_res.success:
            raise AgentPipelineError("Agent 4 (Dispatch & Explanation)", a4_res.error)

        # 6. Assemble sequence and log to immutable audit store
        agent_sequence = {
            "agent1_telemetry": a1_res.model_dump(),
            "agent2_digital_twin": a2_res.model_dump(),
            "agent3_policy_rag": a3_res.model_dump(),
            "agent4_dispatch": a4_res.model_dump()
        }

        final_decision = {
            "solver_summary": a4_res.data.get("solver_output", {}),
            "net_savings_lkr": a4_res.data.get("net_savings_lkr"),
            "savings_percentage": a4_res.data.get("savings_percentage"),
            "peak_shaved_kw": a4_res.data.get("peak_shaved_kw"),
            "explanation": a4_res.data.get("explanation"),
            "faithfulness_audit": a4_res.data.get("faithfulness_audit")
        }

        audit_record = AuditRecord(
            user_id=user_id,
            query_text=user_query,
            agent_sequence=agent_sequence,
            final_decision=final_decision,
            human_approved=False
        )
        log_id = self.audit_repo.log_transaction(audit_record)

        return {
            "session_id": session_id,
            "audit_log_id": log_id,
            "parsed_intent": parsed,
            "recommendation": final_decision,
            "explanation": a4_res.data.get("explanation"),
            "citations": a3_res.data.get("citations", []),
            "digital_twin_feasibility": a2_res.data,
            "requires_human_approval": True,
            "status": "ready_for_operator_approval"
        }
