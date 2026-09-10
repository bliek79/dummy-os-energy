"""Pure shadow-only Safety and Prestart evaluation for Dummy OS Energy."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

MAX_POWER_W = 3200.0
EXECUTION_BUFFER_PERCENT = 2.0
VALID_ACTIONS = {"charge", "discharge"}


def _finite(value: Any, *, non_negative: bool = False) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or (non_negative and number < 0):
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


def _signature(kind: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"kind": kind, **payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _flags() -> dict[str, Any]:
    return {
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "operational_plan_store_write": False,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "execution_handoff_performed": False,
        "service_calls_performed": False,
        "plan_store_mutated": False,
        "mode_switch_performed": False,
    }


def build_do_plan_safety(
    *,
    scheduler_result: Any,
    store_snapshot: Any,
    reserve_result: Any,
    soc_percent: Any,
    now: datetime,
) -> dict[str, Any]:
    """Validate the Scheduler-selected plan without mutating or executing it."""
    now_utc = _utc(now)
    evaluated_at = now_utc.isoformat() if now_utc else None
    base = {
        "status": "blocked",
        "safety_status": "blocked",
        "safety_ready": False,
        "selected_slot_id": None,
        "selected_plan_id": None,
        "selected_action": None,
        "selected_origin": None,
        "power_w": None,
        "planned_energy_kwh": None,
        "target_soc_percent": None,
        "current_soc_percent": None,
        "reserve_soc_target_percent": None,
        "execution_floor_soc_percent": None,
        "max_power_w": MAX_POWER_W,
        "max_runtime_minutes": None,
        "decision_signature": None,
        "safety_signature": None,
        "evaluated_at": evaluated_at,
        "blockers": [],
        **_flags(),
    }
    blockers: list[str] = []
    if now_utc is None:
        blockers.append("safety_input_time_invalid")
    if not isinstance(scheduler_result, dict) or scheduler_result.get("scheduler_status") != "ready" or scheduler_result.get("scheduler_ready") is not True:
        blockers.append("scheduler_not_ready")
    if not isinstance(store_snapshot, dict) or not isinstance(store_snapshot.get("slots"), list):
        blockers.append("selected_plan_missing")
        slots = []
    else:
        slots = store_snapshot["slots"]

    slot_id = scheduler_result.get("selected_slot_id") if isinstance(scheduler_result, dict) else None
    plan_id = scheduler_result.get("selected_plan_id") if isinstance(scheduler_result, dict) else None
    decision_signature = scheduler_result.get("decision_signature") if isinstance(scheduler_result, dict) else None
    selected = next((slot for slot in slots if isinstance(slot, dict) and slot.get("slot_id") == slot_id), None)
    if selected is None:
        blockers.append("selected_plan_missing")
    elif not plan_id or selected.get("plan_id") != plan_id:
        blockers.append("selected_plan_identity_mismatch")
    elif selected.get("status") != "pending":
        blockers.append("selected_slot_not_pending")

    soc = _finite(soc_percent, non_negative=True)
    if soc is None or soc > 100:
        blockers.append("soc_unavailable")
    reserve_target = None
    if not isinstance(reserve_result, dict) or reserve_result.get("status") != "ready" or reserve_result.get("valid") is not True:
        blockers.append("reserve_not_ready")
    else:
        reserve_target = _finite(reserve_result.get("reserve_soc_target_percent"), non_negative=True)
        if reserve_target is None or reserve_target > 100:
            blockers.append("reserve_target_invalid")
    execution_floor = min(100.0, reserve_target + EXECUTION_BUFFER_PERCENT) if reserve_target is not None else None

    action = selected.get("action") if selected else None
    power = _finite(selected.get("power_w"), non_negative=True) if selected else None
    energy = _finite(selected.get("planned_energy_kwh"), non_negative=True) if selected else None
    runtime = _finite(selected.get("max_runtime_minutes"), non_negative=True) if selected else None
    target = _finite(selected.get("target_soc_percent"), non_negative=True) if selected else None
    if selected:
        if action not in VALID_ACTIONS:
            blockers.append("action_invalid")
        if power is None or power <= 0:
            blockers.append("power_invalid")
        elif power > MAX_POWER_W:
            blockers.append("power_above_limit")
        if runtime is None or runtime <= 0:
            blockers.append("runtime_invalid")
        if energy is None or energy <= 0:
            blockers.append("planned_energy_invalid")
        if target is None or target > 100:
            blockers.append("target_soc_invalid")
        if action == "charge" and soc is not None and target is not None and target <= soc:
            blockers.append("charge_target_not_above_current_soc")
        if action == "discharge" and soc is not None and execution_floor is not None and soc <= execution_floor:
            blockers.append("discharge_current_soc_at_or_below_floor")
        if action == "discharge" and target is not None and execution_floor is not None and target < execution_floor:
            blockers.append("discharge_target_below_execution_floor")

    unique_blockers = sorted(set(blockers))
    ready = not unique_blockers
    status = "ready" if ready else ("idle" if "scheduler_not_ready" in unique_blockers and len(unique_blockers) == 1 else "blocked")
    signature_payload = {
        "decision_signature": decision_signature,
        "slot_id": slot_id,
        "plan_id": plan_id,
        "action": action,
        "power_w": power,
        "energy_kwh": energy,
        "runtime_minutes": runtime,
        "target_soc": target,
        "soc": soc,
        "reserve_target": reserve_target,
        "execution_floor": execution_floor,
        "status": status,
        "blockers": unique_blockers,
    }
    base.update({
        "status": status,
        "safety_status": status,
        "safety_ready": ready,
        "selected_slot_id": slot_id,
        "selected_plan_id": plan_id,
        "selected_action": action,
        "selected_origin": selected.get("origin") if selected else None,
        "power_w": power,
        "planned_energy_kwh": energy,
        "target_soc_percent": target,
        "current_soc_percent": soc,
        "reserve_soc_target_percent": reserve_target,
        "execution_floor_soc_percent": execution_floor,
        "max_runtime_minutes": runtime,
        "decision_signature": decision_signature,
        "safety_signature": _signature("safety", signature_payload),
        "blockers": unique_blockers,
    })
    return base


def build_do_plan_prestart(
    *,
    scheduler_result: Any,
    safety_result: Any,
    store_snapshot: Any,
    now: datetime,
) -> dict[str, Any]:
    """Revalidate identity, timing and Safety readiness without execution."""
    now_utc = _utc(now)
    blockers: list[str] = []
    scheduler = scheduler_result if isinstance(scheduler_result, dict) else {}
    safety = safety_result if isinstance(safety_result, dict) else {}
    slot_id = scheduler.get("selected_slot_id")
    plan_id = scheduler.get("selected_plan_id")
    if now_utc is None:
        blockers.append("prestart_time_invalid")
    if scheduler.get("scheduler_status") != "ready" or scheduler.get("scheduler_ready") is not True:
        blockers.append("scheduler_not_ready")
    if safety.get("safety_status") != "ready" or safety.get("safety_ready") is not True:
        blockers.append("safety_not_ready")
    if safety.get("selected_slot_id") != slot_id or safety.get("selected_plan_id") != plan_id:
        blockers.append("safety_identity_mismatch")
    slots = store_snapshot.get("slots") if isinstance(store_snapshot, dict) else None
    selected = next((slot for slot in slots or [] if isinstance(slot, dict) and slot.get("slot_id") == slot_id), None)
    if selected is None:
        blockers.append("selected_plan_missing")
    elif selected.get("plan_id") != plan_id or selected.get("status") != "pending":
        blockers.append("selected_plan_identity_mismatch")
    start = _utc(scheduler.get("selected_start_time"))
    window_end = _utc(scheduler.get("selected_window_end"))
    if start is None or window_end is None:
        blockers.append("prestart_window_invalid")
    elif now_utc is not None:
        if now_utc < start:
            blockers.append("prestart_before_window")
        elif now_utc > window_end:
            blockers.append("prestart_window_expired")
    unique_blockers = sorted(set(blockers))
    if not unique_blockers:
        status = "ready"
    elif unique_blockers == ["prestart_before_window"]:
        status = "waiting"
    elif "scheduler_not_ready" in unique_blockers and not plan_id:
        status = "idle"
    else:
        status = "blocked"
    signature_payload = {
        "scheduler_signature": scheduler.get("decision_signature"),
        "safety_signature": safety.get("safety_signature"),
        "slot_id": slot_id,
        "plan_id": plan_id,
        "start": start.isoformat() if start else None,
        "window_end": window_end.isoformat() if window_end else None,
        "status": status,
        "blockers": unique_blockers,
    }
    return {
        "status": status,
        "prestart_status": status,
        "prestart_ready": status == "ready",
        "selected_slot_id": slot_id,
        "selected_plan_id": plan_id,
        "selected_action": scheduler.get("selected_action"),
        "selected_origin": scheduler.get("selected_origin"),
        "selected_start_time": start.isoformat() if start else scheduler.get("selected_start_time"),
        "selected_window_end": window_end.isoformat() if window_end else scheduler.get("selected_window_end"),
        "scheduler_status": scheduler.get("scheduler_status"),
        "scheduler_ready": scheduler.get("scheduler_ready") is True,
        "safety_status": safety.get("safety_status"),
        "safety_ready": safety.get("safety_ready") is True,
        "scheduler_decision_signature": scheduler.get("decision_signature"),
        "safety_signature": safety.get("safety_signature"),
        "prestart_signature": _signature("prestart", signature_payload),
        "evaluated_at": now_utc.isoformat() if now_utc else None,
        "blockers": unique_blockers,
        **_flags(),
    }
