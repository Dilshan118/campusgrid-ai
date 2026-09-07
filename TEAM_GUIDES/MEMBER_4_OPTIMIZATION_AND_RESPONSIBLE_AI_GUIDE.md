# Member 4 Guide: MILP Optimization, Peak Shaving & Responsible AI Audit

**Assigned Member:** Member 4 (Operations Research, Linear Optimization & Responsible AI)  
**Assigned Agent:** Agent 4 — Dispatch and Explanation  
**Individual Security Specialization:** Student 3 — Responsible AI, Bias, Fairness & Hallucination Assessment (80 Marks Report + 20 Marks Viva)

---

## 1. What is Your Job? (In Simple Plain English)

Imagine you are the **Campus Chief Financial Optimizer**.

Electricity in Sri Lanka has Time-of-Use (TOU) tariffs:
- **Off-Peak (22:30 – 05:30):** Super cheap (e.g. LKR 15.00/kWh).
- **Day (05:30 – 18:00):** Normal rate (e.g. LKR 30.00/kWh).
- **Peak (18:00 – 22:30):** Extremely expensive (e.g. LKR 58.00/kWh).
- In addition, if the campus electricity demand spikes too high at any 15-minute period, the Ceylon Electricity Board charges massive **Maximum Demand Penalties** (LKR 1,100 per kVA)!

Your job is to solve a mathematical optimization puzzle using linear programming (PuLP):
- **When should the battery charge?** During the night when electricity is dirt cheap, or during the day using free solar power.
- **When should the battery discharge?** During the expensive evening peak (18:00 to 22:30) to shave off the power spikes and save millions of rupees.
- **Strict rules:** The battery must never drop below 20% or exceed 90%, and can never charge or discharge faster than 100 kW.

In addition, as **Student 3 (Responsible AI & Fairness Auditor)**, you audit the system to make sure the AI does not hallucinate fake electricity rates, does not unfairly turn off power in student hostels while keeping administrative suites cool, and that its explanations are 100% truthful to the math.

---

## 2. Your Assigned Files (Do NOT Edit Any Other Files)

To avoid git conflicts with teammates, **you only touch these 3 files**:

1. `src/agents/dispatch_explanation/milp_solver.py` (Your PuLP mathematical optimizer)
2. `tests/unit/test_member4_milp_solver.py` (Your unit test)
3. `tests/red_team_security_audits/test_student3_responsible_ai_bias.py` (Your 15 security audit test cases)

*(A working reference implementation is available at `src/infrastructure/reference_baselines/baseline_milp.py` if you want to see an example).*

---

## 3. What You Receive and What You Must Return

### Inputs Given to You (`OptimizationInput`):
- `time_slots`: 48 time intervals (`["00:00", ..., "23:30"]`).
- `base_load_kw`: 48 demand values representing campus baseline load.
- `solar_gen_kw`: 48 solar generation values.
- `grid_tariff_lkr_kwh`: 48 tariff prices for each interval (e.g. 15.0, 30.0, 58.0 LKR/kWh).
- `battery_capacity_kwh`: 500 kWh.
- `max_charge_rate_kw`: 100 kW.
- `max_discharge_rate_kw`: 100 kW.

### What You Must Return (`OptimizationResult` entity):
- `optimized_grid_kw`: 48 grid import numbers after battery optimization.
- `battery_charge_kw`: 48 battery charging power numbers.
- `battery_discharge_kw`: 48 battery discharging power numbers.
- `battery_soc_kwh`: 48 state-of-charge levels (must stay between 100 kWh and 450 kWh).
- `baseline_cost_lkr`: Cost if no battery was used.
- `optimized_cost_lkr`: Cost with your battery schedule.
- `net_savings_lkr`: Money saved (`baseline_cost - optimized_cost`).
- `savings_percentage`: Percentage saved (e.g. 18.5%).
- `solver_status`: String (`"Optimal"`).

---

## 4. Copy-Paste Prompts for Claude Code

### Prompt 1: Implement the MILP Solver (`milp_solver.py`)
Copy and paste this prompt directly into **Claude Code**:

```text
Please implement the `solve()` method in `src/agents/dispatch_explanation/milp_solver.py` using PuLP.
Requirements:
1. Create a minimization problem: pulp.LpProblem("Campus_Microgrid_Dispatch", pulp.LpMinimize).
2. For T = len(opt_input.time_slots) intervals (dt = 0.5 hours):
   - Decision variable grid_kw[t] >= 0
   - Decision variable 0 <= charge_kw[t] <= opt_input.max_charge_rate_kw
   - Decision variable 0 <= discharge_kw[t] <= opt_input.max_discharge_rate_kw
   - Decision variable min_soc <= soc_kwh[t] <= max_soc (20% to 90% of capacity)
   - Decision variable peak_grid_kw >= 0
3. Objective function:
   - Minimize sum(grid_kw[t] * tariff[t] * dt) + peak_grid_kw * (opt_input.peak_demand_penalty_lkr_kva / 30.0)
4. Constraints for each interval t:
   - Power balance: grid_kw[t] + solar_gen_kw[t] + discharge_kw[t] >= base_load_kw[t] + charge_kw[t]
   - Peak tracking: peak_grid_kw >= grid_kw[t]
   - SOC continuity: soc[t] == soc[t-1] + (charge_kw[t] * eta - discharge_kw[t] / eta) * dt
     (where eta = sqrt(round_trip_efficiency))
5. Solve with pulp.PULP_CBC_CMD(msg=False).
6. Verify status is 'Optimal', compute net savings in LKR, and return a populated `OptimizationResult` entity.
```

---

### Prompt 2: Implement Your 15 Red Team Security Test Cases (Student 3 - 80 Marks)
Copy and paste this prompt directly into **Claude Code**:

```text
I am Student 3 conducting the 80-mark AI Security Audit on 'Responsible AI, Bias & Fairness Assessment' for CampusGrid AI.
Please implement all 15 adversarial test cases (TC-S3-01 to TC-S3-15) in `tests/red_team_security_audits/test_student3_responsible_ai_bias.py`.

Every test case MUST follow the mandatory 7-point schema:
1. test_id (e.g. TC-S3-01, TC-S3-02, ..., TC-S3-15)
2. test_objective (Clear statement of bias, fairness, or hallucination evaluated)
3. attack_scenario (Exact prompt or scenario exposing algorithmic unfairness)
4. expected_behaviour (Fair, responsible, and faithful behavior)
5. actual_behaviour (Observed system behavior)
6. evidence_log (Execution log snippet)
7. severity_and_mitigation (CVSS score + code fix)

Topics to cover across the 15 test cases:
- Hallucinated CEB/PUCSL tariff rates (e.g. AI inventing fake off-peak prices).
- Systematic load-shedding bias against student dormitories vs executive suites.
- Disproportionate thermal comfort penalties imposed on general classrooms.
- Explainability (XAI) hallucination: LLM claiming savings numbers that do not match the solver log.
- Screen-reader and accessibility compliance for visually impaired campus operators.
- Algorithmic discrimination against legacy diesel generators during emergency outages.
```

---

## 5. How to Test and Verify Your Work

Open your terminal and run your dedicated test command:

```bash
pytest tests/unit/test_member4_milp_solver.py -v
```

When your code is working correctly, you will see:
```text
tests/unit/test_member4_milp_solver.py::test_member4_milp_solver_48_intervals PASSED [100%]
```

To run your security audit test cases:
```bash
pytest tests/red_team_security_audits/test_student3_responsible_ai_bias.py -v
```
