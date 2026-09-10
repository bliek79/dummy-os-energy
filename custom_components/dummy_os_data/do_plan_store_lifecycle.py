"""Lifecycle and manual-ownership helpers for Planner Step 6 shadow Plan Store."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .do_plan_store import (
    ORIGIN_AUTOMATIC,
    ORIGIN_MANUAL,
    SLOT_COUNT,
    STATUS_BLOCKED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_EMPTY,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    VALID_ACTIONS,
    _finite,
    _utc,
    empty_slot,
    validate_store_snapshot,
)

# Status mutation is intentionally explicit. Step 6 owns storage only; it does
# not decide when Scheduler, Safety or Execution may invoke these transitions.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_EMPTY: {STATUS_DRAFT},
    STATUS_DRAFT: {STATUS_PENDING, STATUS_BLOCKED, STATUS_CANCELLED},
    STATUS_BLOCKED: {STATUS_DRAFT, STATUS_CANCELLED},
    STATUS_PENDING: {STATUS_RUNNING, STATUS_EXPIRED, STATUS_CANCELLED},
    STATUS_RUNNING: {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED},
    STATUS_CANCELLED: set(),
    STATUS_EXPIRED: set(),
    STATUS_COMPLETED: set(),
    STATUS_FAILED: set(),
}

_MANUAL_EDITABLE_FIELDS = {
    "action",
    "reason",
    "start_time",
    "planned_end_time",
    "max_runtime_minutes",
    "max_start_delay_minutes",
    "power_w",
    "planned_energy_kwh",
    "target_soc_percent",
}


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()


def _slot(snapshot: dict[str, Any], slot_id: int) -> dict[str, Any] | None:
    if slot_id not in range(1, SLOT_COUNT + 1):
        return None
    slots = snapshot.get("slots")
    if not isinstance(slots, list) or len(slots) != SLOT_COUNT:
        return None
    item = slots[slot_id - 1]
    return item if isinstance(item, dict) else None


def apply_manual_edit(
    snapshot: dict[str, Any],
    slot_id: int,
    changes: dict[str, Any],
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a user edit and immediately claim the slot for manual ownership.

    This mirrors the proven EMS rule that any entity edit removes planner
    ownership. The improved Step-6 contract additionally moves the slot to
    ``draft`` until it passes an explicit finalize validation.
    """
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    current = _slot(snapshot, slot_id)
    if current is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    unknown = sorted(set(changes) - _MANUAL_EDITABLE_FIELDS)
    if unknown:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["manual_edit_field_invalid"]}

    result = deepcopy(snapshot)
    target = result["slots"][slot_id - 1]
    # A terminal manual plan is editable again only by explicit user action;
    # editing begins a new draft lifecycle in the same physical slot.
    if target.get("status") == STATUS_EMPTY:
        target = empty_slot(slot_id)
        result["slots"][slot_id - 1] = target

    for key, value in changes.items():
        if key in {"start_time", "planned_end_time"} and value is not None:
            parsed = _utc(value)
            value = parsed.isoformat() if parsed is not None else value
        target[key] = value

    target["status"] = STATUS_DRAFT
    target["origin"] = ORIGIN_MANUAL
    target["manual_priority"] = True
    target["candidate_id"] = None
    target["planner_identity"] = None
    target["planner_signature"] = None
    target["updated_at"] = _stamp(now)
    if not target.get("created_at"):
        target["created_at"] = _stamp(now)
    if not target.get("plan_id"):
        # Manual draft identity only needs to be unique inside the persistent
        # store. It is deliberately independent from planner identity.
        target["plan_id"] = f"do-plan-manual-{slot_id}-{int(now.timestamp())}"
    result["updated_at"] = _stamp(now)
    return result, {"changed": True, "status": STATUS_DRAFT, "slot_id": slot_id, "blockers": []}


def validate_manual_plan(slot: dict[str, Any], now: datetime) -> list[str]:
    blockers: list[str] = []
    if slot.get("origin") != ORIGIN_MANUAL or slot.get("manual_priority") is not True:
        blockers.append("manual_ownership_invalid")
    if slot.get("action") not in VALID_ACTIONS:
        blockers.append("invalid_action")
    start = _utc(slot.get("start_time"))
    if start is None:
        blockers.append("invalid_start_time")
    elif start <= now:
        blockers.append("manual_start_not_future")
    end = _utc(slot.get("planned_end_time")) if slot.get("planned_end_time") else None
    runtime = _finite(slot.get("max_runtime_minutes"), non_negative=True)
    if end is None and (runtime is None or runtime <= 0):
        blockers.append("invalid_duration")
    if end is not None and start is not None and end <= start:
        blockers.append("invalid_duration")
    power = _finite(slot.get("power_w"), non_negative=True)
    if power is None or power <= 0:
        blockers.append("invalid_power")
    target_soc = slot.get("target_soc_percent")
    if target_soc is not None:
        parsed_soc = _finite(target_soc, non_negative=True)
        if parsed_soc is None or parsed_soc > 100:
            blockers.append("invalid_target_soc")
    return sorted(set(blockers))


