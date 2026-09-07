"""Objective Step 13 Model Health/readiness evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

MODEL_HEALTH_CONTRACT_VERSION = 2
READINESS_ALGORITHM_VERSION = "model_health_readiness_v1"
SUPPORTED_PROFILES = {"normal", "away"}

READINESS_THRESHOLDS = {
    "learning": {
        "history_days_min": 7,
        "evaluation_samples_min": 32,
        "forecast_coverage_percent_min": 80.0,
        "average_confidence_percent_min": 45.0,
    },
    "usable": {
        "history_days_min": 14,
        "evaluation_samples_min": 256,
        "forecast_coverage_percent_min": 95.0,
        "average_confidence_percent_min": 60.0,
        "accuracy_percent_min": 35.0,
        "mae_kwh_max": 0.100,
        "absolute_bias_kwh_max": 0.020,
    },
    "strong": {
        "history_days_min": 28,
        "evaluation_samples_min": 1024,
        "forecast_coverage_percent_min": 98.0,
        "average_confidence_percent_min": 65.0,
        "accuracy_percent_min": 45.0,
        "mae_kwh_max": 0.075,
        "absolute_bias_kwh_max": 0.010,
        "horizon_observing_count_min": 8,
        "weak_segment_count_max": 0,
    },
}


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _profile_history_basis(
    records: list[dict[str, Any]],
    profile: str,
    localize: Callable[[datetime], datetime],
) -> tuple[int, int]:
    dates: set[str] = set()
    quarters = 0
    for record in records:
        if record.get("profile") != profile or record.get("valid") is not True:
            continue
        start = _aware_datetime(record.get("start"))
        if start is None:
            continue
        try:
            float(record["energy_kwh"])
        except (KeyError, TypeError, ValueError):
            continue
        quarters += 1
        dates.add(localize(start).date().isoformat())
    return len(dates), quarters


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _failed_min(name: str, value: float | None, minimum: float) -> str | None:
    if value is None:
        return f"missing_{name}"
    if value < minimum:
        return f"{name}_below_{minimum:g}"
    return None


def _failed_max(name: str, value: float | None, maximum: float) -> str | None:
    if value is None:
        return f"missing_{name}"
    if value > maximum:
        return f"{name}_above_{maximum:g}"
    return None


def _weak_segments(day_type_daypart: dict[str, Any], hour_quality: dict[str, Any]) -> list[str]:
    weak: list[str] = []
    for name, segment in dict(day_type_daypart.get("combinations") or {}).items():
        if segment.get("status") != "sufficient_basis":
            continue
        accuracy = _number(segment.get("accuracy_percent"))
        if accuracy is not None and accuracy < 20.0:
            weak.append(f"day_type_daypart:{name}")
    for name, segment in dict(hour_quality.get("hours") or {}).items():
        if segment.get("status") != "sufficient_basis":
            continue
        accuracy = _number(segment.get("accuracy_percent"))
        if accuracy is not None and accuracy < 20.0:
            weak.append(f"hour:{name}")
    return sorted(weak)


def _horizon_summary(horizon_quality: dict[str, Any]) -> tuple[int, int, list[str]]:
    observing = 0
    sufficient = 0
    blockers: list[str] = []
    for name, horizon in dict(horizon_quality.get("horizons") or {}).items():
        status = horizon.get("status")
        if status in {"observing", "sufficient_basis"}:
            observing += 1
        if status == "sufficient_basis":
            sufficient += 1
            accuracy = _number(horizon.get("accuracy_percent"))
            bias = _number(horizon.get("bias_kwh"))
            if accuracy is None:
                blockers.append(f"horizon:{name}:missing_accuracy")
            elif accuracy < 25.0:
                blockers.append(f"horizon:{name}:accuracy_below_25")
            if bias is None:
                blockers.append(f"horizon:{name}:missing_bias")
            elif abs(bias) > 0.030:
                blockers.append(f"horizon:{name}:absolute_bias_above_0.03")
    return observing, sufficient, sorted(blockers)


def _gate_failures(
    gate: str,
    values: dict[str, float | None],
    *,
    horizon_blockers: list[str],
    weak_segments: list[str],
) -> list[str]:
    thresholds = READINESS_THRESHOLDS[gate]
    failures: list[str] = []
    for key, threshold in thresholds.items():
        if key.endswith("_min"):
            metric = key[:-4]
            failure = _failed_min(metric, values.get(metric), float(threshold))
            if failure:
                failures.append(failure)
        elif key.endswith("_max"):
            metric = key[:-4]
            failure = _failed_max(metric, values.get(metric), float(threshold))
            if failure:
                failures.append(failure)
    if gate == "strong":
        failures.extend(horizon_blockers)
        if weak_segments:
            failures.extend(f"weak_segment:{name}" for name in weak_segments)
    return sorted(set(failures))


def calculate_model_health_readiness(
    *,
    records: list[dict[str, Any]],
    profile: str,
    source_available: bool,
    forecast_coverage_percent: Any,
    average_confidence_percent: Any,
    evaluation_metrics: dict[str, Any],
    horizon_quality: dict[str, Any],
    day_type_daypart_quality: dict[str, Any],
    hour_quality: dict[str, Any],
    localize: Callable[[datetime], datetime],
) -> dict[str, Any]:
    """Return deterministic model readiness without conflating runtime source health."""
    if profile not in SUPPORTED_PROFILES:
        return {
            "model_health_contract_version": MODEL_HEALTH_CONTRACT_VERSION,
            "readiness_algorithm_version": READINESS_ALGORITHM_VERSION,
            "profile": profile,
            "readiness_status": "profile_unclassified",
            "runtime_input_status": "available" if source_available else "source_unavailable",
            "forecast_operational_input_ok": bool(source_available),
            "readiness_blockers": ["profile_unclassified"],
            "runtime_blockers": [] if source_available else ["source_unavailable"],
            "readiness_thresholds": READINESS_THRESHOLDS,
        }

    history_days, valid_quarters = _profile_history_basis(records, profile, localize)
    horizon_observing_count, horizon_sufficient_count, horizon_blockers = _horizon_summary(horizon_quality)
    weak_segments = _weak_segments(day_type_daypart_quality, hour_quality)

    accuracy = _number(evaluation_metrics.get("accuracy_percent"))
    mae = _number(evaluation_metrics.get("mae_kwh"))
    bias = _number(evaluation_metrics.get("bias_kwh"))
    evaluation_samples = _number(evaluation_metrics.get("samples"))
    coverage = _number(forecast_coverage_percent)
    confidence = _number(average_confidence_percent)
    values = {
        "history_days": float(history_days),
        "evaluation_samples": evaluation_samples,
        "forecast_coverage_percent": coverage,
        "average_confidence_percent": confidence,
        "accuracy_percent": accuracy,
        "mae_kwh": mae,
        "absolute_bias_kwh": abs(bias) if bias is not None else None,
        "horizon_observing_count": float(horizon_observing_count),
        "weak_segment_count": float(len(weak_segments)),
    }

    learning_failures = _gate_failures("learning", values, horizon_blockers=horizon_blockers, weak_segments=weak_segments)
    usable_failures = _gate_failures("usable", values, horizon_blockers=horizon_blockers, weak_segments=weak_segments)
    strong_failures = _gate_failures("strong", values, horizon_blockers=horizon_blockers, weak_segments=weak_segments)

    readiness = "collecting"
    blockers = learning_failures
    if not learning_failures:
        readiness = "learning"
        blockers = usable_failures
    if not learning_failures and not usable_failures:
        readiness = "usable"
        blockers = strong_failures
    if not learning_failures and not usable_failures and not strong_failures:
        readiness = "strong"
        blockers = []

    return {
        "model_health_contract_version": MODEL_HEALTH_CONTRACT_VERSION,
        "readiness_algorithm_version": READINESS_ALGORITHM_VERSION,
        "profile": profile,
        "model": "historical_baseline",
        "model_version": "0.4",
        "readiness_status": readiness,
        "history_days": history_days,
        "valid_quarters": valid_quarters,
        "forecast_coverage_percent": round(coverage, 1) if coverage is not None else None,
        "average_confidence_percent": round(confidence, 1) if confidence is not None else None,
        "evaluation_samples": int(evaluation_samples) if evaluation_samples is not None else None,
        "accuracy_percent": round(accuracy, 1) if accuracy is not None else None,
        "mae_kwh": round(mae, 6) if mae is not None else None,
        "bias_kwh": round(bias, 6) if bias is not None else None,
        "absolute_bias_kwh": round(abs(bias), 6) if bias is not None else None,
        "horizon_evidence_status": horizon_quality.get("status"),
        "horizon_observing_count": horizon_observing_count,
        "horizon_sufficient_count": horizon_sufficient_count,
        "weak_segment_count": len(weak_segments),
        "weak_segments": weak_segments,
        "runtime_input_status": "available" if source_available else "source_unavailable",
        "forecast_operational_input_ok": bool(source_available),
        "readiness_thresholds": READINESS_THRESHOLDS,
        "readiness_blockers": blockers,
        "runtime_blockers": [] if source_available else ["source_unavailable"],
    }
