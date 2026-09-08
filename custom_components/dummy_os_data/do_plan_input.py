"""Observer-only 72-hour planner input matrix for Dummy OS Energy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any, Iterable

CONTRACT_NAME = "dummy_os_forecast_to_planner"
CONTRACT_VERSION = 1
SCHEMA_VERSION = 1
PROFILE_CONTRACT_VERSION = 1
SUPPORTED_PROFILES = {"normal", "away"}
PLANNER_HOUR_COUNT = 72
NATIVE_RESOLUTION_MINUTES = 15
NATIVE_SLOT_COUNT = 288
PLANNER_RESOLUTION_MINUTES = 60
QUARTERS_PER_HOUR = 4


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _aware_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finite(value: Any, *, non_negative: bool = False) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if non_negative and number < 0:
        return None
    return number


def _index_points(points: Iterable[Any]) -> dict[datetime, Any]:
    indexed: dict[datetime, Any] = {}
    for point in points:
        start = _aware_utc(_get(point, "start"))
        if start is not None:
            indexed[start] = point
    return indexed


def _validate_contract(contract: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if contract.get("contract_name") != CONTRACT_NAME:
        blockers.append("contract_name_mismatch")
    if contract.get("contract_version") != CONTRACT_VERSION:
        blockers.append("contract_version_mismatch")
    if contract.get("schema_version") != SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if contract.get("profile_contract_version") != PROFILE_CONTRACT_VERSION:
        blockers.append("profile_contract_version_mismatch")
    if contract.get("profile") not in SUPPORTED_PROFILES:
        blockers.append("profile_unclassified")
    if contract.get("ready_for_planner") is not True:
        blockers.append("contract_not_ready_for_planner")
    if contract.get("native_resolution_minutes") != NATIVE_RESOLUTION_MINUTES:
        blockers.append("native_resolution_not_15")
    if contract.get("native_slot_count") != NATIVE_SLOT_COUNT:
        blockers.append("native_slot_count_not_288")
    if contract.get("planner_resolution_minutes") != PLANNER_RESOLUTION_MINUTES:
        blockers.append("planner_resolution_not_60")
    if contract.get("planner_hour_count") != PLANNER_HOUR_COUNT:
        blockers.append("planner_hour_count_not_72")
    if contract.get("quarters_per_hour") != QUARTERS_PER_HOUR:
        blockers.append("quarters_per_hour_not_4")
    if contract.get("padding_used") is not False:
        blockers.append("padding_detected")
    if contract.get("second_forecast_architecture") is not False:
        blockers.append("second_forecast_architecture_detected")
    if contract.get("physical_execution_authority") is not False:
        blockers.append("upstream_physical_authority_not_false")

    hours = contract.get("hours")
    if not isinstance(hours, list) or len(hours) != PLANNER_HOUR_COUNT:
        blockers.append("hours_not_exactly_72")
        return sorted(set(blockers))

    previous_end: datetime | None = None
    for expected_index, hour in enumerate(hours):
        if not isinstance(hour, dict):
            blockers.append(f"hour_{expected_index}_invalid")
            continue
        if hour.get("index") != expected_index:
            blockers.append(f"hour_{expected_index}_index_mismatch")
        start = _aware_utc(hour.get("start"))
        end = _aware_utc(hour.get("end"))
        if start is None or end is None:
            blockers.append(f"hour_{expected_index}_timestamp_invalid")
            continue
        if end - start != timedelta(hours=1):
            blockers.append(f"hour_{expected_index}_duration_not_60m")
        if previous_end is not None and start != previous_end:
            blockers.append(f"hour_{expected_index}_not_contiguous")
        previous_end = end
        if _finite(hour.get("energy_kwh"), non_negative=True) is None:
            blockers.append(f"hour_{expected_index}_home_invalid")
    return sorted(set(blockers))


def _signature(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_do_plan_input_72h(
    *,
    contract: dict[str, Any],
    solar_points: Iterable[Any],
    price_points: Iterable[Any],
    solar_status: str | None = None,
    prices_status: str | None = None,
    prices_freshness: str | None = None,
) -> dict[str, Any]:
    """Join Forecast, Solar and Prices on exact timestamps without fallback.

    The function is deliberately observer-only. It never writes a plan, calls a
    scheduler or exercises physical battery control.
    """
    contract_blockers = _validate_contract(contract)
    base = {
        "profile": contract.get("profile"),
        "native_resolution_minutes": NATIVE_RESOLUTION_MINUTES,
        "native_slot_count": NATIVE_SLOT_COUNT,
        "planner_resolution_minutes": PLANNER_RESOLUTION_MINUTES,
        "planner_hour_count": PLANNER_HOUR_COUNT,
        "quarters_per_hour": QUARTERS_PER_HOUR,
        "planner_start": contract.get("planner_start"),
        "planner_end": contract.get("planner_end"),
        "home_source": "sensor.do_energy_forecast_planner_contract",
        "solar_source": "sensor.do_solar_forecast_timeline",
        "price_source": "sensor.do_prices_timeline",
        "upstream_consumer_scope": contract.get("consumer_scope"),
        "consumer_scope": "dummy_os_energy_internal_planner",
        "runtime_input_status": contract.get("runtime_input_status"),
        "forecast_operational_input_ok": contract.get("forecast_operational_input_ok"),
        "padding_used": False,
        "second_forecast_architecture": False,
        "physical_execution_authority": False,
        "shadow_only": True,
        "active_use_permitted": False,
        "published_pairs": False,
    }
    if contract_blockers:
        return {
            **base,
            "status": "blocked",
            "blockers": contract_blockers,
            "runtime_blockers": list(contract.get("runtime_blockers") or []),
            "hour_count": 0,
            "valid_home_hours": 0,
            "valid_solar_hours": 0,
            "valid_price_hours": 0,
            "fully_valid_hours": 0,
            "missing_solar_hours": PLANNER_HOUR_COUNT,
            "missing_price_hours": PLANNER_HOUR_COUNT,
            "rows_signature": None,
            "rows": [],
        }

    solar_by_start = _index_points(solar_points)
    prices_by_start = _index_points(price_points)
    rows: list[dict[str, Any]] = []
    valid_home_hours = 0
    valid_solar_hours = 0
    valid_price_hours = 0
    fully_valid_hours = 0

    for hour in contract["hours"]:
        start = _aware_utc(hour["start"])
        end = _aware_utc(hour["end"])
        assert start is not None and end is not None
        home = _finite(hour.get("energy_kwh"), non_negative=True)
        home_valid = home is not None
        if home_valid:
            valid_home_hours += 1

        quarter_starts = [
            start + timedelta(minutes=index * NATIVE_RESOLUTION_MINUTES)
            for index in range(QUARTERS_PER_HOUR)
        ]

        solar_values: list[float] = []
        solar_quarters: list[dict[str, Any]] = []
        for quarter_start in quarter_starts:
            point = solar_by_start.get(quarter_start)
            value = _finite(_get(point, "total_kwh"), non_negative=True) if point is not None else None
            solar_quarters.append(
                {"start": quarter_start.isoformat(), "kwh": value}
            )
            if value is not None:
                solar_values.append(value)
        solar_valid = len(solar_values) == QUARTERS_PER_HOUR
        solar_kwh = round(sum(solar_values), 6) if solar_valid else None
        if solar_valid:
            valid_solar_hours += 1

        import_values: list[float] = []
        export_values: list[float] = []
        price_quarters: list[dict[str, Any]] = []
        for quarter_start in quarter_starts:
            point = prices_by_start.get(quarter_start)
            import_price = _finite(_get(point, "import_all_in")) if point is not None else None
            export_price = _finite(_get(point, "export_all_in")) if point is not None else None
            price_quarters.append(
                {
                    "start": quarter_start.isoformat(),
                    "import_price": import_price,
                    "export_price": export_price,
                    "kind": _get(point, "kind") if point is not None else None,
                    "source_resolution_minutes": (
                        _get(point, "source_resolution_minutes") if point is not None else None
                    ),
                }
            )
            if import_price is not None:
                import_values.append(import_price)
            if export_price is not None:
                export_values.append(export_price)
        price_valid = (
            len(import_values) == QUARTERS_PER_HOUR
            and len(export_values) == QUARTERS_PER_HOUR
        )
        import_price = round(sum(import_values) / QUARTERS_PER_HOUR, 6) if price_valid else None
        export_price = round(sum(export_values) / QUARTERS_PER_HOUR, 6) if price_valid else None
        if price_valid:
            valid_price_hours += 1

        fully_valid = home_valid and solar_valid and price_valid
        if fully_valid:
            fully_valid_hours += 1

        rows.append(
            {
                "index": hour["index"],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "profile": contract["profile"],
                "home_kwh": home,
                "solar_kwh": solar_kwh,
                "import_price": import_price,
                "export_price": export_price,
                "home_valid": home_valid,
                "solar_valid": solar_valid,
                "price_valid": price_valid,
                "fully_valid": fully_valid,
                "quarter_count": QUARTERS_PER_HOUR,
                "solar_quarters": solar_quarters,
                "price_quarters": price_quarters,
            }
        )

    blockers: list[str] = []
    if valid_solar_hours != PLANNER_HOUR_COUNT:
        blockers.append("solar_hours_incomplete")
    if valid_price_hours != PLANNER_HOUR_COUNT:
        blockers.append("price_hours_incomplete")

    runtime_blockers = [str(value) for value in (contract.get("runtime_blockers") or [])]
    if contract.get("forecast_operational_input_ok") is not True:
        runtime_blockers.append("forecast_runtime_not_operational")
    if solar_status != "ok":
        runtime_blockers.append(f"solar_runtime_{solar_status or 'unknown'}")
    if prices_status != "ok":
        runtime_blockers.append(f"prices_runtime_{prices_status or 'unknown'}")
    if prices_freshness != "fresh":
        runtime_blockers.append(f"prices_freshness_{prices_freshness or 'unknown'}")
    runtime_blockers = sorted(set(runtime_blockers))

    if blockers:
        status = "partial"
    elif runtime_blockers:
        status = "runtime_blocked"
    else:
        status = "ready"

    return {
        **base,
        "status": status,
        "blockers": blockers,
        "runtime_blockers": runtime_blockers,
        "solar_runtime_status": solar_status,
        "prices_runtime_status": prices_status,
        "prices_freshness": prices_freshness,
        "hour_count": len(rows),
        "valid_home_hours": valid_home_hours,
        "valid_solar_hours": valid_solar_hours,
        "valid_price_hours": valid_price_hours,
        "fully_valid_hours": fully_valid_hours,
        "missing_solar_hours": PLANNER_HOUR_COUNT - valid_solar_hours,
        "missing_price_hours": PLANNER_HOUR_COUNT - valid_price_hours,
        "rows_signature": _signature(rows),
        "rows": rows,
    }
