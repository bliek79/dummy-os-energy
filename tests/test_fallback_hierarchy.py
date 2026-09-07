from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/fallback_hierarchy.py"
SPEC = importlib.util.spec_from_file_location("fallback_hierarchy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
FH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FH)
UTC = timezone.utc


def localize(dt):
    return dt


def record(start, energy, profile="normal", valid=True):
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=15)).isoformat(),
        "energy_kwh": energy,
        "coverage": 1.0,
        "profile": profile,
        "valid": valid,
    }


def evaluation(target, captured, forecast, source, actual, profile="normal"):
    return {
        "evaluation_schema_version": 1,
        "start": target.isoformat(),
        "end": (target + timedelta(minutes=15)).isoformat(),
        "profile": profile,
        "forecast_kwh": forecast,
        "forecast_captured_at": captured.isoformat(),
        "actual_kwh": actual,
        "actual_coverage": 1.0,
        "source": source,
        "confidence": 0.5,
        "sample_count": 1,
        "model": "historical_baseline",
        "model_version": "0.4",
    }


def control_from_history(records, target, captured, profile="normal"):
    history = FH._history_before_capture(records, profile=profile, captured_at=captured, localize=localize)
    source, value, _ = FH._hierarchy_forecast(
        history,
        target_start=target,
        captured_at=captured,
        hierarchy=FH.CONTROL_HIERARCHY,
        localize=localize,
    )
    return source, round(value, 6) if value is not None else None


def test_contract_constants_are_frozen():
    assert FH.SCHEMA_VERSION == 1
    assert FH.ALGORITHM_VERSION == "fallback_hierarchy_observer_v1"
    assert FH.CONTROL_HALF_LIFE_DAYS == 28.0
    assert FH.CONTROL_HIERARCHY == (
        "weekday_quarter", "day_type_quarter", "quarter_of_day", "profile_mean"
    )
    assert FH.CANDIDATE_HIERARCHY == (
        "weekday_quarter", "day_type_quarter", "nearby_quarter_day_type",
        "same_hour_profile", "daypart_profile", "profile_global_median"
    )


def test_nearby_quarter_prefers_15_minutes_then_30_and_never_wraps():
    target = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    history = [
        {"start": target - timedelta(days=7, minutes=15), "energy_kwh": 0.1, "local": target - timedelta(days=7, minutes=15), "qidx": 47, "day_type": "weekday", "daypart": "morning"},
        {"start": target - timedelta(days=7) + timedelta(minutes=15), "energy_kwh": 0.3, "local": target - timedelta(days=7) + timedelta(minutes=15), "qidx": 49, "day_type": "weekday", "daypart": "afternoon"},
        {"start": target - timedelta(days=7, minutes=30), "energy_kwh": 9.0, "local": target - timedelta(days=7, minutes=30), "qidx": 46, "day_type": "weekday", "daypart": "morning"},
    ]
    samples = FH._level_samples(history, target_start=target, level="nearby_quarter_day_type", localize=localize)
    assert sorted(v for _, v in samples) == [0.1, 0.3]

    midnight = datetime(2026, 9, 7, 0, 0, tzinfo=UTC)
    history = [
        {"start": midnight - timedelta(days=7, minutes=15), "energy_kwh": 5.0, "local": midnight - timedelta(days=7, minutes=15), "qidx": 95, "day_type": "weekday", "daypart": "evening"},
        {"start": midnight - timedelta(days=7) + timedelta(minutes=15), "energy_kwh": 0.2, "local": midnight - timedelta(days=7) + timedelta(minutes=15), "qidx": 1, "day_type": "weekday", "daypart": "night"},
    ]
    samples = FH._level_samples(history, target_start=midnight, level="nearby_quarter_day_type", localize=localize)
    assert [v for _, v in samples] == [0.2]


def test_candidate_hierarchy_uses_nearby_before_same_hour():
    target = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    captured = target
    records = [
        record(datetime(2026, 9, 7, 11, 45, tzinfo=UTC), 0.20),
        record(datetime(2026, 9, 7, 12, 30, tzinfo=UTC), 0.80),
    ]
    history = FH._history_before_capture(records, profile="normal", captured_at=captured, localize=localize)
    source, value, count = FH._hierarchy_forecast(
        history, target_start=target, captured_at=captured,
        hierarchy=FH.CANDIDATE_HIERARCHY, localize=localize
    )
    assert source == "nearby_quarter_day_type"
    assert count == 1
    assert round(value, 6) == 0.20


