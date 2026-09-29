"""Pure helpers for F2 Solar temperature-candidate A/B validation."""

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


def build_temperature_ab_pair(
    raw: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Validate one exact-lock raw/candidate pair and return a compact sample."""
    if not isinstance(raw, Mapping) or not isinstance(candidate, Mapping):
        return "missing_evaluation", None
    if raw.get("status") != "ok" or candidate.get("status") != "ok":
        return "invalid_evaluation", None
    if raw.get("valid") is not True or candidate.get("valid") is not True:
        return "invalid_evaluation", None

    slot_id = raw.get("slot_id")
    if not isinstance(slot_id, str) or candidate.get("slot_id") != slot_id:
        return "slot_mismatch", None
    captured_at = raw.get("forecast_captured_at")
    if not isinstance(captured_at, str) or candidate.get("forecast_captured_at") != captured_at:
        return "lock_mismatch", None

    sample: dict[str, Any] = {
        "slot_id": slot_id,
        "forecast_captured_at": captured_at,
        "components": {},
    }
    for roof in ROOFS:
        if raw.get(f"valid_{roof}") is not True or candidate.get(f"valid_{roof}") is not True:
            return "invalid_component", None
        raw_actual = _finite_number(raw.get(f"actual_{roof}_kwh"))
        candidate_actual = _finite_number(candidate.get(f"actual_{roof}_kwh"))
        raw_forecast = _finite_number(raw.get(f"forecast_{roof}_kwh"))
        candidate_forecast = _finite_number(candidate.get(f"forecast_{roof}_kwh"))
        raw_coverage = _finite_number(raw.get(f"coverage_{roof}_percent"))
        candidate_coverage = _finite_number(candidate.get(f"coverage_{roof}_percent"))
        if None in (
            raw_actual,
            candidate_actual,
            raw_forecast,
            candidate_forecast,
            raw_coverage,
            candidate_coverage,
        ):
            return "missing_component_value", None
        if abs(raw_actual - candidate_actual) > 0.000001:
            return "actual_mismatch", None
        if abs(raw_coverage - candidate_coverage) > 0.1:
            return "coverage_mismatch", None

        raw_error = raw_forecast - raw_actual
        candidate_error = candidate_forecast - raw_actual
        sample["components"][roof] = {
            "actual_kwh": round(raw_actual, 6),
            "raw_forecast_kwh": round(raw_forecast, 6),
            "candidate_forecast_kwh": round(candidate_forecast, 6),
            "raw_error_kwh": round(raw_error, 6),
            "candidate_error_kwh": round(candidate_error, 6),
            "raw_absolute_error_kwh": round(abs(raw_error), 6),
            "candidate_absolute_error_kwh": round(abs(candidate_error), 6),
            "coverage_percent": round(raw_coverage, 1),
        }

    for field in (
        "north_ambient_temperature_c",
        "south_ambient_temperature_c",
        "north_cell_temperature_c",
        "south_cell_temperature_c",
        "north_temperature_factor",
        "south_temperature_factor",
    ):
        value = _finite_number(candidate.get(field))
        if value is not None:
            sample[field] = round(value, 6)
    return "ok", sample


def new_temperature_ab_day(date_key: str) -> dict[str, Any]:
    """Return an empty persistent daily F2 aggregate."""
    return {
        "date": date_key,
        "sample_count": 0,
        "first_slot_id": None,
        "last_slot_id": None,
        "components": {
            roof: {
                "actual_kwh_sum": 0.0,
                "raw_forecast_kwh_sum": 0.0,
                "candidate_forecast_kwh_sum": 0.0,
                "raw_error_kwh_sum": 0.0,
                "candidate_error_kwh_sum": 0.0,
                "raw_absolute_error_kwh_sum": 0.0,
                "candidate_absolute_error_kwh_sum": 0.0,
            }
            for roof in ROOFS
        },
        "temperature": {
            "north_cell_min_c": None,
            "north_cell_max_c": None,
            "south_cell_min_c": None,
            "south_cell_max_c": None,
            "north_factor_min": None,
            "north_factor_max": None,
            "south_factor_min": None,
            "south_factor_max": None,
        },
    }


def _update_minmax(container: dict[str, Any], min_key: str, max_key: str, value: Any) -> None:
    number = _finite_number(value)
    if number is None:
        return
    current_min = _finite_number(container.get(min_key))
    current_max = _finite_number(container.get(max_key))
    container[min_key] = round(number if current_min is None else min(current_min, number), 6)
    container[max_key] = round(number if current_max is None else max(current_max, number), 6)


def add_temperature_ab_sample(day: dict[str, Any], sample: Mapping[str, Any]) -> dict[str, Any]:
    """Add one validated F2 sample to one daily aggregate."""
    if not isinstance(day, dict) or not isinstance(sample, Mapping):
        raise ValueError("day and sample are required")
    slot_id = sample.get("slot_id")
    components = sample.get("components")
    if not isinstance(slot_id, str) or not isinstance(components, Mapping):
        raise ValueError("invalid F2 sample")

    day["sample_count"] = max(0, int(day.get("sample_count", 0))) + 1
    if day.get("first_slot_id") is None:
        day["first_slot_id"] = slot_id
    day["last_slot_id"] = slot_id

    day_components = day.setdefault("components", {})
    for roof in ROOFS:
        source = components.get(roof)
        if not isinstance(source, Mapping):
            raise ValueError(f"missing {roof} component")
        target = day_components.setdefault(roof, {})
        for source_key, target_key in (
            ("actual_kwh", "actual_kwh_sum"),
            ("raw_forecast_kwh", "raw_forecast_kwh_sum"),
            ("candidate_forecast_kwh", "candidate_forecast_kwh_sum"),
            ("raw_error_kwh", "raw_error_kwh_sum"),
            ("candidate_error_kwh", "candidate_error_kwh_sum"),
            ("raw_absolute_error_kwh", "raw_absolute_error_kwh_sum"),
            ("candidate_absolute_error_kwh", "candidate_absolute_error_kwh_sum"),
        ):
            value = _finite_number(source.get(source_key))
            if value is None:
                raise ValueError(f"invalid {roof} {source_key}")
            target[target_key] = round(float(target.get(target_key, 0.0)) + value, 6)

    temperature = day.setdefault("temperature", {})
    _update_minmax(temperature, "north_cell_min_c", "north_cell_max_c", sample.get("north_cell_temperature_c"))
    _update_minmax(temperature, "south_cell_min_c", "south_cell_max_c", sample.get("south_cell_temperature_c"))
    _update_minmax(temperature, "north_factor_min", "north_factor_max", sample.get("north_temperature_factor"))
    _update_minmax(temperature, "south_factor_min", "south_factor_max", sample.get("south_temperature_factor"))
    return day


def _component_summary(days: list[Mapping[str, Any]], roof: str) -> dict[str, Any]:
    sample_count = 0
    totals = {
        "actual_kwh_sum": 0.0,
        "raw_forecast_kwh_sum": 0.0,
        "candidate_forecast_kwh_sum": 0.0,
        "raw_error_kwh_sum": 0.0,
        "candidate_error_kwh_sum": 0.0,
        "raw_absolute_error_kwh_sum": 0.0,
        "candidate_absolute_error_kwh_sum": 0.0,
    }
    for day in days:
        sample_count += max(0, int(day.get("sample_count", 0)))
        component = day.get("components", {}).get(roof, {})
        for key in totals:
            value = _finite_number(component.get(key))
            if value is not None:
                totals[key] += value

    actual = totals["actual_kwh_sum"]
    raw_abs = totals["raw_absolute_error_kwh_sum"]
    candidate_abs = totals["candidate_absolute_error_kwh_sum"]
    raw_error = totals["raw_error_kwh_sum"]
    candidate_error = totals["candidate_error_kwh_sum"]
    denominator_ok = actual >= EVALUATION_EPSILON_KWH
    return {
        "sample_count": sample_count,
        "actual_kwh": round(actual, 6),
        "raw_forecast_kwh": round(totals["raw_forecast_kwh_sum"], 6),
        "candidate_forecast_kwh": round(totals["candidate_forecast_kwh_sum"], 6),
        "raw_signed_error_kwh": round(raw_error, 6),
        "candidate_signed_error_kwh": round(candidate_error, 6),
        "raw_absolute_error_kwh": round(raw_abs, 6),
        "candidate_absolute_error_kwh": round(candidate_abs, 6),
        "raw_bias_percent": round(100.0 * raw_error / actual, 2) if denominator_ok else None,
        "candidate_bias_percent": round(100.0 * candidate_error / actual, 2) if denominator_ok else None,
        "raw_wape_percent": round(100.0 * raw_abs / actual, 2) if denominator_ok else None,
        "candidate_wape_percent": round(100.0 * candidate_abs / actual, 2) if denominator_ok else None,
    }


def summarize_temperature_ab_history(history: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize persistent daily F2 aggregates without selecting a winner."""
    days = sorted(
        [day for day in history if isinstance(day, Mapping) and isinstance(day.get("date"), str)],
        key=lambda item: str(item.get("date")),
    )
    temperatures: dict[str, float | None] = {
        "north_cell_min_c": None,
        "north_cell_max_c": None,
        "south_cell_min_c": None,
        "south_cell_max_c": None,
        "north_factor_min": None,
        "north_factor_max": None,
        "south_factor_min": None,
        "south_factor_max": None,
    }
    for day in days:
        temp = day.get("temperature")
        if not isinstance(temp, Mapping):
            continue
        for min_key, max_key in (
            ("north_cell_min_c", "north_cell_max_c"),
            ("south_cell_min_c", "south_cell_max_c"),
            ("north_factor_min", "north_factor_max"),
            ("south_factor_min", "south_factor_max"),
        ):
            min_value = _finite_number(temp.get(min_key))
            max_value = _finite_number(temp.get(max_key))
            if min_value is not None:
                current = _finite_number(temperatures[min_key])
                temperatures[min_key] = round(min_value if current is None else min(current, min_value), 6)
            if max_value is not None:
                current = _finite_number(temperatures[max_key])
                temperatures[max_key] = round(max_value if current is None else max(current, max_value), 6)

    sample_count = sum(max(0, int(day.get("sample_count", 0))) for day in days)
    return {
        "sample_count": sample_count,
        "day_count": len(days),
        "first_date": days[0].get("date") if days else None,
        "last_date": days[-1].get("date") if days else None,
        "components": {roof: _component_summary(days, roof) for roof in ROOFS},
        "temperature_range": temperatures,
        "recent_days": [dict(day) for day in days[-14:]],
    }
