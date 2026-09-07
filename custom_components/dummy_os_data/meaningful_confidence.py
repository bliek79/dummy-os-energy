"""Observer-only Step 11 meaningful-confidence evaluation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
from math import pow, sqrt
from typing import Any, Callable

SCHEMA_VERSION = 1
ALGORITHM_VERSION = "meaningful_confidence_observer_v1"
SUPPORTED_PROFILES = {"normal", "away"}
PRODUCTION_MODEL = "historical_baseline"
PRODUCTION_MODEL_VERSION = "0.4"
HALF_LIFE_DAYS = 28.0
MIN_ACTUAL_COVERAGE = 0.90
MIN_OBSERVING_EVALUATIONS = 32
MIN_OBSERVING_DAYS = 8
MIN_SUPPORTED_EVALUATIONS = 64
MIN_SUPPORTED_DAYS = 14
MIN_BUCKET_SAMPLES = 12

SOURCE_DEPTH_FACTOR = {
    "weekday_quarter": 1.00,
    "day_type_quarter": 0.88,
    "quarter_of_day": 0.68,
    "profile_mean": 0.48,
}


def _parse_aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _quarter_index(local_dt: datetime) -> int:
    return local_dt.hour * 4 + local_dt.minute // 15


def _day_type(local_dt: datetime) -> str:
    return "weekend" if local_dt.weekday() >= 5 else "weekday"


def _weight(sample_start: datetime, reference: datetime) -> float:
    age_days = max(0.0, (reference - sample_start).total_seconds() / 86400.0)
    return pow(0.5, age_days / HALF_LIFE_DAYS)


def _history_before_capture(
    records: list[dict[str, Any]],
    *,
    profile: str,
    captured_at: datetime,
    target_start: datetime,
    source: str,
    localize: Callable[[datetime], datetime],
) -> list[tuple[datetime, float, float]]:
    target_local = localize(target_start)
    target_qidx = _quarter_index(target_local)
    target_day_type = _day_type(target_local)
    rows: list[tuple[datetime, float, float]] = []
    for record in records:
        if record.get("valid") is not True or record.get("profile") != profile:
            continue
        start = _parse_aware(record.get("start"))
        end = _parse_aware(record.get("end"))
        if start is None or end is None or end > captured_at:
            continue
        try:
            energy = float(record["energy_kwh"])
            coverage = float(record.get("coverage", 1.0))
        except (KeyError, TypeError, ValueError):
            continue
        local = localize(start)
        qidx = _quarter_index(local)
        if source == "weekday_quarter":
            include = local.weekday() == target_local.weekday() and qidx == target_qidx
        elif source == "day_type_quarter":
            include = _day_type(local) == target_day_type and qidx == target_qidx
        elif source == "quarter_of_day":
            include = qidx == target_qidx
        elif source == "profile_mean":
            include = True
        else:
            include = False
        if include:
            rows.append((start, energy, max(0.0, min(1.0, coverage))))
    return rows


def _weighted_mean(values: list[tuple[float, float]]) -> float | None:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in values) / total_weight


def _effective_sample_size(weights: list[float]) -> float:
    if not weights:
        return 0.0
    total = sum(weights)
    squares = sum(weight * weight for weight in weights)
    if squares <= 0:
        return 0.0
    return total * total / squares


def _historical_components(
    samples: list[tuple[datetime, float, float]],
    *,
    captured_at: datetime,
) -> dict[str, float]:
    if not samples:
        return {
            "effective_sample_size": 0.0,
            "support_factor": 0.0,
            "stability_factor": 0.0,
            "coverage_factor": 0.0,
        }
    weighted = [(_weight(start, captured_at), value, coverage) for start, value, coverage in samples]
    weights = [row[0] for row in weighted]
    ess = _effective_sample_size(weights)
    support_factor = min(1.0, sqrt(ess / 5.0)) if ess > 0 else 0.0
    mean = _weighted_mean([(value, weight) for weight, value, _ in weighted]) or 0.0
    variance = _weighted_mean([((value - mean) ** 2, weight) for weight, value, _ in weighted]) or 0.0
    stddev = sqrt(max(0.0, variance))
    scale = max(abs(mean), 0.03)
    cv = stddev / scale
    stability_factor = max(0.05, 1.0 / (1.0 + cv))
    coverage = _weighted_mean([(coverage, weight) for weight, _, coverage in weighted]) or 0.0
    return {
        "effective_sample_size": round(ess, 3),
        "support_factor": round(support_factor, 4),
        "stability_factor": round(stability_factor, 4),
        "coverage_factor": round(max(0.0, min(1.0, coverage)), 4),
    }


def _recent_error_factor(
    evaluations: list[dict[str, Any]],
    *,
    profile: str,
    captured_at: datetime,
    source: str,
) -> tuple[float, int]:
    prior: list[tuple[datetime, float, float]] = []
    for item in evaluations:
        if item.get("profile") != profile or item.get("source") != source:
            continue
        start = _parse_aware(item.get("start"))
        if start is None or start >= captured_at:
            continue
        try:
            absolute_error = abs(float(item["absolute_error_kwh"]))
            actual = abs(float(item["actual_kwh"]))
        except (KeyError, TypeError, ValueError):
            continue
        prior.append((start, absolute_error, actual))
    prior.sort(key=lambda row: row[0], reverse=True)
    prior = prior[:32]
    if len(prior) < 4:
        return 0.70, len(prior)
    mae = sum(row[1] for row in prior) / len(prior)
    typical = sum(row[2] for row in prior) / len(prior)
    normalized = mae / max(typical, 0.03)
    return round(max(0.05, 1.0 / (1.0 + normalized)), 4), len(prior)


def _candidate_confidence(
    *,
    source: str,
    components: dict[str, float],
    recent_error_factor: float,
) -> float:
    depth = SOURCE_DEPTH_FACTOR.get(source, 0.35)
    score = (
        0.10
        + 0.26 * components["support_factor"]
        + 0.28 * components["stability_factor"]
        + 0.16 * components["coverage_factor"]
        + 0.20 * recent_error_factor
    ) * depth
    return round(max(0.02, min(0.98, score)), 3)


def _bucket(confidence: float) -> str:
    low = int(max(0, min(9, confidence * 10))) * 10
    return f"{low:02d}-{low + 10:02d}"


def _bucket_metrics(rows: list[dict[str, Any]], confidence_key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_bucket(float(row[confidence_key]))].append(row)
    result: dict[str, Any] = {}
    for key in sorted(groups):
        group = groups[key]
        errors = [float(row["absolute_error_kwh"]) for row in group]
        result[key] = {
            "sample_count": len(group),
            "mean_confidence": round(sum(float(row[confidence_key]) for row in group) / len(group), 3),
            "mae_kwh": round(sum(errors) / len(errors), 6),
        }
    return result


def _separation(rows: list[dict[str, Any]], confidence_key: str) -> dict[str, Any]:
    if len(rows) < 8:
        return {"high_count": 0, "low_count": 0, "high_mae_kwh": None, "low_mae_kwh": None, "higher_confidence_has_lower_error": None}
    ordered = sorted(rows, key=lambda row: float(row[confidence_key]))
    width = max(1, len(ordered) // 4)
    low = ordered[:width]
    high = ordered[-width:]
    low_mae = sum(float(row["absolute_error_kwh"]) for row in low) / len(low)
    high_mae = sum(float(row["absolute_error_kwh"]) for row in high) / len(high)
    return {
        "high_count": len(high),
        "low_count": len(low),
        "high_mae_kwh": round(high_mae, 6),
        "low_mae_kwh": round(low_mae, 6),
        "higher_confidence_has_lower_error": high_mae < low_mae,
    }


def _fingerprint(profile: str, rows: list[dict[str, Any]]) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "profile": profile,
        "rows": [(row["start"], row["candidate_confidence"]) for row in rows],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return f"mc_{digest}"


def calculate_meaningful_confidence(
    records: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    profile: str,
    localize: Callable[[datetime], datetime],
) -> dict[str, Any]:
    """Evaluate candidate confidence against frozen forward-looking evaluations."""
    if profile not in SUPPORTED_PROFILES:
        return {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "status": "inactive_profile",
            "profile": profile,
            "observer_only": True,
            "forecast_influence_enabled": False,
            "production_confidence_unchanged": True,
            "evaluation_count": 0,
            "distinct_local_days": 0,
            "production_buckets": {},
            "candidate_buckets": {},
            "production_separation": _separation([], "production_confidence"),
            "candidate_separation": _separation([], "candidate_confidence"),
            "candidate_supported": False,
            "promotion_ready": False,
            "live_shadow_required": True,
            "blockers": ["profile_unclassified"],
            "calibration_fingerprint": _fingerprint(profile, []),
        }

    rows: list[dict[str, Any]] = []
    excluded: dict[str, int] = defaultdict(int)
    component_totals: dict[str, float] = defaultdict(float)
    source_counts: dict[str, int] = defaultdict(int)

    for item in evaluations:
        if item.get("profile") != profile:
            continue
        if item.get("model") != PRODUCTION_MODEL or str(item.get("model_version")) != PRODUCTION_MODEL_VERSION:
            excluded["unsupported_model"] += 1
            continue
        start = _parse_aware(item.get("start"))
        captured_at = _parse_aware(item.get("forecast_captured_at"))
        if start is None or captured_at is None or captured_at > start:
            excluded["invalid_or_late_capture"] += 1
            continue
        try:
            actual_coverage = float(item["actual_coverage"])
            absolute_error = abs(float(item["absolute_error_kwh"]))
            production_confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError):
            excluded["non_numeric_evaluation"] += 1
            continue
        if actual_coverage < MIN_ACTUAL_COVERAGE:
            excluded["invalid_actual_coverage"] += 1
            continue
        source = str(item.get("source") or "")
        if source not in SOURCE_DEPTH_FACTOR:
            excluded["unsupported_source"] += 1
            continue

        samples = _history_before_capture(
            records,
            profile=profile,
            captured_at=captured_at,
            target_start=start,
            source=source,
            localize=localize,
        )
        components = _historical_components(samples, captured_at=captured_at)
        recent_error_factor, recent_error_samples = _recent_error_factor(
            evaluations,
            profile=profile,
            captured_at=captured_at,
            source=source,
        )
        candidate = _candidate_confidence(
            source=source,
            components=components,
            recent_error_factor=recent_error_factor,
        )
        row = {
            "start": start.isoformat(),
            "absolute_error_kwh": absolute_error,
            "production_confidence": max(0.0, min(1.0, production_confidence)),
            "candidate_confidence": candidate,
            "source": source,
            "recent_error_samples": recent_error_samples,
            **components,
            "recent_error_factor": recent_error_factor,
        }
        rows.append(row)
        source_counts[source] += 1
        for key in ("effective_sample_size", "support_factor", "stability_factor", "coverage_factor", "recent_error_factor"):
            component_totals[key] += float(row[key])

    distinct_days = len({localize(_parse_aware(row["start"])).date().isoformat() for row in rows if _parse_aware(row["start"]) is not None})
    production_sep = _separation(rows, "production_confidence")
    candidate_sep = _separation(rows, "candidate_confidence")
    enough_observing = len(rows) >= MIN_OBSERVING_EVALUATIONS and distinct_days >= MIN_OBSERVING_DAYS
    enough_supported = len(rows) >= MIN_SUPPORTED_EVALUATIONS and distinct_days >= MIN_SUPPORTED_DAYS
    candidate_supported = bool(
        enough_supported
        and candidate_sep["higher_confidence_has_lower_error"] is True
    )
    blockers: list[str] = []
    if not enough_observing:
        blockers.append("insufficient_evidence")
    elif not enough_supported:
        blockers.append("observing_only")
    if enough_supported and candidate_sep["higher_confidence_has_lower_error"] is not True:
        blockers.append("confidence_not_error_separating")

    status = "collecting"
    if enough_observing:
        status = "observing"
    if candidate_supported:
        status = "candidate_supported"

    averages = {
        key: round(total / len(rows), 4) if rows else None
        for key, total in component_totals.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "status": status,
        "profile": profile,
        "observer_only": True,
        "forecast_influence_enabled": False,
        "production_confidence_unchanged": True,
        "production_model": PRODUCTION_MODEL,
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "native_resolution_minutes": 15,
        "confidence_components": ["recency_effective_sample_size", "historical_stability", "historical_coverage", "fallback_depth", "recent_forward_error"],
        "evaluation_count": len(rows),
        "distinct_local_days": distinct_days,
        "excluded_record_counts": dict(excluded),
        "source_counts": dict(source_counts),
        "component_averages": averages,
        "production_buckets": _bucket_metrics(rows, "production_confidence"),
        "candidate_buckets": _bucket_metrics(rows, "candidate_confidence"),
        "production_separation": production_sep,
        "candidate_separation": candidate_sep,
        "candidate_supported": candidate_supported,
        "promotion_ready": False,
        "live_shadow_required": True,
        "blockers": blockers,
        "calibration_fingerprint": _fingerprint(profile, rows),
    }
