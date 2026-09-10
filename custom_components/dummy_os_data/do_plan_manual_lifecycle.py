"""Pure manual planning lifecycle for the three-slot Dummy OS Plan Store.

This module contains no Home Assistant service calls and no physical control path.
It validates and transforms shadow Plan Store snapshots only.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any

from .do_plan_store import (
    ORIGIN_AUTOMATIC,
    ORIGIN_MANUAL,
    SLOT_COUNT,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_EMPTY,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    VALID_ACTIONS,
    empty_slot,
    validate_store_snapshot,
)

MAX_POWER_W = 3200.0
MIN_SOC_PERCENT = 5.0
MAX_SOC_PERCENT = 100.0
MIN_RUNTIME_MINUTES = 15.0
MAX_RUNTIME_MINUTES = 24.0 * 60.0
MAX_START_DELAY_MINUTES = 60.0
QUARTER_MINUTES = 15
TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_EXPIRED, STATUS_FAILED, "cancelled"}
EDITABLE_MANUAL_STATUSES = {STATUS_PENDING, STATUS_BLOCKED, STATUS_DRAFT}


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


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _quarter_aligned(value: datetime) -> bool:
    return value.second == 0 and value.microsecond == 0 and value.minute % QUARTER_MINUTES == 0


def _slot(snapshot: dict[str, Any], slot_id: int) -> dict[str, Any] | None:
    slots = snapshot.get("slots") if isinstance(snapshot, dict) else None
    if not isinstance(slots, list) or slot_id not in range(1, SLOT_COUNT + 1):
        return None
    candidate = slots[slot_id - 1]
    return candidate if isinstance(candidate, dict) and candidate.get("slot_id") == slot_id else None


def _signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reservation_window(slot_like: dict[str, Any]) -> tuple[datetime, datetime] | None:
    start = _utc(slot_like.get("start_time"))
    runtime = _finite(slot_like.get("max_runtime_minutes"))
    delay = _finite(slot_like.get("max_start_delay_minutes")) or 0.0
    if start is None or runtime is None or runtime <= 0 or delay < 0:
        return None
    end = start + timedelta(minutes=runtime + delay)
    declared = _utc(slot_like.get("planned_end_time"))
    if declared is not None and declared > end:
        end = declared
    return start, end


def _overlaps(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _base_draft(slot_id: int, *, mode: str, now: datetime) -> dict[str, Any]:
    stamp = now.astimezone(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "slot_id": slot_id,
        "mode": mode,
        "status": STATUS_DRAFT,
        "base_plan_id": None,
        "base_updated_at": None,
        "action": None,
        "start_time": None,
        "power_w": None,
        "target_soc_percent": None,
        "max_runtime_minutes": 60.0,
        "max_start_delay_minutes": 10.0,
        "planned_end_time": None,
        "planned_energy_kwh": None,
        "created_at": stamp,
        "updated_at": stamp,
        "validation_status": "not_validated",
        "validation_blockers": [],
        "draft_signature": None,
    }


def new_manual_draft(snapshot: dict[str, Any], slot_id: int, now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a draft descriptor without changing the Plan Store snapshot."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return {}, {"status": "blocked", "blockers": blockers}
    slot = _slot(snapshot, slot_id)
    if slot is None:
        return {}, {"status": "blocked", "blockers": ["slot_structure_invalid"]}
    if slot.get("status") != STATUS_EMPTY:
        return {}, {"status": "blocked", "blockers": ["selected_slot_not_empty"]}
    return _base_draft(slot_id, mode="new", now=now), {"status": STATUS_DRAFT, "blockers": []}


def edit_manual_draft(snapshot: dict[str, Any], slot_id: int, now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create an editable draft from an existing manual plan without mutating it."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return {}, {"status": "blocked", "blockers": blockers}
    slot = _slot(snapshot, slot_id)
    if slot is None:
        return {}, {"status": "blocked", "blockers": ["slot_structure_invalid"]}
    if slot.get("origin") != ORIGIN_MANUAL:
        return {}, {"status": "blocked", "blockers": ["selected_slot_not_manual"]}
    if slot.get("status") == STATUS_RUNNING:
        return {}, {"status": "blocked", "blockers": ["running_plan_not_editable"]}
    if slot.get("status") not in EDITABLE_MANUAL_STATUSES:
        return {}, {"status": "blocked", "blockers": ["manual_plan_not_editable"]}

    draft = _base_draft(slot_id, mode="edit", now=now)
    for field in (
        "action",
        "start_time",
        "power_w",
        "target_soc_percent",
        "max_runtime_minutes",
        "max_start_delay_minutes",
        "planned_end_time",
        "planned_energy_kwh",
    ):
        draft[field] = slot.get(field)
    draft["base_plan_id"] = slot.get("plan_id")
    draft["base_updated_at"] = slot.get("updated_at")
    return draft, {"status": STATUS_DRAFT, "blockers": []}


def patch_manual_draft(draft: dict[str, Any], changes: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Return a changed draft and invalidate any previous validation."""
    result = deepcopy(draft)
    allowed = {
        "action",
        "start_time",
        "power_w",
        "target_soc_percent",
        "max_runtime_minutes",
        "max_start_delay_minutes",
    }
    for key, value in changes.items():
        if key in allowed:
            result[key] = value
    result["status"] = STATUS_DRAFT
    result["updated_at"] = now.astimezone(timezone.utc).isoformat()
    result["validation_status"] = "not_validated"
    result["validation_blockers"] = []
    result["draft_signature"] = None
    result["planned_end_time"] = None
    result["planned_energy_kwh"] = None
    return result


