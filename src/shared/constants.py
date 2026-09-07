"""
CampusGrid AI: Shared Domain Constants
PUCSL electricity tariff schedules, ASHRAE thermal comfort bounds, and physical guardrails.
"""

# PUCSL Time-of-Use (TOU) Electricity Tariffs (Sri Lanka GP-2 / Industrial I-2)
TARIFF_OFF_PEAK_LKR = 15.00   # 22:30 - 05:30 (Low demand rate)
TARIFF_DAY_LKR = 30.00        # 05:30 - 18:00 (Standard daytime rate)
TARIFF_PEAK_LKR = 58.00       # 18:00 - 22:30 (High demand peak surcharge rate)

# Maximum Demand Penalty (kVA)
MAX_DEMAND_SURCHARGE_LKR_KVA = 1100.00  # Penalty applied to peak 15-minute spike

# ASHRAE Standard 55-2023 Indoor Thermal Comfort Limits (Celsius)
COMFORT_TEMP_MIN_C = 21.0
COMFORT_TEMP_MAX_C = 25.5
COMFORT_SETPOINT_DEFAULT_C = 24.0

# BESS Electrochemical Hard Physical Safety Guardrails
BATTERY_CAPACITY_DEFAULT_KWH = 500.0
BATTERY_MAX_POWER_DEFAULT_KW = 100.0
BATTERY_SOC_MIN_RATIO = 0.20   # 20% minimum SOC to prevent cell degradation
BATTERY_SOC_MAX_RATIO = 0.90   # 90% maximum SOC to prevent thermal runaway
BATTERY_ROUND_TRIP_EFFICIENCY = 0.92

# Building Grey-Box Thermal Defaults (2R2C Model)
HEAT_PER_OCCUPANT_KW = 0.10    # 100 Watts per student body
BUILDING_CIN_DEFAULT = 50.0    # Thermal capacitance (kWh / °C)
BUILDING_RVENT_DEFAULT = 2.5   # Thermal resistance (°C / kW)
TIME_STEP_HOURS = 0.5          # 30-minute intervals
TOTAL_INTERVALS = 48           # 48 intervals per 24 hours
