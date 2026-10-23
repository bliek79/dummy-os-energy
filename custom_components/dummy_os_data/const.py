"""Constants for Dummy OS Energy."""

from __future__ import annotations

DOMAIN = "dummy_os_data"
NAME = "Dummy OS Energy"
VERSION = "0.2.0-alpha.52"

# Canonical Dummy OS Energy source-layer energy inputs.
# Grid power is one bidirectional source: positive = import, negative = export.
CONF_GRID_NET_POWER_ENTITY = "grid_net_power_entity"
CONF_DATA_SOLAR_POWER_ENTITY = "data_solar_power_entity"
CONF_BATTERY_CHARGE_POWER_ENTITY = "battery_charge_power_entity"
CONF_BATTERY_DISCHARGE_POWER_ENTITY = "battery_discharge_power_entity"
DATA_POWER_SOURCE_KEYS = [
    CONF_GRID_NET_POWER_ENTITY,
    CONF_DATA_SOLAR_POWER_ENTITY,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
]

# Temporary alpha.11.5 option keys retained only to prefill migration safely.
LEGACY_CONF_GRID_IMPORT_POWER_ENTITY = "grid_import_power_entity"
LEGACY_CONF_GRID_EXPORT_POWER_ENTITY = "grid_export_power_entity"

CONF_SOLAR_ACTUAL_TOTAL_ENTITY = "solar_actual_total_entity"
CONF_SOLAR_ACTUAL_NORTH_DC_ENTITY = "solar_actual_north_dc_entity"
CONF_SOLAR_ACTUAL_SOUTH_DC_ENTITY = "solar_actual_south_dc_entity"
CONF_SOLAR_LATITUDE = "solar_latitude"
CONF_SOLAR_LONGITUDE = "solar_longitude"
CONF_SOLAR_NORTH_DC_KWP = "solar_north_dc_kwp"
CONF_SOLAR_NORTH_AC_KW = "solar_north_ac_kw"
CONF_SOLAR_NORTH_TILT = "solar_north_tilt"
CONF_SOLAR_NORTH_AZIMUTH = "solar_north_open_meteo_azimuth"
CONF_SOLAR_NORTH_FACTOR = "solar_north_performance_factor"
CONF_SOLAR_NORTH_HORIZON_PROFILE = "solar_north_horizon_profile_json"
CONF_SOLAR_SOUTH_DC_KWP = "solar_south_dc_kwp"
CONF_SOLAR_SOUTH_AC_KW = "solar_south_ac_kw"
CONF_SOLAR_SOUTH_TILT = "solar_south_tilt"
CONF_SOLAR_SOUTH_AZIMUTH = "solar_south_open_meteo_azimuth"
CONF_SOLAR_SOUTH_FACTOR = "solar_south_performance_factor"
CONF_SOLAR_SOUTH_HORIZON_PROFILE = "solar_south_horizon_profile_json"

DEFAULT_SOLAR_ACTUAL_TOTAL_ENTITY = "sensor.sb3_6_1av_41_857_pv_power"
DEFAULT_SOLAR_ACTUAL_NORTH_DC_ENTITY = "sensor.sb3_6_1av_41_857_pv_power_a"
DEFAULT_SOLAR_ACTUAL_SOUTH_DC_ENTITY = "sensor.sb3_6_1av_41_857_pv_power_b"

PLATFORMS = ["sensor"]

SOLAR_STORAGE_VERSION = 1
SOLAR_STORAGE_KEY = f"{DOMAIN}.solar_evaluation"

QUARTER_MINUTES = 15
QUARTER_SECONDS = QUARTER_MINUTES * 60
QUARTERS_PER_DAY = 96
FORECAST_HORIZON_HOURS = 72
FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES
MAX_HISTORY_DAYS = 400
SOLAR_MIN_VALID_COVERAGE = 0.90
