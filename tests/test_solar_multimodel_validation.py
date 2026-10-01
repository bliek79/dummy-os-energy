"""Regression contract for F4 Solar multi-model validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "custom_components" / "dummy_os_data" / "solar_multimodel_validation.py"
)
SPEC = importlib.util.spec_from_file_location("solar_multimodel_validation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MM)


def _evaluation(
    *,
    slot: str = "2026-09-30T14:15:00+00:00",
    captured: str = "2026-09-30T14:15:00+00:00",
    forecasts: tuple[float, float, float] = (0.09, 0.04, 0.13),
    actuals: tuple[float, float, float] = (0.10, 0.05, 0.15),
) -> dict:
    result = {
        "slot_id": slot,
        "forecast_captured_at": captured,
        "status": "ok",
        "valid": True,
    }
    for roof, forecast, actual in zip(MM.ROOFS, forecasts, actuals, strict=True):
        result[f"forecast_{roof}_kwh"] = forecast
        result[f"actual_{roof}_kwh"] = actual
        result[f"valid_{roof}"] = True
        result[f"coverage_{roof}_percent"] = 100.0
    return result


def _horizon_evaluation(
    *,
    forecasts: tuple[float, float, float] = (0.095, 0.045, 0.14),
    solar_azimuth_deg: float = 230.0,
    solar_elevation_deg: float = 23.6,
    direct: float = 5.7,
    diffuse: float = 79.3,
) -> dict:
    result = _evaluation(forecasts=forecasts)
    result.update(
        {
            "solar_azimuth_deg": solar_azimuth_deg,
            "solar_elevation_deg": solar_elevation_deg,
            "north_direct_radiation_wm2": direct,
            "south_direct_radiation_wm2": direct,
            "north_diffuse_radiation_wm2": diffuse,
            "south_diffuse_radiation_wm2": diffuse,
        }
    )
    return result


def test_exact_lock_triple_builds_one_shared_actual_sample() -> None:
    raw = _evaluation(forecasts=(0.11, 0.05, 0.16))
    temperature = _evaluation(forecasts=(0.10, 0.05, 0.15))
    horizon = _horizon_evaluation(forecasts=(0.095, 0.045, 0.14))

    status, sample = MM.build_multimodel_pair(raw, temperature, horizon)

    assert status == "ok"
    assert sample is not None
    assert sample["slot_id"] == raw["slot_id"]
    assert sample["forecast_captured_at"] == raw["forecast_captured_at"]
    total = sample["components"]["total"]
    assert total["actual_kwh"] == 0.15
    assert total["raw_absolute_error_kwh"] == 0.01
    assert total["temperature_absolute_error_kwh"] == 0.0
    assert total["horizon_absolute_error_kwh"] == 0.01
    assert sample["solar_elevation_band"] == "medium"
    assert sample["solar_azimuth_sector"] == "west"
    assert sample["weather_regime"] == "diffuse_dominant"


def test_triple_rejects_non_identical_lock_actual_or_coverage() -> None:
    raw = _evaluation()
    temperature = _evaluation()
    horizon = _horizon_evaluation()

    temperature["slot_id"] = "2026-09-30T14:30:00+00:00"
    assert MM.build_multimodel_pair(raw, temperature, horizon)[0] == "slot_mismatch"

    temperature = _evaluation(captured="2026-09-30T14:00:00+00:00")
    assert MM.build_multimodel_pair(raw, temperature, horizon)[0] == "lock_mismatch"

    temperature = _evaluation()
    horizon = _horizon_evaluation()
    horizon["actual_total_kwh"] = 0.151
    assert MM.build_multimodel_pair(raw, temperature, horizon)[0] == "actual_mismatch"

    horizon = _horizon_evaluation()
    horizon["coverage_total_percent"] = 99.0
    assert MM.build_multimodel_pair(raw, temperature, horizon)[0] == "coverage_mismatch"

    horizon = _horizon_evaluation()
    horizon["status"] = "missing_or_late_forecast_snapshot"
    horizon["valid"] = False
    assert MM.build_multimodel_pair(raw, temperature, horizon)[0] == "invalid_evaluation"


def test_condition_classification_contract() -> None:
    assert MM.classify_solar_elevation(-0.1) == "below_horizon"
    assert MM.classify_solar_elevation(0.0) == "low"
    assert MM.classify_solar_elevation(9.999) == "low"
    assert MM.classify_solar_elevation(10.0) == "medium"
    assert MM.classify_solar_elevation(25.0) == "high"

    assert MM.classify_solar_azimuth(359.0) == "north"
    assert MM.classify_solar_azimuth(45.0) == "east"
    assert MM.classify_solar_azimuth(180.0) == "south"
    assert MM.classify_solar_azimuth(230.0) == "west"

    assert MM.classify_weather_regime(0.0, 0.0)[0] == "dark"
    assert MM.classify_weather_regime(5.7, 79.3)[0] == "diffuse_dominant"
    assert MM.classify_weather_regime(60.0, 40.0)[0] == "mixed"
    assert MM.classify_weather_regime(80.0, 20.0)[0] == "direct_dominant"


def test_daily_and_breakdown_aggregation_reports_all_models_without_winner() -> None:
    first_status, first = MM.build_multimodel_pair(
        _evaluation(forecasts=(0.11, 0.05, 0.16)),
        _evaluation(forecasts=(0.10, 0.05, 0.15)),
        _horizon_evaluation(forecasts=(0.095, 0.045, 0.14)),
    )
    assert first_status == "ok" and first is not None

    raw2 = _evaluation(
        slot="2026-09-30T14:30:00+00:00",
        captured="2026-09-30T14:30:00+00:00",
        forecasts=(0.08, 0.04, 0.12),
        actuals=(0.09, 0.04, 0.13),
    )
    temp2 = _evaluation(
        slot="2026-09-30T14:30:00+00:00",
        captured="2026-09-30T14:30:00+00:00",
        forecasts=(0.085, 0.04, 0.125),
        actuals=(0.09, 0.04, 0.13),
    )
    hor2 = _horizon_evaluation(
        forecasts=(0.088, 0.041, 0.129),
        solar_azimuth_deg=235.0,
        solar_elevation_deg=20.0,
        direct=70.0,
        diffuse=30.0,
    )
    hor2["slot_id"] = raw2["slot_id"]
    hor2["forecast_captured_at"] = raw2["forecast_captured_at"]
    for roof in MM.ROOFS:
        hor2[f"actual_{roof}_kwh"] = raw2[f"actual_{roof}_kwh"]
    second_status, second = MM.build_multimodel_pair(raw2, temp2, hor2)
    assert second_status == "ok" and second is not None

    day = MM.new_multimodel_day("2026-09-30")
    MM.add_multimodel_sample(day, first)
    MM.add_multimodel_sample(day, second)
    summary = MM.summarize_multimodel_history([day])

    assert summary["sample_count"] == 2
    assert summary["day_count"] == 1
    total = summary["components"]["total"]
    assert total["sample_count"] == 2
    assert total["actual_kwh"] == 0.28
    assert total["temperature_absolute_error_kwh"] == 0.005
    assert "medium" in summary["breakdown_by_solar_elevation"]
    assert "west" in summary["breakdown_by_solar_azimuth"]
    assert "diffuse_dominant" in summary["breakdown_by_weather_regime"]
    assert "direct_dominant" in summary["breakdown_by_weather_regime"]
    assert "winner" not in str(summary).lower()
    assert "promotion" not in str(summary).lower()


def test_f4_runtime_contract_is_persistent_canonical_and_non_promoting() -> None:
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

    for marker in (
        '"multimodel_history"',
        '"multimodel_last_pair_status"',
        '"multimodel_last_slot_id"',
        "build_multimodel_pair(",
        "summarize_multimodel_history(",
        "self._record_multimodel_validation()",
    ):
        assert marker in solar

    unique_id = "do_solar_multimodel_validation"
    assert f'_attr_unique_id = "{unique_id}"' in sensor
    assert f'("sensor", "{unique_id}", "sensor.{unique_id}")' in init_source
    assert (
        f'"{unique_id}": "sensor.dummy_os_energy_{unique_id}"'
        in migrations
    )
    assert '"promotion_authority": False' in sensor
    assert "partial_shading" not in MODULE_PATH.read_text(encoding="utf-8")
    assert "residual_learning" not in MODULE_PATH.read_text(encoding="utf-8")


def test_f4_does_not_change_native_forecast_contract() -> None:
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
    assert "self._source_points = points" in solar
    assert "self._temperature_candidate_points = candidate_points" in solar
    assert "self._horizon_candidate_points = horizon_points" in solar
