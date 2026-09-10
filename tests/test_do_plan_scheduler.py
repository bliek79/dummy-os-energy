from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "dummy_os_data" / "do_plan_scheduler.py"
spec = importlib.util.spec_from_file_location("do_plan_scheduler", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
build_do_plan_scheduler = module.build_do_plan_scheduler

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def empty_slot(slot_id: int) -> dict:
    return {
        "slot_id": slot_id,
        "plan_id": None,
        "origin": None,
        "status": "empty",
        "action": None,
        "start_time": None,
        "planned_end_time": None,
        "max_runtime_minutes": None,
        "max_start_delay_minutes": None,
        "power_w": None,
        "planned_energy_kwh": None,
        "target_soc_percent": None,
        "created_at": None,
        "updated_at": None,
    }


def pending(slot_id: int, start: datetime, delay: int = 10, *, plan_id: str | None = None) -> dict:
    value = empty_slot(slot_id)
    value.update(
        {
            "plan_id": plan_id or f"plan-{slot_id}",
            "origin": "automatic_72h_planner",
            "status": "pending",
            "action": "charge" if slot_id != 2 else "discharge",
            "start_time": start.isoformat(),
            "planned_end_time": (start + timedelta(hours=1)).isoformat(),
            "max_runtime_minutes": 60,
            "max_start_delay_minutes": delay,
            "power_w": 1200,
            "planned_energy_kwh": 1.2,
            "target_soc_percent": 70,
            "created_at": (NOW - timedelta(hours=1)).isoformat(),
            "updated_at": (NOW - timedelta(minutes=5)).isoformat(),
        }
    )
    return value


def store(*slots: dict) -> dict:
    return {"schema_version": 1, "updated_at": NOW.isoformat(), "slots": list(slots)}


SUMMARY = {
    "status": "ready",
    "store_valid": True,
    "persistence_loaded": True,
    "manual_priority_ok": True,
}


def run(snapshot: dict, now: datetime = NOW, summary: dict | None = None) -> dict:
    return build_do_plan_scheduler(store_snapshot=snapshot, store_summary=summary or SUMMARY, now=now)


def test_future_plan_waits_and_exposes_next_start() -> None:
    future = NOW + timedelta(minutes=15)
    result = run(store(pending(1, future), empty_slot(2), empty_slot(3)))
    assert result["scheduler_status"] == "waiting"
    assert result["scheduler_ready"] is False
    assert result["next_future_slot_id"] == 1
    assert result["next_future_start_time"] == future.isoformat()
    assert result["service_calls_performed"] is False


def test_plan_inside_start_window_is_ready() -> None:
    start = NOW - timedelta(minutes=5)
    result = run(store(pending(1, start), empty_slot(2), empty_slot(3)))
    assert result["scheduler_status"] == "ready"
    assert result["selected_slot_id"] == 1
    assert result["slot_states"][0]["scheduler_slot_status"] == "ready"


def test_plan_after_window_is_expired_without_mutating_store() -> None:
    snapshot = store(pending(1, NOW - timedelta(minutes=11), delay=10), empty_slot(2), empty_slot(3))
    original = deepcopy(snapshot)
    result = run(snapshot)
    assert result["scheduler_status"] == "attention"
    assert result["expired_count"] == 1
    assert result["scheduler_ready"] is False
    assert snapshot == original
    assert result["plan_store_mutated"] is False


def test_two_ready_candidates_choose_oldest_due_time() -> None:
    result = run(
        store(
            pending(1, NOW - timedelta(minutes=2)),
            pending(2, NOW - timedelta(minutes=5)),
            empty_slot(3),
        )
    )
    assert result["selected_slot_id"] == 2
    assert result["conflict_count"] == 1
    assert result["slot_states"][0]["scheduler_slot_status"] == "conflict"


def test_equal_start_time_uses_lowest_slot_id() -> None:
    start = NOW - timedelta(minutes=2)
    result = run(store(pending(1, start), pending(2, start), empty_slot(3)))
    assert result["selected_slot_id"] == 1
    assert result["conflict_count"] == 1


def test_running_plan_blocks_second_ready_selection() -> None:
    running = pending(1, NOW - timedelta(minutes=1))
    running["status"] = "running"
    result = run(store(running, pending(2, NOW - timedelta(minutes=1)), empty_slot(3)))
    assert result["scheduler_status"] == "running"
    assert result["scheduler_ready"] is False
    assert result["selected_slot_id"] is None
    assert "running_plan_present" in result["blockers"]
    assert result["slot_states"][1]["scheduler_slot_status"] == "conflict"


def test_draft_blocked_and_terminal_plans_never_start() -> None:
    draft = pending(1, NOW); draft["status"] = "draft"
    blocked = pending(2, NOW); blocked["status"] = "blocked"
    completed = pending(3, NOW); completed["status"] = "completed"
    result = run(store(draft, blocked, completed))
    assert result["scheduler_status"] == "idle"
    assert result["scheduler_ready"] is False


def test_naive_start_time_is_invalid_not_localized() -> None:
    slot = pending(1, NOW)
    slot["start_time"] = "2026-09-10T12:00:00"
    result = run(store(slot, empty_slot(2), empty_slot(3)))
    assert result["scheduler_status"] == "attention"
    assert result["invalid_count"] == 1
    assert result["slot_states"][0]["blockers"] == ["invalid_start_time"]


def test_invalid_store_blocks_scheduler() -> None:
    summary = dict(SUMMARY, store_valid=False)
    result = run(store(empty_slot(1), empty_slot(2), empty_slot(3)), summary=summary)
    assert result["scheduler_status"] == "blocked"
    assert result["scheduler_ready"] is False
    assert "store_invalid" in result["blockers"]


def test_manual_priority_not_ok_blocks_scheduler() -> None:
    summary = dict(SUMMARY, manual_priority_ok=False)
    result = run(store(empty_slot(1), empty_slot(2), empty_slot(3)), summary=summary)
    assert "manual_priority_not_ok" in result["blockers"]


def test_decision_signature_stable_inside_native_quarter() -> None:
    snapshot = store(pending(1, NOW - timedelta(minutes=1)), empty_slot(2), empty_slot(3))
    first = run(snapshot, NOW)
    second = run(snapshot, NOW + timedelta(minutes=1))
    assert first["decision_signature"] == second["decision_signature"]


def test_decision_signature_changes_next_native_quarter() -> None:
    snapshot = store(pending(1, NOW + timedelta(hours=1)), empty_slot(2), empty_slot(3))
    first = run(snapshot, NOW)
    second = run(snapshot, NOW + timedelta(minutes=15))
    assert first["decision_signature"] != second["decision_signature"]


def test_no_execution_or_safety_authority() -> None:
    result = run(store(pending(1, NOW), empty_slot(2), empty_slot(3)))
    assert result["shadow_only"] is True
    assert result["active_use_permitted"] is False
    assert result["physical_execution_authority"] is False
    assert result["operational_plan_store_write"] is False
    assert result["scheduler_invoked"] is False
    assert result["safety_chain_invoked"] is False
    assert result["service_calls_performed"] is False
