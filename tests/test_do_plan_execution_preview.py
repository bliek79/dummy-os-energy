from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components/dummy_os_data/do_plan_execution_preview.py"
spec = importlib.util.spec_from_file_location("do_plan_execution_preview", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
build = mod.build_do_plan_execution_preview

NOW = datetime(2026, 9, 10, 12, 30, tzinfo=timezone.utc)


def slot(**changes):
    value = {
        "slot_id": 1,
        "plan_id": "plan-1",
        "origin": "automatic",
        "status": "pending",
        "action": "charge",
        "power_w": 1200,
        "planned_energy_kwh": 0.6,
        "target_soc_percent": 70.0,
        "max_runtime_minutes": 30,
        "start_time": "2026-09-10T12:30:00+00:00",
        "planned_end_time": "2026-09-10T13:00:00+00:00",
    }
    value.update(changes)
    return value


def upstream(prestart_status="ready"):
    scheduler = {
        "scheduler_status": "ready", "scheduler_ready": True,
        "selected_slot_id": 1, "selected_plan_id": "plan-1", "selected_action": "charge",
        "selected_window_end": "2026-09-10T12:45:00+00:00", "decision_signature": "sched",
    }
    safety = {
        "safety_status": "ready", "safety_ready": True,
        "selected_slot_id": 1, "selected_plan_id": "plan-1", "selected_action": "charge",
        "safety_signature": "safe",
    }
    prestart = {
        "prestart_status": prestart_status, "prestart_ready": prestart_status == "ready",
        "selected_slot_id": 1, "selected_plan_id": "plan-1", "selected_action": "charge",
        "prestart_signature": "pre",
    }
    return scheduler, safety, prestart


def evaluate(store=None, prestart_status="ready"):
    scheduler, safety, prestart = upstream(prestart_status)
    return build(
        scheduler_result=scheduler,
        safety_result=safety,
        prestart_result=prestart,
        store_snapshot=store or {"slots": [slot(), {"slot_id": 2}, {"slot_id": 3}]},
        now=NOW,
    )


def test_ready_preview_copies_plan_store_command_without_authority():
    result = evaluate()
    assert result["status"] == "ready"
    assert result["execution_preview_ready"] is True
    assert result["action"] == "charge"
    assert result["power_w"] == 1200
    assert result["target_soc_percent"] == 70.0
    assert result["max_runtime_minutes"] == 30
    assert result["shadow_only"] is True
    assert result["physical_execution_authority"] is False
    assert result["service_calls_performed"] is False
    assert result["command_dispatched"] is False


def test_waiting_prestart_never_becomes_ready():
    result = evaluate(prestart_status="waiting")
    assert result["status"] == "waiting"
    assert result["execution_preview_ready"] is False


def test_stale_plan_identity_blocks():
    scheduler, safety, prestart = upstream()
    safety["selected_plan_id"] = "stale"
    result = build(scheduler_result=scheduler, safety_result=safety, prestart_result=prestart, store_snapshot={"slots":[slot()]}, now=NOW)
    assert result["status"] == "blocked"
    assert "upstream_identity_mismatch" in result["blockers"]


def test_changed_store_identity_blocks():
    result = evaluate({"slots": [slot(plan_id="new-plan")]})
    assert result["status"] == "blocked"
    assert "selected_plan_identity_mismatch" in result["blockers"]


def test_non_pending_store_slot_blocks():
    result = evaluate({"slots": [slot(status="running")]})
    assert "selected_slot_not_pending" in result["blockers"]


def test_action_mismatch_blocks():
    result = evaluate({"slots": [slot(action="discharge")]})
    assert result["status"] == "blocked"
    assert "scheduler_action_mismatch" in result["blockers"]


def test_store_is_never_mutated():
    store = {"slots": [slot(), {"slot_id": 2}, {"slot_id": 3}]}
    before = deepcopy(store)
    evaluate(store)
    assert store == before


def test_invalid_time_blocks():
    scheduler, safety, prestart = upstream()
    result = build(scheduler_result=scheduler, safety_result=safety, prestart_result=prestart, store_snapshot={"slots":[slot()]}, now=datetime(2026,9,10,12,30))
    assert "execution_preview_time_invalid" in result["blockers"]


def test_signature_is_deterministic_for_same_inputs():
    assert evaluate()["execution_preview_signature"] == evaluate()["execution_preview_signature"]