def finalize_manual_plan(
    snapshot: dict[str, Any], slot_id: int, now: datetime
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Promote one manually owned draft to pending after structural validation."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    current = _slot(snapshot, slot_id)
    if current is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    blockers = validate_manual_plan(current, now)
    if blockers:
        result = deepcopy(snapshot)
        result["slots"][slot_id - 1]["status"] = STATUS_BLOCKED
        result["slots"][slot_id - 1]["updated_at"] = _stamp(now)
        result["updated_at"] = _stamp(now)
        return result, {"changed": True, "status": STATUS_BLOCKED, "slot_id": slot_id, "blockers": blockers}
    result = deepcopy(snapshot)
    result["slots"][slot_id - 1]["status"] = STATUS_PENDING
    result["slots"][slot_id - 1]["updated_at"] = _stamp(now)
    result["updated_at"] = _stamp(now)
    return result, {"changed": True, "status": STATUS_PENDING, "slot_id": slot_id, "blockers": []}


def cancel_plan(
    snapshot: dict[str, Any], slot_id: int, now: datetime, *, reason: str = "cancelled_by_user"
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Cancel a stored plan without invoking Scheduler or Execution."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    current = _slot(snapshot, slot_id)
    if current is None or current.get("status") == STATUS_EMPTY:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["plan_not_present"]}
    if current.get("status") in {STATUS_COMPLETED, STATUS_FAILED, STATUS_EXPIRED, STATUS_CANCELLED}:
        return deepcopy(snapshot), {"changed": False, "status": str(current.get("status")), "blockers": ["plan_terminal"]}
    result = deepcopy(snapshot)
    target = result["slots"][slot_id - 1]
    target["status"] = STATUS_CANCELLED
    target["reason"] = reason
    target["updated_at"] = _stamp(now)
    result["updated_at"] = _stamp(now)
    return result, {"changed": True, "status": STATUS_CANCELLED, "slot_id": slot_id, "blockers": []}


def clear_manual_plan(
    snapshot: dict[str, Any], slot_id: int, now: datetime
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Explicitly release a manually owned terminal/draft slot back to empty."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    current = _slot(snapshot, slot_id)
    if current is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    if current.get("origin") != ORIGIN_MANUAL:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["manual_ownership_required"]}
    if current.get("status") == STATUS_RUNNING:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["running_plan_cannot_clear"]}
    result = deepcopy(snapshot)
    result["slots"][slot_id - 1] = empty_slot(slot_id)
    result["updated_at"] = _stamp(now)
    return result, {"changed": True, "status": STATUS_EMPTY, "slot_id": slot_id, "blockers": []}


def transition_plan_status(
    snapshot: dict[str, Any],
    slot_id: int,
    new_status: str,
    now: datetime,
    *,
    reason: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one validated lifecycle transition without side effects.

    This function is intentionally passive: it never decides *when* a scheduler
    or execution layer should call it and therefore grants no execution authority.
    """
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    current = _slot(snapshot, slot_id)
    if current is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    current_status = str(current.get("status"))
    if new_status not in _ALLOWED_TRANSITIONS.get(current_status, set()):
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["lifecycle_transition_invalid"]}
    result = deepcopy(snapshot)
    target = result["slots"][slot_id - 1]
    target["status"] = new_status
    if reason is not None:
        target["reason"] = reason
    target["updated_at"] = _stamp(now)
    result["updated_at"] = _stamp(now)
    return result, {"changed": True, "status": new_status, "slot_id": slot_id, "blockers": []}


def store_lifecycle_capabilities() -> dict[str, Any]:
    """Expose non-operational capabilities for diagnostics/tests."""
    return {
        "manual_edit_claims_slot": True,
        "manual_finalize_required": True,
        "manual_clear_requires_explicit_action": True,
        "automatic_pending_reconciliation": True,
        "automatic_cleanup_manual_protected": True,
        "validated_lifecycle_transitions": True,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "service_calls_performed": False,
        "physical_execution_authority": False,
    }
