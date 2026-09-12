"""Constants for Dummy OS Energy."""

from __future__ import annotations

DOMAIN = "dummy_os_data"
NAME = "Dummy OS Energy"
VERSION = "0.2.0-alpha.25"

# Legacy Energy Forecast source key retained for config-entry compatibility only.
# Energy Forecast production always consumes the canonical Source Home Power entity.
CONF_HOME_POWER_ENTITY = "home_power_entity"
DEFAULT_HOME_POWER_ENTITY = "sensor.home_power"

# Canonical source-layer Home Power entity used by Energy Forecast production.
CANONICAL_HOME_POWER_ENTITY = "sensor.do_source_home_power"

# Native architecture constants.
QUARTER_MINUTES = 15
FORECAST_HORIZON_HOURS = 72
FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES
