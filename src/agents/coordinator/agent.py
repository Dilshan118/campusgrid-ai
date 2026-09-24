"""
CampusGrid AI: Central Orchestrator & Multi-Agent Coordinator
Manages the deterministic 4-agent execution pipeline:
User Query -> NLP Parser (+ LLM router when unsure) -> Agent 1 (Forecast) -> Agent 2 (Simulation)
-> Agent 3 (RAG) -> Agent 4 (Solver & XAI) -> Audit Store -> Human Approval

Each intent runs only the agents it needs:
    policy_lookup       Agent 3
    telemetry_status    Agent 1
    what_if_simulation  Agent 1 -> Agent 2
    optimize_dispatch   Agent 1 -> Agent 2 -> Agent 3 -> Agent 4   (then waits for human approval)
    out_of_scope        no agents
"""

import uuid
from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.agents.coordinator.nlp_parser import (
    NLPQueryParser,
    ACTION_OPTIMIZE_DISPATCH,
    ACTION_WHAT_IF_SIMULATION,
    ACTION_POLICY_LOOKUP,
    ACTION_TELEMETRY_STATUS,
    ACTION_OUT_OF_SCOPE,
)
from src.agents.telemetry.agent import TelemetryForecastingAgent
from src.agents.digital_twin.agent import DigitalTwinAgent
from src.agents.policy_rag.agent import PolicyRAGAgent
from src.agents.dispatch_explanation.agent import DispatchExplanationAgent
from src.domain.interfaces.repositories import AuditLogRepository
from src.domain.entities.audit import (
    AuditRecord,
    RECORD_DISPATCH_RECOMMENDATION,
    RECORD_POLICY_LOOKUP,
    RECORD_WHAT_IF_SIMULATION,
    RECORD_FORECAST_REVIEW,
    RECORD_OUT_OF_SCOPE,
    APPROVAL_PENDING,
    APPROVAL_NOT_REQUIRED,
)
from src.domain.exceptions.base import DomainException
from src.shared.constants import COMFORT_TEMP_MIN_C, COMFORT_TEMP_MAX_C
from src.shared.datetime_utils import build_tou_tariff_profile

