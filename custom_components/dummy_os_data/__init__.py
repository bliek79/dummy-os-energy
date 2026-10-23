"""Dummy OS Energy - retained Source, Weather, Solar and Degree Days."""
from __future__ import annotations
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, NAME, PLATFORMS
from .coordinator import DummyOSDataCoordinator
from .degree_days import DummyOSDegreeDaysCoordinator
from .entity_migrations import OBSOLETE_HOME_INPUT_ENTITY_ALIASES, is_known_generated_entity_id
from .solar import DummyOSSolarCoordinator

_LOGGER = logging.getLogger(__name__)
type DummyOSDataConfigEntry = ConfigEntry[DummyOSDataCoordinator]

# Alpha.12 changes the public identity namespace while keeping the technical
# integration domain stable. Existing registry rows are migrated in-place so
# Home Assistant does not create duplicate entities with the new unique IDs.
_IDENTITY_MIGRATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("sensor", "do_data_grid_net_power", "do_source_grid_net_power", "sensor.do_source_grid_net_power"),
    ("sensor", "do_data_grid_import_power", "do_source_grid_import_power", "sensor.do_source_grid_import_power"),
    ("sensor", "do_data_grid_export_power", "do_source_grid_export_power", "sensor.do_source_grid_export_power"),
    ("sensor", "do_data_solar_power", "do_source_solar_power", "sensor.do_source_solar_power"),
    ("sensor", "do_data_battery_charge_power", "do_source_battery_charge_power", "sensor.do_source_battery_charge_power"),
    ("sensor", "do_data_battery_discharge_power", "do_source_battery_discharge_power", "sensor.do_source_battery_discharge_power"),
    ("sensor", "do_data_home_power", "do_source_home_power", "sensor.do_source_home_power"),
    ("sensor", "dummy_os_data_energy_peak_learning", "do_energy_peak_learning", "sensor.do_energy_peak_learning"),
    ("select", "do_home_profile", "do_energy_profile", "select.do_energy_profile"),
)

# Direct runtime states from the old Degree Days publisher and stale states left
# behind by the alpha.12 generated entity IDs. They are removed only when they
# are not registered entities, both before and after platform setup.
_DEGREE_DAYS_RUNTIME_STATE_ALIASES: tuple[str, ...] = (
    "sensor.do_degree_days_status",
    "sensor.do_degree_days_history_days",
    "sensor.do_degree_days_temperature_daily",
    "sensor.do_degree_days_daily",
    "sensor.do_weighted_degree_days_daily",
    "sensor.do_degree_days_reference_daily",
    "sensor.do_weighted_degree_days_reference_daily",
    "sensor.do_degree_days_difference",
    "sensor.do_weighted_degree_days_difference",
    "sensor.do_heat_degree_days_last_day",
    "sensor.dummy_os_forecast_do_degree_days_status",
    "sensor.dummy_os_forecast_do_degree_days_history_days",
    "sensor.dummy_os_forecast_do_degree_days_temperature_daily",
    "sensor.dummy_os_forecast_do_degree_days_daily",
    "sensor.dummy_os_forecast_do_degree_days_weighted_daily",
    "sensor.dummy_os_forecast_do_degree_days_reference_daily",
    "sensor.dummy_os_forecast_do_degree_days_weighted_reference_daily",
    "sensor.dummy_os_forecast_do_degree_days_difference",
    "sensor.dummy_os_forecast_do_degree_days_weighted_difference",
    "sensor.dummy_os_forecast_do_degree_days_last_day",
)

