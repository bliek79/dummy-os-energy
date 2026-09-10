from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

from custom_components.dummy_os_data.do_plan_store import (
    cleanup_automatic_slots,
    new_store_snapshot,
    set_manual_plan,
    sync_automatic_candidates,
    validate_store_snapshot,
)

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def candidate(candidate_id="c1", identity="charge|grid_support|a", signature="sig-1", start_hours=2, energy=0.5):
    return {
        "candidate_id": candidate_id,
        "planner_identity": identity,
        "planner_signature": signature,
        "action": "charge",
        "reason": "grid_support",
        "start_time": (NOW + timedelta(hours=start_hours)).isoformat(),
        "planned_end_time": (NOW + timedelta(hours=start_hours, minutes=30)).isoformat(),
        "max_runtime_minutes": 30,
        "max_start_delay_minutes": 10,
        "power_w": 1200,
        "planned_energy_kwh": energy,
        "target_soc_percent": 70,
    }


def manual_plan(start_hours=1):
    return {
        "action": "charge",
        "reason": "manual",
        "start_time": (NOW + timedelta(hours=start_hours)).isoformat(),
        "max_runtime_minutes": 30,
        "power_w": 1000,
        "planned_energy_kwh": 0.4,
        "target_soc_percent": 65,
    }


def test_new_store_is_exactly_three_slots_and_valid():
    store = new_store_snapshot(NOW)
    valid, blockers = validate_store_snapshot(store)
    assert valid and not blockers
    assert len(store["slots"]) == 3
    assert [slot["slot_id"] for slot in store["slots"]] == [1, 2, 3]


def test_manual_plan_claims_slot_and_is_never_overwritten():
    store, result = set_manual_plan(new_store_snapshot(NOW), 1, manual_plan(), NOW)
    assert result["changed"] is True
    assert store["slots"][0]["origin"] == "manual"
    assert store["slots"][0]["manual_priority"] is True
    updated, sync = sync_automatic_candidates(store, [candidate()], NOW)
    assert updated["slots"][0]["origin"] == "manual"
    assert updated["slots"][1]["origin"] == "automatic_72h_planner"
    assert sync["written_slots"] == [2]


def test_duplicate_signature_does_not_create_second_plan():
    store, first = sync_automatic_candidates(new_store_snapshot(NOW), [candidate()], NOW)
    assert first["written_slots"] == [1]
    store2, second = sync_automatic_candidates(store, [candidate(candidate_id="c2")], NOW)
    assert second["changed"] is False
    assert second["duplicate_candidate_ids"] == ["c2"]
    assert sum(1 for slot in store2["slots"] if slot["origin"] == "automatic_72h_planner") == 1


def test_same_identity_reconciles_future_pending_revision_without_new_slot():
    store, _ = sync_automatic_candidates(new_store_snapshot(NOW), [candidate()], NOW)
    plan_id = store["slots"][0]["plan_id"]
    revised = candidate(candidate_id="c2", signature="sig-2", energy=0.7)
    store2, result = sync_automatic_candidates(store, [revised], NOW + timedelta(minutes=5))
    assert result["reconciled_slots"] == [1]
    assert store2["slots"][0]["plan_id"] == plan_id
    assert store2["slots"][0]["planned_energy_kwh"] == 0.7
    assert store2["slots"][1]["status"] == "empty"


def test_three_manual_slots_block_automatic_capacity():
    store = new_store_snapshot(NOW)
    for slot in (1, 2, 3):
        store, _ = set_manual_plan(store, slot, manual_plan(slot), NOW)
    store2, result = sync_automatic_candidates(store, [candidate()], NOW)
    assert store2 == store
    assert result["rejected_candidates"][0]["blockers"] == ["manual_capacity_full"]


def test_cleanup_only_releases_automatic_and_never_manual():
    store, _ = set_manual_plan(new_store_snapshot(NOW), 1, manual_plan(), NOW)
    store, _ = sync_automatic_candidates(store, [candidate(start_hours=1)], NOW)
    cleaned, result = cleanup_automatic_slots(store, NOW + timedelta(hours=2))
    assert result["released_slots"] == [2]
    assert cleaned["slots"][0]["origin"] == "manual"
    assert cleaned["slots"][1]["status"] == "empty"


def test_corrupt_store_is_not_silently_treated_as_empty():
    valid, blockers = validate_store_snapshot({"schema_version": 1, "slots": []})
    assert valid is False
    assert "slot_structure_invalid" in blockers


def _plan_id_from_fresh_process(signature: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "custom_components" / "dummy_os_data" / "do_plan_store.py"
    code = (
        "from datetime import datetime, timezone; "
        "import importlib.util; "
        f"spec=importlib.util.spec_from_file_location('do_plan_store_pure', {str(module_path)!r}); "
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        f"print(module._plan_id('automatic_72h_planner', 1, datetime(2026,9,10,8,0,tzinfo=timezone.utc), {signature!r}))"
    )
    return subprocess.check_output([sys.executable, "-c", code], cwd=repo_root, text=True).strip()


def test_plan_id_is_stable_across_fresh_python_processes():
    first = _plan_id_from_fresh_process("sig-restart-stable")
    second = _plan_id_from_fresh_process("sig-restart-stable")
    assert first == second
    assert first.startswith("do-plan-20260910T080000Z-aut-")


def test_new_automatic_plan_ids_differ_for_different_signatures():
    first = _plan_id_from_fresh_process("sig-a")
    second = _plan_id_from_fresh_process("sig-b")
    assert first != second