def validate_manual_draft(
    draft: Any,
    snapshot: Any,
    now: datetime,
) -> dict[str, Any]:
    """Validate a manual draft against current store state and overlap rules."""
    blockers: list[str] = []
    valid_store, store_blockers = validate_store_snapshot(snapshot)
    if not valid_store:
        blockers.extend(store_blockers)
    if not isinstance(draft, dict):
        return {"status": "invalid", "valid": False, "blockers": ["draft_invalid"]}

    slot_id = draft.get("slot_id")
    if slot_id not in range(1, SLOT_COUNT + 1):
        blockers.append("slot_structure_invalid")
        slot = None
    else:
        slot = _slot(snapshot, int(slot_id)) if valid_store else None
        if slot is None:
            blockers.append("selected_slot_missing")

    mode = draft.get("mode")
    if mode not in {"new", "edit"}:
        blockers.append("draft_mode_invalid")

    if isinstance(slot, dict):
        if slot.get("status") == STATUS_RUNNING:
            blockers.append("running_plan_not_editable")
        if mode == "new" and slot.get("status") != STATUS_EMPTY:
            blockers.append("selected_slot_not_empty")
        if mode == "edit":
            if slot.get("origin") != ORIGIN_MANUAL:
                blockers.append("selected_slot_not_manual")
            if slot.get("status") not in EDITABLE_MANUAL_STATUSES:
                blockers.append("manual_plan_not_editable")
            if slot.get("plan_id") != draft.get("base_plan_id") or slot.get("updated_at") != draft.get("base_updated_at"):
                blockers.append("draft_base_stale")

    action = draft.get("action")
    if action not in VALID_ACTIONS:
        blockers.append("invalid_action")

    start = _utc(draft.get("start_time"))
    if start is None:
        blockers.append("invalid_start_time")
    else:
        if start <= now.astimezone(timezone.utc):
            blockers.append("start_not_future")
        if not _quarter_aligned(start):
            blockers.append("start_not_quarter_aligned")

    power = _finite(draft.get("power_w"))
    if power is None or power <= 0:
        blockers.append("invalid_power")
    elif power > MAX_POWER_W:
        blockers.append("power_above_limit")

    target = _finite(draft.get("target_soc_percent"))
    if target is None:
        blockers.append("invalid_target_soc")
    elif not MIN_SOC_PERCENT <= target <= MAX_SOC_PERCENT:
        blockers.append("target_soc_out_of_range")

    runtime = _finite(draft.get("max_runtime_minutes"))
    if runtime is None or runtime < MIN_RUNTIME_MINUTES or runtime > MAX_RUNTIME_MINUTES:
        blockers.append("invalid_duration")
    elif runtime % QUARTER_MINUTES != 0:
        blockers.append("runtime_not_quarter_aligned")

    delay = _finite(draft.get("max_start_delay_minutes"))
    if delay is None or delay < 0 or delay > MAX_START_DELAY_MINUTES:
        blockers.append("invalid_start_delay")

    planned_end = None
    planned_energy = None
    if start is not None and runtime is not None and runtime > 0:
        planned_end = start + timedelta(minutes=runtime)
    if power is not None and power > 0 and runtime is not None and runtime > 0:
        planned_energy = power * runtime / 60.0 / 1000.0

    candidate = deepcopy(draft)
    candidate["planned_end_time"] = planned_end.isoformat() if planned_end else None
    candidate["planned_energy_kwh"] = round(planned_energy, 6) if planned_energy is not None else None
    candidate_window = _reservation_window(candidate)
    overlaps: list[int] = []
    if valid_store and candidate_window is not None and isinstance(slot_id, int):
        for other in snapshot.get("slots", []):
            if not isinstance(other, dict) or other.get("slot_id") == slot_id:
                continue
            if other.get("status") == STATUS_EMPTY or other.get("status") in TERMINAL_STATUSES:
                continue
            other_window = _reservation_window(other)
            if other_window is not None and _overlaps(candidate_window, other_window):
                overlaps.append(int(other.get("slot_id")))
        if overlaps:
            blockers.append("plan_overlap")

    normalized = {
        "slot_id": slot_id,
        "mode": mode,
        "base_plan_id": draft.get("base_plan_id"),
        "base_updated_at": draft.get("base_updated_at"),
        "action": action,
        "start_time": start.isoformat() if start else None,
        "power_w": power,
        "target_soc_percent": target,
        "max_runtime_minutes": runtime,
        "max_start_delay_minutes": delay,
        "planned_end_time": planned_end.isoformat() if planned_end else None,
        "planned_energy_kwh": round(planned_energy, 6) if planned_energy is not None else None,
    }
    signature = _signature(normalized)
    unique = sorted(set(blockers))
    return {
        "status": "valid" if not unique else "invalid",
        "valid": not unique,
        "blockers": unique,
        "overlap_slot_ids": sorted(overlaps),
        "normalized": normalized,
        "draft_signature": signature,
        "reservation_start": candidate_window[0].isoformat() if candidate_window else None,
        "reservation_end": candidate_window[1].isoformat() if candidate_window else None,
    }


