"""Pure helpers for F5 horizon-simple versus partial-shading validation."""

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


def build_partial_shading_pair(
    horizon: Mapping[str, Any] | None,
    partial: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Validate one exact-lock F3/F5 pair and return a compact sample."""
    if not isinstance(horizon, Mapping) or not isinstance(partial, Mapping):
        return "missing_evaluation", None
    if horizon.get("status") != "ok" or partial.get("status") != "ok":
        return "invalid_evaluation", None
    if horizon.get("valid") is not True or partial.get("valid") is not True:
        return "invalid_evaluation", None

    slot_id = horizon.get("slot_id")
    if not isinstance(slot_id, str) or partial.get("slot_id") != slot_id:
        return "slot_mismatch", None
    captured_at = horizon.get("forecast_captured_at")
    if (
        not isinstance(captured_at, str)
        or partial.get("forecast_captured_at") != captured_at
    ):
        return "lock_mismatch", None

    sample: dict[str, Any] = {
        "slot_id": slot_id,
        "forecast_captured_at": captured_at,
        "components": {},
    }
    for roof in ROOFS:
        if (
            horizon.get(f"valid_{roof}") is not True
            or partial.get(f"valid_{roof}") is not True
        ):
            return "invalid_component", None
        horizon_actual = _finite_number(horizon.get(f"actual_{roof}_kwh"))
        partial_actual = _finite_number(partial.get(f"actual_{roof}_kwh"))
        horizon_forecast = _finite_number(horizon.get(f"forecast_{roof}_kwh"))
        partial_forecast = _finite_number(partial.get(f"forecast_{roof}_kwh"))
        horizon_coverage = _finite_number(horizon.get(f"coverage_{roof}_percent"))
        partial_coverage = _finite_number(partial.get(f"coverage_{roof}_percent"))
        if None in (
            horizon_actual,
            partial_actual,
            horizon_forecast,
            partial_forecast,
            horizon_coverage,
            partial_coverage,
        ):
            return "missing_component_value", None
        if abs(horizon_actual - partial_actual) > 0.000001:
            return "actual_mismatch", None
        if abs(horizon_coverage - partial_coverage) > 0.000001:
            return "coverage_mismatch", None

        if roof == "total":
            blocked = bool(
                partial.get("north_horizon_blocked")
                or partial.get("south_horizon_blocked")
            )
        else:
            blocked_value = partial.get(f"{roof}_horizon_blocked")
            if not isinstance(blocked_value, bool):
                return "missing_blocked_diagnostic", None
            blocked = blocked_value

        horizon_error = horizon_forecast - horizon_actual
        partial_error = partial_forecast - horizon_actual
        sample["components"][roof] = {
            "actual_kwh": round(horizon_actual, 6),
            "horizon_forecast_kwh": round(horizon_forecast, 6),
            "partial_forecast_kwh": round(partial_forecast, 6),
            "horizon_error_kwh": round(horizon_error, 6),
            "partial_error_kwh": round(partial_error, 6),
            "horizon_absolute_error_kwh": round(abs(horizon_error), 6),
            "partial_absolute_error_kwh": round(abs(partial_error), 6),
            "coverage_percent": round(horizon_coverage, 1),
            "horizon_blocked": blocked,
        }

    for field in (
        "solar_azimuth_deg",
        "solar_elevation_deg",
        "north_horizon_elevation_deg",
        "south_horizon_elevation_deg",
        "north_partial_factor",
        "south_partial_factor",
        "north_effective_irradiance_wm2",
        "south_effective_irradiance_wm2",
    ):
        value = _finite_number(partial.get(field))
        if value is not None:
            sample[field] = round(value, 6)

    return "ok", sample


def _new_component_aggregate() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "blocked_sample_count": 0,
        "actual_kwh_sum": 0.0,
        "horizon_forecast_kwh_sum": 0.0,
        "partial_forecast_kwh_sum": 0.0,
        "horizon_error_kwh_sum": 0.0,
        "partial_error_kwh_sum": 0.0,
        "horizon_absolute_error_kwh_sum": 0.0,
        "partial_absolute_error_kwh_sum": 0.0,
        "blocked_actual_kwh_sum": 0.0,
        "blocked_horizon_forecast_kwh_sum": 0.0,
        "blocked_partial_forecast_kwh_sum": 0.0,
        "blocked_horizon_error_kwh_sum": 0.0,
        "blocked_partial_error_kwh_sum": 0.0,
        "blocked_horizon_absolute_error_kwh_sum": 0.0,
        "blocked_partial_absolute_error_kwh_sum": 0.0,
    }


def new_partial_shading_day(date_key: str) -> dict[str, Any]:
    """Return one empty local-day F5 aggregate."""
    return {
        "date": date_key,
        "sample_count": 0,
        "first_slot_id": None,
        "last_slot_id": None,
        "components": {roof: _new_component_aggregate() for roof in ROOFS},
    }


def add_partial_shading_sample(
    day: dict[str, Any],
    sample: Mapping[str, Any],
) -> dict[str, Any]:
    """Add one valid exact-lock F5 sample to a daily aggregate."""
    slot_id = sample.get("slot_id")
    components = sample.get("components")
    if not isinstance(slot_id, str) or not isinstance(components, Mapping):
        raise ValueError("invalid F5 sample")

    day["sample_count"] = max(0, int(day.get("sample_count", 0))) + 1
    if day.get("first_slot_id") is None:
        day["first_slot_id"] = slot_id
    day["last_slot_id"] = slot_id

    targets = day.setdefault("components", {})
    for roof in ROOFS:
        source = components.get(roof)
        if not isinstance(source, Mapping):
            raise ValueError(f"missing {roof} component")
        target = targets.setdefault(roof, _new_component_aggregate())
        target["sample_count"] = max(0, int(target.get("sample_count", 0))) + 1
        blocked = source.get("horizon_blocked") is True
        if blocked:
            target["blocked_sample_count"] = (
                max(0, int(target.get("blocked_sample_count", 0))) + 1
            )

        for source_key, target_key in (
            ("actual_kwh", "actual_kwh_sum"),
            ("horizon_forecast_kwh", "horizon_forecast_kwh_sum"),
            ("partial_forecast_kwh", "partial_forecast_kwh_sum"),
            ("horizon_error_kwh", "horizon_error_kwh_sum"),
            ("partial_error_kwh", "partial_error_kwh_sum"),
            ("horizon_absolute_error_kwh", "horizon_absolute_error_kwh_sum"),
            ("partial_absolute_error_kwh", "partial_absolute_error_kwh_sum"),
        ):
            value = _finite_number(source.get(source_key))
            if value is None:
                raise ValueError(f"invalid {roof} {source_key}")
            target[target_key] = round(float(target.get(target_key, 0.0)) + value, 6)
            if blocked:
                blocked_key = f"blocked_{target_key}"
                target[blocked_key] = round(
                    float(target.get(blocked_key, 0.0)) + value,
                    6,
                )
    return day


def _merge_component(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key in _new_component_aggregate():
        if key in ("sample_count", "blocked_sample_count"):
            target[key] = max(0, int(target.get(key, 0))) + max(
                0, int(source.get(key, 0))
            )
        else:
            value = _finite_number(source.get(key))
            if value is not None:
                target[key] = round(float(target.get(key, 0.0)) + value, 6)


def _metrics_from_totals(
    totals: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    actual = _finite_number(totals.get(f"{prefix}actual_kwh_sum")) or 0.0
    horizon_forecast = (
        _finite_number(totals.get(f"{prefix}horizon_forecast_kwh_sum")) or 0.0
    )
    partial_forecast = (
        _finite_number(totals.get(f"{prefix}partial_forecast_kwh_sum")) or 0.0
    )
    horizon_error = _finite_number(totals.get(f"{prefix}horizon_error_kwh_sum")) or 0.0
    partial_error = _finite_number(totals.get(f"{prefix}partial_error_kwh_sum")) or 0.0
    horizon_abs = (
        _finite_number(totals.get(f"{prefix}horizon_absolute_error_kwh_sum")) or 0.0
    )
    partial_abs = (
        _finite_number(totals.get(f"{prefix}partial_absolute_error_kwh_sum")) or 0.0
    )
    denominator_ok = actual >= EVALUATION_EPSILON_KWH
    return {
        "actual_kwh": round(actual, 6),
        "horizon_forecast_kwh": round(horizon_forecast, 6),
        "partial_forecast_kwh": round(partial_forecast, 6),
        "horizon_signed_error_kwh": round(horizon_error, 6),
        "partial_signed_error_kwh": round(partial_error, 6),
        "horizon_absolute_error_kwh": round(horizon_abs, 6),
        "partial_absolute_error_kwh": round(partial_abs, 6),
        "horizon_bias_percent": (
            round(100.0 * horizon_error / actual, 2) if denominator_ok else None
        ),
        "partial_bias_percent": (
            round(100.0 * partial_error / actual, 2) if denominator_ok else None
        ),
        "horizon_wape_percent": (
            round(100.0 * horizon_abs / actual, 2) if denominator_ok else None
        ),
        "partial_wape_percent": (
            round(100.0 * partial_abs / actual, 2) if denominator_ok else None
        ),
    }


def _component_summary(days: list[Mapping[str, Any]], roof: str) -> dict[str, Any]:
    totals = _new_component_aggregate()
    for day in days:
        component = day.get("components", {}).get(roof, {})
        if isinstance(component, Mapping):
            _merge_component(totals, component)
    return {
        "sample_count": totals["sample_count"],
        **_metrics_from_totals(totals),
        "blocked_effect": {
            "sample_count": totals["blocked_sample_count"],
            **_metrics_from_totals(totals, prefix="blocked_"),
        },
    }


def summarize_partial_shading_history(
    history: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize F5 evidence without winner or promotion logic."""
    days = sorted(
        [
            day
            for day in history
            if isinstance(day, Mapping) and isinstance(day.get("date"), str)
        ],
        key=lambda item: str(item.get("date")),
    )
    return {
        "sample_count": sum(max(0, int(day.get("sample_count", 0))) for day in days),
        "day_count": len(days),
        "first_date": days[0].get("date") if days else None,
        "last_date": days[-1].get("date") if days else None,
        "components": {roof: _component_summary(days, roof) for roof in ROOFS},
        "recent_days": [dict(day) for day in days[-14:]],
    }
