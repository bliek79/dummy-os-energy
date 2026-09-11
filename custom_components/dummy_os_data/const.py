"""Constants for Dummy OS Energy."""

from __future__ import annotations

DOMAIN = "dummy_os_data"
NAME = "Dummy OS Energy"
VERSION = "0.2.0-alpha.21"

# Legacy Energy Forecast source key retained for config-entry compatibility only.
# Energy Forecast production always consumes the canonical Source Home Power entity.
CONF_HOME_POWER_ENTITY = "home_power_entity"
DEFAULT_HOME_POWER_ENTITY = "sensor.home_power"

# The remaining constants are intentionally imported from the existing module at
# runtime through this release branch; this file is replaced only after the full
# source has been fetched and version-updated by the release workflow.