def test_same_hour_then_daypart_then_global_median():
    target = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    captured = target
    records = [record(datetime(2026, 9, 6, 12, 45, tzinfo=UTC), 0.40)]
    history = FH._history_before_capture(records, profile="normal", captured_at=captured, localize=localize)
    source, value, _ = FH._hierarchy_forecast(history, target_start=target, captured_at=captured, hierarchy=FH.CANDIDATE_HIERARCHY, localize=localize)
    assert source == "same_hour_profile"
    assert round(value, 6) == 0.40

    records = [record(datetime(2026, 9, 6, 14, 0, tzinfo=UTC), 0.50)]
    history = FH._history_before_capture(records, profile="normal", captured_at=captured, localize=localize)
    source, value, _ = FH._hierarchy_forecast(history, target_start=target, captured_at=captured, hierarchy=FH.CANDIDATE_HIERARCHY, localize=localize)
    assert source == "daypart_profile"
    assert round(value, 6) == 0.50

    records = [record(datetime(2026, 9, 6, 2, 0, tzinfo=UTC), 0.60)]
    history = FH._history_before_capture(records, profile="normal", captured_at=captured, localize=localize)
    source, value, _ = FH._hierarchy_forecast(history, target_start=target, captured_at=captured, hierarchy=FH.CANDIDATE_HIERARCHY, localize=localize)
    assert source == "profile_global_median"
    assert round(value, 6) == 0.60


def test_weighted_median_is_robust_to_single_outlier():
    ref = datetime(2026, 9, 10, tzinfo=UTC)
    samples = [
        (ref - timedelta(days=1), 0.10),
        (ref - timedelta(days=2), 0.11),
        (ref - timedelta(days=3), 0.12),
        (ref - timedelta(days=4), 10.0),
    ]
    median = FH._weighted_median(samples, ref)
    mean = FH._weighted_mean(samples, ref)
    assert median in {0.10, 0.11, 0.12}
    assert mean is not None and mean > 2.0


def test_history_requires_completed_quarter_before_capture_and_never_crosses_profile():
    capture = datetime(2026, 9, 7, 12, 10, tzinfo=UTC)
    records = [
        record(datetime(2026, 9, 7, 11, 45, tzinfo=UTC), 0.2, "normal"),
        record(datetime(2026, 9, 7, 12, 0, tzinfo=UTC), 99.0, "normal"),
        record(datetime(2026, 9, 7, 11, 45, tzinfo=UTC), 88.0, "away"),
        record(datetime(2026, 9, 7, 11, 30, tzinfo=UTC), 77.0, "normal", valid=False),
    ]
    history = FH._history_before_capture(records, profile="normal", captured_at=capture, localize=localize)
    assert [row["energy_kwh"] for row in history] == [0.2]


def test_unclassified_or_unknown_profile_is_blocked_not_normal():
    result = FH.calculate_fallback_hierarchy([], [], "unclassified", localize)
    assert result["status"] == "blocked"
    assert result["forecast_influence_enabled"] is False
    assert "invalid_profile" in result["blockers"]


def test_control_reproduction_mismatch_is_excluded_from_promotion_evidence():
    target = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    captured = target
    records = [record(datetime(2026, 9, 7, 12, 0, tzinfo=UTC), 0.2)]
    ev = evaluation(target, captured, 9.9, "day_type_quarter", 0.3)
    result = FH.calculate_fallback_hierarchy(records, [ev], "normal", localize)
    assert result["evaluation_count"] == 0
    assert result["excluded_record_counts"]["control_replay_mismatch"] == 1
    assert result["promotion_ready"] is False


def test_valid_replay_is_observer_only_and_fingerprint_is_order_independent():
    records = []
    evaluations = []
    origin = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    for day in range(20):
        date = origin + timedelta(days=day)
        records.append(record(date.replace(hour=11, minute=45), 0.2 + day * 0.001))
        records.append(record(date.replace(hour=12, minute=0), 0.5 + day * 0.001))
    for day in range(7, 18):
        target = origin + timedelta(days=day)
        source, control = control_from_history(records, target, target)
        if control is None:
            continue
        evaluations.append(evaluation(target, target, control, source, 0.3))
    first = FH.calculate_fallback_hierarchy(records, evaluations, "normal", localize)
    second = FH.calculate_fallback_hierarchy(list(reversed(records)), list(reversed(evaluations)), "normal", localize)
    assert first["observer_only"] is True
    assert first["forecast_influence_enabled"] is False
    assert first["promotion_ready"] is False
    assert first["live_shadow_required"] is True
    assert first["calibration_fingerprint"] == second["calibration_fingerprint"]
    assert first["calibration_fingerprint"].startswith("fh_")


def test_late_capture_is_rejected():
    target = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    captured = target + timedelta(minutes=1)
    result = FH.calculate_fallback_hierarchy([], [evaluation(target, captured, 0.2, "profile_mean", 0.2)], "normal", localize)
    assert result["excluded_record_counts"]["late_capture"] == 1
