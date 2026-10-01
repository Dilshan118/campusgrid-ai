"""
CampusGrid AI: Agent 4 — Dispatch and Explanation (LLM · Optimization)
Formulates 48-period MILP cost minimization, eliminates peak demand spikes,
and synthesizes plain-English XAI justifications from solver logs and source-labeled tariff references.

Fairness tiers are opt-in per request (`tier_loads_kw`, or `enable_tiers` for the documented
synthetic split) or for every request (the `tier_shares` constructor argument, decision D-1).
They stay off by default because the synthetic split, not measured data, would then drive
every plan's savings figure; when on, the plan reports how much of the saving came from moving
load rather than from the battery, and says whether the split is synthetic.
"""

import logging
from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.domain.entities.optimization import OptimizationInput
from src.domain.exceptions.base import DomainException
from src.domain.interfaces.llm import LLMProvider
from src.domain.interfaces.optimizer import (
    MicrogridOptimizerInterface,
    XAIExplainerInterface,
    FaithfulnessVerifierInterface,
)
from src.agents.dispatch_explanation.milp_solver import CampusMicrogridOptimizer
from src.agents.dispatch_explanation.xai_explainer import (
    XAIExplainer,
    solver_only_explanation,
    tariff_text,
    comfort_verdict_text,
)
from src.agents.dispatch_explanation.faithfulness import FaithfulnessVerifier
from src.agents.dispatch_explanation.tier_category_mapping import TIER_1, TIER_2
from src.agents.dispatch_explanation.tier_guardrails import (
    TierLoads,
    TierPolicy,
    allocate_to_zones,
    classify_room_type,
    synthetic_tier_loads,
)
from src.shared.constants import (
    BATTERY_CAPACITY_DEFAULT_KWH,
    BATTERY_MAX_POWER_DEFAULT_KW,
    BATTERY_SOC_MIN_RATIO,
    BATTERY_SOC_MAX_RATIO,
    MAX_DEMAND_SURCHARGE_LKR_KVA,
    TARIFF_DAY_LKR,
)

logger = logging.getLogger("campusgrid.agents.dispatch")

# The site battery, overridden by the container from settings and per request by the dispatch form.
DEFAULT_BATTERY = {
    "battery_capacity_kwh": BATTERY_CAPACITY_DEFAULT_KWH,
    "max_charge_rate_kw": BATTERY_MAX_POWER_DEFAULT_KW,
    "max_discharge_rate_kw": BATTERY_MAX_POWER_DEFAULT_KW,
    "initial_soc_ratio": 0.50,
    "min_soc_ratio": BATTERY_SOC_MIN_RATIO,
    "max_soc_ratio": BATTERY_SOC_MAX_RATIO,
}
# Fields a caller (the dispatch form) may override per request.
_REQUEST_BATTERY_FIELDS = ("battery_capacity_kwh", "max_charge_rate_kw", "max_discharge_rate_kw", "initial_soc_ratio")
_DT_HOURS = 0.5


