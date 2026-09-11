from copy import deepcopy
from datetime import datetime, timezone

from custom_components.dummy_os_data.do_plan_manual_diagnostic import run_manual_lifecycle_diagnostic
from custom_components.dummy_os_data.do_plan_store import ORIGIN_AUTOMATIC, STATUS_PENDING, STATUS_RUNNING, new_store_snapshot

NOW = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)


def test_diagnostic_completes_full_lifecycle_and_restores_empty_slot():
    snapshot = new_store_snapshot(NOW)
    updated, result = run_manual_lifecycle_diagnostic(snapshot, slot_id=2, now=NOW)
    assert result["status"] == "passed"
    assert result["passed"] is True
    assert updated["slots"][1]["status"] == "empty"
    assert [step["step"] for step in result["steps"]] == ["draft", "validate_new", "finalize_new", "verify_revision_1", "edit", "validate_edit", "finalize_edit", "verify_revision_2", "clear", "verify_empty"]
    assert all(result[key] is False for key in ("operational_plan_store_write", "scheduler_invoked", "safety_chain_invoked", "execution_handoff_performed", "external_service_calls_performed", "physical_execution_authority", "mode_switch_performed", "command_dispatched"))


def test_diagnostic_blocks_automatic_owned_slot_without_mutation():
    snapshot = new_store_snapshot(NOW)
    snapshot["slots"][1].update({"status": STATUS_PENDING, "origin": ORIGIN_AUTOMATIC, "plan_id": "auto-2", "manual_priority": False})
    before = deepcopy(snapshot)
    updated, result = run_manual_lifecycle_diagnostic(snapshot, slot_id=2, now=NOW)
    assert result["status"] == "blocked"
    assert "selected_slot_not_empty" in result["blockers"]
    assert updated == before


def test_diagnostic_blocks_running_slot_without_mutation():
    snapshot = new_store_snapshot(NOW)
    snapshot["slots"][1].update({"status": STATUS_RUNNING, "origin": "manual", "plan_id": "manual-2", "manual_priority": True})
    before = deepcopy(snapshot)
    updated, result = run_manual_lifecycle_diagnostic(snapshot, slot_id=2, now=NOW)
    assert result["status"] == "blocked"
    assert updated == before


def test_diagnostic_blocks_overlap_and_rolls_back_snapshot():
    snapshot = new_store_snapshot(NOW)
    snapshot["slots"][0].update({"status": STATUS_PENDING, "origin": ORIGIN_AUTOMATIC, "plan_id": "auto-1", "action": "charge", "start_time": "2026-09-11T10:00:00+00:00", "planned_end_time": "2026-09-11T11:00:00+00:00", "max_runtime_minutes": 60, "max_start_delay_minutes": 0, "power_w": 1000, "planned_energy_kwh": 1.0, "target_soc_percent": 50, "manual_priority": False})
    before = deepcopy(snapshot)
    updated, result = run_manual_lifecycle_diagnostic(snapshot, slot_id=2, now=NOW, start_time="2026-09-11T10:15:00+00:00")
    assert result["status"] == "blocked"
    assert "plan_overlap" in result["blockers"]
    assert updated == before
