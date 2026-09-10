from datetime import datetime, timedelta, timezone

from custom_components.dummy_os_data.do_plan_store import new_store_snapshot, sync_automatic_candidates
from custom_components.dummy_os_data.do_plan_store_lifecycle import (
    apply_manual_edit,
    cancel_plan,
    clear_manual_plan,
    finalize_manual_plan,
    store_lifecycle_capabilities,
    transition_plan_status,
)

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def automatic_candidate():
    return {
        "candidate_id": "c1",
        "planner_identity": "charge|grid_support|10:00",
        "planner_signature": "sig-1",
        "action": "charge",
        "reason": "grid_support",
        "start_time": (NOW + timedelta(hours=2)).isoformat(),
        "planned_end_time": (NOW + timedelta(hours=2, minutes=30)).isoformat(),
        "max_runtime_minutes": 30,
        "max_start_delay_minutes": 10,
        "power_w": 1200,
        "planned_energy_kwh": 0.6,
        "target_soc_percent": 70,
    }


def complete_manual_changes():
    return {
        "action": "charge",
        "reason": "manual_test",
        "start_time": (NOW + timedelta(hours=1)).isoformat(),
        "max_runtime_minutes": 30,
        "power_w": 1000,
        "planned_energy_kwh": 0.5,
        "target_soc_percent": 65,
    }


def test_manual_edit_claims_automatic_slot_and_removes_planner_identity():
    store, _ = sync_automatic_candidates(new_store_snapshot(NOW), [automatic_candidate()], NOW)
    store, result = apply_manual_edit(store, 1, {"power_w": 900}, NOW + timedelta(minutes=5))
    slot = store["slots"][0]
    assert result["status"] == "draft"
    assert slot["origin"] == "manual"
    assert slot["manual_priority"] is True
    assert slot["candidate_id"] is None
    assert slot["planner_identity"] is None
    assert slot["planner_signature"] is None


def test_manual_draft_must_validate_before_pending():
    store, _ = apply_manual_edit(new_store_snapshot(NOW), 1, {"power_w": 1000}, NOW)
    store, result = finalize_manual_plan(store, 1, NOW)
    assert result["status"] == "blocked"
    assert "invalid_action" in result["blockers"]
    assert "invalid_start_time" in result["blockers"]


def test_complete_manual_plan_finalizes_to_pending():
    store, _ = apply_manual_edit(new_store_snapshot(NOW), 1, complete_manual_changes(), NOW)
    store, result = finalize_manual_plan(store, 1, NOW)
    assert result["status"] == "pending"
    assert store["slots"][0]["origin"] == "manual"
    assert store["slots"][0]["manual_priority"] is True


def test_cancel_is_store_only_terminal_transition():
    store, _ = apply_manual_edit(new_store_snapshot(NOW), 1, complete_manual_changes(), NOW)
    store, _ = finalize_manual_plan(store, 1, NOW)
    store, result = cancel_plan(store, 1, NOW + timedelta(minutes=1))
    assert result["status"] == "cancelled"
    assert store["slots"][0]["status"] == "cancelled"
    capabilities = store_lifecycle_capabilities()
    assert capabilities["scheduler_invoked"] is False
    assert capabilities["service_calls_performed"] is False
    assert capabilities["physical_execution_authority"] is False


def test_manual_slot_requires_explicit_clear_and_running_cannot_clear():
    store, _ = apply_manual_edit(new_store_snapshot(NOW), 1, complete_manual_changes(), NOW)
    store, _ = finalize_manual_plan(store, 1, NOW)
    store, _ = transition_plan_status(store, 1, "running", NOW + timedelta(minutes=1))
    unchanged, blocked = clear_manual_plan(store, 1, NOW + timedelta(minutes=2))
    assert blocked["blockers"] == ["running_plan_cannot_clear"]
    assert unchanged["slots"][0]["status"] == "running"
    store, _ = transition_plan_status(store, 1, "completed", NOW + timedelta(minutes=3))
    store, cleared = clear_manual_plan(store, 1, NOW + timedelta(minutes=4))
    assert cleared["status"] == "empty"
    assert store["slots"][0]["status"] == "empty"


def test_invalid_lifecycle_transition_is_blocked():
    store, _ = apply_manual_edit(new_store_snapshot(NOW), 1, complete_manual_changes(), NOW)
    store, _ = finalize_manual_plan(store, 1, NOW)
    unchanged, result = transition_plan_status(store, 1, "completed", NOW + timedelta(minutes=1))
    assert result["blockers"] == ["lifecycle_transition_invalid"]
    assert unchanged["slots"][0]["status"] == "pending"


def test_automatic_candidate_cannot_reclaim_manually_edited_slot():
    store, _ = sync_automatic_candidates(new_store_snapshot(NOW), [automatic_candidate()], NOW)
    store, _ = apply_manual_edit(store, 1, {"power_w": 900}, NOW + timedelta(minutes=1))
    revised = automatic_candidate()
    revised["candidate_id"] = "c2"
    revised["planner_signature"] = "sig-2"
    revised["planned_energy_kwh"] = 0.7
    store2, result = sync_automatic_candidates(store, [revised], NOW + timedelta(minutes=2))
    assert store2["slots"][0]["origin"] == "manual"
    assert store2["slots"][0]["power_w"] == 900
    assert result["written_slots"] == [2]
