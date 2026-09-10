"""Pure shadow-only manual Plan Store interface for Dummy OS Energy."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any

from .do_plan_store import ORIGIN_AUTOMATIC, ORIGIN_MANUAL, SLOT_COUNT, STATUS_EMPTY, VALID_ACTIONS, validate_store_snapshot

MAX_POWER_W = 3200.0
VALID_SLOT_OPTIONS = tuple(f"slot_{slot_id}" for slot_id in range(1, SLOT_COUNT + 1))


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime): parsed = value
    elif isinstance(value, str):
        try: parsed = datetime.fromisoformat(value)
        except ValueError: return None
    else: return None
    if parsed.tzinfo is None: return None
    return parsed.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    try: number = float(value)
    except (TypeError, ValueError): return None
    return number if math.isfinite(number) else None


def _slot_id(option: Any) -> int | None:
    if not isinstance(option, str) or option not in VALID_SLOT_OPTIONS: return None
    return int(option.rsplit("_", 1)[1])


def _flags() -> dict[str, Any]:
    return {"shadow_only": True, "manual_interface_write": False, "shadow_store_write": False, "operational_plan_store_write": False, "plan_store_mutated": False, "scheduler_invoked": False, "safety_chain_invoked": False, "execution_handoff_performed": False, "service_calls_performed": False, "physical_execution_authority": False, "mode_switch_performed": False, "command_dispatched": False}


def build_do_plan_manual_interface(*, store_snapshot: Any, store_summary: Any, selected_slot: Any, now: datetime) -> dict[str, Any]:
    """Read and validate one selected Plan Store slot without mutating it."""
    current = _utc(now)
    summary = store_summary if isinstance(store_summary, dict) else {}
    snapshot = deepcopy(store_snapshot)
    blockers: list[str] = []
    if current is None: blockers.append("manual_interface_time_invalid")
    store_valid, store_blockers = validate_store_snapshot(snapshot)
    if not store_valid: blockers.extend(store_blockers or ["store_invalid"])
    if summary.get("status") != "ready": blockers.append("store_not_ready")
    if summary.get("persistence_loaded") is not True: blockers.append("store_not_loaded")
    if summary.get("manual_priority_ok") is not True: blockers.append("manual_priority_not_ok")
    slot_id = _slot_id(selected_slot)
    if slot_id is None: blockers.append("selected_slot_invalid")
    slots = snapshot.get("slots") if isinstance(snapshot, dict) else None
    slot = next((item for item in slots or [] if isinstance(item, dict) and item.get("slot_id") == slot_id), None) if slot_id else None
    if slot_id is not None and slot is None: blockers.append("selected_slot_missing")
    slot_blockers: list[str] = []
    availability = "blocked"
    if isinstance(slot, dict):
        status, origin = slot.get("status"), slot.get("origin")
        if status == STATUS_EMPTY: availability = "available"
        elif origin == ORIGIN_MANUAL:
            availability = "manual_owned"
            if slot.get("manual_priority") is not True: slot_blockers.append("manual_priority_invalid")
            if slot.get("action") not in VALID_ACTIONS: slot_blockers.append("manual_action_invalid")
            if _utc(slot.get("start_time")) is None: slot_blockers.append("manual_start_time_invalid")
            power = _finite(slot.get("power_w"))
            if power is None or power <= 0 or power > MAX_POWER_W: slot_blockers.append("manual_power_invalid")
            runtime = _finite(slot.get("max_runtime_minutes"))
            if runtime is None or runtime <= 0: slot_blockers.append("manual_runtime_invalid")
            target = _finite(slot.get("target_soc_percent"))
            if target is None or not 0.0 <= target <= 100.0: slot_blockers.append("manual_target_soc_invalid")
            if not slot.get("plan_id"): slot_blockers.append("manual_plan_id_missing")
        elif origin == ORIGIN_AUTOMATIC: availability = "automatic_owned"
        else:
            availability = "invalid_owned"
            slot_blockers.append("selected_slot_origin_invalid")
    blockers.extend(slot_blockers)
    blockers = sorted(set(blockers))
    if blockers: interface_status, selection_valid = "blocked", False
    elif availability == "available": interface_status, selection_valid = "available", True
    elif availability == "manual_owned": interface_status, selection_valid = "manual_plan", True
    elif availability == "automatic_owned": interface_status, selection_valid = "occupied_automatic", True
    else: interface_status, selection_valid = "blocked", False
    return {"status": interface_status, "interface_status": interface_status, "selection_valid": selection_valid, "selected_slot": selected_slot if slot_id else None, "selected_slot_id": slot_id, "slot_availability": availability, "slot_status": slot.get("status") if isinstance(slot, dict) else None, "slot_origin": slot.get("origin") if isinstance(slot, dict) else None, "plan_id": slot.get("plan_id") if isinstance(slot, dict) else None, "action": slot.get("action") if isinstance(slot, dict) else None, "reason": slot.get("reason") if isinstance(slot, dict) else None, "start_time": slot.get("start_time") if isinstance(slot, dict) else None, "planned_end_time": slot.get("planned_end_time") if isinstance(slot, dict) else None, "max_runtime_minutes": slot.get("max_runtime_minutes") if isinstance(slot, dict) else None, "max_start_delay_minutes": slot.get("max_start_delay_minutes") if isinstance(slot, dict) else None, "power_w": slot.get("power_w") if isinstance(slot, dict) else None, "planned_energy_kwh": slot.get("planned_energy_kwh") if isinstance(slot, dict) else None, "target_soc_percent": slot.get("target_soc_percent") if isinstance(slot, dict) else None, "manual_priority": slot.get("manual_priority") if isinstance(slot, dict) else False, "created_at": slot.get("created_at") if isinstance(slot, dict) else None, "updated_at": slot.get("updated_at") if isinstance(slot, dict) else None, "store_status": summary.get("status"), "store_valid": store_valid, "persistence_loaded": summary.get("persistence_loaded"), "manual_priority_ok": summary.get("manual_priority_ok"), "evaluated_at": current.isoformat() if current else None, "blockers": blockers, **_flags()}
