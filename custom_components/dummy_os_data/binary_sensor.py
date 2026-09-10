"""Binary sensors for Dummy OS Energy."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DummyOSHomeDataCoordinator
from .do_plan_scheduler_sensor import build_do_plan_scheduler_binary_sensors
from .do_plan_execution_preview_sensor import build_do_plan_execution_preview_binary_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up observer-only Dummy OS Energy binary sensors."""
    coordinator: DummyOSHomeDataCoordinator = entry.runtime_data
    async_add_entities([
        *build_do_plan_scheduler_binary_sensors(coordinator),
        *build_do_plan_execution_preview_binary_sensors(coordinator),
    ])
