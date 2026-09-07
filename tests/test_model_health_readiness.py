from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "dummy_os_data" / "model_health.py"
spec = importlib.util.spec_from_file_location("model_health", MODULE)
model_health = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(model_health)
calculate = model_health.calculate_model_health_readiness


def localize(value: datetime) -> datetime:
    return value


def records(days: int, profile: str = "normal"):
    result = []
    for day in range(days):
        result.append({
            "profile": profile,
            "valid": True,
            "energy_kwh": 0.1,
            "start": datetime(2026, 8, 1 + day, 12, 0, tzinfo=timezone.utc).isoformat(),
        })
    return result


def horizon(status="collecting", accuracy=50.0, bias=0.0):
    return {
        "status": "sufficient_basis" if status == "sufficient_basis" else "collecting",
        "horizons": {
            key: {
                "status": status,
                "accuracy_percent": accuracy if status == "sufficient_basis" else None,
                "bias_kwh": bias if status == "sufficient_basis" else None,
            }
            for key in ("h00_control", "h01", "h03", "h06", "h12", "h24", "h48", "h72_edge")
        },
    }


def quality(segment_accuracy=50.0):
    return {
        "combinations": {
            "weekday_afternoon": {
                "status": "sufficient_basis",
                "accuracy_percent": segment_accuracy,
            }
        }
    }


def hours(hour_accuracy=50.0):
    return {
        "hours": {
            "hour_17": {
                "status": "sufficient_basis",
                "accuracy_percent": hour_accuracy,
            }
        }
    }


def run(*, days=14, samples=300, coverage=100, confidence=70, accuracy=50, mae=0.07, bias=0.0,
        source_available=True, horizon_status="collecting", horizon_accuracy=50, horizon_bias=0.0,
        segment_accuracy=50, hour_accuracy=50, profile="normal"):
    return calculate(
        records=records(days, profile if profile in {"normal", "away"} else "normal"),
        profile=profile,
        source_available=source_available,
        forecast_coverage_percent=coverage,
        average_confidence_percent=confidence,
        evaluation_metrics={"samples": samples, "accuracy_percent": accuracy, "mae_kwh": mae, "bias_kwh": bias},
        horizon_quality=horizon(horizon_status, horizon_accuracy, horizon_bias),
        day_type_daypart_quality=quality(segment_accuracy),
        hour_quality=hours(hour_accuracy),
        localize=localize,
    )


def test_collecting_below_learning_basis():
    result = run(days=6, samples=31, coverage=79.9, confidence=44.9)
    assert result["readiness_status"] == "collecting"
    assert result["readiness_blockers"]


def test_learning_exact_boundary():
    result = run(days=7, samples=32, coverage=80, confidence=45, accuracy=0, mae=9, bias=9)
    assert result["readiness_status"] == "learning"


def test_usable_exact_boundary():
    result = run(days=14, samples=256, coverage=95, confidence=60, accuracy=35, mae=0.100, bias=0.020)
    assert result["readiness_status"] == "usable"


def test_strong_requires_horizon_observing_and_28_days():
    result = run(days=27, samples=1200, coverage=100, confidence=70, accuracy=55, mae=0.05, bias=0.001, horizon_status="collecting")
    assert result["readiness_status"] == "usable"
    assert any("history_days" in blocker for blocker in result["readiness_blockers"])
    assert any("horizon_observing_count" in blocker for blocker in result["readiness_blockers"])


def test_strong_exact_boundary_with_all_horizons_observing():
    result = run(days=28, samples=1024, coverage=98, confidence=65, accuracy=45, mae=0.075, bias=0.010, horizon_status="observing")
    assert result["readiness_status"] == "strong"
    assert result["horizon_observing_count"] == 8


def test_sufficient_weak_horizon_blocks_strong():
    result = run(days=28, samples=1200, coverage=100, confidence=70, accuracy=55, mae=0.05, bias=0.001,
                 horizon_status="sufficient_basis", horizon_accuracy=24.9)
    assert result["readiness_status"] == "usable"
    assert any("accuracy_below_25" in blocker for blocker in result["readiness_blockers"])


def test_sufficient_horizon_bias_blocks_strong():
    result = run(days=28, samples=1200, coverage=100, confidence=70, accuracy=55, mae=0.05, bias=0.001,
                 horizon_status="sufficient_basis", horizon_bias=0.031)
    assert result["readiness_status"] == "usable"
    assert any("absolute_bias_above_0.03" in blocker for blocker in result["readiness_blockers"])


def test_weak_sufficient_hour_blocks_strong():
    result = run(days=28, samples=1200, coverage=100, confidence=70, accuracy=55, mae=0.05, bias=0.001,
                 horizon_status="observing", hour_accuracy=19.9)
    assert result["readiness_status"] == "usable"
    assert result["weak_segment_count"] == 1


def test_source_unavailable_does_not_overwrite_readiness():
    result = run(days=14, samples=300, coverage=100, confidence=70, accuracy=50, mae=0.07, bias=0.001,
                 source_available=False)
    assert result["readiness_status"] == "usable"
    assert result["runtime_input_status"] == "source_unavailable"
    assert result["forecast_operational_input_ok"] is False
    assert result["runtime_blockers"] == ["source_unavailable"]


def test_missing_quality_metrics_do_not_become_zero():
    result = calculate(
        records=records(14), profile="normal", source_available=True,
        forecast_coverage_percent=100, average_confidence_percent=70,
        evaluation_metrics={"samples": 300, "accuracy_percent": None, "mae_kwh": None, "bias_kwh": None},
        horizon_quality=horizon("collecting"), day_type_daypart_quality=quality(), hour_quality=hours(), localize=localize,
    )
    assert result["readiness_status"] == "learning"
    assert result["mae_kwh"] is None
    assert result["bias_kwh"] is None
    assert "missing_mae_kwh" in result["readiness_blockers"]


def test_profile_unclassified_never_borrows_normal_readiness():
    result = run(profile="unclassified")
    assert result["readiness_status"] == "profile_unclassified"
    assert result["readiness_blockers"] == ["profile_unclassified"]
