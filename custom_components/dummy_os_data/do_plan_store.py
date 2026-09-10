"""Pure shadow Plan Store contract for Dummy OS Energy Planner Step 6."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
from typing import Any

SCHEMA_VERSION = 1
SLOT_COUNT = 3
ORIGIN_MANUAL = "manual"
ORIGIN_AUTOMATIC = "automatic_72h_planner"
STATUS_EMPTY = "empty"
STATUS_DRAFT = "draft"
STATUS_PENDING = "pending"
STATUS_BLOCKED = "blocked"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
TERMINAL_STATUSES = {STATUS_CANCELLED, STATUS_EXPIRED, STATUS_COMPLETED, STATUS_FAILED}
VALID_STATUSES = {
    STATUS_EMPTY,
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_BLOCKED,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
}
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


def empty_slot(slot_id: int) -> dict[str, Any]:
    return {
        "slot_id": slot_id,
        "status": STATUS_EMPTY,
        "origin": None,
        "plan_id": None,
        "candidate_id": None,
        "planner_identity": None,
        "planner_signature": None,
        "action": None,
        "reason": None,
        "start_time": None,
        "planned_end_time": None,
        "max_runtime_minutes": None,
        "max_start_delay_minutes": None,
        "power_w": None,
        "planned_energy_kwh": None,
        "target_soc_percent": None,
        "manual_priority": False,
        "created_at": None,
        "updated_at": None,
    }


def new_store_snapshot(now: datetime | None = None) -> dict[str, Any]:
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": stamp,
        "slots": [empty_slot(slot) for slot in range(1, SLOT_COUNT + 1)],
    }


def validate_store_snapshot(snapshot: Any) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if not isinstance(snapshot, dict):
        return False, ["store_payload_invalid"]
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        blockers.append("store_schema_invalid")
    slots = snapshot.get("slots")
    if not isinstance(slots, list) or len(slots) != SLOT_COUNT:
        blockers.append("slot_structure_invalid")
        return False, sorted(set(blockers))
    seen: set[int] = set()
    for expected, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            blockers.append(f"slot_{expected}_invalid")
            continue
        slot_id = slot.get("slot_id")
        if slot_id != expected or slot_id in seen:
            blockers.append(f"slot_{expected}_identity_invalid")
        seen.add(slot_id)
        status = slot.get("status")
        if status not in VALID_STATUSES:
            blockers.append(f"slot_{expected}_status_invalid")
        origin = slot.get("origin")
        if status != STATUS_EMPTY and origin not in {ORIGIN_MANUAL, ORIGIN_AUTOMATIC}:
            blockers.append(f"slot_{expected}_origin_invalid")
        if origin == ORIGIN_MANUAL and slot.get("manual_priority") is not True:
            blockers.append(f"slot_{expected}_manual_priority_invalid")
    return not blockers, sorted(set(blockers))


def _plan_id(origin: str, slot_id: int, now: datetime, signature: str | None = None) -> str:
    anchor = signature or f"slot-{slot_id}"
    compact = abs(hash(anchor)) % 0xFFFFFF
    return f"do-plan-{now.strftime('%Y%m%dT%H%M%SZ')}-{origin[:3]}-{compact:06x}"


def _validate_candidate(candidate: Any, now: datetime) -> list[str]:
    blockers: list[str] = []
    if not isinstance(candidate, dict):
        return ["candidate_invalid"]
    if candidate.get("action") not in VALID_ACTIONS:
        blockers.append("invalid_action")
    start = _utc(candidate.get("start_time"))
    if start is None:
        blockers.append("invalid_start_time")
    elif start <= now:
        blockers.append("candidate_not_future")
    end = _utc(candidate.get("planned_end_time")) if candidate.get("planned_end_time") else None
    duration = _finite(candidate.get("max_runtime_minutes"), non_negative=True)
    if end is None and (duration is None or duration <= 0):
        blockers.append("invalid_duration")
    if end is not None and start is not None and end <= start:
        blockers.append("invalid_duration")
    power = _finite(candidate.get("power_w"), non_negative=True)
    if power is None or power <= 0:
        blockers.append("invalid_power")
    energy = _finite(candidate.get("planned_energy_kwh"), non_negative=True)
    if energy is None or energy <= 0:
        blockers.append("invalid_energy")
    if not candidate.get("candidate_id"):
        blockers.append("candidate_identity_missing")
    if not candidate.get("planner_identity") or not candidate.get("planner_signature"):
        blockers.append("candidate_identity_missing")
    return sorted(set(blockers))


def set_manual_plan(snapshot: dict[str, Any], slot_id: int, plan: dict[str, Any], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    if slot_id not in range(1, SLOT_COUNT + 1):
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    action = plan.get("action")
    start = _utc(plan.get("start_time"))
    power = _finite(plan.get("power_w"), non_negative=True)
    runtime = _finite(plan.get("max_runtime_minutes"), non_negative=True)
    blockers = []
    if action not in VALID_ACTIONS:
        blockers.append("invalid_action")
    if start is None:
        blockers.append("invalid_start_time")
    if power is None or power <= 0:
        blockers.append("invalid_power")
    if runtime is None or runtime <= 0:
        blockers.append("invalid_duration")
    result = deepcopy(snapshot)
    if blockers:
        return result, {"changed": False, "status": STATUS_BLOCKED, "blockers": sorted(set(blockers))}
    stamp = now.astimezone(timezone.utc).isoformat()
    slot = empty_slot(slot_id)
    slot.update({
        "status": STATUS_PENDING,
        "origin": ORIGIN_MANUAL,
        "plan_id": _plan_id(ORIGIN_MANUAL, slot_id, now),
        "action": action,
        "reason": plan.get("reason") or "manual",
        "start_time": start.isoformat(),
        "planned_end_time": plan.get("planned_end_time"),
        "max_runtime_minutes": runtime,
        "max_start_delay_minutes": _finite(plan.get("max_start_delay_minutes"), non_negative=True),
        "power_w": power,
        "planned_energy_kwh": _finite(plan.get("planned_energy_kwh"), non_negative=True),
        "target_soc_percent": _finite(plan.get("target_soc_percent"), non_negative=True),
        "manual_priority": True,
        "created_at": stamp,
        "updated_at": stamp,
    })
    result["slots"][slot_id - 1] = slot
    result["updated_at"] = stamp
    return result, {"changed": True, "status": STATUS_PENDING, "slot_id": slot_id, "blockers": []}


def _revisable(slot: dict[str, Any], now: datetime) -> bool:
    if slot.get("origin") != ORIGIN_AUTOMATIC or slot.get("status") != STATUS_PENDING:
        return False
    start = _utc(slot.get("start_time"))
    return start is not None and now < start


def _expired(slot: dict[str, Any], now: datetime) -> bool:
    if slot.get("origin") != ORIGIN_AUTOMATIC or slot.get("status") != STATUS_PENDING:
        return False
    start = _utc(slot.get("start_time"))
    if start is None:
        return False
    delay = _finite(slot.get("max_start_delay_minutes"), non_negative=True) or 0.0
    return now > start + timedelta(minutes=delay)


def sync_automatic_candidates(snapshot: dict[str, Any], candidates: list[dict[str, Any]], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    result = deepcopy(snapshot)
    written: list[int] = []
    reconciled: list[int] = []
    duplicates: list[str] = []
    rejected: list[dict[str, Any]] = []
    stamp = now.astimezone(timezone.utc).isoformat()

    for candidate in candidates:
        candidate_blockers = _validate_candidate(candidate, now)
        candidate_id = str(candidate.get("candidate_id") or "") if isinstance(candidate, dict) else ""
        if candidate_blockers:
            rejected.append({"candidate_id": candidate_id or None, "blockers": candidate_blockers})
            continue
        signature = str(candidate["planner_signature"])
        identity = str(candidate["planner_identity"])

        duplicate = next((slot for slot in result["slots"] if slot.get("origin") == ORIGIN_AUTOMATIC and slot.get("planner_signature") == signature), None)
        if duplicate is not None:
            duplicates.append(candidate_id)
            continue

        same_identity = next((slot for slot in result["slots"] if _revisable(slot, now) and slot.get("planner_identity") == identity), None)
        target: dict[str, Any] | None = same_identity
        if target is None:
            target = next((slot for slot in result["slots"] if slot.get("status") == STATUS_EMPTY), None)
        if target is None:
            target = next((slot for slot in result["slots"] if slot.get("origin") == ORIGIN_AUTOMATIC and (slot.get("status") in TERMINAL_STATUSES or _expired(slot, now))), None)
        if target is None:
            manual_count = sum(1 for slot in result["slots"] if slot.get("origin") == ORIGIN_MANUAL and slot.get("status") != STATUS_EMPTY)
            rejected.append({"candidate_id": candidate_id, "blockers": ["manual_capacity_full" if manual_count == SLOT_COUNT else "store_capacity_full"]})
            continue
        if target.get("origin") == ORIGIN_MANUAL:
            rejected.append({"candidate_id": candidate_id, "blockers": ["manual_conflict"]})
            continue

        slot_id = int(target["slot_id"])
        was_reconcile = same_identity is not None
        created_at = target.get("created_at") if was_reconcile else stamp
        new_slot = empty_slot(slot_id)
        new_slot.update({
            "status": STATUS_PENDING,
            "origin": ORIGIN_AUTOMATIC,
            "plan_id": target.get("plan_id") if was_reconcile and target.get("plan_id") else _plan_id(ORIGIN_AUTOMATIC, slot_id, now, signature),
            "candidate_id": candidate_id,
            "planner_identity": identity,
            "planner_signature": signature,
            "action": candidate["action"],
            "reason": candidate.get("reason"),
            "start_time": _utc(candidate["start_time"]).isoformat(),
            "planned_end_time": _utc(candidate.get("planned_end_time")).isoformat() if candidate.get("planned_end_time") and _utc(candidate.get("planned_end_time")) else None,
            "max_runtime_minutes": _finite(candidate.get("max_runtime_minutes"), non_negative=True),
            "max_start_delay_minutes": _finite(candidate.get("max_start_delay_minutes"), non_negative=True),
            "power_w": _finite(candidate.get("power_w"), non_negative=True),
            "planned_energy_kwh": _finite(candidate.get("planned_energy_kwh"), non_negative=True),
            "target_soc_percent": _finite(candidate.get("target_soc_percent"), non_negative=True),
            "manual_priority": False,
            "created_at": created_at,
            "updated_at": stamp,
        })
        result["slots"][slot_id - 1] = new_slot
        (reconciled if was_reconcile else written).append(slot_id)

    changed = bool(written or reconciled)
    if changed:
        result["updated_at"] = stamp
    return result, {
        "changed": changed,
        "status": "ready",
        "written_slots": written,
        "reconciled_slots": reconciled,
        "duplicate_candidate_ids": duplicates,
        "rejected_candidates": rejected,
        "blockers": [],
    }


def cleanup_automatic_slots(snapshot: dict[str, Any], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    result = deepcopy(snapshot)
    released: list[int] = []
    stamp = now.astimezone(timezone.utc).isoformat()
    for index, slot in enumerate(result["slots"]):
        if slot.get("origin") != ORIGIN_AUTOMATIC:
            continue
        if _expired(slot, now) or slot.get("status") in TERMINAL_STATUSES:
            result["slots"][index] = empty_slot(int(slot["slot_id"]))
            released.append(int(slot["slot_id"]))
    if released:
        result["updated_at"] = stamp
    return result, {"changed": bool(released), "status": "ready", "released_slots": released, "blockers": []}


def summarize_store(snapshot: Any, *, loaded: bool, persistence_error: str | None = None) -> dict[str, Any]:
    valid, blockers = validate_store_snapshot(snapshot)
    if persistence_error:
        blockers = sorted(set([*blockers, "persistence_write_failed"]))
        valid = False
    slots = snapshot.get("slots", []) if isinstance(snapshot, dict) else []
    if not isinstance(slots, list):
        slots = []
    manual = sum(1 for slot in slots if isinstance(slot, dict) and slot.get("origin") == ORIGIN_MANUAL and slot.get("status") != STATUS_EMPTY)
    automatic = sum(1 for slot in slots if isinstance(slot, dict) and slot.get("origin") == ORIGIN_AUTOMATIC and slot.get("status") != STATUS_EMPTY)
    empty = sum(1 for slot in slots if isinstance(slot, dict) and slot.get("status") == STATUS_EMPTY)
    pending = sum(1 for slot in slots if isinstance(slot, dict) and slot.get("status") == STATUS_PENDING)
    blocked = sum(1 for slot in slots if isinstance(slot, dict) and slot.get("status") == STATUS_BLOCKED)
    return {
        "status": "ready" if valid and loaded else ("initializing" if not loaded else "invalid"),
        "schema_version": snapshot.get("schema_version") if isinstance(snapshot, dict) else None,
        "slot_count": len(slots),
        "occupied_slots": manual + automatic,
        "manual_slots": manual,
        "automatic_slots": automatic,
        "empty_slots": empty,
        "pending_slots": pending,
        "blocked_slots": blocked,
        "store_valid": valid,
        "persistence_loaded": loaded,
        "manual_priority_ok": valid,
        "automatic_reconciliation_ok": valid,
        "blockers": blockers,
        "shadow_only": True,
        "shadow_store_write": True,
        "operational_plan_store_write": False,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "service_calls_performed": False,
    }
