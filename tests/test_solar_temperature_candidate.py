"""Regression contract for F1 Solar temperature candidate."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLAR = ROOT / "custom_components" / "dummy_os_data" / "solar.py"
SOLAR_SENSOR = ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py"


def _solar_source() -> str:
    return SOLAR.read_text(encoding="utf-8")


def _sensor_source() -> str:
    return SOLAR_SENSOR.read_text(encoding="utf-8")


def test_candidate_sources_parse() -> None:
    ast.parse(_solar_source())
    ast.parse(_sensor_source())


def test_raw_model_and_native_contract_remain_present() -> None:
    source = _solar_source()
    assert '"model": "open_meteo_gti_physical_v0.1"' in source
    assert "FORECAST_SLOTS" in source
    assert "SOLAR_RESOLUTION_MINUTES = 15" in source
    assert "self._source_points = points" in source


def test_open_meteo_request_keeps_f1_temperature_when_f3_inputs_are_added() -> None:
    source = _solar_source()
    assert '"minutely_15": "temperature_2m,global_tilted_irradiance,direct_radiation,diffuse_radiation"' in source
    assert "self._temperature_candidate_points = candidate_points" in source
    assert "temperature_corrected_pv_power_kw(" in source


def test_interval_average_temperature_uses_adjacent_boundaries() -> None:
    source = _solar_source()
    assert "previous = float(temperatures[index - 1])" in source
    assert "current = float(temperatures[index])" in source
    assert "round((previous + current) / 2.0, 6)" in source
    assert "backward_average_slot_start(" in source


def test_candidate_failure_clears_candidate_without_raising_raw() -> None:
    source = _solar_source()
    raw_publish = source.index("self._source_points = points")
    candidate_try = source.index("try:", raw_publish)
    candidate_clear = source.index("self._temperature_candidate_points = []", candidate_try)
    generation_metadata = source.index("self.source_generation_time_ms = {", candidate_clear)
    assert raw_publish < candidate_try < candidate_clear < generation_metadata


def test_candidate_is_locked_and_persisted_separately() -> None:
    source = _solar_source()
    assert "self._temperature_candidate_snapshot_for_slot(" in source
    assert '"temperature_candidate_snapshot": self._temperature_candidate_snapshot' in source
    assert '"last_temperature_candidate_evaluation"' in source
    assert "self.last_temperature_candidate_evaluation = build_quarter_evaluation(" in source


def test_candidate_entities_use_candidate_not_shadow_identity() -> None:
    source = _sensor_source()
    entity_ids = (
        "do_solar_temperature_candidate_timeline",
        "do_solar_temperature_candidate_next_quarter",
        "do_solar_temperature_candidate_evaluation_last_completed_quarter",
    )
    for entity_id in entity_ids:
        assert entity_id in source
        assert "shadow" not in entity_id


def test_candidate_diagnostics_expose_reference_parameters() -> None:
    source = _sensor_source()
    for marker in (
        "SOLAR_TEMPERATURE_ROSS_K_REFERENCE",
        "SOLAR_TEMPERATURE_ALPHA_REFERENCE",
        "SOLAR_TEMPERATURE_CELL_STC_C",
        "candidate_role",
        "parallel_observer",
    ):
        assert marker in source


def test_candidate_entities_have_canonical_migration_routes() -> None:
    init_source = (ROOT / "custom_components" / "dummy_os_data" / "__init__.py").read_text(encoding="utf-8")
    migration_source = (ROOT / "custom_components" / "dummy_os_data" / "entity_migrations.py").read_text(encoding="utf-8")
    expected = {
        "do_solar_temperature_candidate_timeline": "sensor.do_solar_temperature_candidate_timeline",
        "do_solar_temperature_candidate_next_quarter": "sensor.do_solar_temperature_candidate_next_quarter",
        "do_solar_temperature_candidate_evaluation_last_completed_quarter": "sensor.do_solar_temperature_candidate_evaluation_last_completed_quarter",
    }
    for unique_id, entity_id in expected.items():
        assert f'("sensor", "{unique_id}", "{entity_id}")' in init_source
        generated = f"sensor.dummy_os_energy_{unique_id}"
        assert f'"{unique_id}": "{generated}"' in migration_source


def test_candidate_status_uses_parallel_not_shadow_semantics() -> None:
    source = _sensor_source()
    assert '"mode": "observation_parallel"' in source
    assert '"mode": "observation_shadow"' not in source
