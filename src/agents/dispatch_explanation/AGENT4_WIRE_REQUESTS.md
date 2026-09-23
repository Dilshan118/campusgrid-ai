# Agent 4 — Tier 0/1/2 Enforcement: WIRE Requests

**From:** Member 4 (Dev 3 — Optimization & Responsible AI), Agent 4: Dispatch & Explanation
**To:** Team Lead
**Branch:** `feature/agent4-dispatch-explanation`
**Status:** Proposal only — nothing below has been implemented or committed.

## Why this document exists

Agent 4 has completed room/category tier classification (`tier_category_mapping.py`,
`tier_guardrails.py` — committed in `1e458e7` and `8c4509b`). A follow-up architecture
analysis established that **real Tier 0/1/2 dispatch enforcement cannot be built yet**,
because the data and contracts it would need don't exist anywhere in the current
pipeline — not because of a gap in Agent 4's own code, but because the required inputs
were never produced upstream. Concretely:

- `OptimizationInput` only carries aggregate campus load (`base_load_kw[t]`); there is
  no per-room or per-tier breakdown anywhere in the telemetry pipeline.
- The MILP has no load-shedding/curtailment variable at all today — `grid_kw[t]` is
  unbounded above, so the solver can always import more grid power rather than ever
  being forced to reduce anyone's supply, Tier 0 included.
- Agent 2 simulates thermal behaviour as a forward process (setpoint/HVAC power →
  temperature) for a single zone; it does not produce the inverse relationship
  (allowed setback → power saved) that Tier 1's ±1.5°C policy would need.

This document requests four specific decisions/changes from the Lead before Agent 4
can implement genuine tier enforcement. Each is scoped to what actually requires Lead
sign-off under `TEAM_GUIDES/OWNERSHIP.md` — none of this can be resolved by Agent 4
alone without either guessing at another owner's data or touching files outside
`src/agents/dispatch_explanation/`.

---

## WIRE-1 — Tier-load carrier for Agent 4

**Current limitation**
`OptimizationInput` only contains aggregate campus load. There is no field on it, or
anywhere upstream, that expresses how much of that load belongs to Tier 0, Tier 1, or
Tier 2 facilities.

**Required change**
An additive tier-load representation carrying, for the 48 forecast intervals:
- `tier0_load_kw`
- `tier1_load_kw`
- `tier2_load_kw`

**Why Agent 4 cannot safely implement it alone**
`OptimizationInput` and `MicrogridOptimizerInterface` live in `src/domain/**`, which is
Lead-owned. Per OWNERSHIP.md, output/input shapes are contracts — changing them needs
Lead sign-off and a team-wide announcement, not a unilateral edit from one agent's
folder.

**Proposed contract**
A small sibling model (not a modification of `OptimizationInput` itself) carrying the
three lists above, each length 48, passed alongside `OptimizationInput` into `solve()`
as an optional parameter. This keeps the existing `OptimizationInput` shape, the
reference baseline, and all current tests untouched. **This is only a proposal and
requires Lead approval** — Agent 4 has not assumed this design is accepted.

**Owner**
Lead.

**Dependency / impact**
Blocks WIRE-3 and WIRE-4 from being useful in practice (a sensitivity or an import cap
has nothing to act on without a tier-load breakdown to constrain). Also blocks all of
"Agent 4 implementation after approval" below, items 2–5.

---

## WIRE-2 — Source of tier-load aggregation

**Current limitation**
No per-room or per-tier energy data exists anywhere in the current telemetry
pipeline. `RoomRepository` has room categories; `MeterHistoryRepository` has only a
single campus-wide load figure per interval. Nothing joins the two, and no per-room
metering data source is known to exist.

**Required change**
A decision on how tier loads in WIRE-1 will actually be obtained. Agent 4 is not
proposing to invent this data, and is presenting two directions rather than picking
one:

1. **Real per-room/sub-metered load source** — if such metering exists or can be
   added, tier loads are computed by aggregating real per-room readings through
   `RoomRepository`'s category field.
2. **Explicitly documented synthetic/static allocation for coursework**, if the team
   decides real sub-metering isn't achievable this term — e.g. a fixed percentage
   split of `base_load_kw` per tier, agreed and written down as an approximation.

If direction 2 is chosen, **the allocation must be clearly labeled as synthetic
everywhere it appears (code comments, reports, the viva) and must never be presented
as real telemetry evidence.** This matters directly for the Responsible AI report —
presenting an invented split as measured data would be the same "invented evidence"
problem already identified and fixed in the security-audit test file.

**Why Agent 4 cannot safely implement it alone**
This touches `RoomRepository` (Lead-owned) and/or the telemetry pipeline (Dev 1-owned),
and more importantly it's a scope/feasibility decision — whether real per-room metering
is achievable this term — that Agent 4 isn't positioned to make unilaterally.

