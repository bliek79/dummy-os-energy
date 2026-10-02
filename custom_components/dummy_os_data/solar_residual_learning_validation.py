"""Pure helpers for F6 exact-lock parent versus learned validation."""

from __future__ import annotations

import math
from typing import Any, Mapping

ROOFS = ("north", "south", "total")
EVALUATION_EPSILON_KWH = 0.01


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def build_residual_learning_pair(
    parent: Mapping[str, Any] | None,
    learned: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Validate one immutable F5/F6 exact-lock pair."""
    if not isinstance(parent, Mapping) or not isinstance(learned, Mapping):
        return "missing_evaluation", None
    if parent.get("status") != "ok" or learned.get("status") != "ok":
        return "invalid_evaluation", None
    if parent.get("valid") is not True or learned.get("valid") is not True:
        return "invalid_evaluation", None

    slot_id = parent.get("slot_id")
    captured_at = parent.get("forecast_captured_at")
    if not isinstance(slot_id, str) or learned.get("slot_id") != slot_id:
        return "slot_mismatch", None
    if (
        not isinstance(captured_at, str)
        or learned.get("forecast_captured_at") != captured_at
    ):
        return "lock_mismatch", None

    sample: dict[str, Any] = {
        "slot_id": slot_id,
        "forecast_captured_at": captured_at,
        "model_revision": learned.get("model_revision"),
        "parent_model": learned.get("parent_model"),
        "parent_signature": learned.get("parent_signature"),
        "solar_elevation_deg": learned.get("solar_elevation_deg"),
        "solar_elevation_band": learned.get("solar_elevation_band"),
        "solar_azimuth_sector": learned.get("solar_azimuth_sector"),
        "weather_regime": learned.get("weather_regime"),
        "daylight": (
            learned.get("solar_elevation_band") in {"low", "medium", "high"}
            and learned.get("weather_regime")
            in {"diffuse_dominant", "mixed", "direct_dominant"}
        ),
        "components": {},
    }

    for roof in ROOFS:
        if (
            parent.get(f"valid_{roof}") is not True
            or learned.get(f"valid_{roof}") is not True
        ):
            return "invalid_component", None
        parent_actual = _finite_number(parent.get(f"actual_{roof}_kwh"))
        learned_actual = _finite_number(learned.get(f"actual_{roof}_kwh"))
        parent_forecast = _finite_number(parent.get(f"forecast_{roof}_kwh"))
        learned_forecast = _finite_number(learned.get(f"forecast_{roof}_kwh"))
        parent_coverage = _finite_number(parent.get(f"coverage_{roof}_percent"))
        learned_coverage = _finite_number(learned.get(f"coverage_{roof}_percent"))
        if None in (
            parent_actual,
            learned_actual,
            parent_forecast,
            learned_forecast,
            parent_coverage,
            learned_coverage,
        ):
            return "missing_component_value", None
        assert (
            parent_actual is not None
            and learned_actual is not None
            and parent_forecast is not None
            and learned_forecast is not None
            and parent_coverage is not None
            and learned_coverage is not None
        )
        if abs(parent_actual - learned_actual) > 0.000001:
            return "actual_mismatch", None
        if abs(parent_coverage - learned_coverage) > 0.000001:
            return "coverage_mismatch", None

        parent_error = parent_forecast - parent_actual
        learned_error = learned_forecast - parent_actual
        component = {
            "actual_kwh": round(parent_actual, 6),
            "parent_forecast_kwh": round(parent_forecast, 6),
            "learned_forecast_kwh": round(learned_forecast, 6),
            "parent_error_kwh": round(parent_error, 6),
            "learned_error_kwh": round(learned_error, 6),
            "parent_absolute_error_kwh": round(abs(parent_error), 6),
            "learned_absolute_error_kwh": round(abs(learned_error), 6),
            "coverage_percent": round(parent_coverage, 1),
        }
        if roof in ("north", "south"):
            component["bin"] = learned.get(f"{roof}_bin")
            component["bin_status"] = learned.get(f"{roof}_bin_status")
            component["applied_factor"] = learned.get(
                f"{roof}_applied_factor"
            )
        else:
            component["bin"] = (
                f"north={learned.get('north_bin')}|"
                f"south={learned.get('south_bin')}"
            )
        sample["components"][roof] = component
    return "ok", sample


def _empty_metrics() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "daylight_sample_count": 0,
        "actual_kwh_sum": 0.0,
        "parent_forecast_kwh_sum": 0.0,
        "learned_forecast_kwh_sum": 0.0,
        "parent_error_kwh_sum": 0.0,
        "learned_error_kwh_sum": 0.0,
        "parent_absolute_error_kwh_sum": 0.0,
        "learned_absolute_error_kwh_sum": 0.0,
    }


def _add_metrics(
    target: dict[str, Any],
    source: Mapping[str, Any],
    *,
    daylight: bool,
) -> None:
    target["sample_count"] = max(0, int(target.get("sample_count", 0))) + 1
    if daylight:
        target["daylight_sample_count"] = (
            max(0, int(target.get("daylight_sample_count", 0))) + 1
        )
    for source_key, target_key in (
        ("actual_kwh", "actual_kwh_sum"),
        ("parent_forecast_kwh", "parent_forecast_kwh_sum"),
        ("learned_forecast_kwh", "learned_forecast_kwh_sum"),
        ("parent_error_kwh", "parent_error_kwh_sum"),
        ("learned_error_kwh", "learned_error_kwh_sum"),
        ("parent_absolute_error_kwh", "parent_absolute_error_kwh_sum"),
        ("learned_absolute_error_kwh", "learned_absolute_error_kwh_sum"),
    ):
        value = _finite_number(source.get(source_key))
        if value is None:
            raise ValueError(f"invalid {source_key}")
        target[target_key] = round(
            float(target.get(target_key, 0.0)) + value, 6
        )


def new_residual_learning_day(date_key: str) -> dict[str, Any]:
    return {
        "date": date_key,
        "sample_count": 0,
        "daylight_sample_count": 0,
        "first_slot_id": None,
        "last_slot_id": None,
        "components": {roof: _empty_metrics() for roof in ROOFS},
        "condition_bins": {roof: {} for roof in ROOFS},
    }


def add_residual_learning_sample(
    day: dict[str, Any],
    sample: Mapping[str, Any],
) -> dict[str, Any]:
    slot_id = sample.get("slot_id")
    components = sample.get("components")
    if not isinstance(slot_id, str) or not isinstance(components, Mapping):
        raise ValueError("invalid F6 validation sample")
    daylight = sample.get("daylight") is True
    day["sample_count"] = max(0, int(day.get("sample_count", 0))) + 1
    if daylight:
        day["daylight_sample_count"] = (
            max(0, int(day.get("daylight_sample_count", 0))) + 1
        )
    if day.get("first_slot_id") is None:
        day["first_slot_id"] = slot_id
    day["last_slot_id"] = slot_id

    targets = day.setdefault("components", {})
    bins = day.setdefault("condition_bins", {})
    for roof in ROOFS:
        source = components.get(roof)
        if not isinstance(source, Mapping):
            raise ValueError(f"missing {roof} component")
        target = targets.setdefault(roof, _empty_metrics())
        _add_metrics(target, source, daylight=daylight)
        bin_key = source.get("bin")
        if isinstance(bin_key, str):
            roof_bins = bins.setdefault(roof, {})
            bucket = roof_bins.setdefault(bin_key, _empty_metrics())
            _add_metrics(bucket, source, daylight=daylight)
    return day


def _merge_metrics(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    for key in ("sample_count", "daylight_sample_count"):
        target[key] = max(0, int(target.get(key, 0))) + max(
            0, int(source.get(key, 0))
        )
    for key in (
        "actual_kwh_sum",
        "parent_forecast_kwh_sum",
        "learned_forecast_kwh_sum",
        "parent_error_kwh_sum",
        "learned_error_kwh_sum",
        "parent_absolute_error_kwh_sum",
        "learned_absolute_error_kwh_sum",
    ):
        value = _finite_number(source.get(key))
        if value is not None:
            target[key] = round(
                float(target.get(key, 0.0)) + value, 6
            )


def _summarize_metrics(total: Mapping[str, Any]) -> dict[str, Any]:
    actual = _finite_number(total.get("actual_kwh_sum")) or 0.0
    parent_forecast = (
        _finite_number(total.get("parent_forecast_kwh_sum")) or 0.0
    )
    learned_forecast = (
        _finite_number(total.get("learned_forecast_kwh_sum")) or 0.0
    )
    parent_error = _finite_number(total.get("parent_error_kwh_sum")) or 0.0
    learned_error = _finite_number(total.get("learned_error_kwh_sum")) or 0.0
    parent_abs = (
        _finite_number(total.get("parent_absolute_error_kwh_sum")) or 0.0
    )
    learned_abs = (
        _finite_number(total.get("learned_absolute_error_kwh_sum")) or 0.0
    )
    denominator_ok = actual >= EVALUATION_EPSILON_KWH
    return {
        "sample_count": max(0, int(total.get("sample_count", 0))),
        "daylight_sample_count": max(
            0, int(total.get("daylight_sample_count", 0))
        ),
        "actual_kwh": round(actual, 6),
        "parent_forecast_kwh": round(parent_forecast, 6),
        "learned_forecast_kwh": round(learned_forecast, 6),
        "parent_signed_error_kwh": round(parent_error, 6),
        "learned_signed_error_kwh": round(learned_error, 6),
        "parent_absolute_error_kwh": round(parent_abs, 6),
        "learned_absolute_error_kwh": round(learned_abs, 6),
        "parent_bias_percent": (
            round(100.0 * parent_error / actual, 2)
            if denominator_ok
            else None
        ),
        "learned_bias_percent": (
            round(100.0 * learned_error / actual, 2)
            if denominator_ok
            else None
        ),
        "parent_wape_percent": (
            round(100.0 * parent_abs / actual, 2)
            if denominator_ok
            else None
        ),
        "learned_wape_percent": (
            round(100.0 * learned_abs / actual, 2)
            if denominator_ok
            else None
        ),
    }


def summarize_residual_learning_history(
    history: list[Mapping[str, Any]],
) -> dict[str, Any]:
    days = sorted(
        [
            day
            for day in history
            if isinstance(day, Mapping)
            and isinstance(day.get("date"), str)
        ],
        key=lambda item: str(item.get("date")),
    )
    components: dict[str, Any] = {}
    breakdown: dict[str, Any] = {}
    for roof in ROOFS:
        total = _empty_metrics()
        merged_bins: dict[str, dict[str, Any]] = {}
        for day in days:
            source = day.get("components", {}).get(roof, {})
            if isinstance(source, Mapping):
                _merge_metrics(total, source)
            raw_bins = day.get("condition_bins", {}).get(roof, {})
            if isinstance(raw_bins, Mapping):
                for key, raw in raw_bins.items():
                    if (
                        not isinstance(key, str)
                        or not isinstance(raw, Mapping)
                    ):
                        continue
                    target = merged_bins.setdefault(key, _empty_metrics())
                    _merge_metrics(target, raw)
        components[roof] = _summarize_metrics(total)
        breakdown[roof] = {
            key: _summarize_metrics(value)
            for key, value in sorted(merged_bins.items())
        }

    daylight_days = [
        day
        for day in days
        if max(0, int(day.get("daylight_sample_count", 0))) > 0
    ]
    return {
        "sample_count": sum(
            max(0, int(day.get("sample_count", 0))) for day in days
        ),
        "daylight_sample_count": sum(
            max(0, int(day.get("daylight_sample_count", 0)))
            for day in days
        ),
        "day_count": len(days),
        "daylight_day_count": len(daylight_days),
        "first_date": days[0].get("date") if days else None,
        "last_date": days[-1].get("date") if days else None,
        "components": components,
        "breakdown_by_condition_bin": breakdown,
        "recent_days": [dict(day) for day in days[-14:]],
    }
