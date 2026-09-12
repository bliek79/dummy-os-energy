from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "dummy_os_data" / "do_plan_operating_mode.py"
spec = importlib.util.spec_from_file_location("do_plan_operating_mode", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def mode(name: str) -> dict:
    return module.build_operating_mode_status(
        mode=name,
        previous_mode=None,
        changed_at=None,
        mode_source="test",
        runtime_ready=True,
    )


def scheduler(origin: str | None, ready: bool = True) -> dict:
    return {
        "status": "ready" if ready else "idle",
        "scheduler_status": "ready" if ready else "idle",
        "scheduler_ready": ready,
        "selected_slot_id": 1 if ready else None,
        "selected_plan_id": "p1" if ready else None,
        "selected_origin": origin,
        "selected_action": "charge" if ready else None,
        "selected_start_time": "2026-09-12T05:00:00+00:00" if ready else None,
        "selected_window_end": "2026-09-12T05:10:00+00:00" if ready else None,
        "decision_signature": "sched",
        "blockers": [],
        "slot_states": [],
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "service_calls_performed": False,
    }


def test_mode_matrix_and_safety_flags() -> None:
    automatic = mode(module.MODE_AUTOMATIC)
    manual = mode(module.MODE_MANUAL)
    self_consumption = mode(module.MODE_SELF_CONSUMPTION)
    disabled = mode(module.MODE_DISABLED)
    assert automatic["manual_selection_allowed"] is True
    assert automatic["automatic_selection_allowed"] is True
    assert manual["manual_selection_allowed"] is True
    assert manual["automatic_selection_allowed"] is False
    assert self_consumption["scheduler_selection_allowed"] is False
    assert disabled["scheduler_selection_allowed"] is False
    for result in (automatic, manual, self_consumption, disabled):
        assert result["shadow_only"] is True
        assert result["active_use_permitted"] is False
        assert result["physical_execution_authority"] is False
        assert result["service_calls_performed"] is False
        assert result["mode_switch_performed"] is False


def test_unready_or_invalid_mode_fails_closed() -> None:
    unready = module.build_operating_mode_status(
        mode=module.MODE_AUTOMATIC,
        previous_mode=None,
        changed_at=None,
        mode_source="test",
        runtime_ready=False,
    )
    invalid = module.build_operating_mode_status(
        mode="third_party_control",
        previous_mode=None,
        changed_at=None,
        mode_source="test",
        runtime_ready=True,
    )
    assert unready["status"] == "initializing"
    assert unready["scheduler_selection_allowed"] is False
    assert invalid["status"] == "blocked"
    assert "operating_mode_invalid" in invalid["blockers"]
    assert invalid["scheduler_selection_allowed"] is False


def test_scheduler_gate_blocks_non_selecting_modes() -> None:
    base = scheduler("automatic_72h_planner")
    for name in (module.MODE_SELF_CONSUMPTION, module.MODE_DISABLED):
        result = module.apply_scheduler_mode_gate(base, mode(name))
        assert result["scheduler_ready"] is False
        assert result["selected_plan_id"] is None
        assert result["scheduler_status"] == "idle"
        assert result["operating_mode_signature"] == mode(name)["operating_mode_signature"]


def test_manual_mode_accepts_manual_and_rejects_automatic() -> None:
    accepted = module.apply_scheduler_mode_gate(scheduler("manual"), mode(module.MODE_MANUAL))
    rejected = module.apply_scheduler_mode_gate(scheduler("automatic_72h_planner"), mode(module.MODE_MANUAL))
    assert accepted["scheduler_ready"] is True
    assert rejected["scheduler_ready"] is False
    assert "plan_origin_not_allowed" in rejected["blockers"]


def test_automatic_mode_accepts_manual_and_automatic_origins() -> None:
    for origin in ("manual", "automatic_72h_planner"):
        result = module.apply_scheduler_mode_gate(scheduler(origin), mode(module.MODE_AUTOMATIC))
        assert result["scheduler_ready"] is True
        assert result["selected_origin"] == origin


def test_safety_revalidates_origin_against_mode() -> None:
    safety = {
        "status": "ready",
        "safety_status": "ready",
        "safety_ready": True,
        "selected_origin": "automatic_72h_planner",
        "blockers": [],
    }
    result = module.apply_safety_mode_gate(safety, mode(module.MODE_MANUAL))
    assert result["safety_ready"] is False
    assert result["safety_status"] == "blocked"
    assert "selected_origin_not_allowed_by_mode" in result["blockers"]


def test_prestart_detects_mode_signature_change() -> None:
    automatic = mode(module.MODE_AUTOMATIC)
    manual = mode(module.MODE_MANUAL)
    sched = scheduler("manual")
    sched["operating_mode_signature"] = automatic["operating_mode_signature"]
    safety = {
        "safety_status": "ready",
        "safety_ready": True,
        "operating_mode_signature": automatic["operating_mode_signature"],
    }
    prestart = {"status": "ready", "prestart_status": "ready", "prestart_ready": True, "blockers": []}
    result = module.apply_prestart_mode_gate(prestart, sched, safety, manual)
    assert result["prestart_ready"] is False
    assert result["prestart_status"] == "blocked"
    assert "operating_mode_changed" in result["blockers"]