OUT_OF_SCOPE_MESSAGE = (
    "CampusGrid AI can help with day-ahead energy forecasts, what-if comfort simulations, "
    "tariff and regulation lookups, and battery / HVAC dispatch plans. This request is outside "
    "that scope, so no agents were run."
)


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
        nlp_parser: Optional[NLPQueryParser] = None,
        intent_router: Optional[Any] = None,
        llm_routing_threshold: float = 0.6,
        comfort_min_c: float = COMFORT_TEMP_MIN_C,
        comfort_max_c: float = COMFORT_TEMP_MAX_C,
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
        self.intent_router = intent_router
        self.llm_routing_threshold = llm_routing_threshold
        self.comfort_min_c = comfort_min_c
        self.comfort_max_c = comfort_max_c

    # ------------------------------------------------------------------

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_query = input_data.get("query", "Optimize 24h battery schedule to minimize peak demand charge.")
        user_id = input_data.get("user_id", "operator_facility_manager")
        session_id = input_data.get("session_id") or str(uuid.uuid4())

        parsed = self._understand(user_query)
        if input_data.get("force_full_pipeline"):
            parsed["action"] = ACTION_OPTIMIZE_DISPATCH
        self._apply_structured_overrides(parsed, input_data)

        context = {
            "query": user_query,
            "user_id": user_id,
            "session_id": session_id,
            "parsed": parsed,
            "battery_parameters": input_data.get("battery_parameters") or {},
        }
        action = parsed["action"]

        if action == ACTION_OUT_OF_SCOPE:
            return self._handle_out_of_scope(context)
        if action == ACTION_POLICY_LOOKUP:
            return self._handle_policy_lookup(context)

        a1_res = self.agent1.execute({
            "date": parsed["date"],
            "room": parsed["room"],
            "building": parsed["building"]
        })
        if not a1_res.success:
            raise AgentPipelineError("Agent 1 (Telemetry & Forecasting)", a1_res.error)

        if action == ACTION_TELEMETRY_STATUS:
            return self._handle_forecast_only(context, a1_res)

        a2_res = self.agent2.execute({
            "initial_temp_c": parsed.get("target_temp_c", 24.0),
            "target_setpoint_c": parsed.get("target_temp_c", 24.0),
            "ambient_temperatures_c": a1_res.data.get("ambient_temperatures_c", []),
            "occupancy_counts": a1_res.data.get("occupancy_counts", []),
            # Explicit dashboard slider values win; otherwise use what the query text asked for.
            "perturb_temp_delta_c": self._override(input_data, parsed, "perturb_temp_delta_c", 0.0),
            "perturb_occ_multiplier": self._override(input_data, parsed, "perturb_occ_multiplier", 1.0),
            "comfort_min_c": self.comfort_min_c,
            "comfort_max_c": self.comfort_max_c,
        })
        if not a2_res.success:
            raise AgentPipelineError("Agent 2 (Digital Twin Simulation)", a2_res.error)

        if action == ACTION_WHAT_IF_SIMULATION:
            return self._handle_simulation(context, a1_res, a2_res)

        return self._handle_dispatch(context, a1_res, a2_res)

    # ------------------------------------------------------------------
    # Intent understanding
    # ------------------------------------------------------------------

    def _understand(self, query: str) -> Dict[str, Any]:
        parsed = self.nlp_parser.parse(query)
        if self.intent_router is not None and parsed["confidence"] < self.llm_routing_threshold:
            routed = self.intent_router.route(query)
            if routed is not None:
                parsed["rule_action"] = parsed["action"]
                parsed["action"], parsed["confidence"] = routed
                parsed["intent_source"] = "llm_router"
        return parsed

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------

    def _handle_out_of_scope(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        log_id = self._audit(ctx, RECORD_OUT_OF_SCOPE, {}, {"summary": "No agents run: request outside system scope."})
        return self._response(ctx, log_id, status="out_of_scope", recommendation={}, explanation=OUT_OF_SCOPE_MESSAGE)

    def _handle_policy_lookup(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        a3_res = self.agent3.execute({"query": ctx["query"], "top_k": 3})
        if not a3_res.success:
            raise AgentPipelineError("Agent 3 (Policy & Information Retrieval)", a3_res.error)

        citations = a3_res.data.get("citations", [])
        decision = {
            "summary": f"Retrieved {len(citations)} verified regulatory clauses.",
            "extracted_rules": a3_res.data.get("extracted_rules", {})
        }
        log_id = self._audit(ctx, RECORD_POLICY_LOOKUP, {"agent3_policy_rag": a3_res.model_dump()}, decision)
        return self._response(
            ctx, log_id,
            status="policy_info_retrieved",
            recommendation=decision,
            explanation=f"Regulatory lookup completed. Retrieved {len(citations)} legal clauses.",
            citations=citations,
            extracted_rules=a3_res.data.get("extracted_rules", {}),
        )

    def _handle_forecast_only(self, ctx: Dict[str, Any], a1_res) -> Dict[str, Any]:
        data = a1_res.data
        demand = data.get("forecast_demand_kw", [])
        slots = data.get("time_slots", [])
        peak_idx = demand.index(max(demand)) if demand else None
        decision = {
            "summary": "Day-ahead demand and solar forecast.",
            "target_date": data.get("target_date"),
            "peak_demand_kw": max(demand) if demand else None,
            "peak_time_slot": slots[peak_idx] if peak_idx is not None and peak_idx < len(slots) else None,
            "anomaly_count": data.get("anomaly_count", 0),
            "forecast_summary": data.get("forecast_summary"),
        }
        log_id = self._audit(ctx, RECORD_FORECAST_REVIEW, {"agent1_telemetry": a1_res.model_dump()}, decision)
        return self._response(
            ctx, log_id,
            status="forecast_ready",
            recommendation=decision,
            explanation=data.get("forecast_summary") or (
                f"Forecast peak of {decision['peak_demand_kw']} kW at {decision['peak_time_slot']}."
                if demand else "Forecast produced no intervals."
            ),
            forecast=data,
        )

    def _handle_simulation(self, ctx: Dict[str, Any], a1_res, a2_res) -> Dict[str, Any]:
        feasible, violations = self._thermal_verdict(a2_res.data)
        decision = {"summary": "Completed cyber-physical what-if simulation", "feasibility": a2_res.data}
        log_id = self._audit(
            ctx, RECORD_WHAT_IF_SIMULATION,
            {"agent1_telemetry": a1_res.model_dump(), "agent2_digital_twin": a2_res.model_dump()},
            decision,
        )
        verdict = "comfort maintained" if feasible else f"{violations} interval(s) outside the comfort band"
        return self._response(
            ctx, log_id,
            status="simulation_completed",
            recommendation=decision,
            explanation=f"Simulation finished: {verdict}.",
            digital_twin_feasibility=a2_res.data,
        )

    def _handle_dispatch(self, ctx: Dict[str, Any], a1_res, a2_res) -> Dict[str, Any]:
        parsed = ctx["parsed"]
        a3_res = self.agent3.execute({"query": ctx["query"], "top_k": 2, "include_tariff_constraints": True})
        if not a3_res.success:
            raise AgentPipelineError("Agent 3 (Policy & Information Retrieval)", a3_res.error)

        # Tariff profile built from the rates and windows Agent 3 retrieved — not from meter history.
        rules = a3_res.data.get("extracted_rules", {})
        rates = rules.get("rates_lkr_kwh", {})
        time_slots = a1_res.data.get("time_slots", [])
        tariffs_from_rag = build_tou_tariff_profile(
            time_slots,
            rates.get("peak", a3_res.data.get("peak_tariff_lkr", 58.0)),
            rates.get("day", a3_res.data.get("day_tariff_lkr", 30.0)),
            rates.get("off_peak", a3_res.data.get("off_peak_tariff_lkr", 15.0)),
            windows=rules.get("windows"),
        )
        citations = a3_res.data.get("all_citations", a3_res.data.get("citations", []))
        thermal_feasible, comfort_violations = self._thermal_verdict(a2_res.data)

        a4_res = self.agent4.execute({
            "time_slots": time_slots,
            "forecast_demand_kw": a1_res.data.get("forecast_demand_kw", []),
            "forecast_solar_kw": a1_res.data.get("forecast_solar_kw", []),
            "tariffs_lkr_kwh": tariffs_from_rag,
            "citations": citations,
            "user_query": ctx["query"],
            "feasibility_verdict": thermal_feasible,
            "max_demand_penalty_lkr_kva": rules.get("max_demand_penalty_lkr_kva", 1100.0),
            **ctx["battery_parameters"],
        })
        if not a4_res.success:
            raise AgentPipelineError("Agent 4 (Dispatch & Explanation)", a4_res.error)

        tariff_inputs = {
            "rates_lkr_kwh": rates,
            "windows": rules.get("windows"),
            "max_demand_penalty_lkr_kva": rules.get("max_demand_penalty_lkr_kva"),
            "provenance": rules.get("provenance", {}),
            "source_clauses": rules.get("source_clauses", {}),
        }
        warnings = self._dispatch_warnings(parsed, rules, thermal_feasible, comfort_violations, a4_res.data)

        final_decision = {
            "solver_summary": a4_res.data.get("solver_output", {}),
            "net_savings_lkr": a4_res.data.get("net_savings_lkr"),
            "savings_percentage": a4_res.data.get("savings_percentage"),
            "peak_shaved_kw": a4_res.data.get("peak_shaved_kw"),
            "explanation": a4_res.data.get("explanation"),
            "faithfulness_audit": a4_res.data.get("faithfulness_audit"),
            "tariff_inputs": tariff_inputs,
            "thermal_feasibility": {
                "is_feasible": thermal_feasible,
                "comfort_violations_count": comfort_violations,
                "comfort_band_c": [self.comfort_min_c, self.comfort_max_c],
            },
            "target": {
                "room": parsed["room"],
                "building": parsed["building"],
                "date": parsed["date"],
                "target_temp_c": parsed["target_temp_c"],
            },
            "forecast_summary": a1_res.data.get("forecast_summary"),
            "warnings": warnings,
        }

        agent_sequence = {
            "agent1_telemetry": a1_res.model_dump(),
            "agent2_digital_twin": a2_res.model_dump(),
            "agent3_policy_rag": a3_res.model_dump(),
            "agent4_dispatch": a4_res.model_dump()
        }
        log_id = self._audit(ctx, RECORD_DISPATCH_RECOMMENDATION, agent_sequence, final_decision, APPROVAL_PENDING)

        return self._response(
            ctx, log_id,
            status="ready_for_operator_approval",
            recommendation=final_decision,
            explanation=a4_res.data.get("explanation"),
            explanation_concise=self._concise_explanation(final_decision["solver_summary"]),
            citations=citations,
            requires_human_approval=True,
            digital_twin_feasibility=a2_res.data,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_structured_overrides(self, parsed: Dict[str, Any], input_data: Dict[str, Any]) -> None:
        """Room / date chosen in a form (not typed in the query) replace the parsed values."""
        room = str(input_data.get("room") or "").upper()
        if room:
            if room in self.nlp_parser.rooms:
                parsed["room"], parsed["room_explicit"] = room, True
                parsed["building"] = self.nlp_parser.rooms[room].get("building_name", parsed["building"])
            else:
                parsed.setdefault("notes", []).append(f"Room '{room}' is not in the campus inventory; using {parsed['room']}.")
        if input_data.get("date"):
            parsed["date"], parsed["date_explicit"] = input_data["date"], True

    @staticmethod
    def _concise_explanation(solver: Dict[str, Any]) -> Optional[str]:
        """One-line summary built only from solver numbers (variant A of the XAI A/B test)."""
        try:
            return (
                f"Plan saves LKR {float(solver['net_savings_lkr']):,.0f} "
                f"({float(solver['savings_percentage']):.1f}%) and lowers the peak from "
                f"{float(solver['peak_demand_baseline_kw']):.0f} kW to {float(solver['peak_demand_optimized_kw']):.0f} kW."
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _override(input_data: Dict[str, Any], parsed: Dict[str, Any], key: str, default: float) -> float:
        value = input_data.get(key)
        return float(value) if value is not None else float(parsed.get(key, default))

    @staticmethod
    def _thermal_verdict(twin_data: Dict[str, Any]):
        # Agent 2 reports "is_thermal_feasible"; "is_feasible" is the simulation tool's key.
        feasible = twin_data.get("is_thermal_feasible", twin_data.get("is_feasible", True))
        return bool(feasible), int(twin_data.get("comfort_violations_count", twin_data.get("comfort_violation_count", 0)) or 0)

    @staticmethod
    def _dispatch_warnings(parsed, rules, thermal_feasible, comfort_violations, a4_data) -> List[str]:
        warnings: List[str] = []
        if not thermal_feasible:
            warnings.append(
                f"Digital twin predicts {comfort_violations} interval(s) outside the ASHRAE-55 comfort band."
            )
        audit = a4_data.get("faithfulness_audit") or {}
        if audit.get("is_faithful") is False:
            claims = audit.get("hallucinated_claims") or []
            warnings.append(f"Explanation failed the faithfulness check ({len(claims)} unsupported claim(s)).")
        for field, source in (rules.get("provenance") or {}).items():
            if field in ("peak", "day", "off_peak", "max_demand_penalty_lkr_kva") and source != "retrieved":
                warnings.append(f"Tariff figure '{field}' was not found in the retrieved documents ({source}); reference value used.")
        warnings.extend(rules.get("validation_warnings") or [])
        if parsed.get("security_flags"):
            warnings.append(
                "The request contained instruction-like text (" + ", ".join(parsed["security_flags"]) +
                "); it was treated as plain text and did not change any limit."
            )
        return warnings

    def _audit(
        self,
        ctx: Dict[str, Any],
        record_type: str,
        agent_sequence: Dict[str, Any],
        decision: Dict[str, Any],
        approval_status: str = APPROVAL_NOT_REQUIRED,
    ) -> int:
        parsed = ctx["parsed"]
        decision = {
            **decision,
            "intent": {k: parsed.get(k) for k in ("action", "confidence", "intent_source", "room", "date")},
            "security_flags": parsed.get("security_flags", []),
            "session_id": ctx["session_id"],
        }
        return self.audit_repo.log_transaction(AuditRecord(
            user_id=ctx["user_id"],
            query_text=ctx["query"],
            agent_sequence=agent_sequence,
            final_decision=decision,
            human_approved=False,
            record_type=record_type,
            approval_status=approval_status,
        ))

    @staticmethod
    def _response(
        ctx: Dict[str, Any],
        log_id: int,
        status: str,
        recommendation: Dict[str, Any],
        explanation: Optional[str],
        citations: Optional[List[Dict[str, Any]]] = None,
        requires_human_approval: bool = False,
        **extra: Any,
    ) -> Dict[str, Any]:
        parsed = ctx["parsed"]
        return {
            "session_id": ctx["session_id"],
            "audit_log_id": log_id,
            "parsed_intent": parsed,
            "status": status,
            "recommendation": recommendation,
            "explanation": explanation,
            "citations": citations or [],
            "requires_human_approval": requires_human_approval,
            "approval_status": APPROVAL_PENDING if requires_human_approval else APPROVAL_NOT_REQUIRED,
            "assumptions": parsed.get("notes", []),
            "security_flags": parsed.get("security_flags", []),
            **extra,
        }
