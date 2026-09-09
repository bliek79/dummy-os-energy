"""Observer-only Step 4 action preview for Dummy OS Energy."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

ENERGY_EPSILON_KWH = 0.01
DEFAULT_CHARGE_EFFICIENCY_PERCENT = 92.0
DEFAULT_DISCHARGE_EFFICIENCY_PERCENT = 92.0
DEFAULT_MINIMUM_TRADE_MARGIN = 0.10
DEFAULT_MAX_CHARGE_POWER_W = 3200
DEFAULT_MAX_DISCHARGE_POWER_W = 3200
SOLAR_PROTECTION_HOURS = 12


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


def _utc(value: Any) -> datetime | None:
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


def _blocked(base: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    return {
        **base,
        "status": "blocked",
        "valid": False,
        "reason": blockers[0],
        "blockers": sorted(set(blockers)),
        "decision": "wait",
        "safety_charge_needed": None,
        "safety_charge_battery_kwh": None,
        "safety_charge_grid_input_kwh": None,
        "safety_schedule_sufficient": None,
        "safety_charge_hours": [],
        "safety_charge_hour_count": 0,
        "free_above_reserve_kwh": None,
        "free_capacity_kwh": None,
        "solar_protection_kwh": None,
        "trade_charge_headroom_kwh": None,
        "best_import_avoidance": None,
        "best_export_trade": None,
        "best_trade_type": None,
        "best_trade_margin": None,
    }


def build_do_plan_preview(
    *,
    input_result: dict[str, Any],
    reserve_result: dict[str, Any],
    now: datetime,
    charge_efficiency_percent: float = DEFAULT_CHARGE_EFFICIENCY_PERCENT,
    discharge_efficiency_percent: float = DEFAULT_DISCHARGE_EFFICIENCY_PERCENT,
    minimum_trade_margin: float = DEFAULT_MINIMUM_TRADE_MARGIN,
    max_charge_power_w: int = DEFAULT_MAX_CHARGE_POWER_W,
    max_discharge_power_w: int = DEFAULT_MAX_DISCHARGE_POWER_W,
) -> dict[str, Any]:
    """Build an observer-only safety/financial preview from Steps 1-3.

    Step 3 remains the sole source of protected reserve position. This layer
    applies efficiencies only to action economics and charge requirements; it
    never recalculates the protected reserve target and never executes actions.
    """
    now_utc = _utc(now)
    charge_eff = _finite(charge_efficiency_percent, non_negative=True)
    discharge_eff = _finite(discharge_efficiency_percent, non_negative=True)
    min_margin = _finite(minimum_trade_margin, non_negative=True)

    base = {
        "input_status": input_result.get("status"),
        "input_rows_signature": input_result.get("rows_signature"),
        "reserve_status": reserve_result.get("status"),
        "reserve_reason": reserve_result.get("reason"),
        "first_usable_solar": reserve_result.get("first_usable_solar"),
        "reserve_soc_target_percent": reserve_result.get("reserve_soc_target_percent"),
        "reserve_deficit_kwh": reserve_result.get("reserve_deficit_kwh"),
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "calculation_scope": "observer_only_safety_and_financial_preview",
        "reserve_source": "do_plan_reserve_soc",
        "reserve_recalculated": False,
        "prices_fallback_used": False,
        "missing_as_zero_used": False,
    }

    blockers: list[str] = []
    if now_utc is None:
        blockers.append("now_invalid")
    if input_result.get("status") != "ready":
        blockers.append("planner_input_not_runtime_ready")
    if input_result.get("fully_valid_hours") != 72:
        blockers.append("planner_input_not_fully_valid")
    rows = input_result.get("rows")
    if not isinstance(rows, list) or len(rows) != 72:
        blockers.append("planner_rows_not_exactly_72")
    if reserve_result.get("status") != "ready" or reserve_result.get("valid") is not True:
        blockers.append("reserve_soc_not_ready")

    if charge_eff is None or not 50.0 <= charge_eff <= 100.0:
        blockers.append("charge_efficiency_invalid")
    if discharge_eff is None or not 50.0 <= discharge_eff <= 100.0:
        blockers.append("discharge_efficiency_invalid")
    if min_margin is None:
        blockers.append("minimum_trade_margin_invalid")
    if max_charge_power_w <= 0:
        blockers.append("max_charge_power_invalid")
    if max_discharge_power_w <= 0:
        blockers.append("max_discharge_power_invalid")

    capacity = _finite(reserve_result.get("battery_capacity_kwh"), non_negative=True)
    soc = _finite(reserve_result.get("soc_percent"), non_negative=True)
    reserve_deficit = _finite(reserve_result.get("reserve_deficit_kwh"), non_negative=True)
    free_above_reserve = _finite(reserve_result.get("free_above_reserve_kwh"), non_negative=True)
    first_usable = _utc(reserve_result.get("first_usable_solar"))
    if capacity is None or capacity <= 0:
        blockers.append("battery_capacity_invalid")
    if soc is None or soc > 100:
        blockers.append("soc_invalid")
    if reserve_deficit is None:
        blockers.append("reserve_deficit_invalid")
    if free_above_reserve is None:
        blockers.append("free_above_reserve_invalid")
    if first_usable is None:
        blockers.append("first_usable_solar_invalid")

    parsed_rows: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict) or raw.get("fully_valid") is not True:
                blockers.append(f"row_{index}_not_fully_valid")
                continue
            start = _utc(raw.get("start"))
            end = _utc(raw.get("end"))
            home = _finite(raw.get("home_kwh"), non_negative=True)
            solar = _finite(raw.get("solar_kwh"), non_negative=True)
            import_price = _finite(raw.get("import_price"))
            export_price = _finite(raw.get("export_price"))
            if None in (start, end, home, solar, import_price, export_price):
                blockers.append(f"row_{index}_invalid")
                continue
            parsed_rows.append(
                {
                    "index": index,
                    "start": start,
                    "end": end,
                    "home_kwh": home,
                    "solar_kwh": solar,
                    "import_price": import_price,
                    "export_price": export_price,
                }
            )

    if blockers:
        return _blocked(base, blockers)

    assert now_utc is not None
    assert charge_eff is not None and discharge_eff is not None and min_margin is not None
    assert capacity is not None and soc is not None
    assert reserve_deficit is not None and free_above_reserve is not None and first_usable is not None
    charge_ratio = charge_eff / 100.0
    discharge_ratio = discharge_eff / 100.0
    roundtrip_ratio = charge_ratio * discharge_ratio

    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    future_rows = [row for row in parsed_rows if row["end"] > now_utc]

    # Safety charge: fill only the Step-3 reserve deficit and only before usable solar.
    safety_charge_needed = reserve_deficit > ENERGY_EPSILON_KWH
    remaining_battery_kwh = reserve_deficit
    safety_hours: list[dict[str, Any]] = []
    safety_candidates = [row for row in future_rows if row["start"] < first_usable]
    safety_candidates.sort(key=lambda row: (row["import_price"], row["start"]))
    for row in safety_candidates:
        if remaining_battery_kwh <= ENERGY_EPSILON_KWH:
            break
        fraction = 1.0
        if row["start"] <= now_utc < row["end"]:
            fraction = max(0.0, min(1.0, (row["end"] - now_utc).total_seconds() / 3600.0))
        battery_capacity_kwh = max_charge_power_w / 1000.0 * fraction * charge_ratio
        if battery_capacity_kwh <= 0:
            continue
        battery_allocated = min(remaining_battery_kwh, battery_capacity_kwh)
        grid_input = battery_allocated / charge_ratio
        safety_hours.append(
            {
                "start": row["start"].isoformat(),
                "end": row["end"].isoformat(),
                "import_price": round(row["import_price"], 6),
                "battery_energy_kwh": round(battery_allocated, 3),
                "grid_input_kwh": round(grid_input, 3),
            }
        )
        remaining_battery_kwh -= battery_allocated
    safety_schedule_sufficient = (not safety_charge_needed) or remaining_battery_kwh <= ENERGY_EPSILON_KWH
    safety_grid_input = reserve_deficit / charge_ratio if safety_charge_needed else 0.0

    # Protect headroom for forecast solar surplus after usable solar returns.
    free_capacity_kwh = capacity * max(100.0 - soc, 0.0) / 100.0
    solar_window = [
        row
        for row in parsed_rows
        if first_usable <= row["start"] < first_usable.replace() and False
    ]
    # datetime.replace() above is deliberately not used for window arithmetic;
    # use timestamps below to stay DST-independent in UTC.
    solar_window_end_ts = first_usable.timestamp() + SOLAR_PROTECTION_HOURS * 3600
    solar_window = [
        row
        for row in parsed_rows
        if first_usable <= row["start"] and row["start"].timestamp() < solar_window_end_ts
    ]
    solar_surplus_ac_kwh = sum(max(row["solar_kwh"] - row["home_kwh"], 0.0) for row in solar_window)
    solar_protection_kwh = min(free_capacity_kwh, solar_surplus_ac_kwh * charge_ratio)
    trade_charge_headroom_kwh = max(free_capacity_kwh - solar_protection_kwh, 0.0)

    # Financial pair search. Import avoidance and export trade are intentionally
    # separate because import and export all-in prices are distinct contracts.
    best_import: dict[str, Any] | None = None
    best_export: dict[str, Any] | None = None
    for i, charge_row in enumerate(future_rows):
        effective_delivered_cost = charge_row["import_price"] / roundtrip_ratio
        for discharge_row in future_rows[i + 1 :]:
            import_margin = discharge_row["import_price"] - effective_delivered_cost
            export_margin = discharge_row["export_price"] - effective_delivered_cost
            import_candidate = {
                "charge_time": charge_row["start"].isoformat(),
                "discharge_time": discharge_row["start"].isoformat(),
                "charge_import_price": round(charge_row["import_price"], 6),
                "avoided_import_price": round(discharge_row["import_price"], 6),
                "effective_charge_cost_per_delivered_kwh": round(effective_delivered_cost, 6),
                "margin_per_delivered_kwh": round(import_margin, 6),
            }
            export_candidate = {
                "charge_time": charge_row["start"].isoformat(),
                "discharge_time": discharge_row["start"].isoformat(),
                "charge_import_price": round(charge_row["import_price"], 6),
                "export_price": round(discharge_row["export_price"], 6),
                "effective_charge_cost_per_exported_kwh": round(effective_delivered_cost, 6),
                "margin_per_exported_kwh": round(export_margin, 6),
            }
            if best_import is None or import_margin > best_import["_margin"]:
                best_import = {**import_candidate, "_margin": import_margin}
            if best_export is None or export_margin > best_export["_margin"]:
                best_export = {**export_candidate, "_margin": export_margin}

    if best_import is not None:
        best_import.pop("_margin", None)
    if best_export is not None:
        best_export.pop("_margin", None)

    import_margin = best_import["margin_per_delivered_kwh"] if best_import else None
    export_margin = best_export["margin_per_exported_kwh"] if best_export else None
    import_profitable = import_margin is not None and import_margin >= min_margin
    export_profitable = export_margin is not None and export_margin >= min_margin

    best_trade_type = None
    best_trade_margin = None
    if import_profitable or export_profitable:
        if export_profitable and (not import_profitable or float(export_margin) > float(import_margin)):
            best_trade_type = "export_trade"
            best_trade_margin = float(export_margin)
        else:
            best_trade_type = "import_avoidance"
            best_trade_margin = float(import_margin)

    if safety_charge_needed:
        decision = "safety_charge" if safety_schedule_sufficient else "safety_charge_insufficient_window"
        reason = "reserve_deficit_has_priority"
    elif solar_protection_kwh > ENERGY_EPSILON_KWH and trade_charge_headroom_kwh <= ENERGY_EPSILON_KWH:
        decision = "hold_capacity_for_solar"
        reason = "forecast_solar_surplus_uses_available_headroom"
    elif best_trade_type is not None and trade_charge_headroom_kwh > ENERGY_EPSILON_KWH:
        decision = best_trade_type
        reason = "financial_margin_above_threshold"
    elif free_above_reserve > ENERGY_EPSILON_KWH and best_trade_type is not None:
        decision = "discharge_opportunity"
        reason = "energy_above_protected_reserve_and_profitable_future_value"
    else:
        decision = "wait"
        reason = "no_priority_action_candidate"

    return {
        **base,
        "status": "ready",
        "valid": True,
        "reason": reason,
        "blockers": [],
        "decision": decision,
        "charge_efficiency_percent": round(charge_eff, 3),
        "discharge_efficiency_percent": round(discharge_eff, 3),
        "roundtrip_efficiency_percent": round(roundtrip_ratio * 100.0, 3),
        "minimum_trade_margin": round(min_margin, 6),
        "max_charge_power_w": int(max_charge_power_w),
        "max_discharge_power_w": int(max_discharge_power_w),
        "safety_charge_needed": safety_charge_needed,
        "safety_charge_battery_kwh": round(reserve_deficit, 3),
        "safety_charge_grid_input_kwh": round(safety_grid_input, 3),
        "safety_schedule_sufficient": safety_schedule_sufficient,
        "safety_charge_hours": safety_hours,
        "safety_charge_hour_count": len(safety_hours),
        "free_above_reserve_kwh": round(free_above_reserve, 3),
        "free_capacity_kwh": round(free_capacity_kwh, 3),
        "solar_surplus_ac_kwh": round(solar_surplus_ac_kwh, 3),
        "solar_protection_kwh": round(solar_protection_kwh, 3),
        "trade_charge_headroom_kwh": round(trade_charge_headroom_kwh, 3),
        "best_import_avoidance": best_import,
        "best_export_trade": best_export,
        "import_avoidance_profitable": import_profitable,
        "export_trade_profitable": export_profitable,
        "best_trade_type": best_trade_type,
        "best_trade_margin": round(best_trade_margin, 6) if best_trade_margin is not None else None,
        "current_hour": current_hour.isoformat(),
    }
