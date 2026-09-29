"""Regression contract for F2 Solar temperature A/B validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AB_PATH = ROOT / "custom_components" / "dummy_os_data" / "solar_temperature_ab.py"
SPEC = importlib.util.spec_from_file_location("solar_temperature_ab", AB_PATH)
assert SPEC is not None and SPEC.loader is not None
AB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AB)


def _evaluation(
    *,
    slot: str = "2026-09-29T10:00:00+00:00",
    captured: str = "2026-09-29T10:00:00+00:00",
    forecasts: tuple[float, float, float] = (0.4, 0.2, 0.6),
    actuals: tuple[float, float, float] = (0.3, 0.2, 0.5),
) -> dict:
    result = {
        "slot_id": slot,
        "forecast_captured_at": captured,
        "status": "ok",
        "valid": True,
    }
    for roof, forecast, actual in zip(AB.ROOFS, forecasts, actuals, strict=True):
        result[f"forecast_{roof}_kwh"] = forecast
        result[f"actual_{roof}_kwh"] = actual
        result[f"valid_{roof}"] = True
        result[f"coverage_{roof}_percent"] = 100.0
    return result


def test_exact_lock_pair_builds_same_actual_sample() -> None:
    raw = _evaluation(forecasts=(0.4, 0.2, 0.6))
    candidate = _evaluation(forecasts=(0.35, 0.2, 0.55))
    candidate.update(
        {
            "north_cell_temperature_c": 33.0,
            "south_cell_temperature_c": 34.0,
            "north_temperature_factor": 0.968,
            "south_temperature_factor": 0.964,
        }
    )

    status, sample = AB.build_temperature_ab_pair(raw, candidate)

    assert status == "ok"
    assert sample is not None
    assert sample["slot_id"] == raw["slot_id"]
    assert sample["forecast_captured_at"] == raw["forecast_captured_at"]
    assert sample["components"]["total"]["actual_kwh"] == 0.5
    assert sample["components"]["total"]["raw_absolute_error_kwh"] == 0.1
    assert sample["components"]["total"]["candidate_absolute_error_kwh"] == 0.05
    assert sample["north_temperature_factor"] == 0.968


def test_pair_rejects_invalid_or_non_identical_lock_contract() -> None:
    raw = _evaluation()
    candidate = _evaluation()

    candidate["slot_id"] = "2026-09-29T10:15:00+00:00"
    assert AB.build_temperature_ab_pair(raw, candidate)[0] == "slot_mismatch"

    candidate = _evaluation(captured="2026-09-29T09:45:00+00:00")
    assert AB.build_temperature_ab_pair(raw, candidate)[0] == "lock_mismatch"

    candidate = _evaluation()
    candidate["actual_total_kwh"] = 0.51
    assert AB.build_temperature_ab_pair(raw, candidate)[0] == "actual_mismatch"

    candidate = _evaluation()
    candidate["coverage_total_percent"] = 89.0
    assert AB.build_temperature_ab_pair(raw, candidate)[0] == "coverage_mismatch"

    candidate = _evaluation()
    candidate["status"] = "insufficient_total_coverage"
    candidate["valid"] = False
    assert AB.build_temperature_ab_pair(raw, candidate)[0] == "invalid_evaluation"


def test_daily_aggregation_reports_bias_and_wape_without_winner() -> None:
    raw = _evaluation(forecasts=(0.4, 0.2, 0.6))
    candidate = _evaluation(forecasts=(0.35, 0.2, 0.55))
    status, first = AB.build_temperature_ab_pair(raw, candidate)
    assert status == "ok" and first is not None

    raw2 = _evaluation(
        slot="2026-09-29T10:15:00+00:00",
        captured="2026-09-29T10:15:00+00:00",
        forecasts=(0.2, 0.3, 0.5),
        actuals=(0.25, 0.25, 0.5),
    )
    candidate2 = _evaluation(
        slot="2026-09-29T10:15:00+00:00",
        captured="2026-09-29T10:15:00+00:00",
        forecasts=(0.24, 0.27, 0.51),
        actuals=(0.25, 0.25, 0.5),
    )
    status, second = AB.build_temperature_ab_pair(raw2, candidate2)
    assert status == "ok" and second is not None

    day = AB.new_temperature_ab_day("2026-09-29")
    AB.add_temperature_ab_sample(day, first)
    AB.add_temperature_ab_sample(day, second)
    summary = AB.summarize_temperature_ab_history([day])

    assert summary["sample_count"] == 2
    assert summary["day_count"] == 1
    total = summary["components"]["total"]
    assert total["actual_kwh"] == 1.0
    assert total["raw_absolute_error_kwh"] == 0.1
    assert total["candidate_absolute_error_kwh"] == 0.06
    assert total["raw_wape_percent"] == 10.0
    assert total["candidate_wape_percent"] == 6.0
    assert "winner" not in summary
    assert "promotion" not in summary


def test_f2_runtime_contract_is_persistent_and_canonical() -> None:
    solar = (ROOT / "custom_components" / "dummy_os_data" / "solar.py").read_text(encoding="utf-8")
    sensor = (ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py").read_text(encoding="utf-8")
    init_source = (ROOT / "custom_components" / "dummy_os_data" / "__init__.py").read_text(encoding="utf-8")
    migrations = (ROOT / "custom_components" / "dummy_os_data" / "entity_migrations.py").read_text(encoding="utf-8")

    for marker in (
        '"temperature_ab_history"',
        '"temperature_ab_last_pair_status"',
        '"temperature_ab_last_slot_id"',
        "build_temperature_ab_pair(",
        "summarize_temperature_ab_history(",
    ):
        assert marker in solar

    assert '_attr_unique_id = "do_solar_temperature_ab_validation"' in sensor
    assert '"promotion_authority": False' in sensor
    assert '("sensor", "do_solar_temperature_ab_validation", "sensor.do_solar_temperature_ab_validation")' in init_source
    assert '"do_solar_temperature_ab_validation": "sensor.dummy_os_energy_do_solar_temperature_ab_validation"' in migrations


def test_f2_does_not_add_f3_or_learning_logic() -> None:
    ab_source = AB_PATH.read_text(encoding="utf-8")
    sensor = (ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py").read_text(encoding="utf-8")
    assert "direct_radiation" not in ab_source
    assert "diffuse_radiation" not in ab_source
    assert "horizon_profile" not in ab_source
    assert "residual_learning" not in ab_source
    assert "observation_shadow" not in sensor
