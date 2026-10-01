"""Pure helpers for F4 Solar raw/temperature/horizon multi-model validation."""

from __future__ import annotations

import math
from typing import Any, Mapping

ROOFS = ("north", "south", "total")
MODELS = ("raw", "temperature", "horizon")
EVALUATION_EPSILON_KWH = 0.01

SOLAR_ELEVATION_BANDS = ("below_horizon", "low", "medium", "high")
SOLAR_AZIMUTH_SECTORS = ("north", "east", "south", "west")
WEATHER_REGIMES = ("dark", "diffuse_dominant", "mixed", "direct_dominant")


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def classify_solar_elevation(value: Any) -> str | None:
    """Return the binding F4 solar-elevation validation band."""
    elevation = _finite_number(value)
    if elevation is None:
        return None
    if elevation < 0.0:
        return "below_horizon"
    if elevation < 10.0:
        return "low"
    if elevation < 25.0:
        return "medium"
    return "high"


def classify_solar_azimuth(value: Any) -> str | None:
    """Return the binding F4 compass sector."""
    azimuth = _finite_number(value)
    if azimuth is None:
        return None
    normalized = azimuth % 360.0
    if normalized >= 315.0 or normalized < 45.0:
        return "north"
    if normalized < 135.0:
        return "east"
    if normalized < 225.0:
        return "south"
    return "west"


def classify_weather_regime(
    direct_radiation_wm2: Any,
    diffuse_radiation_wm2: Any,
) -> tuple[str | None, float | None]:
    """Classify F4 validation weather regime from locked direct/diffuse radiation."""
    direct = _finite_number(direct_radiation_wm2)
    diffuse = _finite_number(diffuse_radiation_wm2)
    if direct is None or diffuse is None:
        return None, None
    direct = max(0.0, direct)
    diffuse = max(0.0, diffuse)
    total = direct + diffuse
    if total <= 1.0:
        return "dark", None
    diffuse_fraction = diffuse / total
    if diffuse_fraction >= 0.75:
        regime = "diffuse_dominant"
    elif diffuse_fraction >= 0.35:
        regime = "mixed"
    else:
        regime = "direct_dominant"
    return regime, round(diffuse_fraction, 6)