# Stable namespaces keep deterministic canonical entity IDs for automatically
# generated aliases from previous alphas. Degree Days is included explicitly so
# alpha.12 registrations such as sensor.dummy_os_forecast_do_degree_days_* are
# migrated in-place to the agreed sensor.do_degree_days_* IDs.
_ENTITY_ID_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("sensor", "do_weather_temperature", "sensor.do_weather_temperature"),
    ("sensor", "do_weather_apparent_temperature", "sensor.do_weather_apparent_temperature"),
    ("sensor", "do_weather_relative_humidity", "sensor.do_weather_relative_humidity"),
    ("sensor", "do_weather_precipitation", "sensor.do_weather_precipitation"),
    ("sensor", "do_weather_cloud_cover", "sensor.do_weather_cloud_cover"),
    ("sensor", "do_weather_wind_speed", "sensor.do_weather_wind_speed"),
    ("sensor", "do_weather_wind_direction", "sensor.do_weather_wind_direction"),
    ("sensor", "do_weather_wind_gusts", "sensor.do_weather_wind_gusts"),
    ("sensor", "do_weather_weather_code", "sensor.do_weather_weather_code"),
    ("sensor", "do_weather_forecast_timeline", "sensor.do_weather_forecast_timeline"),
    ("sensor", "do_weather_source_status", "sensor.do_weather_source_status"),
    ("sensor", "do_weather_source_freshness", "sensor.do_weather_source_freshness"),
    ("sensor", "do_weather_last_update", "sensor.do_weather_last_update"),
    ("sensor", "do_weather_model", "sensor.do_weather_model"),
    ("sensor", "do_solar_status", "sensor.do_solar_status"),
    ("sensor", "do_solar_forecast_timeline", "sensor.do_solar_forecast_timeline"),
    ("sensor", "do_solar_forecast_today_north", "sensor.do_solar_forecast_today_north"),
    ("sensor", "do_solar_forecast_today_south", "sensor.do_solar_forecast_today_south"),
    ("sensor", "do_solar_forecast_today_total", "sensor.do_solar_forecast_today_total"),
    ("sensor", "do_solar_forecast_tomorrow_north", "sensor.do_solar_forecast_tomorrow_north"),
    ("sensor", "do_solar_forecast_tomorrow_south", "sensor.do_solar_forecast_tomorrow_south"),
    ("sensor", "do_solar_forecast_tomorrow_total", "sensor.do_solar_forecast_tomorrow_total"),
    ("sensor", "do_solar_forecast_next_quarter", "sensor.do_solar_forecast_next_quarter"),
    ("sensor", "do_solar_actual_power_north", "sensor.do_solar_actual_power_north"),
    ("sensor", "do_solar_actual_power_south", "sensor.do_solar_actual_power_south"),
    ("sensor", "do_solar_actual_power_total", "sensor.do_solar_actual_power_total"),
    ("sensor", "do_solar_evaluation_last_completed_quarter", "sensor.do_solar_evaluation_last_completed_quarter"),
    ("sensor", "do_solar_evaluation_horizon_1h", "sensor.do_solar_evaluation_horizon_1h"),
    ("sensor", "do_solar_evaluation_horizon_6h", "sensor.do_solar_evaluation_horizon_6h"),
    ("sensor", "do_solar_evaluation_horizon_24h", "sensor.do_solar_evaluation_horizon_24h"),
    ("sensor", "do_solar_evaluation_horizon_48h", "sensor.do_solar_evaluation_horizon_48h"),
    ("sensor", "do_solar_evaluation_horizon_72h", "sensor.do_solar_evaluation_horizon_72h"),
    ("sensor", "do_solar_model", "sensor.do_solar_model"),
    ("sensor", "do_solar_temperature_candidate_timeline", "sensor.do_solar_temperature_candidate_timeline"),
    ("sensor", "do_solar_temperature_candidate_next_quarter", "sensor.do_solar_temperature_candidate_next_quarter"),
    ("sensor", "do_solar_temperature_candidate_evaluation_last_completed_quarter", "sensor.do_solar_temperature_candidate_evaluation_last_completed_quarter"),
    ("sensor", "do_solar_temperature_ab_validation", "sensor.do_solar_temperature_ab_validation"),
    ("sensor", "do_solar_horizon_candidate_timeline", "sensor.do_solar_horizon_candidate_timeline"),
    ("sensor", "do_solar_horizon_candidate_next_quarter", "sensor.do_solar_horizon_candidate_next_quarter"),
    ("sensor", "do_solar_horizon_candidate_evaluation_last_completed_quarter", "sensor.do_solar_horizon_candidate_evaluation_last_completed_quarter"),
    ("sensor", "do_solar_multimodel_validation", "sensor.do_solar_multimodel_validation"),
    ("sensor", "do_solar_partial_shading_candidate_timeline", "sensor.do_solar_partial_shading_candidate_timeline"),
    ("sensor", "do_solar_partial_shading_candidate_next_quarter", "sensor.do_solar_partial_shading_candidate_next_quarter"),
    ("sensor", "do_solar_partial_shading_candidate_evaluation_last_completed_quarter", "sensor.do_solar_partial_shading_candidate_evaluation_last_completed_quarter"),
    ("sensor", "do_solar_partial_shading_validation", "sensor.do_solar_partial_shading_validation"),
    ("sensor", "do_solar_residual_learning_status", "sensor.do_solar_residual_learning_status"),
    ("sensor", "do_solar_residual_learning_candidate_timeline", "sensor.do_solar_residual_learning_candidate_timeline"),
    ("sensor", "do_solar_residual_learning_candidate_next_quarter", "sensor.do_solar_residual_learning_candidate_next_quarter"),
    ("sensor", "do_solar_residual_learning_candidate_evaluation_last_completed_quarter", "sensor.do_solar_residual_learning_candidate_evaluation_last_completed_quarter"),
    ("sensor", "do_solar_residual_learning_validation", "sensor.do_solar_residual_learning_validation"),
    ("sensor", "do_degree_days_status", "sensor.do_degree_days_status"),
    ("sensor", "do_degree_days_history_days", "sensor.do_degree_days_history_days"),
    ("sensor", "do_degree_days_temperature_daily", "sensor.do_degree_days_temperature_daily"),
    ("sensor", "do_degree_days_daily", "sensor.do_degree_days_daily"),
    ("sensor", "do_degree_days_weighted_daily", "sensor.do_degree_days_weighted_daily"),
    ("sensor", "do_degree_days_reference_daily", "sensor.do_degree_days_reference_daily"),
    ("sensor", "do_degree_days_weighted_reference_daily", "sensor.do_degree_days_weighted_reference_daily"),
    ("sensor", "do_degree_days_difference", "sensor.do_degree_days_difference"),
    ("sensor", "do_degree_days_weighted_difference", "sensor.do_degree_days_weighted_difference"),
    ("sensor", "do_degree_days_last_day", "sensor.do_degree_days_last_day"),
)