**Proposed contract**
Deliberately left open pending the decision above. Specifying a shape here would mean
guessing at a data source that may not exist.

**Owner**
Lead + Dev 1 (joint decision).

**Dependency / impact**
Blocks WIRE-1 from being backed by anything real. Without this, WIRE-1's data would
either be empty or would have to fall back to a synthetic placeholder, which must be
labeled as such per above.

---

## WIRE-3 — Agent 2 thermal sensitivity

**Current limitation**
Agent 2 currently performs forward thermal simulation (setpoint/HVAC power in →
indoor temperature out) but does not provide the power-saving sensitivity needed to
represent Tier 1's ±1.5°C flexibility — i.e. it cannot currently answer "how much
less cooling power is needed if this zone is allowed to drift 1.5°C warmer."

**Required change**
A documented output from Agent 2 representing the relationship between allowed
temperature flexibility and HVAC power reduction — expressed as `kw_saved_per_degree_c`
or an equivalent per-interval representation, whichever fits Agent 2's own physics
model best.

**Why Agent 4 cannot safely implement it alone**
`src/agents/digital_twin/**` is Dev 2-owned. **Agent 4 should not invent this
coefficient** — it depends on Dev 2's 2R2C thermal constants and physical model, which
Agent 4 has no authority or visibility to guess at correctly.

**Proposed contract**
`kw_saved_per_degree_c: float` (or a 48-length per-interval list, if the sensitivity
varies meaningfully across the day), added to Agent 2's existing simulation output.

**Owner**
Dev 2.

**Dependency / impact**
Blocks Tier 1 enforcement specifically (item 5 in the implementation sequence below).
Tier 0 and Tier 2 work does not depend on this and can proceed once WIRE-1/2 land.

---

## WIRE-4 — Maximum grid import capacity

**Current limitation**
`grid_kw[t]` is currently unbounded above in both the committed solver and the
reference baseline. This makes Tier 0 protection effectively vacuous: the model can
always import additional grid power to meet 100% of demand, so it is never actually
forced to choose between curtailing anyone. A "hard constraint" that can never bind
isn't a real guarantee.

**Required change**
A documented `max_grid_import_kw` constraint/capacity, representing the campus's real
utility connection limit.

**Why Agent 4 cannot safely implement it alone**
This requires Lead approval because it affects shared configuration/domain contracts
(`src/config/settings.py` and/or `src/shared/constants.py`, plus a new field on
`OptimizationInput`), all of which are Lead-owned or request-only for every other
member.

**Proposed contract**
`max_grid_import_kw: float`, defaulting to an effectively unbounded value so existing
behaviour is unchanged for anyone not yet exercising tier logic.

**Owner**
Lead.

**Dependency / impact**
Blocks a *non-vacuous* Tier 0 guarantee. Without this, Tier 0 enforcement (item 3
below) can be implemented mathematically but will have no scenario in which it is ever
tested for real — it should still be built, but its test coverage will need a
deliberately constructed infeasible-without-shedding fixture rather than a realistic
one, until this lands.

---

## Agent 4 implementation after approval

Once the above are resolved (fully or partially — items below are ordered so Agent 4
can start as soon as WIRE-1 lands, without waiting on all four):

1. Synthetic unit-test fixture using the approved contract
2. Tier-aware MILP variables and constraints
3. Tier 0 hard protection
4. Tier 2 curtailment/shift logic
5. Tier 1 flexibility logic once Agent 2 sensitivity exists
6. Enforcement tests
7. Integration after upstream wiring is available
8. Responsible-AI verification

## Explicit notes for the record

- **Tier 0 must fail safely through infeasibility rather than silently under-serving
  protected demand.** If the model cannot mathematically guarantee Tier 0's load is
  fully served, it must raise (consistent with the existing `InfeasibleOptimizationError`
  pattern already used in `milp_solver.py`), not quietly reduce Tier 0's supply.
- **Tier 2 shift behaviour needs an explicit team decision** about whether deferred
  energy must be fully recovered somewhere within the 24-hour optimization horizon, or
  whether some Tier 2 energy may be dropped for the day. The guide does not specify
  this, and Agent 4 is not deciding it unilaterally.
- **Unknown room types already fail safely** through the existing classifier —
  `tier_guardrails.classify_room_type()` raises `EntityNotFoundError` on any category
  not explicitly named in the authoritative guide (e.g. "Computer Lab", "Auditorium",
  "Dormitory"), rather than defaulting them to any tier. This part is already
  implemented and tested (`tests/unit/test_member4_tier_guardrails.py`) and needs no
  further action from the Lead.
