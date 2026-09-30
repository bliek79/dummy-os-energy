"""Regression contract for F3 Solar horizon/direct-diffuse candidate."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOLAR = ROOT / "custom_components" / "dummy_os_data" / "solar.py"
SOLAR_SENSOR = ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py"
CONST = ROOT / "custom_components" / "dummy_os_data" / "const.py"
CONFIG = ROOT / "custom_components" / "dummy_os_data" / "config_flow.py"
INIT = ROOT / "custom_components" / "dummy_os_data" / "__init__.py"
MIGRATIONS = ROOT / "custom_components" / "dummy_os_data" / "entity_migrations.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_f3_sources_parse() -> None:
    ast.parse(_text(SOLAR))
    ast.parse(_text(SOLAR_SENSOR))
    ast.parse(_text(CONFIG))


def test_f3_open_meteo_inputs_share_native_request() -> None:
    source = _text(SOLAR)
    assert '"minutely_15": "temperature_2m,global_tilted_irradiance,direct_radiation,diffuse_radiation"' in source
    assert '_normalize_radiation(north_payload, cutoff_utc, "direct_radiation")' in source
    assert '_normalize_radiation(north_payload, cutoff_utc, "diffuse_radiation")' in source
    assert "backward_average_slot_start(" in source


def test_f3_profiles_are_options_not_learned_curves() -> None:
    const = _text(CONST)
    config = _text(CONFIG)
    assert 'CONF_SOLAR_NORTH_HORIZON_PROFILE = "solar_north_horizon_profile_json"' in const
    assert 'CONF_SOLAR_SOUTH_HORIZON_PROFILE = "solar_south_horizon_profile_json"' in const
    assert "parse_horizon_profile" in config
    assert 'default=self._current(CONF_SOLAR_NORTH_HORIZON_PROFILE, "[]")' in config
    assert 'default=self._current(CONF_SOLAR_SOUTH_HORIZON_PROFILE, "[]")' in config


def test_f3_simple_horizon_rule_has_no_partial_shading() -> None:
    source = _text(SOLAR)
    model = _text(ROOT / "custom_components" / "dummy_os_data" / "solar_model.py")
    assert "horizon_effective_irradiance_wm2(" in source
    assert "diffuse if blocked else gti" in model
    assert "partial_shading" not in source
    assert "direct_radiation_role" in _text(SOLAR_SENSOR)


def test_f3_keeps_raw_and_f1_publish_before_candidate() -> None:
    source = _text(SOLAR)
    raw_publish = source.index("self._source_points = points")
    f1_publish = source.index("self._temperature_candidate_points = candidate_points")
    f3_publish = source.index("self._horizon_candidate_points = horizon_points")
    assert raw_publish < f1_publish < f3_publish


def test_f3_uses_existing_per_array_energy_ac_cap() -> None:
    source = _text(SOLAR)
    horizon_start = source.index("# F3 is isolated from raw/F1")
    horizon_end = source.index("self.source_generation_time_ms", horizon_start)
    block = source[horizon_start:horizon_end]
    assert "self.north.ac_limit_kw" in block
    assert "self.south.ac_limit_kw" in block
    assert "temperature_corrected_pv_power_kw(" in block


def test_f3_candidate_entities_are_canonical_and_parallel() -> None:
    sensor = _text(SOLAR_SENSOR)
    init = _text(INIT)
    migrations = _text(MIGRATIONS)
    expected = (
        "do_solar_horizon_candidate_timeline",
        "do_solar_horizon_candidate_next_quarter",
        "do_solar_horizon_candidate_evaluation_last_completed_quarter",
    )
    for unique_id in expected:
        assert f'_attr_unique_id = "{unique_id}"' in sensor
        assert f'("sensor", "{unique_id}", "sensor.{unique_id}")' in init
        assert f'"{unique_id}": "sensor.dummy_os_energy_{unique_id}"' in migrations
        assert "shadow" not in unique_id
    assert 'SOLAR_HORIZON_CANDIDATE_MODEL = "open_meteo_gti_horizon_temperature_candidate_v0.1"' in _text(SOLAR)
    assert '"promotion_authority": False' in sensor


def test_f3_lock_is_persistent_and_separate() -> None:
    source = _text(SOLAR)
    assert "self._horizon_candidate_snapshot_for_slot(" in source
    assert '"horizon_candidate_snapshot": self._horizon_candidate_snapshot' in source
    assert '"last_horizon_candidate_evaluation": self.last_horizon_candidate_evaluation' in source
    assert "self.last_horizon_candidate_evaluation = build_quarter_evaluation(" in source


def test_f3_native_contract_remains_15_72_288() -> None:
    source = _text(SOLAR)
    const = _text(CONST)
    assert "SOLAR_RESOLUTION_MINUTES = 15" in source
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const
    assert "[:FORECAST_SLOTS]" in source
