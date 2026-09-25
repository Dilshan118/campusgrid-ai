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

import contextvars
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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

# Shared by every orchestrator instance: Agent 3 runs here while Agents 1 and 2 run on the request thread.
_PARALLEL_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cg-agent")

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
        battery_limits: Optional[Dict[str, float]] = None,
        parallel_agents: bool = True,
        agent3_timeout_seconds: float = 60.0,
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
        self.battery_limits = battery_limits or {}
        self.parallel_agents = parallel_agents
        self.agent3_timeout_seconds = agent3_timeout_seconds

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

        # Agent 3 depends only on the question, not on the forecast or the comfort check, so for a
        # dispatch plan it runs concurrently with Agents 1 -> 2. Agent 4 waits for all three.
        a3_future: Optional[Future] = None
        if action == ACTION_OPTIMIZE_DISPATCH:
            a3_future = self._start_agent3(user_query)

        a1_res = self.agent1.execute({
            "date": parsed["date"],
            "room": parsed["room"],
            "building": parsed["building"]
        })
        if not a1_res.success:
            raise AgentPipelineError("Agent 1 (Telemetry & Forecasting)", a1_res.error)

        if action == ACTION_TELEMETRY_STATUS:
            return self._handle_forecast_only(context, a1_res)

        occupancy, capped, capacity = self.room_level_occupancy(parsed["room"], a1_res.data.get("occupancy_counts", []))
        if capped:
            parsed.setdefault("notes", []).append(
                f"Occupancy was capped at {parsed['room']}'s capacity ({capacity}) for {capped} half-hours; "
                "the forecast's headcounts are campus-wide."
            )
        a2_res = self.agent2.execute({
            "initial_temp_c": parsed.get("target_temp_c", 24.0),
            "target_setpoint_c": parsed.get("target_temp_c", 24.0),
            "ambient_temperatures_c": a1_res.data.get("ambient_temperatures_c", []),
            "occupancy_counts": occupancy,
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

        return self._handle_dispatch(context, a1_res, a2_res, a3_future)

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
        verdict = "comfort maintained" if feasible else self._comfort_problem(violations)
        return self._response(
            ctx, log_id,
            status="simulation_completed",
            recommendation=decision,
            explanation=f"Simulation finished: {verdict}.",
            digital_twin_feasibility=a2_res.data,
        )

    def _start_agent3(self, query: str) -> Optional[Future]:
        if not self.parallel_agents:
            return None
        run_in_context = contextvars.copy_context().run  # keeps the request ID in Agent 3's trace logs
        return _PARALLEL_POOL.submit(run_in_context, self.agent3.execute, self._agent3_dispatch_input(query))

    @staticmethod
    def _agent3_dispatch_input(query: str) -> Dict[str, Any]:
        return {"query": query, "top_k": 2, "include_tariff_constraints": True}

    def _handle_dispatch(self, ctx: Dict[str, Any], a1_res, a2_res, a3_future: Optional[Future] = None) -> Dict[str, Any]:
        parsed = ctx["parsed"]
        if a3_future is not None:
            try:
                a3_res = a3_future.result(timeout=self.agent3_timeout_seconds)
            except FutureTimeoutError:
                # The worker thread cannot be cancelled; it finishes in the background and is discarded.
                raise AgentPipelineError(
                    "Agent 3 (Policy & Information Retrieval)",
                    f"no answer within {self.agent3_timeout_seconds:g} seconds",
                )
        else:
            a3_res = self.agent3.execute(self._agent3_dispatch_input(ctx["query"]))
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
        tariff_summary = {
            "rates_lkr_kwh": {
                "peak": rates.get("peak", a3_res.data.get("peak_tariff_lkr", 58.0)),
                "day": rates.get("day", a3_res.data.get("day_tariff_lkr", 30.0)),
                "off_peak": rates.get("off_peak", a3_res.data.get("off_peak_tariff_lkr", 15.0)),
            },
            "windows": rules.get("windows"),
            "max_demand_penalty_lkr_kva": rules.get("max_demand_penalty_lkr_kva", 1100.0),
        }

        a4_res = self.agent4.execute({
            "time_slots": time_slots,
            "forecast_demand_kw": a1_res.data.get("forecast_demand_kw", []),
            "forecast_solar_kw": a1_res.data.get("forecast_solar_kw", []),
            "tariffs_lkr_kwh": tariffs_from_rag,
            "citations": citations,
            "user_query": ctx["query"],
            "feasibility_verdict": thermal_feasible,
            "max_demand_penalty_lkr_kva": rules.get("max_demand_penalty_lkr_kva", 1100.0),
            "tariff_summary": tariff_summary,
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
            "explanation_source": a4_res.data.get("explanation_source"),
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
        # Stored with the plan so a reviewer can render it from the audit record alone.
        final_decision["explanation_concise"] = self._concise_explanation(final_decision["solver_summary"])
        final_decision["citations"] = citations
        final_decision["battery_limits"] = self._battery_limits_used(a4_res.data.get("battery_parameters"))
        final_decision["assumptions"] = list(parsed.get("notes", []))
        demand = a1_res.data.get("forecast_demand_kw", [])
        solar = a1_res.data.get("forecast_solar_kw", [])
        final_decision["baseline_grid_kw"] = [
            round(max(0.0, d - (solar[i] if i < len(solar) else 0.0)), 1) for i, d in enumerate(demand)
        ]

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
            explanation_concise=final_decision["explanation_concise"],
            citations=citations,
            requires_human_approval=True,
            digital_twin_feasibility=a2_res.data,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def room_level_occupancy(self, room_id: str, counts: List[int]):
        """Hand-off check between Agent 1 and Agent 2: the digital twin simulates ONE room, but the
        forecast's headcounts can be campus-wide. Counts above the room's capacity are capped.
        Returns (counts, number_capped, capacity)."""
        capacity = (self.nlp_parser.rooms.get(str(room_id).upper()) or {}).get("max_capacity")
        if not capacity:
            return list(counts), 0, None
        capped = sum(1 for c in counts if c > capacity)
        return [min(int(c), int(capacity)) for c in counts], capped, capacity

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

    def _battery_limits_used(self, params: Optional[Dict[str, float]]) -> Dict[str, float]:
        """The battery limits the plan was actually solved with (settings, or the dispatch form's values)."""
        if not params:
            return self.battery_limits
        capacity = float(params["battery_capacity_kwh"])
        return {
            "capacity_kwh": capacity,
            "min_soc_kwh": round(capacity * float(params["min_soc_ratio"]), 2),
            "max_soc_kwh": round(capacity * float(params["max_soc_ratio"]), 2),
            "max_power_kw": max(float(params["max_charge_rate_kw"]), float(params["max_discharge_rate_kw"])),
            "max_charge_kw": float(params["max_charge_rate_kw"]),
            "max_discharge_kw": float(params["max_discharge_rate_kw"]),
        }

    @staticmethod
    def _concise_explanation(solver: Dict[str, Any]) -> Optional[str]:
        """One-line summary built only from solver numbers (variant A of the XAI A/B test)."""
        try:
            savings = float(solver["net_savings_lkr"])
            outcome = f"saves LKR {savings:,.0f}" if savings >= 0 else f"costs LKR {abs(savings):,.0f} more"
            return (
                f"Plan {outcome} "
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
        # A missing verdict fails closed: an unverified plan is never reported as comfortable.
        feasible = twin_data.get("is_thermal_feasible", twin_data.get("is_feasible"))
        return bool(feasible), int(twin_data.get("comfort_violations_count", twin_data.get("comfort_violation_count", 0)) or 0)

    @staticmethod
    def _comfort_problem(violations: int) -> str:
        if violations:
            return f"{violations} interval(s) outside the comfort band"
        return "the digital twin did not confirm the comfort band"

    @staticmethod
    def _dispatch_warnings(parsed, rules, thermal_feasible, comfort_violations, a4_data) -> List[str]:
        warnings: List[str] = []
        if not thermal_feasible and comfort_violations:
            warnings.append(
                f"Digital twin predicts {comfort_violations} interval(s) outside the ASHRAE-55 comfort band."
            )
        elif not thermal_feasible:
            warnings.append("The digital twin did not confirm the ASHRAE-55 comfort band; comfort is unverified.")
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
