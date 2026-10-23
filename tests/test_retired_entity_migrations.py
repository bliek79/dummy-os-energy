"""Regression: retired Energy alias table must not break Solar/Heat registry migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components" / "dummy_os_data" / "entity_migrations.py"
SPEC = importlib.util.spec_from_file_location("do_entity_migrations_alpha53", PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_all_retained_solar_and_degree_days_aliases_are_usable() -> None:
    for alias_map in (
        module.SOLAR_GENERATED_ENTITY_ID_ALIASES,
        module.DEGREE_DAYS_GENERATED_ENTITY_ID_ALIASES,
    ):
        for unique_id, entity_id in alias_map.items():
            assert module.is_known_generated_entity_id("sensor", unique_id, entity_id)


def test_source_and_obsolete_home_aliases_are_still_resolved() -> None:
    for unique_id, aliases in (
        *module.DATA_GENERATED_ENTITY_ID_ALIASES.items(),
        *module.OBSOLETE_HOME_INPUT_ENTITY_ALIASES.items(),
    ):
        for entity_id in aliases:
            assert module.is_known_generated_entity_id("sensor", unique_id, entity_id)


def test_custom_renames_and_removed_energy_aliases_are_not_claimed() -> None:
    assert not module.is_known_generated_entity_id(
        "sensor", "do_solar_forecast_timeline", "sensor.my_custom_solar_forecast"
    )
    assert not module.is_known_generated_entity_id(
        "sensor", "do_energy_time_windows", "sensor.dummy_os_forecast_do_energy_time_windows"
    )
    assert not hasattr(module, "ENERGY_GENERATED_ENTITY_ID_ALIASES")


def test_original_generated_prefix_remains_supported() -> None:
    assert module.is_known_generated_entity_id(
        "sensor", "do_solar_status", "sensor.dummy_os_data_dummy_os_legacy_status"
    )