def build_multimodel_pair(
    raw: Mapping[str, Any] | None,
    temperature: Mapping[str, Any] | None,
    horizon: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Validate one exact-lock raw/temperature/horizon triple and return a sample."""
    evaluations = (raw, temperature, horizon)
    if not all(isinstance(item, Mapping) for item in evaluations):
        return "missing_evaluation", None
    assert isinstance(raw, Mapping)
    assert isinstance(temperature, Mapping)
    assert isinstance(horizon, Mapping)

    if any(item.get("status") != "ok" for item in evaluations):
        return "invalid_evaluation", None
    if any(item.get("valid") is not True for item in evaluations):
        return "invalid_evaluation", None

    slot_id = raw.get("slot_id")
    if (
        not isinstance(slot_id, str)
        or temperature.get("slot_id") != slot_id
        or horizon.get("slot_id") != slot_id
    ):
        return "slot_mismatch", None

    captured_at = raw.get("forecast_captured_at")
    if (
        not isinstance(captured_at, str)
        or temperature.get("forecast_captured_at") != captured_at
        or horizon.get("forecast_captured_at") != captured_at
    ):
        return "lock_mismatch", None

    sample: dict[str, Any] = {
        "slot_id": slot_id,
        "forecast_captured_at": captured_at,
        "components": {},
    }

    for roof in ROOFS:
        if any(item.get(f"valid_{roof}") is not True for item in evaluations):
            return "invalid_component", None

        actuals = [
            _finite_number(item.get(f"actual_{roof}_kwh"))
            for item in evaluations
        ]
        forecasts = {
            "raw": _finite_number(raw.get(f"forecast_{roof}_kwh")),
            "temperature": _finite_number(temperature.get(f"forecast_{roof}_kwh")),
            "horizon": _finite_number(horizon.get(f"forecast_{roof}_kwh")),
        }
        coverages = [
            _finite_number(item.get(f"coverage_{roof}_percent"))
            for item in evaluations
        ]
        if any(value is None for value in actuals):
            return "missing_component_value", None
        if any(value is None for value in forecasts.values()):
            return "missing_component_value", None
        if any(value is None for value in coverages):
            return "missing_component_value", None

        actual = float(actuals[0])
        coverage = float(coverages[0])
        if any(abs(float(value) - actual) > 0.000001 for value in actuals[1:]):
            return "actual_mismatch", None
        if any(abs(float(value) - coverage) > 0.000001 for value in coverages[1:]):
            return "coverage_mismatch", None

        component: dict[str, Any] = {
            "actual_kwh": round(actual, 6),
            "coverage_percent": round(coverage, 1),
        }
        for model in MODELS:
            forecast = float(forecasts[model])
            error = forecast - actual
            component[f"{model}_forecast_kwh"] = round(forecast, 6)
            component[f"{model}_error_kwh"] = round(error, 6)
            component[f"{model}_absolute_error_kwh"] = round(abs(error), 6)
        sample["components"][roof] = component

    solar_azimuth = _finite_number(horizon.get("solar_azimuth_deg"))
    solar_elevation = _finite_number(horizon.get("solar_elevation_deg"))
    if solar_azimuth is None or solar_elevation is None:
        return "missing_solar_position", None

    direct_values = (
        _finite_number(horizon.get("north_direct_radiation_wm2")),
        _finite_number(horizon.get("south_direct_radiation_wm2")),
    )
    diffuse_values = (
        _finite_number(horizon.get("north_diffuse_radiation_wm2")),
        _finite_number(horizon.get("south_diffuse_radiation_wm2")),
    )
    if any(value is None for value in (*direct_values, *diffuse_values)):
        return "missing_weather_diagnostics", None

    direct = sum(float(value) for value in direct_values) / 2.0
    diffuse = sum(float(value) for value in diffuse_values) / 2.0
    elevation_band = classify_solar_elevation(solar_elevation)
    azimuth_sector = classify_solar_azimuth(solar_azimuth)
    weather_regime, diffuse_fraction = classify_weather_regime(direct, diffuse)
    if elevation_band is None or azimuth_sector is None or weather_regime is None:
        return "invalid_condition_classification", None

    sample.update(
        {
            "solar_azimuth_deg": round(solar_azimuth, 6),
            "solar_elevation_deg": round(solar_elevation, 6),
            "solar_elevation_band": elevation_band,
            "solar_azimuth_sector": azimuth_sector,
            "direct_radiation_wm2": round(max(0.0, direct), 6),
            "diffuse_radiation_wm2": round(max(0.0, diffuse), 6),
            "diffuse_fraction": diffuse_fraction,
            "weather_regime": weather_regime,
        }
    )
    return "ok", sample


def _empty_component_aggregate() -> dict[str, Any]:
    aggregate: dict[str, Any] = {
        "sample_count": 0,
        "actual_kwh_sum": 0.0,
    }
    for model in MODELS:
        aggregate[f"{model}_forecast_kwh_sum"] = 0.0
        aggregate[f"{model}_error_kwh_sum"] = 0.0
        aggregate[f"{model}_absolute_error_kwh_sum"] = 0.0
    return aggregate


def _add_component(
    aggregate: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    actual = _finite_number(source.get("actual_kwh"))
    if actual is None:
        raise ValueError("invalid actual_kwh")
    aggregate["sample_count"] = max(0, int(aggregate.get("sample_count", 0))) + 1
    aggregate["actual_kwh_sum"] = round(
        float(aggregate.get("actual_kwh_sum", 0.0)) + actual,
        6,
    )
    for model in MODELS:
        for source_key, target_key in (
            (f"{model}_forecast_kwh", f"{model}_forecast_kwh_sum"),
            (f"{model}_error_kwh", f"{model}_error_kwh_sum"),
            (f"{model}_absolute_error_kwh", f"{model}_absolute_error_kwh_sum"),
        ):
            value = _finite_number(source.get(source_key))
            if value is None:
                raise ValueError(f"invalid {source_key}")
            aggregate[target_key] = round(
                float(aggregate.get(target_key, 0.0)) + value,
                6,
            )


def _add_sample_to_bucket(
    buckets: dict[str, Any],
    bucket_key: str,
    sample: Mapping[str, Any],
) -> None:
    bucket = buckets.setdefault(
        bucket_key,
        {
            "sample_count": 0,
            "components": {roof: _empty_component_aggregate() for roof in ROOFS},
        },
    )
    bucket["sample_count"] = max(0, int(bucket.get("sample_count", 0))) + 1
    components = sample.get("components")
    if not isinstance(components, Mapping):
        raise ValueError("sample components are required")
    target_components = bucket.setdefault("components", {})
    for roof in ROOFS:
        source_component = components.get(roof)
        if not isinstance(source_component, Mapping):
            raise ValueError(f"missing {roof} component")
        target = target_components.setdefault(roof, _empty_component_aggregate())
        _add_component(target, source_component)


def new_multimodel_day(date_key: str) -> dict[str, Any]:
    """Return an empty persistent daily F4 aggregate."""
    return {
        "date": date_key,
        "sample_count": 0,
        "first_slot_id": None,
        "last_slot_id": None,
        "components": {roof: _empty_component_aggregate() for roof in ROOFS},
        "breakdowns": {
            "solar_elevation": {},
            "solar_azimuth": {},
            "weather_regime": {},
        },
    }


def add_multimodel_sample(
    day: dict[str, Any],
    sample: Mapping[str, Any],
) -> dict[str, Any]:
    """Add one valid F4 sample to one local-calendar-day aggregate."""
    if not isinstance(day, dict) or not isinstance(sample, Mapping):
        raise ValueError("day and sample are required")
    slot_id = sample.get("slot_id")
    components = sample.get("components")
    if not isinstance(slot_id, str) or not isinstance(components, Mapping):
        raise ValueError("invalid F4 sample")

    day["sample_count"] = max(0, int(day.get("sample_count", 0))) + 1
    if day.get("first_slot_id") is None:
        day["first_slot_id"] = slot_id
    day["last_slot_id"] = slot_id

    day_components = day.setdefault("components", {})
    for roof in ROOFS:
        source_component = components.get(roof)
        if not isinstance(source_component, Mapping):
            raise ValueError(f"missing {roof} component")
        target = day_components.setdefault(roof, _empty_component_aggregate())
        _add_component(target, source_component)

    breakdowns = day.setdefault("breakdowns", {})
    for dimension, sample_key in (
        ("solar_elevation", "solar_elevation_band"),
        ("solar_azimuth", "solar_azimuth_sector"),
        ("weather_regime", "weather_regime"),
    ):
        bucket_key = sample.get(sample_key)
        if not isinstance(bucket_key, str):
            raise ValueError(f"missing {sample_key}")
        buckets = breakdowns.setdefault(dimension, {})
        _add_sample_to_bucket(buckets, bucket_key, sample)
    return day


def _merge_component_aggregate(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    target["sample_count"] = max(0, int(target.get("sample_count", 0))) + max(
        0, int(source.get("sample_count", 0))
    )
    for key in ("actual_kwh_sum",):
        value = _finite_number(source.get(key))
        if value is not None:
            target[key] = round(float(target.get(key, 0.0)) + value, 6)
    for model in MODELS:
        for key in (
            f"{model}_forecast_kwh_sum",
            f"{model}_error_kwh_sum",
            f"{model}_absolute_error_kwh_sum",
        ):
            value = _finite_number(source.get(key))
            if value is not None:
                target[key] = round(float(target.get(key, 0.0)) + value, 6)


def _component_summary(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    actual = _finite_number(aggregate.get("actual_kwh_sum")) or 0.0
    denominator_ok = actual >= EVALUATION_EPSILON_KWH
    result: dict[str, Any] = {
        "sample_count": max(0, int(aggregate.get("sample_count", 0))),
        "actual_kwh": round(actual, 6),
    }
    for model in MODELS:
        forecast = _finite_number(aggregate.get(f"{model}_forecast_kwh_sum")) or 0.0
        error = _finite_number(aggregate.get(f"{model}_error_kwh_sum")) or 0.0
        absolute_error = (
            _finite_number(aggregate.get(f"{model}_absolute_error_kwh_sum")) or 0.0
        )
        result[f"{model}_forecast_kwh"] = round(forecast, 6)
        result[f"{model}_signed_error_kwh"] = round(error, 6)
        result[f"{model}_absolute_error_kwh"] = round(absolute_error, 6)
        result[f"{model}_bias_percent"] = (
            round(100.0 * error / actual, 2) if denominator_ok else None
        )
        result[f"{model}_wape_percent"] = (
            round(100.0 * absolute_error / actual, 2)
            if denominator_ok
            else None
        )
    return result


def _summarize_components(days: list[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for roof in ROOFS:
        aggregate = _empty_component_aggregate()
        for day in days:
            source = day.get("components", {}).get(roof, {})
            if isinstance(source, Mapping):
                _merge_component_aggregate(aggregate, source)
        result[roof] = _component_summary(aggregate)
    return result


def _summarize_breakdown(
    days: list[Mapping[str, Any]],
    dimension: str,
) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for day in days:
        buckets = day.get("breakdowns", {}).get(dimension, {})
        if not isinstance(buckets, Mapping):
            continue
        for key, raw_bucket in buckets.items():
            if not isinstance(key, str) or not isinstance(raw_bucket, Mapping):
                continue
            target = merged.setdefault(
                key,
                {
                    "sample_count": 0,
                    "components": {
                        roof: _empty_component_aggregate() for roof in ROOFS
                    },
                },
            )
            target["sample_count"] = max(0, int(target.get("sample_count", 0))) + max(
                0, int(raw_bucket.get("sample_count", 0))
            )
            source_components = raw_bucket.get("components", {})
            if not isinstance(source_components, Mapping):
                continue
            for roof in ROOFS:
                source = source_components.get(roof)
                if isinstance(source, Mapping):
                    _merge_component_aggregate(target["components"][roof], source)

    result: dict[str, Any] = {}
    for key, bucket in merged.items():
        result[key] = {
            "sample_count": int(bucket.get("sample_count", 0)),
            "metrics": {
                roof: _component_summary(bucket["components"][roof])
                for roof in ROOFS
            },
        }
    return result


def _recent_day_summary(day: Mapping[str, Any]) -> dict[str, Any]:
    one_day = [day]
    breakdowns = day.get("breakdowns", {})
    condition_counts: dict[str, dict[str, int]] = {}
    if isinstance(breakdowns, Mapping):
        for dimension in ("solar_elevation", "solar_azimuth", "weather_regime"):
            buckets = breakdowns.get(dimension, {})
            if isinstance(buckets, Mapping):
                condition_counts[dimension] = {
                    str(key): max(0, int(value.get("sample_count", 0)))
                    for key, value in buckets.items()
                    if isinstance(value, Mapping)
                }
    return {
        "date": day.get("date"),
        "sample_count": max(0, int(day.get("sample_count", 0))),
        "first_slot_id": day.get("first_slot_id"),
        "last_slot_id": day.get("last_slot_id"),
        "metrics": _summarize_components(one_day),
        "condition_counts": condition_counts,
    }


def summarize_multimodel_history(history: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize F4 history without winner or promotion logic."""
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
        "components": _summarize_components(days),
        "breakdown_by_solar_elevation": _summarize_breakdown(
            days, "solar_elevation"
        ),
        "breakdown_by_solar_azimuth": _summarize_breakdown(
            days, "solar_azimuth"
        ),
        "breakdown_by_weather_regime": _summarize_breakdown(
            days, "weather_regime"
        ),
        "recent_days": [_recent_day_summary(day) for day in days[-14:]],
    }
