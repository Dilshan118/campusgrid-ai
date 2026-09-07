# Member 2 Guide: Telemetry, Forecasting & Privacy Audit

**Assigned Member:** Member 2 (Telemetry, Data Engineering & Machine Learning)  
**Assigned Agent:** Agent 1 — Telemetry and Forecasting  
**Individual Security Specialization:** Student 2 — Privacy and Data Leakage Assessment (80 Marks Report + 20 Marks Viva)

---

## 1. What is Your Job? (In Simple Plain English)

Imagine you are the **Campus Weather & Energy Forecaster**.

Every single day, the university campus consumes electricity for lecture halls, laboratories, air conditioners, and computers. At the same time, rooftop solar panels generate clean electricity from the sun.

Your job is to look at:
1. **Past meter data:** How much electricity the campus usually uses at every time of day.
2. **The weather:** How hot it will be tomorrow (hotter weather means people turn up the AC).
3. **Classroom timetables:** How many students will be sitting in the classrooms.

With this information, you predict:
- How much electricity the campus will demand tomorrow for every 30-minute interval (48 numbers).
- How much solar energy the rooftop panels will generate.
- The safe upper and lower boundaries (confidence intervals) so the campus knows if an unusual spike is happening.

In addition, as **Student 2 (AI Security Analyst)**, you audit the system to make sure nobody can spy on students or figure out which secret laboratory machines are running by looking at power meter data.

---

## 2. Your Assigned Files (Do NOT Edit Any Other Files)

To avoid git conflicts with teammates, **you only touch these 4 files**:

1. `src/agents/telemetry/forecaster.py` (Your forecasting algorithm)
2. `src/pipelines/periodic_retraining/train_forecaster.py` (Your offline ML training script)
3. `tests/unit/test_member2_telemetry.py` (Your unit test)
4. `tests/red_team_security_audits/test_student2_privacy_leakage.py` (Your 15 security audit test cases)

*(A working reference implementation is available at `src/infrastructure/reference_baselines/baseline_forecaster.py` if you want to see an example).*

---

## 3. What You Receive and What You Must Return

### Inputs Given to You:
- `historical_intervals`: 48 intervals of yesterday's meter readings (`base_load_kw`, `solar_gen_kw`).
- `temperature_series`: 48 ambient temperature numbers in Celsius (e.g. `[28.0, 29.5, 31.0, ...]`).
- `occupancy_counts`: 48 headcounts of students in the rooms (e.g. `[0, 50, 120, ...]`).

### What You Must Return (`PowerForecast` entity):
- `time_slots`: List of 48 strings (`["00:00", "00:30", ..., "23:30"]`).
- `forecast_demand_kw`: List of 48 predicted campus demand numbers (kW).
- `forecast_solar_kw`: List of 48 predicted solar generation numbers (kW).
- `lower_bound_kw`: 95% lower confidence bound (~6% below forecast).
- `upper_bound_kw`: 95% upper confidence bound (~6% above forecast).
- `anomaly_indices`: List of indices where demand spikes dangerously (e.g. > 850 kW).

---

## 4. Copy-Paste Prompts for Claude Code

### Prompt 1: Implement Your Forecasting Algorithm (`forecaster.py`)
Copy and paste this prompt directly into **Claude Code**:

```text
Please implement the predict() method in `src/agents/telemetry/forecaster.py`.
Requirements:
1. Ingest historical_intervals, temperature_series, and occupancy_counts.
2. For each 30-minute interval:
   - Calculate cooling load: If temperature is above 28.0°C, add 15 kW for every degree above 28°C.
   - Calculate occupancy equipment load: Add 0.05 kW for each student in the room.
   - Forecast demand = base_load + cooling_load + occupancy_load.
   - Forecast solar = historical solar_gen_kw.
   - Compute lower bound (forecast * 0.94) and upper bound (forecast * 1.06).
   - Flag any index where predicted demand exceeds 850 kW as an anomaly.
3. Return a valid `PowerForecast` object containing all 48 intervals.
4. Ensure all types match `src/domain/entities/telemetry.py`.
```

---

### Prompt 2: Implement Offline Retraining (`train_forecaster.py`)
Copy and paste this prompt directly into **Claude Code**:

```text
Please implement the offline model retraining script in `src/pipelines/periodic_retraining/train_forecaster.py`.
Requirements:
1. Read the historical dataset from `backend/data/seeds/sample_campus_seed.csv` using pandas.
2. Engineer features: hour of day, day of week, outdoor_temp_c, zone_occupancy_count.
3. Train a Scikit-Learn or LightGBM regressor predicting base_load_kw.
4. Calculate RMSE and MAE on a 20% test split.
5. Save the trained model pipeline to `src/agents/telemetry/model.joblib`.
```

---

### Prompt 3: Implement Your 15 Red Team Security Test Cases (Student 2 - 80 Marks)
Copy and paste this prompt directly into **Claude Code**:

```text
I am Student 2 conducting the 80-mark AI Security Audit on 'Privacy and Data Leakage Assessment' for CampusGrid AI.
Please implement all 15 adversarial test cases (TC-S2-01 to TC-S2-15) in `tests/red_team_security_audits/test_student2_privacy_leakage.py`.

Every test case MUST follow the mandatory 7-point schema:
1. test_id (e.g. TC-S2-01, TC-S2-02, ..., TC-S2-15)
2. test_objective (Clear statement of the privacy boundary tested)
3. attack_scenario (Exact adversarial query or data-leak payload)
4. expected_behaviour (Privacy-preserving behavior)
5. actual_behaviour (Observed system behavior)
6. evidence_log (Simulated or actual log snippet)
7. severity_and_mitigation (CVSS score + engineering patch)

Topics to cover across the 15 test cases:
- Student and faculty schedule deanonymization.
- Sub-meter Non-Intrusive Load Monitoring (NILM) appliance disaggregation attacks.
- Cross-tenant data leakage between campuses.
- Differential Privacy (Laplace noise epsilon=1.0) verification.
- Markdown image and URL exfiltration attacks.
- Prompt-based indirect extraction of raw database records.
```

---

## 5. How to Test and Verify Your Work

Open your terminal and run your dedicated test command:

```bash
pytest tests/unit/test_member2_telemetry.py -v
```

When your code is working correctly, you will see:
```text
tests/unit/test_member2_telemetry.py::test_member2_forecaster_contract PASSED [100%]
```

To run your security audit test cases:
```bash
pytest tests/red_team_security_audits/test_student2_privacy_leakage.py -v
```
