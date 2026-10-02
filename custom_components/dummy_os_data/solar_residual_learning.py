"""Pure helpers for F6 Solar residual learning."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import statistics
from typing import Any, Mapping

ARRAYS = ("north", "south")
F6_PARENT_MODEL = "open_meteo_gti_horizon_partial_temperature_candidate_v0.1"
F6_MODEL = "open_meteo_gti_horizon_partial_temperature_residual_candidate_v0.1"
F6_BIN_CONTRACT = "solar_residual_bins_v0.1"
F6_REVISION_CONTRACT = "solar_residual_revision_v0.1"
F6_STATE_SCHEMA_VERSION = 1
F6_MAX_SAMPLES_PER_BIN = 120
F6_PLAUSIBILITY_MIN_RATIO = 0.25
F6_PLAUSIBILITY_MAX_RATIO = 4.0
F6_MAD_MIN_SAMPLES = 20
F6_MIN_QUALIFIED_SAMPLES = 40
F6_MIN_QUALIFIED_DAYS = 7
F6_FACTOR_MIN = 0.75
F6_FACTOR_MAX = 1.25
F6_MIN_PARENT_KWH = 0.02
F6_AC_CAP_EPSILON_KWH = 0.000001


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def season_for_month(month: int) -> str:
    """Return a compact local-season diagnostic label."""
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def condition_key(
    array: str,
    solar_elevation_band: str,
    solar_azimuth_sector: str,
    weather_regime: str,
) -> str | None:
    """Return the transparent F6 per-array condition key."""
    if array not in ARRAYS:
        return None
    if solar_elevation_band not in {"low", "medium", "high"}:
        return None
    if solar_azimuth_sector not in {"north", "east", "south", "west"}:
        return None
    if weather_regime not in {"diffuse_dominant", "mixed", "direct_dominant"}:
        return None
    return f"{array}|{solar_elevation_band}|{solar_azimuth_sector}|{weather_regime}"


def build_parent_signature(payload: Mapping[str, Any]) -> str:
    """Return a deterministic signature for the frozen physical parent inputs."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def thresholds() -> dict[str, Any]:
    return {
        "max_samples_per_bin": F6_MAX_SAMPLES_PER_BIN,
        "plausibility_ratio_min": F6_PLAUSIBILITY_MIN_RATIO,
        "plausibility_ratio_max": F6_PLAUSIBILITY_MAX_RATIO,
        "mad_min_samples": F6_MAD_MIN_SAMPLES,
        "minimum_qualified_samples": F6_MIN_QUALIFIED_SAMPLES,
        "minimum_qualified_days": F6_MIN_QUALIFIED_DAYS,
        "factor_min": F6_FACTOR_MIN,
        "factor_max": F6_FACTOR_MAX,
        "minimum_parent_kwh": F6_MIN_PARENT_KWH,
    }


def _initial_revision(parent_model: str, parent_signature: str) -> dict[str, Any]:
    payload = {
        "revision_contract": F6_REVISION_CONTRACT,
        "parent_model": parent_model,
        "parent_signature": parent_signature,
        "training_cutoff": None,
        "bin_contract": F6_BIN_CONTRACT,
        "thresholds": thresholds(),
        "bins": {},
    }
    digest = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()[:16]
    payload["model_revision"] = f"f6-initial-{digest}"
    return payload


def new_learning_state(parent_model: str, parent_signature: str) -> dict[str, Any]:
    """Return a clean restart-persistent F6 learner state."""
    return {
        "schema_version": F6_STATE_SCHEMA_VERSION,
        "parent_model": parent_model,
        "parent_signature": parent_signature,
        "bins": {},
        "revision": _initial_revision(parent_model, parent_signature),
        "last_revision_local_date": None,
        "last_training_cutoff": None,
        "last_reset_reason": None,
    }