class DispatchExplanationAgent(BaseAgent):
    """Agent 4: Solves microgrid dispatch and explains actions to operators."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        optimizer: Optional[MicrogridOptimizerInterface] = None,
        explainer: Optional[XAIExplainerInterface] = None,
        verifier: Optional[FaithfulnessVerifierInterface] = None,
        battery_defaults: Optional[Dict[str, float]] = None,
        tier_shares: Optional[Dict[str, float]] = None,
        tier_policy: Optional[TierPolicy] = None,
    ):
        super().__init__(
            name="Agent 4: Dispatch & Explanation",
            description="Solves 48-period MILP dispatch and generates plain-English XAI justifications."
        )
        self.optimizer = optimizer or CampusMicrogridOptimizer()
        self.explainer = explainer or XAIExplainer(llm_provider=llm_provider)
        self.verifier = verifier or FaithfulnessVerifier(llm_provider=llm_provider)
        self.battery_defaults = {**DEFAULT_BATTERY, **(battery_defaults or {})}
        # D-1 synthetic split applied to every request when set; None keeps tiers opt-in per request.
        self.tier_shares = tier_shares
        self.tier_policy = tier_policy or TierPolicy()

    def _battery_parameters(self, input_data: Dict[str, Any]) -> Dict[str, float]:
        params = dict(self.battery_defaults)
        for key in _REQUEST_BATTERY_FIELDS:
            if input_data.get(key) is not None:
                params[key] = float(input_data[key])
        return params

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        time_slots = input_data.get("time_slots", [])
        base_load = input_data.get("forecast_demand_kw", [])
        solar_gen = input_data.get("forecast_solar_kw", [])
        tariffs = input_data.get("tariffs_lkr_kwh", [])
        citations = input_data.get("citations", [])
        user_query = input_data.get("user_query", "Optimize 24h battery schedule to minimize peak demand charge.")
        comfort_feasible = input_data.get("feasibility_verdict")
        tariff_summary = input_data.get("tariff_summary")
        demand_charge = input_data.get("max_demand_penalty_lkr_kva")
        grid_limit = input_data.get("max_grid_import_kw")
        battery = self._battery_parameters(input_data)

        # Default tariffs if missing
        if not tariffs:
            tariffs = [TARIFF_DAY_LKR] * len(time_slots)

        opt_input = OptimizationInput(
            time_slots=time_slots,
            base_load_kw=base_load,
            solar_gen_kw=solar_gen,
            grid_tariff_lkr_kwh=tariffs,
            peak_demand_penalty_lkr_kva=float(demand_charge) if demand_charge is not None else MAX_DEMAND_SURCHARGE_LKR_KVA,
            max_grid_import_kw=float(grid_limit) if grid_limit is not None else None,
            **battery,
        )

        # 1. Solve MILP Optimization (with fairness tiers when requested and supported)
        solver_output, tier_dispatch = self._solve(opt_input, input_data)

        # 2. Synthesize Grounded XAI Justification. A language-model outage must not discard a
        #    solved plan: fall back to a deterministic explanation built from the solver numbers.
        try:
            explanation = self.explainer.generate_explanation(
                solver_output=solver_output,
                citations=citations,
                user_query=user_query,
                tariff_summary=tariff_summary,
                comfort_feasible=comfort_feasible,
            )
            explanation_source = "llm"
        except Exception as exc:
            logger.warning("Explanation model unavailable (%s); using the solver-only explanation.", type(exc).__name__)
            explanation = solver_only_explanation(solver_output, comfort_feasible)
            explanation_source = "solver_template"
        fairness_note = self._fairness_note(tier_dispatch)
        if fairness_note:
            explanation = f"{explanation}\n\n{fairness_note}"

        # 3. Verify Faithfulness against the solver, the citations and every other verified input.
        #    The raw operator query is NOT verified input: only the deterministically parsed
        #    request parameters may ground a figure (SEC-01).
        audit_res = self.verifier.verify(
            explanation_text=explanation,
            solver_output=solver_output,
            citations=citations,
            grounding_text=self._grounding_text(
                input_data.get("request_parameters"), tariff_summary, comfort_feasible, battery, tier_dispatch,
            ),
        )

        return {
            "solver_output": solver_output.model_dump(),
            "explanation": explanation,
            "explanation_source": explanation_source,
            "faithfulness_audit": audit_res,
            "baseline_cost_lkr": solver_output.baseline_cost_lkr,
            "optimized_cost_lkr": solver_output.optimized_cost_lkr,
            "net_savings_lkr": solver_output.net_savings_lkr,
            "savings_percentage": solver_output.savings_percentage,
            "peak_shaved_kw": round(solver_output.peak_demand_baseline_kw - solver_output.peak_demand_optimized_kw, 1),
            "battery_parameters": {**battery, "peak_demand_penalty_lkr_kva": opt_input.peak_demand_penalty_lkr_kva},
            "tier_dispatch": tier_dispatch,
            "requires_human_approval": True,
            "citations": citations
        }

    @staticmethod
    def _grounding_text(
        request_parameters: Optional[Dict[str, Any]],
        tariff_summary: Optional[Dict[str, Any]],
        comfort_feasible: Optional[bool],
        battery: Dict[str, float],
        tier_dispatch: Optional[Dict[str, Any]] = None,
    ) -> str:
        """System-provided context an explanation may quote, besides solver output and citations.

        The operator's free text is deliberately absent: a number typed into the query (or an
        instruction to state one) must never count as evidence for the explanation. Only the
        parser values and configured default rates are context, not proof that a tariff source is official.
        """
        lines = []
        params = {k: v for k, v in (request_parameters or {}).items() if v is not None}
        if params:
            lines.append("Parsed operator request: " + ", ".join(f"{k} {v}" for k, v in sorted(params.items())))
        lines += [
            f"Retrieved tariff:\n{tariff_text(tariff_summary)}",
            f"Comfort verdict: {comfort_verdict_text(comfort_feasible)}",
            (
                f"Battery: capacity {battery['battery_capacity_kwh']:g} kWh, charge limit {battery['max_charge_rate_kw']:g} kW, "
                f"discharge limit {battery['max_discharge_rate_kw']:g} kW, state-of-charge band "
                f"{battery['min_soc_ratio'] * 100:g}% to {battery['max_soc_ratio'] * 100:g}%, "
                f"starting at {battery['initial_soc_ratio'] * 100:g}%."
            ),
        ]
        note = DispatchExplanationAgent._fairness_note(tier_dispatch)
        if note:
            lines.append(f"Fairness tiers: {note}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Fairness tiers
    # ------------------------------------------------------------------

    def _tier_loads(self, input_data: Dict[str, Any], base_load: List[float]) -> Optional[TierLoads]:
        supplied = input_data.get("tier_loads_kw")
        if supplied:
            loads = TierLoads(
                tier0_kw=[float(v) for v in supplied["tier0"]],
                tier1_kw=[float(v) for v in supplied["tier1"]],
                tier2_kw=[float(v) for v in supplied["tier2"]],
                source=str(input_data.get("tier_load_source") or "provided"),
            )
            loads.validate_against(base_load)
            return loads
        if input_data.get("enable_tiers") or self.tier_shares:
            return synthetic_tier_loads(base_load, input_data.get("tier_shares") or self.tier_shares)
        return None

    def _solve(self, opt_input: OptimizationInput, input_data: Dict[str, Any]):
        """Returns (OptimizationResult, tier_dispatch report)."""
        loads = self._tier_loads(input_data, opt_input.base_load_kw)
        if loads is None:
            return self.optimizer.solve(opt_input), {
                "enabled": False,
                "reason": "No per-tier load was supplied and the synthetic tier split is not enabled.",
            }
        if not hasattr(self.optimizer, "solve_detailed"):
            return self.optimizer.solve(opt_input), {
                "enabled": False,
                "reason": "The active optimizer does not support fairness tiers.",
            }

        policy = self.tier_policy
        if input_data.get("tier1_kw_per_degree_c") is not None:  # WIRE-3: Agent 2's sensitivity
            policy = TierPolicy(**{**policy.__dict__, "tier1_kw_per_degree_c": float(input_data["tier1_kw_per_degree_c"])})
        tiered = opt_input.model_copy(update={
            "tier0_load_kw": loads.tier0_kw, "tier1_load_kw": loads.tier1_kw, "tier2_load_kw": loads.tier2_kw,
        })
        solution = self.optimizer.solve_detailed(tiered, tier_policy=policy, tier_source=loads.source)
        report = dict(solution.tier_report)

        # Transparency: how much of the saving comes from moving load rather than from the battery.
        try:
            battery_only = self.optimizer.solve(opt_input).net_savings_lkr
            report["battery_only_net_savings_lkr"] = battery_only
            report["savings_from_load_flexibility_lkr"] = round(solution.result.net_savings_lkr - battery_only, 2)
        except DomainException:  # e.g. the grid limit makes the plan infeasible without load flexibility
            report["battery_only_net_savings_lkr"] = None
            report["savings_from_load_flexibility_lkr"] = None

        zones = input_data.get("zones")
        if zones:
            report["zone_allocation"] = self._zone_allocation(zones, loads, report)
        return solution.result, report

    @staticmethod
    def _zone_allocation(zones: List[Dict[str, Any]], loads: TierLoads, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Splits each tier's reduction across its zones in proportion to their share of the tier's
        load. A zone's category is used only to look up its tier, so two zones with the same tier
        and share are always asked for the same reduction, whatever they are called.
        """
        tier_of = {z["zone_id"]: classify_room_type(z["room_type"]) for z in zones}
        per_tier = {
            TIER_1: (loads.tier1_kw, [max(0.0, -v) for v in report["tier1"]["schedule_kw"]]),
            TIER_2: (loads.tier2_kw, [max(0.0, -v) for v in report["tier2"]["schedule_kw"]]),
        }
        shares: Dict[str, Dict[str, float]] = {}
        for z in zones:
            shares.setdefault(tier_of[z["zone_id"]], {})[z["zone_id"]] = float(z["load_share"])
        for tier, zone_shares in shares.items():
            total = sum(zone_shares.values())
            if total <= 0 or total > 1.0 + 1e-6:
                raise DomainException(f"Zone load shares in {tier} must add up to more than 0 and at most 1.",
                                      error_code="TIER_LOAD_INVALID")

        rows = []
        for z in zones:
            zone_id, tier = z["zone_id"], tier_of[z["zone_id"]]
            row = {"zone_id": zone_id, "room_type": z["room_type"], "tier": tier,
                   "reduced_kwh": 0.0, "max_reduction_kw": 0.0, "reduction_pct_of_zone_energy": 0.0}
            if tier in per_tier:  # Tier 0 zones are never reduced
                tier_load, tier_cut = per_tier[tier]
                zone_shares = shares[tier]
                zone_energy = reduced = peak_cut = 0.0
                for t in range(len(tier_load)):
                    zone_loads = {zid: tier_load[t] * share for zid, share in zone_shares.items()}
                    # Zones not listed carry the rest of the tier's load, and their share of the cut.
                    listed_cut = tier_cut[t] * sum(zone_shares.values())
                    cut = allocate_to_zones(min(listed_cut, sum(zone_loads.values())), zone_loads)[zone_id]
                    zone_energy += zone_loads[zone_id] * _DT_HOURS
                    reduced += cut * _DT_HOURS
                    peak_cut = max(peak_cut, cut)
                row.update({
                    "reduced_kwh": round(reduced, 2),
                    "max_reduction_kw": round(peak_cut, 2),
                    "reduction_pct_of_zone_energy": round(100.0 * reduced / zone_energy, 2) if zone_energy > 0 else 0.0,
                })
            rows.append(row)
        return rows

    @staticmethod
    def _fairness_note(tier_dispatch: Optional[Dict[str, Any]]) -> Optional[str]:
        """Plain-text fairness summary built only from the solver's tier report."""
        if not tier_dispatch or not tier_dispatch.get("enabled"):
            return None
        t1, t2 = tier_dispatch["tier1"], tier_dispatch["tier2"]
        synthetic = tier_dispatch.get("load_split_source") == "synthetic"
        parts = [
            "Fairness tiers" + (" (estimated from a synthetic load split, not metered data)" if synthetic else "") + ":",
            "critical Tier 0 load (research labs, medical rooms, server rooms) was served in full in every interval.",
        ]
        if t1["reduced_kwh"] > 0:
            parts.append(
                f"Tier 1 cooling was reduced by {t1['reduced_kwh']:.1f} kWh during peak hours, by at most "
                f"{t1['max_flex_c']:g} C, and the same energy was used to re-cool the rooms later the same day."
            )
        else:
            parts.append("Tier 1 rooms (teaching, study, office and residential spaces) were not asked to flex.")
        if t2["shifted_kwh"] > 0:
            parts.append(f"{t2['shifted_kwh']:.1f} kWh of Tier 2 load (EV chargers, pumps, ornamental lighting) "
                         "was moved to cheaper hours and fully recovered the same day.")
        flex = tier_dispatch.get("savings_from_load_flexibility_lkr")
        if flex is not None and flex > 0:
            parts.append(f"LKR {flex:,.2f} of the saving comes from moving load rather than from the battery.")
        return " ".join(parts)
