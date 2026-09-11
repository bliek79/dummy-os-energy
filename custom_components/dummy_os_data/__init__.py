"""Dummy OS Energy integration entrypoint with Presence/Away context."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import integration_core as _core
from .const import DOMAIN, NAME, PLATFORMS
from .coordinator import DummyOSHomeDataCoordinator
from .degree_days import DummyOSDegreeDaysCoordinator
from .entity_migrations import is_known_generated_entity_id
from .presence_runtime import DummyOSPresenceContextRuntime
from .prices import DummyOSPricesCoordinator
from .solar import DummyOSSolarCoordinator

type DummyOSDataConfigEntry = ConfigEntry[DummyOSHomeDataCoordinator]

_PRESENCE_ENTITY_IDS = (
    ("sensor", "do_presence_context", "sensor.do_presence_context"),
    ("binary_sensor", "do_presence_away_schedule_valid", "binary_sensor.do_presence_away_schedule_valid"),
    ("binary_sensor", "do_presence_away_active", "binary_sensor.do_presence_away_active"),
    ("switch", "do_presence_away_schedule_enabled", "switch.do_presence_away_schedule_enabled"),
    ("datetime", "do_presence_away_start", "datetime.do_presence_away_start"),
    ("datetime", "do_presence_away_end", "datetime.do_presence_away_end"),
)


def _async_migrate_presence_entity_ids(hass: HomeAssistant) -> None:
    registry = er.async_get(hass)
    for platform, unique_id, target_entity_id in _PRESENCE_ENTITY_IDS:
        current = registry.async_get_entity_id(platform, DOMAIN, unique_id)
        if current is None or current == target_entity_id:
            continue
        if not is_known_generated_entity_id(platform, unique_id, current):
            continue
        if registry.async_get(target_entity_id) is not None:
            continue
        registry.async_update_entity(current, new_entity_id=target_entity_id)
        hass.states.async_remove(current)


async def async_setup_entry(hass: HomeAssistant, entry: DummyOSDataConfigEntry) -> bool:
    _core._async_remove_obsolete_home_input_entities(hass)
    _core._async_migrate_alpha12_identities(hass)
    _core._async_remove_degree_days_runtime_states(hass)
    _core._async_migrate_generated_entity_ids(hass)
    _async_migrate_presence_entity_ids(hass)

    if entry.title in {"Dummy OS", "Dummy OS Data"} and entry.title != NAME:
        hass.config_entries.async_update_entry(entry, title=NAME)

    coordinator = DummyOSHomeDataCoordinator(hass, entry)
    await coordinator.async_setup()
    coordinator.degree_days = DummyOSDegreeDaysCoordinator(hass, coordinator.weather)
    await coordinator.degree_days.async_setup()
    coordinator.prices = DummyOSPricesCoordinator(hass, entry)
    await coordinator.prices.async_setup()
    coordinator.solar = DummyOSSolarCoordinator(hass, entry)
    await coordinator.solar.async_setup()
    coordinator.presence = DummyOSPresenceContextRuntime(hass, coordinator)
    await coordinator.presence.async_setup()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _core._async_remove_degree_days_runtime_states(hass)
    _core._async_migrate_generated_entity_ids(hass)
    _async_migrate_presence_entity_ids(hass)
    _core._async_remove_obsolete_home_input_entities(hass)
    entry.async_on_unload(entry.add_update_listener(_core._async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DummyOSDataConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        presence = getattr(entry.runtime_data, "presence", None)
        if presence is not None:
            await presence.async_shutdown()
        solar = getattr(entry.runtime_data, "solar", None)
        if solar is not None:
            await solar.async_shutdown()
        prices = getattr(entry.runtime_data, "prices", None)
        if prices is not None:
            await prices.async_shutdown()
        degree_days = getattr(entry.runtime_data, "degree_days", None)
        if degree_days is not None:
            await degree_days.async_shutdown()
        await entry.runtime_data.async_shutdown()
    return unload_ok
