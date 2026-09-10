"""Pure observer-only Scheduler for Dummy OS Energy Planner Step 7."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any

SLOT_COUNT = 3
VALID_ACTIONS = {"charge", "discharge"}
TERMINAL_STATUSES = {"completed", "cancelled", "failed", "expired"}
NON_STARTABLE_STATUSES = {"empty", "draft", "blocked", *TERMINAL_STATUSES}


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


def _finite_non_negative(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _quarter_bucket(now: datetime) -> str:
    value = now.astimezone(timezone.utc)
    value = value.replace(minute=(value.minute // 15) * 15, second=0, microsecond=0)
    return value.isoformat()


def _decision_signature(
    *,
    store_snapshot: dict[str, Any],
    now: datetime,
    selected_slot_id: int | None,
    scheduler_status: str,
) -> str:
    slots = store_snapshot.get("slots") if isinstance(store_snapshot, dict) else None
    normalized_slots: list[dict[str, Any]] = []
    if isinstance(slots, list):
        for raw in slots:
            if not isinstance(raw, dict):
                normalized_slots.append({"invalid": True})
                continue
            normalized_slots.append(
                {
                    "slot_id": raw.get("slot_id"),
                    "plan_id": raw.get("plan_id"),
                    "origin": raw.get("origin"),
                    "status": raw.get("status"),
                    "action": raw.get("action"),
                    "start_time": raw.get("start_time"),
                    "max_start_delay_minutes": raw.get("max_start_delay_minutes"),
                    "updated_at": raw.get("updated_at"),
                }
            )
    payload = {
        "schema_version": store_snapshot.get("schema_version") if isinstance(store_snapshot, dict) else None,
        "quarter": _quarter_bucket(now),
        "scheduler_status": scheduler_status,
        "selected_slot_id": selected_slot_id,
        "slots": normalized_slots,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _base_output(now: datetime) -> dict[str, Any]:
    return {
        "status": "blocked",
        "scheduler_status": "blocked",
        "scheduler_ready": False,
        "selected_slot_id": None,
        "selected_plan_id": None,
        "selected_action": None,
        "selected_origin": None,
        "selected_start_time": None,
        "selected_window_end": None,
        "next_future_slot_id": None,
        "next_future_plan_id": None,
        "next_future_start_time": None,
        "ready_candidate_count": 0,
        "conflict_count": 0,
        "expired_count": 0,
        "invalid_count": 0,
        "decision_signature": None,
        "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "slot_states": [],
        "blockers": [],
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "operational_plan_store_write": False,
        "scheduler_shadow_evaluated": True,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "service_calls_performed": False,
        "plan_store_mutated": False,
    }


def build_do_plan_scheduler(
    *,
    store_snapshot: Any,
    store_summary: Any,
    now: datetime,
) -> dict[str, Any]:
    """Evaluate exactly three persistent Plan Store slots without side effects."""
    now_utc = _utc(now)
    if now_utc is None:
        # A naive ``now`` is itself unsafe; use a stable UTC fallback only for
        # rendering diagnostics, never for selection.
        fallback = datetime.now(timezone.utc)
        result = _base_output(fallback)
        result["blockers"] = ["scheduler_input_invalid"]
        return result

    result = _base_output(now_utc)
    blockers: list[str] = []

    if not isinstance(store_summary, dict):
        blockers.append("store_not_ready")
    else:
        if store_summary.get("status") != "ready":
            blockers.append("store_not_ready")
        if store_summary.get("store_valid") is not True:
            blockers.append("store_invalid")
        if store_summary.get("persistence_loaded") is not True:
            blockers.append("store_not_loaded")
        if store_summary.get("manual_priority_ok") is not True:
            blockers.append("manual_priority_not_ok")

    if not isinstance(store_snapshot, dict):
        blockers.append("slot_structure_invalid")
        slots: list[Any] = []
    else:
        raw_slots = store_snapshot.get("slots")
        if not isinstance(raw_slots, list) or len(raw_slots) != SLOT_COUNT:
            blockers.append("slot_structure_invalid")
            slots = raw_slots if isinstance(raw_slots, list) else []
        else:
            slots = raw_slots

    if blockers:
        result["blockers"] = sorted(set(blockers))
        result["decision_signature"] = _decision_signature(
            store_snapshot=store_snapshot if isinstance(store_snapshot, dict) else {},
            now=now_utc,
            selected_slot_id=None,
            scheduler_status="blocked",
        )
        return result

    details: list[dict[str, Any]] = []
    ready_candidates: list[tuple[datetime, int, dict[str, Any]]] = []
    future_candidates: list[tuple[datetime, int, dict[str, Any]]] = []
    running_slots: list[int] = []
    invalid_count = 0
    expired_count = 0

    for expected_slot_id, slot in enumerate(slots, start=1):
        detail: dict[str, Any] = {
            "slot_id": expected_slot_id,
            "plan_id": None,
            "origin": None,
            "lifecycle_status": None,
            "action": None,
            "start_time": None,
            "start_window_end": None,
            "scheduler_slot_status": "invalid",
            "selected": False,
            "blockers": [],
        }

        if not isinstance(slot, dict) or slot.get("slot_id") != expected_slot_id:
            detail["blockers"] = ["slot_structure_invalid"]
            invalid_count += 1
            details.append(detail)
            continue

        lifecycle = str(slot.get("status") or "")
        detail.update(
            {
                "plan_id": slot.get("plan_id"),
                "origin": slot.get("origin"),
                "lifecycle_status": lifecycle,
                "action": slot.get("action"),
                "start_time": slot.get("start_time"),
                "power_w": slot.get("power_w"),
                "planned_energy_kwh": slot.get("planned_energy_kwh"),
                "target_soc_percent": slot.get("target_soc_percent"),
                "max_runtime_minutes": slot.get("max_runtime_minutes"),
                "max_start_delay_minutes": slot.get("max_start_delay_minutes"),
            }
        )

        if lifecycle == "empty":
            detail["scheduler_slot_status"] = "empty"
            details.append(detail)
            continue
        if lifecycle == "running":
            detail["scheduler_slot_status"] = "running"
            running_slots.append(expected_slot_id)
            details.append(detail)
            continue
        if lifecycle in {"draft", "blocked"}:
            detail["scheduler_slot_status"] = lifecycle
            details.append(detail)
            continue
        if lifecycle in TERMINAL_STATUSES:
            detail["scheduler_slot_status"] = lifecycle
            details.append(detail)
            continue
        if lifecycle != "pending":
            detail["scheduler_slot_status"] = "invalid"
            detail["blockers"] = ["scheduler_input_invalid"]
            invalid_count += 1
            details.append(detail)
            continue

        slot_blockers: list[str] = []
        if not slot.get("plan_id"):
            slot_blockers.append("plan_identity_missing")
        if slot.get("action") not in VALID_ACTIONS:
            slot_blockers.append("invalid_action")
        start = _utc(slot.get("start_time"))
        if start is None:
            slot_blockers.append("invalid_start_time")
        delay = _finite_non_negative(slot.get("max_start_delay_minutes"))
        if delay is None:
            slot_blockers.append("invalid_start_delay")

        if slot_blockers:
            detail["scheduler_slot_status"] = "invalid"
            detail["blockers"] = sorted(set(slot_blockers))
            invalid_count += 1
            details.append(detail)
            continue

        assert start is not None and delay is not None
        window_end = start + timedelta(minutes=delay)
        detail["start_time"] = start.isoformat()
        detail["start_window_end"] = window_end.isoformat()

        if now_utc < start:
            detail["scheduler_slot_status"] = "pending_future"
            future_candidates.append((start, expected_slot_id, detail))
        elif now_utc <= window_end:
            detail["scheduler_slot_status"] = "candidate"
            ready_candidates.append((start, expected_slot_id, detail))
        else:
            detail["scheduler_slot_status"] = "expired"
            expired_count += 1
        details.append(detail)

    selected: dict[str, Any] | None = None
    conflict_count = 0
    ready_candidates.sort(key=lambda item: (item[0], item[1]))
    future_candidates.sort(key=lambda item: (item[0], item[1]))

    if running_slots:
        for _, _, detail in ready_candidates:
            detail["scheduler_slot_status"] = "conflict"
            detail["blockers"] = ["running_plan_present"]
            conflict_count += 1
        scheduler_status = "running"
        blockers.append("running_plan_present")
    elif ready_candidates:
        selected = ready_candidates[0][2]
        selected["scheduler_slot_status"] = "ready"
        selected["selected"] = True
        for _, _, detail in ready_candidates[1:]:
            detail["scheduler_slot_status"] = "conflict"
            conflict_count += 1
        scheduler_status = "ready"
    elif future_candidates:
        scheduler_status = "waiting"
    elif invalid_count or expired_count:
        scheduler_status = "attention"
    else:
        scheduler_status = "idle"

    next_future = future_candidates[0][2] if future_candidates else None
    result.update(
        {
            "status": scheduler_status,
            "scheduler_status": scheduler_status,
            "scheduler_ready": selected is not None,
            "selected_slot_id": selected.get("slot_id") if selected else None,
            "selected_plan_id": selected.get("plan_id") if selected else None,
            "selected_action": selected.get("action") if selected else None,
            "selected_origin": selected.get("origin") if selected else None,
            "selected_start_time": selected.get("start_time") if selected else None,
            "selected_window_end": selected.get("start_window_end") if selected else None,
            "next_future_slot_id": next_future.get("slot_id") if next_future else None,
            "next_future_plan_id": next_future.get("plan_id") if next_future else None,
            "next_future_start_time": next_future.get("start_time") if next_future else None,
            "ready_candidate_count": len(ready_candidates),
            "conflict_count": conflict_count,
            "expired_count": expired_count,
            "invalid_count": invalid_count,
            "slot_states": details,
            "blockers": sorted(set(blockers)),
        }
    )
    result["decision_signature"] = _decision_signature(
        store_snapshot=store_snapshot,
        now=now_utc,
        selected_slot_id=result["selected_slot_id"],
        scheduler_status=scheduler_status,
    )
    return result