def _manual_plan_id(slot_id: int, now: datetime, signature: str) -> str:
    compact = hashlib.sha256(f"{slot_id}|{signature}".encode("utf-8")).hexdigest()[:10]
    return f"do-plan-{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-man-{compact}"


def finalize_manual_draft(
    snapshot: dict[str, Any],
    draft: dict[str, Any],
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Atomically transform one valid draft into a manual pending Plan Store slot."""
    validation = validate_manual_draft(draft, snapshot, now)
    if not validation["valid"]:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, **validation}

    normalized = validation["normalized"]
    slot_id = int(normalized["slot_id"])
    current = _slot(snapshot, slot_id)
    if current is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["selected_slot_missing"]}

    # Idempotent retry after a successful finalize with the same normalized draft.
    if (
        current.get("origin") == ORIGIN_MANUAL
        and current.get("manual_draft_signature") == validation["draft_signature"]
        and current.get("status") == STATUS_PENDING
    ):
        return deepcopy(snapshot), {
            "changed": False,
            "status": STATUS_PENDING,
            "idempotent": True,
            "slot_id": slot_id,
            "plan_id": current.get("plan_id"),
            "blockers": [],
            "draft_signature": validation["draft_signature"],
        }

    result = deepcopy(snapshot)
    stamp = now.astimezone(timezone.utc).isoformat()
    editing = normalized["mode"] == "edit"
    plan_id = current.get("plan_id") if editing else _manual_plan_id(slot_id, now, validation["draft_signature"])
    created_at = current.get("created_at") if editing else stamp
    revision = int(current.get("manual_revision") or 0) + 1 if editing else 1

    slot = empty_slot(slot_id)
    slot.update(
        {
            "status": STATUS_PENDING,
            "origin": ORIGIN_MANUAL,
            "plan_id": plan_id,
            "action": normalized["action"],
            "reason": "manual",
            "start_time": normalized["start_time"],
            "planned_end_time": normalized["planned_end_time"],
            "max_runtime_minutes": normalized["max_runtime_minutes"],
            "max_start_delay_minutes": normalized["max_start_delay_minutes"],
            "power_w": normalized["power_w"],
            "planned_energy_kwh": normalized["planned_energy_kwh"],
            "target_soc_percent": normalized["target_soc_percent"],
            "manual_priority": True,
            "manual_revision": revision,
            "manual_draft_signature": validation["draft_signature"],
            "created_at": created_at,
            "updated_at": stamp,
        }
    )
    result["slots"][slot_id - 1] = slot
    result["updated_at"] = stamp
    return result, {
        "changed": True,
        "status": STATUS_PENDING,
        "idempotent": False,
        "slot_id": slot_id,
        "plan_id": plan_id,
        "manual_revision": revision,
        "draft_signature": validation["draft_signature"],
        "blockers": [],
    }


def clear_manual_slot(
    snapshot: dict[str, Any],
    slot_id: int,
    now: datetime,
    *,
    expected_plan_id: str | None = None,
    expected_updated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Clear one non-running manual slot with optional optimistic-concurrency guards."""
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": blockers}
    slot = _slot(snapshot, slot_id)
    if slot is None:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["slot_structure_invalid"]}
    if slot.get("status") == STATUS_EMPTY:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_EMPTY, "idempotent": True, "blockers": []}
    if slot.get("origin") != ORIGIN_MANUAL:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["automatic_slot_not_clearable"]}
    if slot.get("status") == STATUS_RUNNING:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["running_plan_not_clearable"]}
    if expected_plan_id is not None and slot.get("plan_id") != expected_plan_id:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["clear_base_stale"]}
    if expected_updated_at is not None and slot.get("updated_at") != expected_updated_at:
        return deepcopy(snapshot), {"changed": False, "status": STATUS_BLOCKED, "blockers": ["clear_base_stale"]}

    result = deepcopy(snapshot)
    result["slots"][slot_id - 1] = empty_slot(slot_id)
    result["updated_at"] = now.astimezone(timezone.utc).isoformat()
    return result, {"changed": True, "status": STATUS_EMPTY, "slot_id": slot_id, "blockers": []}
