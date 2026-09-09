"""Observer-only Planner Step 5 grid-support trigger and economic charge-window selection."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

BATTERY_CAPACITY_KWH = 7.2
MIN_SOC_PERCENT = 5.0
SAFETY_RESERVE_PERCENT = 7.0
EXECUTION_BUFFER_PERCENT = 2.0
CHARGE_EFFICIENCY_PERCENT = 92.0
DISCHARGE_EFFICIENCY_PERCENT = 92.0
MAX_CHARGE_POWER_W = 3200
DEFAULT_GRID_CHARGE_TRIGGER_KWH = 0.25
NATIVE_RESOLUTION_MINUTES = 15
NATIVE_SLOT_COUNT = 288
PLANNER_HOUR_COUNT = 72
EPS = 0.01


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


def _base(input_result: dict[str, Any], trigger_kwh: float) -> dict[str, Any]:
    return {
        "input_rows_signature": input_result.get("rows_signature"),
        "native_resolution_minutes": NATIVE_RESOLUTION_MINUTES,
        "native_slot_count": NATIVE_SLOT_COUNT,
        "planner_hour_count": PLANNER_HOUR_COUNT,
        "battery_capacity_kwh": BATTERY_CAPACITY_KWH,
        "charge_efficiency_percent": CHARGE_EFFICIENCY_PERCENT,
        "discharge_efficiency_percent": DISCHARGE_EFFICIENCY_PERCENT,
        "max_charge_power_w": MAX_CHARGE_POWER_W,
        "grid_charge_trigger_kwh": round(trigger_kwh, 3),
        "trigger_rule": "additional_grid_charge_kwh > grid_charge_trigger_kwh",
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "plan_store_write": False,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "service_calls_performed": False,
        "safety_priority_over_trade": True,
        "missing_as_zero_used": False,
        "price_direction": "import_only",
    }


def _blocked(base: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    return {
        **base,
        "status": "blocked",
        "valid": False,
        "reason": blockers[0],
        "blockers": sorted(set(blockers)),
        "trigger_active": False,
        "raw_shortfall_kwh": None,
        "chargeable_battery_kwh": None,
        "required_grid_input_kwh": None,
        "unavoidable_shortfall_kwh": None,
        "critical_deadline": None,
        "selected_slot_count": 0,
        "selected_slots": [],
        "planned_grid_input_kwh": 0.0,
        "planned_battery_charge_kwh": 0.0,
        "unallocated_grid_input_kwh": None,
        "estimated_import_cost_eur": None,
    }


def _critical_deadline(
    *,
    rows: list[dict[str, Any]],
    soc_percent: float,
    first_usable_solar: datetime | None,
) -> datetime | None:
    """Return the conservative hour boundary before protected energy would be breached."""
    stored = BATTERY_CAPACITY_KWH * soc_percent / 100.0
    protected_floor = BATTERY_CAPACITY_KWH * (
        MIN_SOC_PERCENT + SAFETY_RESERVE_PERCENT + EXECUTION_BUFFER_PERCENT
    ) / 100.0
    charge_eff = CHARGE_EFFICIENCY_PERCENT / 100.0
    discharge_eff = DISCHARGE_EFFICIENCY_PERCENT / 100.0

    for row in rows:
        start = _utc(row.get("start"))
        if start is None:
            return None
        if first_usable_solar is not None and start >= first_usable_solar:
            break
        home = _finite(row.get("home_kwh"), non_negative=True)
        solar = _finite(row.get("solar_kwh"), non_negative=True)
        if home is None or solar is None:
            return None
        if solar >= home:
            surplus = solar - home
            stored += min(
                surplus * charge_eff,
                max(0.0, BATTERY_CAPACITY_KWH - stored),
                MAX_CHARGE_POWER_W / 1000.0 * charge_eff,
            )
            continue
        deficit = home - solar
        battery_required = deficit / discharge_eff
        if stored - battery_required < protected_floor - EPS:
            return start
        stored -= battery_required

    return first_usable_solar


def _quarter_slots(rows: list[dict[str, Any]], deadline: datetime) -> tuple[list[dict[str, Any]], list[str]]:
    slots: list[dict[str, Any]] = []
    blockers: list[str] = []
    max_slot_input = MAX_CHARGE_POWER_W / 1000.0 * (NATIVE_RESOLUTION_MINUTES / 60.0)
    for row in rows:
        prices = row.get("price_quarters")
        solar = row.get("solar_quarters")
        if not isinstance(prices, list) or len(prices) != 4:
            blockers.append(f"row_{row.get('index')}_price_quarters_invalid")
            continue
        if not isinstance(solar, list) or len(solar) != 4:
            blockers.append(f"row_{row.get('index')}_solar_quarters_invalid")
            continue
        for idx, price_point in enumerate(prices):
            if not isinstance(price_point, dict):
                blockers.append("price_quarter_invalid")
                continue
            start = _utc(price_point.get("start"))
            price = _finite(price_point.get("import_price"))
            solar_kwh = _finite(solar[idx].get("kwh"), non_negative=True) if isinstance(solar[idx], dict) else None
            if start is None or solar_kwh is None:
                blockers.append("quarter_timestamp_or_solar_invalid")
                continue
            if start >= deadline:
                continue
            if price is None:
                blockers.append(f"price_missing_{start.isoformat()}")
                continue
            # Solar is always first. Without quarter-level home demand we reserve the
            # complete forecast solar quarter against the shared 3200 W charge input.
            # This is deliberately conservative and never fabricates extra headroom.
            grid_headroom_kwh = max(0.0, max_slot_input - solar_kwh)
            slots.append(
                {
                    "start": start.isoformat(),
                    "import_price": price,
                    "source_resolution_minutes": price_point.get("source_resolution_minutes"),
                    "kind": price_point.get("kind"),
                    "solar_kwh": solar_kwh,
                    "grid_input_headroom_kwh": round(grid_headroom_kwh, 6),
                }
            )
    return slots, blockers


def build_do_plan_grid_support(
    *,
    input_result: dict[str, Any],
    energy_need_result: dict[str, Any],
    trigger_kwh: float = DEFAULT_GRID_CHARGE_TRIGGER_KWH,
) -> dict[str, Any]:
    """Build a diagnostic grid-charge candidate without execution authority."""
    trigger = _finite(trigger_kwh, non_negative=True)
    base = _base(input_result, trigger if trigger is not None else DEFAULT_GRID_CHARGE_TRIGGER_KWH)
    blockers: list[str] = []
    if trigger is None:
        blockers.append("grid_charge_trigger_invalid")
    if input_result.get("status") != "ready":
        blockers.append("planner_input_not_ready")
    if input_result.get("fully_valid_hours") != PLANNER_HOUR_COUNT:
        blockers.append("planner_input_not_fully_valid")
    rows = input_result.get("rows")
    if not isinstance(rows, list) or len(rows) != PLANNER_HOUR_COUNT:
        blockers.append("rows_not_exactly_72")
    if energy_need_result.get("status") != "ready" or energy_need_result.get("valid") is not True:
        blockers.append("energy_need_not_ready")
    if energy_need_result.get("input_rows_signature") != input_result.get("rows_signature"):
        blockers.append("input_signature_mismatch")

    raw_shortfall = _finite(energy_need_result.get("additional_grid_charge_kwh"), non_negative=True)
    soc = _finite(energy_need_result.get("soc_percent"), non_negative=True)
    first_solar = _utc(energy_need_result.get("first_usable_solar"))
    if raw_shortfall is None:
        blockers.append("additional_grid_charge_invalid")
    if soc is None or soc > 100:
        blockers.append("soc_invalid")
    if first_solar is None:
        blockers.append("first_usable_solar_invalid")
    if blockers:
        return _blocked(base, blockers)

    assert trigger is not None and raw_shortfall is not None and soc is not None and first_solar is not None and isinstance(rows, list)
    free_capacity_battery = BATTERY_CAPACITY_KWH * max(100.0 - soc, 0.0) / 100.0
    chargeable_battery = min(raw_shortfall, free_capacity_battery)
    unavoidable = max(raw_shortfall - chargeable_battery, 0.0)
    required_grid_input = chargeable_battery / (CHARGE_EFFICIENCY_PERCENT / 100.0) if chargeable_battery > EPS else 0.0
    trigger_active = raw_shortfall > trigger + EPS

    common = {
        **base,
        "raw_shortfall_kwh": round(raw_shortfall, 3),
        "soc_percent": round(soc, 3),
        "free_capacity_battery_kwh": round(free_capacity_battery, 3),
        "chargeable_battery_kwh": round(chargeable_battery, 3),
        "required_grid_input_kwh": round(required_grid_input, 3),
        "unavoidable_shortfall_kwh": round(unavoidable, 3),
        "first_usable_solar": first_solar.isoformat(),
        "trigger_active": trigger_active,
    }

    if not trigger_active:
        return {
            **common,
            "status": "ready",
            "valid": True,
            "reason": "shortfall_below_grid_charge_trigger",
            "blockers": [],
            "critical_deadline": None,
            "selected_slot_count": 0,
            "selected_slots": [],
            "planned_grid_input_kwh": 0.0,
            "planned_battery_charge_kwh": 0.0,
            "unallocated_grid_input_kwh": 0.0,
            "estimated_import_cost_eur": 0.0,
            "selection_method": "no_charge_below_trigger",
        }

    if chargeable_battery <= EPS:
        return {
            **common,
            "status": "infeasible",
            "valid": False,
            "reason": "shortfall_exceeds_trigger_but_battery_has_no_charge_capacity",
            "blockers": ["battery_charge_capacity_unavailable"],
            "critical_deadline": first_solar.isoformat(),
            "selected_slot_count": 0,
            "selected_slots": [],
            "planned_grid_input_kwh": 0.0,
            "planned_battery_charge_kwh": 0.0,
            "unallocated_grid_input_kwh": round(required_grid_input, 3),
            "estimated_import_cost_eur": None,
            "selection_method": "no_capacity",
        }

    deadline = _critical_deadline(rows=rows, soc_percent=soc, first_usable_solar=first_solar)
    if deadline is None:
        return _blocked(base, ["critical_deadline_not_resolvable"])

    slots, slot_blockers = _quarter_slots(rows, deadline)
    # Missing price in any pre-deadline quarter is fail-closed: a zero/nearest price
    # may never be invented for an economic safety decision.
    missing_price_blockers = [b for b in slot_blockers if b.startswith("price_missing_")]
    if missing_price_blockers:
        return {
            **common,
            "status": "blocked",
            "valid": False,
            "reason": "eligible_price_data_incomplete",
            "blockers": missing_price_blockers,
            "critical_deadline": deadline.isoformat(),
            "selected_slot_count": 0,
            "selected_slots": [],
            "planned_grid_input_kwh": 0.0,
            "planned_battery_charge_kwh": 0.0,
            "unallocated_grid_input_kwh": round(required_grid_input, 3),
            "estimated_import_cost_eur": None,
            "selection_method": "fail_closed_missing_price",
        }

    # Economic order: lowest true all-in import price first. For practically equal
    # prices (<= 0.1 eurocent/kWh), prefer the later still-safe slot to preserve
    # flexibility and reduce the chance of displacing later solar.
    price_bucket = 0.001
    slots.sort(key=lambda item: (round(item["import_price"] / price_bucket), -_utc(item["start"]).timestamp()))

    remaining = required_grid_input
    selected: list[dict[str, Any]] = []
    cost = 0.0
    charge_eff = CHARGE_EFFICIENCY_PERCENT / 100.0
    for slot in slots:
        if remaining <= EPS:
            break
        headroom = _finite(slot.get("grid_input_headroom_kwh"), non_negative=True) or 0.0
        if headroom <= EPS:
            continue
        allocated = min(headroom, remaining)
        battery_added = allocated * charge_eff
        selected.append(
            {
                **slot,
                "grid_input_kwh": round(allocated, 6),
                "battery_charge_kwh": round(battery_added, 6),
                "estimated_cost_eur": round(allocated * slot["import_price"], 6),
            }
        )
        cost += allocated * slot["import_price"]
        remaining -= allocated

    planned_grid = max(0.0, required_grid_input - remaining)
    planned_battery = planned_grid * charge_eff
    feasible = remaining <= EPS
    source_resolutions = sorted({slot.get("source_resolution_minutes") for slot in selected if slot.get("source_resolution_minutes") is not None})

    return {
        **common,
        "status": "ready" if feasible else "infeasible",
        "valid": feasible,
        "reason": "economic_grid_charge_candidate_ready" if feasible else "insufficient_safe_charge_capacity_before_deadline",
        "blockers": [] if feasible else ["safe_charge_window_capacity_insufficient"],
        "critical_deadline": deadline.isoformat(),
        "selected_slot_count": len(selected),
        "selected_slots": selected,
        "planned_grid_input_kwh": round(planned_grid, 3),
        "planned_battery_charge_kwh": round(planned_battery, 3),
        "unallocated_grid_input_kwh": round(max(remaining, 0.0), 3),
        "estimated_import_cost_eur": round(cost, 4),
        "selection_method": "true_import_price_then_later_safe_tiebreak",
        "source_resolution_minutes_seen": source_resolutions,
        "solar_first_headroom_rule": "quarter solar input conservatively reserves shared 3200W charge headroom before grid",
        "candidate_resimulation_required": True,
        "candidate_resimulation_scope": "existing_step5_baseline_candidate_72h",
    }
