"""Observer-only Step 12 forecast quality by horizon."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

SCHEMA_VERSION = 1
ALGORITHM_VERSION = "forecast_horizon_quality_observer_v1"
NATIVE_RESOLUTION_MINUTES = 15
FORECAST_HORIZON_HOURS = 72
FORECAST_SLOTS = 288

# (key, slot offset, start lead minutes, target semantics)
HORIZON_PROBES: tuple[tuple[str, int, int, str], ...] = (
    ("h00_control", 0, 0, "quarter_starts_at_capture"),
    ("h01", 4, 60, "target_start_plus_1h"),
    ("h03", 12, 180, "target_start_plus_3h"),
    ("h06", 24, 360, "target_start_plus_6h"),
    ("h12", 48, 720, "target_start_plus_12h"),
    ("h24", 96, 1440, "target_start_plus_24h"),
    ("h48", 192, 2880, "target_start_plus_48h"),
    ("h72_edge", 287, 4305, "last_native_slot_ends_plus_72h"),
)

MIN_OBSERVING_SAMPLES = 32
MIN_OBSERVING_DAYS = 8
MIN_SUFFICIENT_SAMPLES = 64
MIN_SUFFICIENT_DAYS = 14
EVALUATION_EPSILON_KWH = 0.01
SUPPORTED_PROFILES = {"normal", "away"}


def _empty_horizon(key: str, minutes: int, semantics: str) -> dict[str, Any]:
    return {
        "key": key,
        "horizon_minutes": minutes,
        "target_semantics": semantics,
        "status": "collecting",
        "sample_count": 0,
        "distinct_local_days": 0,
        "mae_kwh": None,
        "bias_kwh": None,
        "accuracy_percent": None,
        "mean_captured_confidence": None,
        "source_distribution": {},
        "excluded_record_counts": {},
    }


def calculate_horizon_quality(
    daily_stats: dict[str, dict[str, Any]],
    profile: str,
) -> dict[str, Any]:
    """Aggregate persisted Step 12 daily evidence for one profile."""
    horizons = {
        key: _empty_horizon(key, minutes, semantics)
        for key, _offset, minutes, semantics in HORIZON_PROBES
    }

    if profile not in SUPPORTED_PROFILES:
        return {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "status": "inactive_profile",
            "profile": profile,
            "observer_only": True,
            "forecast_influence_enabled": False,
            "native_resolution_minutes": NATIVE_RESOLUTION_MINUTES,
            "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
            "forecast_slots": FORECAST_SLOTS,
            "horizon_set_minutes": [probe[2] for probe in HORIZON_PROBES],
            "horizons": horizons,
        }

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for bucket in daily_stats.values():
        if bucket.get("profile") != profile:
            continue
        try:
            horizon_minutes = int(bucket["horizon_minutes"])
        except (KeyError, TypeError, ValueError):
            continue
        grouped[horizon_minutes].append(bucket)

    all_sufficient = True
    for key, _offset, minutes, semantics in HORIZON_PROBES:
        buckets = grouped.get(minutes, [])
        sample_count = sum(int(bucket.get("sample_count", 0) or 0) for bucket in buckets)
        distinct_days = len(
            {
                str(bucket.get("local_date"))
                for bucket in buckets
                if int(bucket.get("sample_count", 0) or 0) > 0
                and bucket.get("local_date")
            }
        )
        sum_abs_error = sum(float(bucket.get("sum_abs_error_kwh", 0.0) or 0.0) for bucket in buckets)
        sum_error = sum(float(bucket.get("sum_error_kwh", 0.0) or 0.0) for bucket in buckets)
        sum_actual = sum(float(bucket.get("sum_actual_kwh", 0.0) or 0.0) for bucket in buckets)
        sum_forecast = sum(float(bucket.get("sum_forecast_kwh", 0.0) or 0.0) for bucket in buckets)
        sum_confidence = sum(float(bucket.get("sum_confidence", 0.0) or 0.0) for bucket in buckets)

        source_counts: dict[str, int] = defaultdict(int)
        excluded: dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for source, count in dict(bucket.get("source_counts") or {}).items():
                source_counts[str(source)] += int(count or 0)
            for reason, count in dict(bucket.get("excluded_record_counts") or {}).items():
                excluded[str(reason)] += int(count or 0)

        if sample_count >= MIN_SUFFICIENT_SAMPLES and distinct_days >= MIN_SUFFICIENT_DAYS:
            status = "sufficient_basis"
        elif sample_count >= MIN_OBSERVING_SAMPLES and distinct_days >= MIN_OBSERVING_DAYS:
            status = "observing"
            all_sufficient = False
        else:
            status = "collecting"
            all_sufficient = False

        mae = round(sum_abs_error / sample_count, 6) if sample_count else None
        bias = round(sum_error / sample_count, 6) if sample_count else None
        accuracy = None
        if sample_count:
            denominator = max(sum_actual, EVALUATION_EPSILON_KWH)
            accuracy = round(max(0.0, 100.0 * (1.0 - sum_abs_error / denominator)), 1)
        mean_confidence = round(sum_confidence / sample_count, 3) if sample_count else None

        horizons[key] = {
            "key": key,
            "horizon_minutes": minutes,
            "target_semantics": semantics,
            "status": status,
            "sample_count": sample_count,
            "distinct_local_days": distinct_days,
            "mae_kwh": mae,
            "bias_kwh": bias,
            "accuracy_percent": accuracy,
            "actual_total_kwh": round(sum_actual, 6),
            "forecast_total_kwh": round(sum_forecast, 6),
            "mean_captured_confidence": mean_confidence,
            "source_distribution": dict(sorted(source_counts.items())),
            "excluded_record_counts": dict(sorted(excluded.items())),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "status": "sufficient_basis" if all_sufficient else "collecting",
        "profile": profile,
        "observer_only": True,
        "forecast_influence_enabled": False,
        "native_resolution_minutes": NATIVE_RESOLUTION_MINUTES,
        "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
        "forecast_slots": FORECAST_SLOTS,
        "horizon_set_minutes": [probe[2] for probe in HORIZON_PROBES],
        "minimum_samples_for_observing": MIN_OBSERVING_SAMPLES,
        "minimum_days_for_observing": MIN_OBSERVING_DAYS,
        "minimum_samples_for_sufficient_basis": MIN_SUFFICIENT_SAMPLES,
        "minimum_days_for_sufficient_basis": MIN_SUFFICIENT_DAYS,
        "horizons": horizons,
    }