_RETIRED_UNIQUE_ID_PREFIXES = ("do_energy_", "do_home_", "do_prices_")
_RETIRED_PRICE_STATES = (
    "sensor.do_prices_status", "sensor.do_prices_market_current",
    "sensor.do_prices_import_current", "sensor.do_prices_export_current",
    "sensor.do_prices_timeline", "sensor.do_prices_tariff_profile",
    "sensor.do_prices_gas_market", "sensor.do_prices_gas_all_in",
)

def _async_remove_retired_entities(hass: HomeAssistant) -> None:
    """Remove only obsolete integration-owned entities, never historical data."""
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if entity.platform != DOMAIN or entity.domain not in {"sensor", "select"}:
            continue
        if not str(entity.unique_id).startswith(_RETIRED_UNIQUE_ID_PREFIXES):
            continue
        registry.async_remove(entity.entity_id)
        if hass.states.get(entity.entity_id) is not None:
            hass.states.async_remove(entity.entity_id)
    # Old Price states were published directly without registry entries.
    for entity_id in _RETIRED_PRICE_STATES:
        existing = registry.async_get(entity_id)
        if existing is not None and existing.platform != DOMAIN:
            continue
        if hass.states.get(entity_id) is not None:
            hass.states.async_remove(entity_id)

async def _async_setup_cloud_sources(coordinator: DummyOSDataCoordinator) -> None:
    """Start Weather/Solar concurrently; start Degree Days when complete."""
    results = await asyncio.gather(
        coordinator.weather.async_setup(),
        coordinator.solar.async_setup(),
        return_exceptions=True,
    )
    for name, result in zip(("weather", "solar"), results, strict=True):
        if isinstance(result, BaseException):
            _LOGGER.warning("Dummy OS Data %s startup failed: %s", name, result)
    try:
        await coordinator.degree_days.async_setup()
    except Exception as err:
        _LOGGER.warning("Dummy OS Data Degree Days startup failed: %s", err)


def _is_obsolete_home_input_state(state: State | None) -> bool:
    """Return whether a state has the exact temporary alpha.11.4 signature."""
    if state is None:
        return False
    attrs = state.attributes
    return (
        attrs.get("canonical_sign") == "positive_consumption_negative_export"
        and isinstance(attrs.get("source_entity"), str)
        and "source_available" in attrs
    )


def _async_remove_obsolete_home_input_entities(hass: HomeAssistant) -> None:
    """Remove known automatic alpha.11.4 entities and their stale HA states."""
    registry = er.async_get(hass)

    for unique_id, aliases in OBSOLETE_HOME_INPUT_ENTITY_ALIASES.items():
        registered_entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)

        if registered_entity_id is not None:
            if is_known_generated_entity_id("sensor", unique_id, registered_entity_id):
                registry.async_remove(registered_entity_id)
                hass.states.async_remove(registered_entity_id)
                _LOGGER.info(
                    "Removed obsolete Home input entity and state %s",
                    registered_entity_id,
                )
            else:
                _LOGGER.warning(
                    "Preserving user-renamed obsolete Home input entity %s",
                    registered_entity_id,
                )

        for alias_entity_id in aliases:
            if alias_entity_id == registered_entity_id:
                continue
            if registry.async_get(alias_entity_id) is not None:
                continue
            state = hass.states.get(alias_entity_id)
            if not _is_obsolete_home_input_state(state):
                continue
            hass.states.async_remove(alias_entity_id)
            _LOGGER.info("Removed stale obsolete Home input state %s", alias_entity_id)