def validate_learning_state(
    raw: Any,
    parent_model: str,
    parent_signature: str,
) -> tuple[bool, dict[str, Any]]:
    """Validate persisted state; recover safely to an empty factor-1 state."""
    if not isinstance(raw, Mapping):
        state = new_learning_state(parent_model, parent_signature)
        state["last_reset_reason"] = "missing_or_invalid_state"
        return False, state
    if raw.get("schema_version") != F6_STATE_SCHEMA_VERSION:
        state = new_learning_state(parent_model, parent_signature)
        state["last_reset_reason"] = "schema_mismatch"
        return False, state
    if raw.get("parent_model") != parent_model:
        state = new_learning_state(parent_model, parent_signature)
        state["last_reset_reason"] = "parent_model_changed"
        return False, state
    if raw.get("parent_signature") != parent_signature:
        state = new_learning_state(parent_model, parent_signature)
        state["last_reset_reason"] = "parent_signature_changed"
        return False, state
    if not isinstance(raw.get("bins"), Mapping) or not isinstance(
        raw.get("revision"), Mapping
    ):
        state = new_learning_state(parent_model, parent_signature)
        state["last_reset_reason"] = "corrupt_state"
        return False, state

    state = dict(raw)
    state["bins"] = {
        str(key): dict(value)
        for key, value in raw.get("bins", {}).items()
        if isinstance(key, str) and isinstance(value, Mapping)
    }
    state["revision"] = dict(raw.get("revision", {}))
    return True, state


def reset_for_parent_change(
    state: Mapping[str, Any],
    parent_model: str,
    parent_signature: str,
) -> tuple[bool, dict[str, Any]]:
    """Reset qualification when the frozen physical parent changes."""
    if (
        state.get("parent_model") == parent_model
        and state.get("parent_signature") == parent_signature
    ):
        return False, dict(state)
    reset = new_learning_state(parent_model, parent_signature)
    reset["last_reset_reason"] = "physical_parent_changed"
    return True, reset


def build_training_sample(
    evaluation: Mapping[str, Any] | None,
    *,
    array: str,
    solar_elevation_band: str | None,
    solar_azimuth_sector: str | None,
    weather_regime: str | None,
    ac_limit_kw: float,
    local_date: str,
    local_month: int,
    parent_signature: str,
    expected_parent_signature: str | None,
) -> tuple[str, dict[str, Any] | None]:
    """Apply the binding F6 hard eligibility gates for one array/quarter."""
    if not isinstance(evaluation, Mapping):
        return "missing_evaluation", None
    if evaluation.get("status") != "ok" or evaluation.get("valid") is not True:
        return "invalid_evaluation", None
    if array not in ARRAYS:
        return "invalid_array", None
    if evaluation.get(f"valid_{array}") is not True:
        return "invalid_component", None
    if expected_parent_signature != parent_signature:
        return "parent_signature_mismatch", None

    coverage = _finite_number(evaluation.get(f"coverage_{array}_percent"))
    parent = _finite_number(evaluation.get(f"forecast_{array}_kwh"))
    actual = _finite_number(evaluation.get(f"actual_{array}_kwh"))
    elevation = _finite_number(evaluation.get("solar_elevation_deg"))
    if None in (coverage, parent, actual, elevation):
        return "missing_component_value", None
    assert (
        coverage is not None
        and parent is not None
        and actual is not None
        and elevation is not None
    )
    if coverage < 90.0:
        return "insufficient_coverage", None
    if elevation < 0.0 or weather_regime == "dark":
        return "not_daylight", None
    if parent < F6_MIN_PARENT_KWH:
        return "parent_below_minimum", None

    cap_slot_kwh = max(0.0, float(ac_limit_kw)) * 0.25
    if parent >= cap_slot_kwh - F6_AC_CAP_EPSILON_KWH:
        return "at_ac_cap", None

    key = condition_key(
        array,
        str(solar_elevation_band),
        str(solar_azimuth_sector),
        str(weather_regime),
    )
    if key is None:
        return "invalid_condition", None
    ratio = actual / parent
    if not math.isfinite(ratio):
        return "invalid_ratio", None

    slot_id = evaluation.get("slot_id")
    captured_at = evaluation.get("forecast_captured_at")
    if not isinstance(slot_id, str) or not isinstance(captured_at, str):
        return "invalid_lock_identity", None

    plausible = F6_PLAUSIBILITY_MIN_RATIO <= ratio <= F6_PLAUSIBILITY_MAX_RATIO
    sample = {
        "slot_id": slot_id,
        "forecast_captured_at": captured_at,
        "date": local_date,
        "month": int(local_month),
        "season": season_for_month(int(local_month)),
        "array": array,
        "bin": key,
        "solar_elevation_band": solar_elevation_band,
        "solar_azimuth_sector": solar_azimuth_sector,
        "weather_regime": weather_regime,
        "parent_kwh": round(parent, 6),
        "actual_kwh": round(actual, 6),
        "residual_ratio": round(ratio, 9),
        "plausibility_ok": plausible,
        "parent_signature": parent_signature,
    }
    return ("ok" if plausible else "plausibility_outlier"), sample


