"""Pure shadow-only Execution Preview for Dummy OS Energy."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

VALID_ACTIONS = {"charge", "discharge"}


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


def _signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
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
        "command_dispatched": False,
    }


def build_do_plan_execution_preview(
    *,
    scheduler_result: Any,
    safety_result: Any,
    prestart_result: Any,
    store_snapshot: Any,
    now: datetime,
) -> dict[str, Any]:
    """Build a read-only preview of the action that would be executed later."""
    current = _utc(now)
    scheduler = scheduler_result if isinstance(scheduler_result, dict) else {}
    safety = safety_result if isinstance(safety_result, dict) else {}
    prestart = prestart_result if isinstance(prestart_result, dict) else {}
    blockers: list[str] = []

    if current is None:
        blockers.append("execution_preview_time_invalid")

    scheduler_ready = scheduler.get("scheduler_status") == "ready" and scheduler.get("scheduler_ready") is True
    safety_ready = safety.get("safety_status") == "ready" and safety.get("safety_ready") is True
    prestart_status = prestart.get("prestart_status")
    prestart_ready = prestart_status == "ready" and prestart.get("prestart_ready") is True

    if not scheduler_ready:
        blockers.append("scheduler_not_ready")
    if not safety_ready:
        blockers.append("safety_not_ready")
    if not prestart_ready:
        blockers.append("prestart_not_ready")

    slot_id = scheduler.get("selected_slot_id")
    plan_id = scheduler.get("selected_plan_id")
    identities = [
        ("scheduler", scheduler.get("selected_slot_id"), scheduler.get("selected_plan_id")),
        ("safety", safety.get("selected_slot_id"), safety.get("selected_plan_id")),
        ("prestart", prestart.get("selected_slot_id"), prestart.get("selected_plan_id")),
    ]
    if any(item[1] != slot_id or item[2] != plan_id for item in identities[1:]):
        blockers.append("upstream_identity_mismatch")

    slots = store_snapshot.get("slots") if isinstance(store_snapshot, dict) else None
    selected = next(
        (
            item
            for item in slots or []
            if isinstance(item, dict) and item.get("slot_id") == slot_id
        ),
        None,
    )
    if selected is None:
        blockers.append("selected_plan_missing")
    else:
        if selected.get("plan_id") != plan_id:
            blockers.append("selected_plan_identity_mismatch")
        if selected.get("status") != "pending":
            blockers.append("selected_slot_not_pending")
        if selected.get("action") not in VALID_ACTIONS:
            blockers.append("action_invalid")

    if selected is not None:
        if scheduler.get("selected_action") != selected.get("action"):
            blockers.append("scheduler_action_mismatch")
        if safety.get("selected_action") != selected.get("action"):
            blockers.append("safety_action_mismatch")
        if prestart.get("selected_action") != selected.get("action"):
            blockers.append("prestart_action_mismatch")

    unique_blockers = sorted(set(blockers))
    if not unique_blockers:
        status = "ready"
    elif prestart_status == "waiting" and set(unique_blockers).issubset({"prestart_not_ready"}):
        status = "waiting"
    elif not plan_id and "scheduler_not_ready" in unique_blockers:
        status = "idle"
    else:
        status = "blocked"

    slot = deepcopy(selected) if isinstance(selected, dict) else {}
    payload = {
        "slot_id": slot_id,
        "plan_id": plan_id,
        "action": slot.get("action"),
        "origin": slot.get("origin"),
        "power_w": slot.get("power_w"),
        "planned_energy_kwh": slot.get("planned_energy_kwh"),
        "target_soc_percent": slot.get("target_soc_percent"),
        "max_runtime_minutes": slot.get("max_runtime_minutes"),
        "start_time": slot.get("start_time"),
        "planned_end_time": slot.get("planned_end_time"),
        "scheduler_signature": scheduler.get("decision_signature"),
        "safety_signature": safety.get("safety_signature"),
        "prestart_signature": prestart.get("prestart_signature"),
        "status": status,
        "blockers": unique_blockers,
    }

    return {
        "status": status,
        "execution_preview_status": status,
        "execution_preview_ready": status == "ready",
        "selected_slot_id": slot_id,
        "selected_plan_id": plan_id,
        "selected_origin": slot.get("origin"),
        "action": slot.get("action"),
        "power_w": slot.get("power_w"),
        "planned_energy_kwh": slot.get("planned_energy_kwh"),
        "target_soc_percent": slot.get("target_soc_percent"),
        "max_runtime_minutes": slot.get("max_runtime_minutes"),
        "selected_start_time": slot.get("start_time"),
        "selected_planned_end_time": slot.get("planned_end_time"),
        "selected_window_end": scheduler.get("selected_window_end"),
        "scheduler_decision_signature": scheduler.get("decision_signature"),
        "safety_signature": safety.get("safety_signature"),
        "prestart_signature": prestart.get("prestart_signature"),
        "execution_preview_signature": _signature(payload),
        "evaluated_at": current.isoformat() if current else None,
        "blockers": unique_blockers,
        **_flags(),
    }
