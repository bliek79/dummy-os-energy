"""Observer-only Energy Need analysis for the Dummy OS Energy planner."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

DEFAULT_BATTERY_CAPACITY_KWH = 7.2
DEFAULT_MIN_SOC_PERCENT = 5.0
DEFAULT_SAFETY_RESERVE_PERCENT = 7.0
ENERGY_EPSILON_KWH = 0.01


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


def _aware(value: Any) -> datetime | None:
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


def build_do_plan_energy_need(
    *,
    input_result: dict[str, Any],
    soc_percent: float | None,
    battery_capacity_kwh: float = DEFAULT_BATTERY_CAPACITY_KWH,
    min_soc_percent: float = DEFAULT_MIN_SOC_PERCENT,
    safety_reserve_percent: float = DEFAULT_SAFETY_RESERVE_PERCENT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculate the energy balance until sustainably usable solar returns."""
    rows = input_result.get("rows")
    base = {
        "input_status": input_result.get("status"),
        "input_rows_signature": input_result.get("rows_signature"),
        "battery_capacity_kwh": battery_capacity_kwh,
        "min_soc_percent": min_soc_percent,
        "safety_reserve_percent": safety_reserve_percent,
        "usable_solar_rule": "first of two consecutive complete planner hours where solar_kwh >= home_kwh and solar_kwh > 0",
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
    }
    blockers: list[str] = []
    if not isinstance(rows, list) or len(rows) != 72:
        blockers.append("input_rows_not_exactly_72")
    if input_result.get("status") not in {"ready", "runtime_blocked"}:
        blockers.append("planner_input_not_structurally_ready")
    if input_result.get("fully_valid_hours") != 72:
        blockers.append("planner_input_not_fully_valid")

    capacity = _finite(battery_capacity_kwh, non_negative=True)
    min_soc = _finite(min_soc_percent, non_negative=True)
    reserve_percent = _finite(safety_reserve_percent, non_negative=True)
    soc = _finite(soc_percent, non_negative=True)
    if capacity is None or capacity <= 0:
        blockers.append("battery_capacity_invalid")
    if min_soc is None or min_soc > 100:
        blockers.append("min_soc_invalid")
    if reserve_percent is None or reserve_percent > 30:
        blockers.append("safety_reserve_invalid")
    if soc is None or soc > 100:
        blockers.append("soc_unavailable")

    if blockers:
        return {**base, "status": "blocked", "valid": False, "reason": blockers[0], "blockers": sorted(set(blockers)), "soc_percent": soc, "energy_need_until_solar_kwh": None, "first_usable_solar": None, "available_battery_kwh": None, "safety_reserve_kwh": None, "required_including_reserve_kwh": None, "additional_grid_charge_kwh": None, "tradable_battery_kwh": None, "contributing_hours": 0.0}

    assert capacity is not None and min_soc is not None and reserve_percent is not None and soc is not None
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    current_hour = reference.replace(minute=0, second=0, microsecond=0)

    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return {**base, "status": "blocked", "valid": False, "reason": f"row_{index}_invalid", "blockers": [f"row_{index}_invalid"], "soc_percent": soc}
        start = _aware(row.get("start"))
        home = _finite(row.get("home_kwh"), non_negative=True)
        solar = _finite(row.get("solar_kwh"), non_negative=True)
        if start is None:
            return {**base, "status": "blocked", "valid": False, "reason": f"row_{index}_timestamp_invalid", "blockers": [f"row_{index}_timestamp_invalid"], "soc_percent": soc}
        normalized.append({"start": start, "home": home, "solar": solar})

    usable_index: int | None = None
    for index in range(len(normalized) - 1):
        current = normalized[index]
        following = normalized[index + 1]
        if current["start"] < current_hour:
            continue
        if current["home"] is None or current["solar"] is None or following["home"] is None or following["solar"] is None:
            continue
        if current["solar"] > 0 and current["solar"] >= current["home"] and following["solar"] > 0 and following["solar"] >= following["home"]:
            usable_index = index
            break

    if usable_index is None:
        return {**base, "status": "waiting_for_usable_solar", "valid": False, "reason": "no_two_consecutive_usable_solar_hours_within_horizon", "blockers": ["usable_solar_not_found"], "soc_percent": soc, "energy_need_until_solar_kwh": None, "first_usable_solar": None, "available_battery_kwh": None, "safety_reserve_kwh": None, "required_including_reserve_kwh": None, "additional_grid_charge_kwh": None, "tradable_battery_kwh": None, "contributing_hours": 0.0}

    net_need_kwh = 0.0
    contributing_hours = 0.0
    relevant_missing: list[str] = []
    for index, row in enumerate(normalized[:usable_index]):
        if row["start"] < current_hour:
            continue
        home = row["home"]
        solar = row["solar"]
        if home is None:
            relevant_missing.append(f"row_{index}_home_missing")
            continue
        if solar is None:
            relevant_missing.append(f"row_{index}_solar_missing")
            continue
        fraction = 1.0
        if row["start"] == current_hour:
            elapsed = reference.minute / 60.0 + reference.second / 3600.0
            fraction = max(0.0, min(1.0, 1.0 - elapsed))
        net_need_kwh += max(home - solar, 0.0) * fraction
        contributing_hours += fraction

    if relevant_missing:
        return {**base, "status": "blocked", "valid": False, "reason": "relevant_input_missing", "blockers": relevant_missing, "soc_percent": soc, "energy_need_until_solar_kwh": None, "first_usable_solar": normalized[usable_index]["start"].isoformat(), "available_battery_kwh": None, "safety_reserve_kwh": None, "required_including_reserve_kwh": None, "additional_grid_charge_kwh": None, "tradable_battery_kwh": None, "contributing_hours": round(contributing_hours, 3)}

    usable_soc_percent = max(soc - min_soc, 0.0)
    available_battery_kwh = capacity * usable_soc_percent / 100.0
    reserve_kwh = capacity * reserve_percent / 100.0
    required_including_reserve = net_need_kwh + reserve_kwh
    additional_grid_charge_kwh = max(required_including_reserve - available_battery_kwh, 0.0)
    tradable_battery_kwh = max(available_battery_kwh - required_including_reserve, 0.0)
    reason = "additional_energy_required_for_need_plus_reserve" if additional_grid_charge_kwh > ENERGY_EPSILON_KWH else "battery_covers_need_plus_reserve"
    return {**base, "status": "ready", "valid": True, "reason": reason, "blockers": [], "soc_percent": round(soc, 3), "energy_need_until_solar_kwh": round(net_need_kwh, 3), "first_usable_solar": normalized[usable_index]["start"].isoformat(), "available_battery_kwh": round(available_battery_kwh, 3), "safety_reserve_kwh": round(reserve_kwh, 3), "required_including_reserve_kwh": round(required_including_reserve, 3), "additional_grid_charge_kwh": round(additional_grid_charge_kwh, 3), "tradable_battery_kwh": round(tradable_battery_kwh, 3), "contributing_hours": round(contributing_hours, 3)}
