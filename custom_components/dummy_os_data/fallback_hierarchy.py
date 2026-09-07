"""Observer-only Step 10 fallback-hierarchy evaluation for Energy Forecast."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
from math import pow
from typing import Any, Callable

SCHEMA_VERSION = 1
ALGORITHM_VERSION = "fallback_hierarchy_observer_v1"
CONTROL_HALF_LIFE_DAYS = 28.0
NATIVE_RESOLUTION_MINUTES = 15
MIN_ACTUAL_COVERAGE = 0.90
SUPPORTED_PROFILES = {"normal", "away"}
PRODUCTION_MODEL = "historical_baseline"
PRODUCTION_MODEL_VERSION = "0.4"
CONTROL_REPRODUCTION_TOLERANCE_KWH = 0.000001

CONTROL_HIERARCHY: tuple[str, ...] = (
    "weekday_quarter",
    "day_type_quarter",
    "quarter_of_day",
    "profile_mean",
)
CANDIDATE_HIERARCHY: tuple[str, ...] = (
    "weekday_quarter",
    "day_type_quarter",
    "nearby_quarter_day_type",
    "same_hour_profile",
    "daypart_profile",
    "profile_global_median",
)
NEW_FALLBACK_LEVELS: tuple[str, ...] = CANDIDATE_HIERARCHY[2:]

MIN_OBSERVING_IMPACT_PAIRS = 32
MIN_OBSERVING_DISTINCT_DAYS = 8
MIN_SUPPORTED_IMPACT_PAIRS = 64
MIN_SUPPORTED_DISTINCT_DAYS = 14
MIN_LEVEL_SHADOW_SAMPLES = 32
MIN_SEGMENT_SAMPLES = 32
MIN_STABILITY_DISTINCT_DAYS = 28
MIN_IMPACT_MAE_GAIN_PCT = 5.0
MIN_PAIRED_WIN_RATE = 0.55
MAX_P90_DEGRADATION_PCT = 5.0
MAX_ABSOLUTE_BIAS_DEGRADATION_KWH = 0.005
MAX_TOTAL_MAE_DEGRADATION_PCT = 1.0
MAX_SEGMENT_MAE_DEGRADATION_PCT = 5.0

DAYPARTS: tuple[tuple[str, int, int], ...] = (
    ("night", 0, 6),
    ("morning", 6, 12),
    ("afternoon", 12, 18),
    ("evening", 18, 24),
)


def _parse_aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _quarter_index(local_dt: datetime) -> int:
    return local_dt.hour * 4 + local_dt.minute // NATIVE_RESOLUTION_MINUTES


def _day_type(local_dt: datetime) -> str:
    return "weekend" if local_dt.weekday() >= 5 else "weekday"


def _daypart(local_dt: datetime) -> str:
    for name, start_hour, end_hour in DAYPARTS:
        if start_hour <= local_dt.hour < end_hour:
            return name
    return "evening"


def _recency_weight(sample_start: datetime, reference: datetime) -> float:
    age_days = max(0.0, (reference - sample_start).total_seconds() / 86400.0)
    return pow(0.5, age_days / CONTROL_HALF_LIFE_DAYS)


def _weighted_mean(samples: list[tuple[datetime, float]], reference: datetime) -> float | None:
    if not samples:
        return None
    weighted_total = 0.0
    weight_total = 0.0
    for sample_start, energy in samples:
        weight = _recency_weight(sample_start, reference)
        weighted_total += energy * weight
        weight_total += weight
    if weight_total <= 0.0:
        return None
    return weighted_total / weight_total


def _weighted_median(samples: list[tuple[datetime, float]], reference: datetime) -> float | None:
    if not samples:
        return None
    weighted = [(float(energy), _recency_weight(sample_start, reference)) for sample_start, energy in samples]
    weighted = [(value, weight) for value, weight in weighted if weight > 0.0]
    if not weighted:
        return None
    weighted.sort(key=lambda item: item[0])
    total_weight = sum(weight for _, weight in weighted)
    threshold = total_weight / 2.0
    cumulative = 0.0
    for value, weight in weighted:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return weighted[-1][0]


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _history_before_capture(
    records: list[dict[str, Any]],
    *,
    profile: str,
    captured_at: datetime,
    localize: Callable[[datetime], datetime],
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for record in records:
        if record.get("valid") is not True or record.get("profile") != profile:
            continue
        start = _parse_aware(record.get("start"))
        end = _parse_aware(record.get("end"))
        if start is None or end is None or end > captured_at:
            continue
        try:
            energy = float(record["energy_kwh"])
        except (KeyError, TypeError, ValueError):
            continue
        local = localize(start)
        history.append(
            {
                "start": start,
                "end": end,
                "energy_kwh": energy,
                "local": local,
                "qidx": _quarter_index(local),
                "day_type": _day_type(local),
                "daypart": _daypart(local),
            }
        )
    history.sort(key=lambda row: row["start"])
    return history


def _samples(rows: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    return [(row["start"], row["energy_kwh"]) for row in rows]


def _level_samples(
    history: list[dict[str, Any]],
    *,
    target_start: datetime,
    level: str,
    localize: Callable[[datetime], datetime],
) -> list[tuple[datetime, float]]:
    target_local = localize(target_start)
    target_qidx = _quarter_index(target_local)
    target_day_type = _day_type(target_local)
    target_daypart = _daypart(target_local)

    if level == "weekday_quarter":
        return _samples([
            row for row in history
            if row["local"].weekday() == target_local.weekday() and row["qidx"] == target_qidx
        ])
    if level == "day_type_quarter":
        return _samples([
            row for row in history
            if row["day_type"] == target_day_type and row["qidx"] == target_qidx
        ])
    if level == "quarter_of_day":
        return _samples([row for row in history if row["qidx"] == target_qidx])
    if level == "profile_mean" or level == "profile_global_median":
        return _samples(history)
    if level == "same_hour_profile":
        return _samples([row for row in history if row["local"].hour == target_local.hour])
    if level == "daypart_profile":
        return _samples([row for row in history if row["daypart"] == target_daypart])
    if level == "nearby_quarter_day_type":
        for distance in (1, 2):
            wanted = {target_qidx - distance, target_qidx + distance}
            wanted = {qidx for qidx in wanted if 0 <= qidx < 96}
            if not wanted:
                continue
            selected = [
                row for row in history
                if row["day_type"] == target_day_type and row["qidx"] in wanted
            ]
            if selected:
                return _samples(selected)
        return []
    raise ValueError(f"Unsupported fallback level: {level}")


def _level_forecast(
    history: list[dict[str, Any]],
    *,
    target_start: datetime,
    captured_at: datetime,
    level: str,
    localize: Callable[[datetime], datetime],
) -> tuple[float | None, int]:
    samples = _level_samples(history, target_start=target_start, level=level, localize=localize)
    if level == "profile_global_median":
        value = _weighted_median(samples, captured_at)
    else:
        value = _weighted_mean(samples, captured_at)
    return value, len(samples)


def _hierarchy_forecast(
    history: list[dict[str, Any]],
    *,
    target_start: datetime,
    captured_at: datetime,
    hierarchy: tuple[str, ...],
    localize: Callable[[datetime], datetime],
) -> tuple[str, float | None, int]:
    for level in hierarchy:
        value, sample_count = _level_forecast(
            history,
            target_start=target_start,
            captured_at=captured_at,
            level=level,
            localize=localize,
        )
        if value is not None:
            return level, value, sample_count
    return "unavailable", None, 0


def _metrics(rows: list[dict[str, Any]], forecast_key: str, localize) -> dict[str, Any]:
    usable = [row for row in rows if row.get(forecast_key) is not None]
    result = {
        "sample_count": len(usable),
        "distinct_local_days": len({localize(row["target_start"]).date().isoformat() for row in usable}),
        "mae_kwh": None,
        "bias_kwh": None,
        "absolute_bias_kwh": None,
        "median_absolute_error_kwh": None,
        "p90_absolute_error_kwh": None,
    }
    if not usable:
        return result
    signed = [float(row[forecast_key]) - row["actual_kwh"] for row in usable]
    absolute = [abs(value) for value in signed]
    bias = sum(signed) / len(signed)
    result.update(
        {
            "mae_kwh": round(sum(absolute) / len(absolute), 6),
            "bias_kwh": round(bias, 6),
            "absolute_bias_kwh": round(abs(bias), 6),
            "median_absolute_error_kwh": round(_quantile(absolute, 0.5), 6),
            "p90_absolute_error_kwh": round(_quantile(absolute, 0.9), 6),
        }
    )
    return result


def _improvement_pct(control: float | None, candidate: float | None) -> float | None:
    if control is None or candidate is None:
        return None
    if control == 0:
        return 0.0 if candidate == 0 else None
    return round((control - candidate) / control * 100.0, 3)


def _paired_win_rate(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    wins = 0
    for row in rows:
        control_error = abs(row["control_forecast_kwh"] - row["actual_kwh"])
        candidate_error = abs(row["candidate_forecast_kwh"] - row["actual_kwh"])
        if candidate_error < control_error:
            wins += 1
    return round(wins / len(rows), 3)


def _per_level_metrics(level_rows: dict[str, list[dict[str, Any]]], localize) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for level in CANDIDATE_HIERARCHY[1:]:
        rows = level_rows.get(level, [])
        metrics = _metrics(rows, "level_forecast_kwh", localize)
        result[level] = {
            **metrics,
            "activation_count": sum(1 for row in rows if row.get("candidate_source") == level),
        }
    return result


def _segment_metrics(rows: list[dict[str, Any]], localize) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        local = localize(row["target_start"])
        grouped[f"{_day_type(local)}_{_daypart(local)}"].append(row)
    result: dict[str, Any] = {}
    for key in sorted(grouped):
        segment_rows = grouped[key]
        control = _metrics(segment_rows, "control_forecast_kwh", localize)
        candidate = _metrics(segment_rows, "candidate_forecast_kwh", localize)
        control_mae = control["mae_kwh"]
        candidate_mae = candidate["mae_kwh"]
        degradation = None
        if control_mae is not None and candidate_mae is not None:
            if control_mae > 0:
                degradation = round((candidate_mae - control_mae) / control_mae * 100.0, 3)
            elif candidate_mae == 0:
                degradation = 0.0
        guard = None
        if len(segment_rows) >= MIN_SEGMENT_SAMPLES:
            guard = degradation is not None and degradation <= MAX_SEGMENT_MAE_DEGRADATION_PCT
        result[key] = {
            "sample_count": len(segment_rows),
            "control_mae_kwh": control_mae,
            "candidate_mae_kwh": candidate_mae,
            "mae_degradation_pct": degradation,
            "regression_guard_passed": guard,
        }
    return result


def _early_late_metrics(rows: list[dict[str, Any]], localize) -> dict[str, Any]:
    distinct_days = len({localize(row["target_start"]).date().isoformat() for row in rows})
    if distinct_days < MIN_STABILITY_DISTINCT_DAYS or len(rows) < 2:
        return {
            "required": False,
            "distinct_local_days": distinct_days,
            "early_count": 0,
            "late_count": 0,
            "early_mae_improvement_pct": None,
            "late_mae_improvement_pct": None,
            "stable_direction": None,
        }
    ordered = sorted(rows, key=lambda row: row["target_start"])
    split = len(ordered) // 2
    early = ordered[:split]
    late = ordered[split:]
    early_control = _metrics(early, "control_forecast_kwh", localize)
    early_candidate = _metrics(early, "candidate_forecast_kwh", localize)
    late_control = _metrics(late, "control_forecast_kwh", localize)
    late_candidate = _metrics(late, "candidate_forecast_kwh", localize)
    early_gain = _improvement_pct(early_control["mae_kwh"], early_candidate["mae_kwh"])
    late_gain = _improvement_pct(late_control["mae_kwh"], late_candidate["mae_kwh"])
    stable = None
    if early_gain is not None and late_gain is not None:
        stable = (early_gain >= 0 and late_gain >= 0) or (early_gain < 0 and late_gain < 0)
    return {
        "required": True,
        "distinct_local_days": distinct_days,
        "early_count": len(early),
        "late_count": len(late),
        "early_mae_improvement_pct": early_gain,
        "late_mae_improvement_pct": late_gain,
        "stable_direction": stable,
    }


def _fingerprint(profile: str, evaluation_ids: list[dict[str, Any]]) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "profile": profile,
        "control_hierarchy": CONTROL_HIERARCHY,
        "candidate_hierarchy": CANDIDATE_HIERARCHY,
        "production_model": PRODUCTION_MODEL,
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "control_recency_half_life_days": CONTROL_HALF_LIFE_DAYS,
        "thresholds": {
            "min_observing_impact_pairs": MIN_OBSERVING_IMPACT_PAIRS,
            "min_observing_distinct_days": MIN_OBSERVING_DISTINCT_DAYS,
            "min_supported_impact_pairs": MIN_SUPPORTED_IMPACT_PAIRS,
            "min_supported_distinct_days": MIN_SUPPORTED_DISTINCT_DAYS,
            "min_level_shadow_samples": MIN_LEVEL_SHADOW_SAMPLES,
            "min_segment_samples": MIN_SEGMENT_SAMPLES,
            "min_stability_distinct_days": MIN_STABILITY_DISTINCT_DAYS,
            "min_impact_mae_gain_pct": MIN_IMPACT_MAE_GAIN_PCT,
            "min_paired_win_rate": MIN_PAIRED_WIN_RATE,
            "max_p90_degradation_pct": MAX_P90_DEGRADATION_PCT,
            "max_absolute_bias_degradation_kwh": MAX_ABSOLUTE_BIAS_DEGRADATION_KWH,
            "max_total_mae_degradation_pct": MAX_TOTAL_MAE_DEGRADATION_PCT,
            "max_segment_mae_degradation_pct": MAX_SEGMENT_MAE_DEGRADATION_PCT,
        },
        "evaluation_ids": sorted(
            evaluation_ids,
            key=lambda item: (
                item.get("start") or "",
                item.get("forecast_captured_at") or "",
                item.get("source") or "",
            ),
        ),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return f"fh_{digest}"


def calculate_fallback_hierarchy(
    records: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    profile: str,
    localize: Callable[[datetime], datetime],
) -> dict[str, Any]:
    """Evaluate the Step 10 candidate hierarchy without production influence."""
    if profile not in SUPPORTED_PROFILES:
        return {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "status": "blocked",
            "profile": profile,
            "observer_only": True,
            "forecast_influence_enabled": False,
            "production_model": PRODUCTION_MODEL,
            "production_model_version": PRODUCTION_MODEL_VERSION,
            "control_recency_half_life_days": CONTROL_HALF_LIFE_DAYS,
            "control_hierarchy": list(CONTROL_HIERARCHY),
            "candidate_hierarchy": list(CANDIDATE_HIERARCHY),
            "evaluation_count": 0,
            "distinct_local_days": 0,
            "eligible_level_shadow_count": 0,
            "hierarchy_changed_selection_count": 0,
            "fallback_activation_counts": {},
            "excluded_record_counts": {"invalid_profile": 1},
            "control_metrics": _metrics([], "control_forecast_kwh", localize),
            "candidate_metrics": _metrics([], "candidate_forecast_kwh", localize),
            "hierarchy_impact_control_metrics": _metrics([], "control_forecast_kwh", localize),
            "hierarchy_impact_candidate_metrics": _metrics([], "candidate_forecast_kwh", localize),
            "per_level_metrics": {},
            "day_type_daypart_metrics": {},
            "early_late_metrics": _early_late_metrics([], localize),
            "preferred_candidate_hierarchy": list(CANDIDATE_HIERARCHY),
            "replay_candidate_supported": False,
            "promotion_ready": False,
            "live_shadow_required": True,
            "blockers": ["invalid_profile"],
            "promotion_blockers": ["invalid_profile", "live_shadow_required"],
            "calibration_fingerprint": _fingerprint(profile, []),
        }

    excluded: dict[str, int] = defaultdict(int)
    paired_rows: list[dict[str, Any]] = []
    level_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    activation_counts: dict[str, int] = defaultdict(int)
    evaluation_ids: list[dict[str, Any]] = []
    reproduction_deltas: list[float] = []

    for item in evaluations:
        if item.get("profile") != profile:
            continue
        if item.get("model") != PRODUCTION_MODEL or str(item.get("model_version")) != PRODUCTION_MODEL_VERSION:
            excluded["unsupported_model"] += 1
            continue
        target_start = _parse_aware(item.get("start"))
        target_end = _parse_aware(item.get("end"))
        captured_at = _parse_aware(item.get("forecast_captured_at"))
        if target_start is None or target_end is None or captured_at is None:
            excluded["invalid_time_contract"] += 1
            continue
        if captured_at > target_start:
            excluded["late_capture"] += 1
            continue
        try:
            actual = float(item["actual_kwh"])
            control_stored = float(item["forecast_kwh"])
            coverage = float(item["actual_coverage"])
        except (KeyError, TypeError, ValueError):
            excluded["non_numeric_evaluation"] += 1
            continue
        if coverage < MIN_ACTUAL_COVERAGE:
            excluded["invalid_actual_coverage"] += 1
            continue

        history = _history_before_capture(
            records,
            profile=profile,
            captured_at=captured_at,
            localize=localize,
        )
        control_source_replay, control_replay, _ = _hierarchy_forecast(
            history,
            target_start=target_start,
            captured_at=captured_at,
            hierarchy=CONTROL_HIERARCHY,
            localize=localize,
        )
        if control_replay is None:
            excluded["control_replay_unavailable"] += 1
            continue
        delta = abs(round(control_replay, 6) - round(control_stored, 6))
        reproduction_deltas.append(delta)
        if delta > CONTROL_REPRODUCTION_TOLERANCE_KWH:
            excluded["control_replay_mismatch"] += 1
            continue

        candidate_source, candidate_value, candidate_samples = _hierarchy_forecast(
            history,
            target_start=target_start,
            captured_at=captured_at,
            hierarchy=CANDIDATE_HIERARCHY,
            localize=localize,
        )
        if candidate_value is None:
            excluded["candidate_unavailable"] += 1
            continue

        row = {
            "target_start": target_start,
            "target_end": target_end,
            "captured_at": captured_at,
            "actual_kwh": actual,
            "control_source": str(item.get("source") or control_source_replay),
            "control_replay_source": control_source_replay,
            "control_forecast_kwh": control_stored,
            "candidate_source": candidate_source,
            "candidate_forecast_kwh": candidate_value,
            "candidate_sample_count": candidate_samples,
        }
        paired_rows.append(row)
        activation_counts[candidate_source] += 1
        evaluation_ids.append(
            {
                "start": item.get("start"),
                "forecast_captured_at": item.get("forecast_captured_at"),
                "source": item.get("source"),
            }
        )

        for level in CANDIDATE_HIERARCHY[1:]:
            level_value, level_sample_count = _level_forecast(
                history,
                target_start=target_start,
                captured_at=captured_at,
                level=level,
                localize=localize,
            )
            if level_value is None:
                continue
            level_rows[level].append(
                {
                    "target_start": target_start,
                    "actual_kwh": actual,
                    "level_forecast_kwh": level_value,
                    "level_sample_count": level_sample_count,
                    "candidate_source": candidate_source,
                }
            )

    impact_rows = [
        row for row in paired_rows
        if row["candidate_source"] != row["control_source"]
        or abs(round(row["candidate_forecast_kwh"], 6) - round(row["control_forecast_kwh"], 6)) > CONTROL_REPRODUCTION_TOLERANCE_KWH
    ]

    control_metrics = _metrics(paired_rows, "control_forecast_kwh", localize)
    candidate_metrics = _metrics(paired_rows, "candidate_forecast_kwh", localize)
    impact_control_metrics = _metrics(impact_rows, "control_forecast_kwh", localize)
    impact_candidate_metrics = _metrics(impact_rows, "candidate_forecast_kwh", localize)
    per_level = _per_level_metrics(level_rows, localize)
    segments = _segment_metrics(impact_rows, localize)
    early_late = _early_late_metrics(impact_rows, localize)

    impact_count = len(impact_rows)
    impact_days = len({localize(row["target_start"]).date().isoformat() for row in impact_rows})
    eligible_level_shadow_count = sum(len(level_rows[level]) for level in NEW_FALLBACK_LEVELS)
    impact_gain = _improvement_pct(impact_control_metrics["mae_kwh"], impact_candidate_metrics["mae_kwh"])
    win_rate = _paired_win_rate(impact_rows)

    blockers: list[str] = []
    if impact_count < MIN_OBSERVING_IMPACT_PAIRS:
        blockers.append("insufficient_forward_samples")
    if impact_days < MIN_OBSERVING_DISTINCT_DAYS:
        blockers.append("insufficient_distinct_days")
    if impact_count == 0:
        blockers.append("fallback_not_activated")

    supported_basis = impact_count >= MIN_SUPPORTED_IMPACT_PAIRS and impact_days >= MIN_SUPPORTED_DISTINCT_DAYS
    evidence_blockers: list[str] = []
    relevant_levels = [level for level in NEW_FALLBACK_LEVELS if activation_counts.get(level, 0) > 0]
    for level in relevant_levels:
        if per_level.get(level, {}).get("sample_count", 0) < MIN_LEVEL_SHADOW_SAMPLES:
            evidence_blockers.append(f"insufficient_level_shadow:{level}")

    if supported_basis:
        if impact_gain is None or impact_gain < MIN_IMPACT_MAE_GAIN_PCT:
            evidence_blockers.append("candidate_mae_not_better")
        if win_rate is None or win_rate < MIN_PAIRED_WIN_RATE:
            evidence_blockers.append("paired_win_rate_insufficient")
        control_median = impact_control_metrics["median_absolute_error_kwh"]
        candidate_median = impact_candidate_metrics["median_absolute_error_kwh"]
        if control_median is None or candidate_median is None or candidate_median > control_median:
            evidence_blockers.append("median_error_regression")
        control_p90 = impact_control_metrics["p90_absolute_error_kwh"]
        candidate_p90 = impact_candidate_metrics["p90_absolute_error_kwh"]
        if control_p90 is None or candidate_p90 is None:
            evidence_blockers.append("tail_evidence_missing")
        elif control_p90 > 0 and candidate_p90 > control_p90 * (1.0 + MAX_P90_DEGRADATION_PCT / 100.0):
            evidence_blockers.append("tail_regression")
        elif control_p90 == 0 and candidate_p90 > 0:
            evidence_blockers.append("tail_regression")
        control_abs_bias = impact_control_metrics["absolute_bias_kwh"]
        candidate_abs_bias = impact_candidate_metrics["absolute_bias_kwh"]
        if control_abs_bias is None or candidate_abs_bias is None:
            evidence_blockers.append("bias_evidence_missing")
        elif candidate_abs_bias - control_abs_bias > MAX_ABSOLUTE_BIAS_DEGRADATION_KWH:
            evidence_blockers.append("bias_regression")
        total_control_mae = control_metrics["mae_kwh"]
        total_candidate_mae = candidate_metrics["mae_kwh"]
        if total_control_mae is None or total_candidate_mae is None:
            evidence_blockers.append("overall_evidence_missing")
        elif total_control_mae > 0 and total_candidate_mae > total_control_mae * (1.0 + MAX_TOTAL_MAE_DEGRADATION_PCT / 100.0):
            evidence_blockers.append("overall_regression")
        elif total_control_mae == 0 and total_candidate_mae > 0:
            evidence_blockers.append("overall_regression")
        if any(
            segment["regression_guard_passed"] is False
            for segment in segments.values()
            if segment["sample_count"] >= MIN_SEGMENT_SAMPLES
        ):
            evidence_blockers.append("segment_regression")
        if early_late["required"] and early_late["stable_direction"] is False:
            evidence_blockers.append("unstable_fallback_preference")

    all_blockers = blockers + evidence_blockers
    replay_supported = supported_basis and not evidence_blockers

    if impact_count < MIN_OBSERVING_IMPACT_PAIRS or impact_days < MIN_OBSERVING_DISTINCT_DAYS:
        status = "collecting"
    elif not supported_basis:
        status = "observing"
    elif replay_supported:
        status = "candidate_supported"
    else:
        status = "no_proven_improvement"

    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "status": status,
        "profile": profile,
        "observer_only": True,
        "forecast_influence_enabled": False,
        "native_resolution_minutes": NATIVE_RESOLUTION_MINUTES,
        "production_model": PRODUCTION_MODEL,
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "control_recency_half_life_days": CONTROL_HALF_LIFE_DAYS,
        "control_hierarchy": list(CONTROL_HIERARCHY),
        "candidate_hierarchy": list(CANDIDATE_HIERARCHY),
        "evaluation_count": len(paired_rows),
        "distinct_local_days": control_metrics["distinct_local_days"],
        "eligible_level_shadow_count": eligible_level_shadow_count,
        "hierarchy_changed_selection_count": impact_count,
        "hierarchy_changed_distinct_local_days": impact_days,
        "fallback_activation_counts": dict(sorted(activation_counts.items())),
        "excluded_record_counts": dict(sorted(excluded.items())),
        "control_reproduction_checked_count": len(reproduction_deltas),
        "control_reproduction_ok": not reproduction_deltas or max(reproduction_deltas) <= CONTROL_REPRODUCTION_TOLERANCE_KWH,
        "control_reproduction_max_delta_kwh": round(max(reproduction_deltas), 6) if reproduction_deltas else None,
        "control_metrics": control_metrics,
        "candidate_metrics": candidate_metrics,
        "hierarchy_impact_control_metrics": impact_control_metrics,
        "hierarchy_impact_candidate_metrics": impact_candidate_metrics,
        "hierarchy_impact_mae_improvement_pct": impact_gain,
        "hierarchy_impact_paired_win_rate": win_rate,
        "per_level_metrics": per_level,
        "day_type_daypart_metrics": segments,
        "early_late_metrics": early_late,
        "preferred_candidate_hierarchy": list(CANDIDATE_HIERARCHY),
        "replay_candidate_supported": replay_supported,
        "promotion_ready": False,
        "live_shadow_required": True,
        "blockers": all_blockers,
        "promotion_blockers": (["live_shadow_required"] if replay_supported else all_blockers + ["live_shadow_required"]),
        "thresholds": {
            "minimum_observing_impact_pairs": MIN_OBSERVING_IMPACT_PAIRS,
            "minimum_observing_distinct_days": MIN_OBSERVING_DISTINCT_DAYS,
            "minimum_supported_impact_pairs": MIN_SUPPORTED_IMPACT_PAIRS,
            "minimum_supported_distinct_days": MIN_SUPPORTED_DISTINCT_DAYS,
            "minimum_level_shadow_samples": MIN_LEVEL_SHADOW_SAMPLES,
            "minimum_segment_samples": MIN_SEGMENT_SAMPLES,
            "minimum_stability_distinct_days": MIN_STABILITY_DISTINCT_DAYS,
            "minimum_impact_mae_gain_pct": MIN_IMPACT_MAE_GAIN_PCT,
            "minimum_paired_win_rate": MIN_PAIRED_WIN_RATE,
            "maximum_p90_degradation_pct": MAX_P90_DEGRADATION_PCT,
            "maximum_absolute_bias_degradation_kwh": MAX_ABSOLUTE_BIAS_DEGRADATION_KWH,
            "maximum_total_mae_degradation_pct": MAX_TOTAL_MAE_DEGRADATION_PCT,
            "maximum_segment_mae_degradation_pct": MAX_SEGMENT_MAE_DEGRADATION_PCT,
        },
        "calibration_fingerprint": _fingerprint(profile, evaluation_ids),
    }