def _async_remove_degree_days_runtime_states(hass: HomeAssistant) -> None:
    """Remove only unregistered Degree Days states left by old publishers or migrations."""
    registry = er.async_get(hass)
    for entity_id in _DEGREE_DAYS_RUNTIME_STATE_ALIASES:
        if registry.async_get(entity_id) is not None:
            continue
        if hass.states.get(entity_id) is None:
            continue
        hass.states.async_remove(entity_id)
        _LOGGER.info("Removed legacy Degree Days runtime state %s", entity_id)


def _async_migrate_alpha12_identities(hass: HomeAssistant) -> None:
    """Rename known registry identities from Data/Home to Source/Energy."""
    registry = er.async_get(hass)

    for platform, old_unique_id, new_unique_id, target_entity_id in _IDENTITY_MIGRATIONS:
        current_entity_id = registry.async_get_entity_id(platform, DOMAIN, old_unique_id)
        if current_entity_id is None:
            continue

        existing_target = registry.async_get(target_entity_id)
        if existing_target is not None and target_entity_id != current_entity_id:
            _LOGGER.warning(
                "Cannot migrate %s to %s because the target entity ID already exists",
                current_entity_id,
                target_entity_id,
            )
            continue

        registry.async_update_entity(
            current_entity_id,
            new_entity_id=target_entity_id,
            new_unique_id=new_unique_id,
        )
        if current_entity_id != target_entity_id:
            hass.states.async_remove(current_entity_id)
        _LOGGER.info(
            "Migrated Dummy OS Forecast identity %s/%s to %s/%s",
            current_entity_id,
            old_unique_id,
            target_entity_id,
            new_unique_id,
        )


def _async_migrate_generated_entity_ids(hass: HomeAssistant) -> None:
    """Migrate known automatically generated stable-namespace entity IDs."""
    registry = er.async_get(hass)

    for platform, unique_id, target_entity_id in _ENTITY_ID_MIGRATIONS:
        current_entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
        if current_entity_id is None or current_entity_id == target_entity_id:
            continue

        if not is_known_generated_entity_id(platform, unique_id, current_entity_id):
            continue

        if registry.async_get(target_entity_id) is not None:
            _LOGGER.warning(
                "Cannot migrate %s to %s because the target entity ID already exists",
                current_entity_id,
                target_entity_id,
            )
            continue

        registry.async_update_entity(current_entity_id, new_entity_id=target_entity_id)
        hass.states.async_remove(current_entity_id)
        _LOGGER.info("Migrated entity ID %s to %s", current_entity_id, target_entity_id)



async def async_setup_entry(hass: HomeAssistant, entry: DummyOSDataConfigEntry) -> bool:
    """Only register retained sensors, without Home Forecast or Prices tasks."""
    _async_remove_obsolete_home_input_entities(hass)
    _async_migrate_alpha12_identities(hass)
    _async_remove_degree_days_runtime_states(hass)
    _async_migrate_generated_entity_ids(hass)
    _async_remove_retired_entities(hass)

    if entry.title in {"Dummy OS", "Dummy OS Data"} and entry.title != NAME:
        hass.config_entries.async_update_entry(entry, title=NAME)

    coordinator = DummyOSDataCoordinator(hass, entry)
    coordinator.degree_days = DummyOSDegreeDaysCoordinator(hass, coordinator.weather)
    coordinator.solar = DummyOSSolarCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    source_task = entry.async_create_background_task(
        hass, _async_setup_cloud_sources(coordinator),
        "Dummy OS Data retained cloud sources", eager_start=False,
    )
    coordinator._source_setup_task = source_task
    entry.async_on_unload(source_task.cancel)

    _async_remove_degree_days_runtime_states(hass)
    _async_migrate_generated_entity_ids(hass)
    _async_remove_obsolete_home_input_entities(hass)
    _async_remove_retired_entities(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True

async def _async_update_listener(hass: HomeAssistant, entry: DummyOSDataConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: DummyOSDataConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        source_task = getattr(entry.runtime_data, "_source_setup_task", None)
        if source_task is not None and not source_task.done():
            source_task.cancel()
            try:
                await source_task
            except asyncio.CancelledError:
                pass
        await entry.runtime_data.solar.async_shutdown()
        await entry.runtime_data.degree_days.async_shutdown()
        await entry.runtime_data.weather.async_shutdown()
        _async_remove_retired_entities(hass)
    return unload_ok
