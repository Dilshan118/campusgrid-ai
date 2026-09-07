# Member 3 Guide: Digital Twin, Physics Simulation & Tool Security Audit

**Assigned Member:** Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)  
**Assigned Agent:** Agent 2 — Digital Twin Simulation  
**Individual Security Specialization:** Student 4 — Information Retrieval, Vector Store & Tool/MCP Security Assessment (80 Marks Report + 20 Marks Viva)

---

## 1. What is Your Job? (In Simple Plain English)

Imagine you are the **Campus Cyber-Physical Engineer**.

The university has real physical assets: classroom buildings with air conditioners (HVAC), and a big campus battery (500 kWh Battery Energy Storage System - BESS).

Before we change the temperature or charge the battery in the real world, we need to test everything in a computer simulation (a **Digital Twin**):
1. **Classroom Thermal Physics:** If it is 32°C outside and 80 students walk into a lecture hall, how fast will the room heat up? If the AC runs at 35 kW, will students remain comfortable according to international standards (between 21.0°C and 25.5°C)?
2. **Battery Physics:** When the battery charges or discharges, how much power is lost as heat (92% round-trip efficiency)? Is the battery staying safely between 20% and 90% so it doesn't get damaged?
3. **What-If Simulations:** What if a heatwave strikes (+3°C hotter)? What if 200 extra students arrive for a conference? Your simulation tells the campus whether the building will overheat.

In addition, as **Student 4 (AI Security Analyst)**, you audit the system to prevent hackers from tampering with the simulation tools, poisoning vector databases, or sending dangerous commands like telling the AC to freeze the room to -10°C.

---

## 2. Your Assigned Files (Do NOT Edit Any Other Files)

To avoid git conflicts with teammates, **you only touch these 4 files**:

1. `src/agents/digital_twin/thermal_model.py` (Your 2R2C room temperature simulator)
2. `src/agents/digital_twin/battery_dynamics.py` (Your battery charge & SOC simulator)
3. `tests/unit/test_member3_digital_twin.py` (Your unit tests)
4. `tests/red_team_security_audits/test_student4_retrieval_mcp_security.py` (Your 15 security audit test cases)

*(A working reference implementation is available at `src/infrastructure/reference_baselines/baseline_thermal.py` if you want to see an example).*

---

## 3. What You Receive and What You Must Return

### For Room Thermal Simulation (`BuildingThermalTwin.simulate`):
- **Inputs:** `initial_temp_c` (e.g. 24.0°C), `ambient_temps` (48 outdoor temps), `occupant_counts` (48 headcounts), `hvac_power_kw` (48 cooling power numbers).
- **Return:** A list of 48 simulated indoor temperature values (`List[float]`).

### For Battery Simulation (`BatteryDynamicsModel.simulate_soc_trajectory`):
- **Inputs:** `initial_soc_kwh` (e.g. 250 kWh), `charge_kw_series` (48 charge powers), `discharge_kw_series` (48 discharge powers).
- **Return:** A tuple: `(soc_history, violations_count)`:
  - `soc_history`: List of 48 battery energy levels (kWh).
  - `violations_count`: Number of times the battery dropped below 20% (100 kWh) or exceeded 90% (450 kWh).

---

## 4. Copy-Paste Prompts for Claude Code

### Prompt 1: Implement Room Thermal Physics (`thermal_model.py`)
Copy and paste this prompt directly into **Claude Code**:

```text
Please implement the `simulate()` method in `src/agents/digital_twin/thermal_model.py`.
Requirements:
1. Implement the 2-Resistance 2-Capacitance (2R2C) differential equation:
   dT_in / dt = (1 / (r_vent * c_in)) * (T_amb - T_in) + (Q_occupants - Q_hvac) / c_in
2. Start with temp_history = [initial_temp_c].
3. For each 30-minute interval (dt_hours = 0.5):
   - Q_occ = occupants * 0.10 kW (each student emits 100 Watts).
   - Q_transfer = (t_amb - current_temp) / self.r_vent.
   - delta_t = (Q_transfer + Q_occ - q_hvac) * (dt_hours / self.c_in).
   - next_temp = round(current_temp + delta_t, 2).
   - Append next_temp to temp_history.
4. Return temp_history[1:] (the 48 simulated indoor temperatures).
```

---

### Prompt 2: Implement Battery Dynamics (`battery_dynamics.py`)
Copy and paste this prompt directly into **Claude Code**:

```text
Please implement `simulate_soc_trajectory()` in `src/agents/digital_twin/battery_dynamics.py`.
Requirements:
1. One-way efficiency is sqrt(round_trip_eff) (sqrt(0.92) ≈ 0.959).
2. Min allowed energy = capacity_kwh * 0.20 (100 kWh for 500 kWh battery).
3. Max allowed energy = capacity_kwh * 0.90 (450 kWh for 500 kWh battery).
4. For each 30-min interval:
   - energy_in = charge_kw * one_way_eff * 0.5
   - energy_out = (discharge_kw / one_way_eff) * 0.5
   - current_soc += energy_in - energy_out
   - If current_soc < min_kwh or current_soc > max_kwh, increment violations.
5. Return (soc_history, violations).
```

---

### Prompt 3: Implement Your 15 Red Team Security Test Cases (Student 4 - 80 Marks)
Copy and paste this prompt directly into **Claude Code**:

```text
I am Student 4 conducting the 80-mark AI Security Audit on 'Information Retrieval, Vector Store & Tool Security Assessment' for CampusGrid AI.
Please implement all 15 adversarial test cases (TC-S4-01 to TC-S4-15) in `tests/red_team_security_audits/test_student4_retrieval_mcp_security.py`.

Every test case MUST follow the mandatory 7-point schema:
1. test_id (e.g. TC-S4-01, TC-S4-02, ..., TC-S4-15)
2. test_objective (Vulnerability being tested)
3. attack_scenario (Exact attack payload, poisoned document, or invalid tool call)
4. expected_behaviour (Secure response)
5. actual_behaviour (Observed behavior)
6. evidence_log (Execution log snippet)
7. severity_and_mitigation (CVSS score + code fix)

Topics to cover across the 15 test cases:
- RAG document index poisoning (uploading fake tariff PDFs with 0.05 LKR/kWh).
- Vector embedding collision and semantic clustering manipulation.
- Tool/MCP parameter spoofing (commanding -15°C or 5000 kW to overheat inverters).
- ChromaDB vector store Denial of Service (DoS) with extreme query vectors.
- Man-In-The-Middle (MITM) interception of unencrypted tool calls (mTLS requirement).
- BACnet/IP and OpenADR payload tampering.
```

---

## 5. How to Test and Verify Your Work

Open your terminal and run your dedicated test command:

```bash
pytest tests/unit/test_member3_digital_twin.py -v
```

When your code is working correctly, you will see:
```text
tests/unit/test_member3_digital_twin.py::test_member3_thermal_model_simulation PASSED [ 33%]
tests/unit/test_member3_digital_twin.py::test_member3_thermal_occupant_heat_gain PASSED [ 66%]
tests/unit/test_member3_digital_twin.py::test_member3_battery_soc_tracking PASSED [100%]
```

To run your security audit test cases:
```bash
pytest tests/red_team_security_audits/test_student4_retrieval_mcp_security.py -v
```
