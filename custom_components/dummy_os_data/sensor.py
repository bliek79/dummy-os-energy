"""Sensor platform wrapper including Presence Context."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .sensor_core import async_setup_entry as _core_setup_entry
from .presence_entities import build_presence_sensors

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    await _core_setup_entry(hass, entry, async_add_entities)
    async_add_entities(build_presence_sensors(entry.runtime_data))