def add_training_sample(state: dict[str, Any], sample: Mapping[str, Any]) -> bool:
    """Persist one eligible ratio with deduplication and a 120-sample bin cap."""
    key = sample.get("bin")
    slot_id = sample.get("slot_id")
    if not isinstance(key, str) or not isinstance(slot_id, str):
        return False
    bins = state.setdefault("bins", {})
    raw_bin = bins.setdefault(key, {"samples": []})
    samples = raw_bin.setdefault("samples", [])
    if not isinstance(samples, list):
        raw_bin["samples"] = samples = []
    if any(
        isinstance(item, Mapping) and item.get("slot_id") == slot_id
        for item in samples
    ):
        return False
    samples.append(dict(sample))
    samples.sort(key=lambda item: str(item.get("slot_id", "")))
    raw_bin["samples"] = samples[-F6_MAX_SAMPLES_PER_BIN:]
    return True


def _median_absolute_deviation(values: list[float], median: float) -> float:
    return statistics.median([abs(value - median) for value in values])


def fit_bin(samples: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit one transparent residual bin using plausibility + median/MAD."""
    plausible: list[tuple[float, Mapping[str, Any]]] = []
    plausibility_outliers = 0
    for sample in samples:
        ratio = _finite_number(sample.get("residual_ratio"))
        if ratio is None:
            continue
        if not (
            F6_PLAUSIBILITY_MIN_RATIO
            <= ratio
            <= F6_PLAUSIBILITY_MAX_RATIO
        ):
            plausibility_outliers += 1
            continue
        if sample.get("plausibility_ok") is False:
            plausibility_outliers += 1
            continue
        plausible.append((ratio, sample))

    values = [ratio for ratio, _ in plausible]
    initial_median = statistics.median(values) if values else None
    mad = None
    fit = list(plausible)
    mad_outliers = 0
    if len(values) >= F6_MAD_MIN_SAMPLES and initial_median is not None:
        mad = _median_absolute_deviation(values, initial_median)
        if math.isfinite(mad):
            if mad == 0.0:
                fit = [
                    item
                    for item in plausible
                    if abs(item[0] - initial_median) <= 1e-12
                ]
            else:
                limit = 3.0 * mad
                fit = [
                    item
                    for item in plausible
                    if abs(item[0] - initial_median) <= limit
                ]
            mad_outliers = len(plausible) - len(fit)
        else:
            fit = []

    fit_values = [ratio for ratio, _ in fit]
    fit_median = statistics.median(fit_values) if fit_values else None
    fit_days = sorted(
        {
            str(sample.get("date"))
            for _, sample in fit
            if isinstance(sample.get("date"), str)
        }
    )
    usable_count = len(fit)

    if (
        len(plausible) >= F6_MAD_MIN_SAMPLES
        and usable_count < F6_MAD_MIN_SAMPLES
    ):
        status = "unstable"
    elif (
        usable_count < F6_MIN_QUALIFIED_SAMPLES
        or len(fit_days) < F6_MIN_QUALIFIED_DAYS
    ):
        status = "insufficient"
    elif fit_median is None or not math.isfinite(fit_median):
        status = "unstable"
    elif fit_median <= F6_FACTOR_MIN or fit_median >= F6_FACTOR_MAX:
        status = "saturated"
    else:
        status = "qualified"

    raw_factor = fit_median
    learned_factor = (
        min(F6_FACTOR_MAX, max(F6_FACTOR_MIN, fit_median))
        if fit_median is not None and math.isfinite(fit_median)
        else 1.0
    )
    applied_factor = learned_factor if status == "qualified" else 1.0
    return {
        "status": status,
        "sample_count": len(samples),
        "plausible_sample_count": len(plausible),
        "usable_sample_count": usable_count,
        "day_count": len(fit_days),
        "days": fit_days,
        "median_ratio": (
            round(fit_median, 9) if fit_median is not None else None
        ),
        "mad": round(mad, 9) if mad is not None else None,
        "plausibility_outlier_count": plausibility_outliers,
        "mad_outlier_count": mad_outliers,
        "raw_factor": (
            round(raw_factor, 9) if raw_factor is not None else None
        ),
        "learned_factor": round(learned_factor, 9),
        "applied_factor": round(applied_factor, 9),
    }


def build_revision(
    state: dict[str, Any],
    *,
    training_cutoff: str,
    cutoff_local_date: str,
) -> dict[str, Any]:
    """Create one deterministic daily revision using only pre-cutoff local dates."""
    revision_bins: dict[str, Any] = {}
    for key in sorted(state.get("bins", {})):
        raw_bin = state["bins"].get(key, {})
        raw_samples = (
            raw_bin.get("samples", []) if isinstance(raw_bin, Mapping) else []
        )
        eligible = [
            sample
            for sample in raw_samples
            if isinstance(sample, Mapping)
            and isinstance(sample.get("date"), str)
            and str(sample.get("date")) < cutoff_local_date
        ]
        revision_bins[key] = fit_bin(eligible)

    payload = {
        "revision_contract": F6_REVISION_CONTRACT,
        "parent_model": state.get("parent_model"),
        "parent_signature": state.get("parent_signature"),
        "training_cutoff": training_cutoff,
        "cutoff_local_date": cutoff_local_date,
        "bin_contract": F6_BIN_CONTRACT,
        "thresholds": thresholds(),
        "bins": revision_bins,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()[:16]
    payload["model_revision"] = f"f6-{cutoff_local_date}-{digest}"
    state["revision"] = payload
    state["last_revision_local_date"] = cutoff_local_date
    state["last_training_cutoff"] = training_cutoff
    return payload


def factor_for_bin(
    revision: Mapping[str, Any] | None,
    bin_key: str | None,
    *,
    allow_application: bool = True,
) -> dict[str, Any]:
    """Resolve one slot factor with factor=1 for all fail-safe states."""
    if (
        not allow_application
        or bin_key is None
        or not isinstance(revision, Mapping)
    ):
        return {
            "status": "not_applicable",
            "applied_factor": 1.0,
            "bin": bin_key,
        }
    bins = revision.get("bins")
    if not isinstance(bins, Mapping):
        return {
            "status": "invalid_state",
            "applied_factor": 1.0,
            "bin": bin_key,
        }
    result = bins.get(bin_key)
    if not isinstance(result, Mapping):
        return {
            "status": "insufficient",
            "applied_factor": 1.0,
            "bin": bin_key,
        }
    return {
        "status": str(result.get("status") or "invalid_state"),
        "applied_factor": (
            float(result.get("applied_factor", 1.0))
            if result.get("status") == "qualified"
            else 1.0
        ),
        "bin": bin_key,
        "sample_count": max(0, int(result.get("sample_count", 0))),
        "usable_sample_count": max(
            0, int(result.get("usable_sample_count", 0))
        ),
        "day_count": max(0, int(result.get("day_count", 0))),
        "median_ratio": result.get("median_ratio"),
        "mad": result.get("mad"),
    }


def apply_factor_with_ac_cap(
    parent_kwh: Any, factor: Any, ac_limit_kw: Any
) -> float | None:
    """Apply a residual factor and reapply the immutable per-array AC-slot cap."""
    parent = _finite_number(parent_kwh)
    applied_factor = _finite_number(factor)
    ac_limit = _finite_number(ac_limit_kw)
    if None in (parent, applied_factor, ac_limit):
        return None
    assert (
        parent is not None
        and applied_factor is not None
        and ac_limit is not None
    )
    if parent < 0.0 or applied_factor < 0.0 or ac_limit < 0.0:
        return None
    return round(min(parent * applied_factor, ac_limit * 0.25), 6)


def revision_diagnostics(
    revision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Summarize revision states for the canonical status sensor."""
    bins = revision.get("bins", {}) if isinstance(revision, Mapping) else {}
    if not isinstance(bins, Mapping):
        bins = {}
    counts = {
        "qualified": 0,
        "insufficient": 0,
        "unstable": 0,
        "saturated": 0,
    }
    sample_count = 0
    usable_sample_count = 0
    day_set: set[str] = set()
    for result in bins.values():
        if not isinstance(result, Mapping):
            continue
        status = str(result.get("status") or "insufficient")
        if status in counts:
            counts[status] += 1
        sample_count += max(0, int(result.get("sample_count", 0)))
        usable_sample_count += max(
            0, int(result.get("usable_sample_count", 0))
        )
        raw_days = result.get("days", [])
        for day in raw_days if isinstance(raw_days, list) else []:
            if isinstance(day, str):
                day_set.add(day)
    return {
        "bin_count": len(bins),
        "qualified_bins": counts["qualified"],
        "insufficient_bins": counts["insufficient"],
        "unstable_bins": counts["unstable"],
        "saturated_bins": counts["saturated"],
        "sample_count": sample_count,
        "usable_sample_count": usable_sample_count,
        "day_count": len(day_set),
    }


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
