"""Regression contract for F5 Solar partial-shading observer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "custom_components" / "dummy_os_data" / "solar_model.py"
VALIDATION_PATH = (
    ROOT / "custom_components" / "dummy_os_data" / "solar_partial_shading_validation.py"
)

MODEL_SPEC = importlib.util.spec_from_file_location("solar_model", MODEL_PATH)
assert MODEL_SPEC is not None and MODEL_SPEC.loader is not None
MODEL = importlib.util.module_from_spec(MODEL_SPEC)
MODEL_SPEC.loader.exec_module(MODEL)

VAL_SPEC = importlib.util.spec_from_file_location(
    "solar_partial_shading_validation", VALIDATION_PATH
)
assert VAL_SPEC is not None and VAL_SPEC.loader is not None
VAL = importlib.util.module_from_spec(VAL_SPEC)
VAL_SPEC.loader.exec_module(VAL)


def _evaluation(
    *,
    slot: str = "2026-10-01T08:00:00+00:00",
    captured: str = "2026-10-01T08:00:00+00:00",
    forecasts: tuple[float, float, float] = (0.09, 0.04, 0.13),
    actuals: tuple[float, float, float] = (0.10, 0.05, 0.15),
) -> dict:
    result = {
        "slot_id": slot,
        "forecast_captured_at": captured,
        "status": "ok",
        "valid": True,
    }
    for roof, forecast, actual in zip(VAL.ROOFS, forecasts, actuals, strict=True):
        result[f"forecast_{roof}_kwh"] = forecast
        result[f"actual_{roof}_kwh"] = actual
        result[f"valid_{roof}"] = True
        result[f"coverage_{roof}_percent"] = 100.0
    return result


def _partial_evaluation(
    *,
    forecasts: tuple[float, float, float] = (0.08, 0.04, 0.12),
    north_blocked: bool = True,
    south_blocked: bool = False,
) -> dict:
    result = _evaluation(forecasts=forecasts)
    result.update(
        {
            "north_horizon_blocked": north_blocked,
            "south_horizon_blocked": south_blocked,
            "solar_azimuth_deg": 120.0,
            "solar_elevation_deg": 8.0,
            "north_horizon_elevation_deg": 10.0,
            "south_horizon_elevation_deg": 0.0,
            "north_partial_factor": 0.25,
            "south_partial_factor": 1.0,
            "north_effective_irradiance_wm2": 20.0,
            "south_effective_irradiance_wm2": 100.0,
        }
    )
    return result


def test_partial_helper_preserves_gti_when_unblocked() -> None:
    effective, factor = MODEL.partial_shading_effective_irradiance_wm2(
        300.0, 80.0, 220.0, False
    )
    assert effective == 300.0
    assert factor == 1.0


def test_partial_helper_applies_diffuse_share_when_blocked() -> None:
    effective, factor = MODEL.partial_shading_effective_irradiance_wm2(
        300.0, 80.0, 240.0, True
    )
    assert factor == 0.25
    assert effective == 20.0


def test_partial_helper_zero_radiation_fallback_is_safe() -> None:
    effective, factor = MODEL.partial_shading_effective_irradiance_wm2(
        0.0, 0.0, 0.0, True
    )
    assert factor == 1.0
    assert effective == 0.0


def test_exact_lock_horizon_partial_pair() -> None:
    horizon = _evaluation(forecasts=(0.09, 0.04, 0.13))
    partial = _partial_evaluation(forecasts=(0.08, 0.04, 0.12))
    status, sample = VAL.build_partial_shading_pair(horizon, partial)

    assert status == "ok"
    assert sample is not None
    assert sample["components"]["north"]["horizon_blocked"] is True
    assert sample["components"]["south"]["horizon_blocked"] is False
    assert sample["components"]["total"]["horizon_blocked"] is True


def test_pair_rejects_slot_lock_actual_and_coverage_mismatch() -> None:
    horizon = _evaluation()
    partial = _partial_evaluation()

    partial["slot_id"] = "2026-10-01T08:15:00+00:00"
    assert VAL.build_partial_shading_pair(horizon, partial)[0] == "slot_mismatch"

    partial = _partial_evaluation()
    partial["forecast_captured_at"] = "2026-10-01T07:45:00+00:00"
    assert VAL.build_partial_shading_pair(horizon, partial)[0] == "lock_mismatch"

    partial = _partial_evaluation()
    partial["actual_total_kwh"] = 0.151
    assert VAL.build_partial_shading_pair(horizon, partial)[0] == "actual_mismatch"

    partial = _partial_evaluation()
    partial["coverage_total_percent"] = 99.0
    assert VAL.build_partial_shading_pair(horizon, partial)[0] == "coverage_mismatch"


def test_validation_separates_blocked_effect_from_all_samples() -> None:
    horizon = _evaluation(forecasts=(0.09, 0.04, 0.13))
    partial = _partial_evaluation(forecasts=(0.08, 0.04, 0.12))
    status, sample = VAL.build_partial_shading_pair(horizon, partial)
    assert status == "ok" and sample is not None

    day = VAL.new_partial_shading_day("2026-10-01")
    VAL.add_partial_shading_sample(day, sample)
    summary = VAL.summarize_partial_shading_history([day])

    assert summary["sample_count"] == 1
    assert summary["components"]["north"]["blocked_effect"]["sample_count"] == 1
    assert summary["components"]["south"]["blocked_effect"]["sample_count"] == 0
    assert summary["components"]["total"]["blocked_effect"]["sample_count"] == 1
    assert "winner" not in str(summary).lower()
    assert "promotion" not in str(summary).lower()


def test_f5_runtime_contract_is_parallel_persistent_and_canonical() -> None:
    solar = (ROOT / "custom_components" / "dummy_os_data" / "solar.py").read_text(
        encoding="utf-8"
    )
    sensor = (
        ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py"
    ).read_text(encoding="utf-8")
    init_source = (
        ROOT / "custom_components" / "dummy_os_data" / "__init__.py"
    ).read_text(encoding="utf-8")
    migrations = (
        ROOT / "custom_components" / "dummy_os_data" / "entity_migrations.py"
    ).read_text(encoding="utf-8")

    assert (
        'SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL = '
        '"open_meteo_gti_horizon_partial_temperature_candidate_v0.1"'
        in solar
    )
    for marker in (
        "self._partial_shading_candidate_points",
        "self._partial_shading_candidate_snapshot_for_slot(",
        "self.last_partial_shading_candidate_evaluation = build_quarter_evaluation(",
        "self._record_partial_shading_validation()",
        '"partial_shading_history"',
        '"partial_shading_last_pair_status"',
        '"partial_shading_last_slot_id"',
    ):
        assert marker in solar

    expected = (
        "do_solar_partial_shading_candidate_timeline",
        "do_solar_partial_shading_candidate_next_quarter",
        "do_solar_partial_shading_candidate_evaluation_last_completed_quarter",
        "do_solar_partial_shading_validation",
    )
    for unique_id in expected:
        assert f'_attr_unique_id = "{unique_id}"' in sensor
        assert f'("sensor", "{unique_id}", "sensor.{unique_id}")' in init_source
        assert f'"{unique_id}": "sensor.dummy_os_energy_{unique_id}"' in migrations

    assert '"promotion_authority": False' in sensor


def test_f5_keeps_f3_and_native_contract_unchanged() -> None:
    solar = (ROOT / "custom_components" / "dummy_os_data" / "solar.py").read_text(
        encoding="utf-8"
    )
    const = (ROOT / "custom_components" / "dummy_os_data" / "const.py").read_text(
        encoding="utf-8"
    )
    assert "SOLAR_RESOLUTION_MINUTES = 15" in solar
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert (
        "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES"
        in const
    )
    assert "self._horizon_candidate_points = horizon_points" in solar
    assert "self._partial_shading_candidate_points = partial_points" in solar
    assert solar.index("self._horizon_candidate_points = horizon_points") < solar.index(
        "self._partial_shading_candidate_points = partial_points"
    )
