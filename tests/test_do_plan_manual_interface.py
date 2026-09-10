from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1] / "custom_components" / "dummy_os_data"
pkg = types.ModuleType("custom_components.dummy_os_data")
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules["custom_components.dummy_os_data"] = pkg
for name in ("do_plan_store", "do_plan_manual_interface"):
    spec = importlib.util.spec_from_file_location(f"custom_components.dummy_os_data.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
manual = sys.modules["custom_components.dummy_os_data.do_plan_manual_interface"]
store = sys.modules["custom_components.dummy_os_data.do_plan_store"]
NOW = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
SUMMARY = {"status":"ready","persistence_loaded":True,"manual_priority_ok":True}

def evaluate(snapshot, slot="slot_1"):
    return manual.build_do_plan_manual_interface(store_snapshot=snapshot, store_summary=SUMMARY, selected_slot=slot, now=NOW)

def test_empty_slots_are_selectable_and_available():
    snapshot = store.new_store_snapshot(NOW)
    for option, slot_id in (("slot_1",1),("slot_2",2),("slot_3",3)):
        result=evaluate(snapshot,option); assert result["status"]=="available"; assert result["selected_slot_id"]==slot_id

def test_manual_plan_is_read_and_validated_without_mutation():
    snapshot=store.new_store_snapshot(NOW)
    slot=snapshot["slots"][1]; slot.update({"status":"pending","origin":"manual","plan_id":"manual-2","action":"charge","reason":"manual","start_time":"2026-09-10T14:00:00+00:00","max_runtime_minutes":30,"power_w":1200,"target_soc_percent":70,"manual_priority":True})
    before=deepcopy(snapshot); result=evaluate(snapshot,"slot_2")
    assert result["status"]=="manual_plan"; assert result["plan_id"]=="manual-2"; assert result["power_w"]==1200; assert snapshot==before

def test_automatic_slot_is_read_only_occupied():
    snapshot=store.new_store_snapshot(NOW)
    snapshot["slots"][2].update({"status":"pending","origin":"automatic_72h_planner","plan_id":"auto-3","action":"discharge","manual_priority":False})
    result=evaluate(snapshot,"slot_3"); assert result["status"]=="occupied_automatic"; assert result["selection_valid"] is True

def test_invalid_manual_power_blocks():
    snapshot=store.new_store_snapshot(NOW)
    snapshot["slots"][0].update({"status":"pending","origin":"manual","plan_id":"manual-1","action":"charge","start_time":"2026-09-10T14:00:00+00:00","max_runtime_minutes":30,"power_w":3201,"target_soc_percent":70,"manual_priority":True})
    result=evaluate(snapshot); assert result["status"]=="blocked"; assert "manual_power_invalid" in result["blockers"]

def test_naive_manual_time_blocks():
    snapshot=store.new_store_snapshot(NOW)
    snapshot["slots"][0].update({"status":"pending","origin":"manual","plan_id":"manual-1","action":"charge","start_time":"2026-09-10T14:00:00","max_runtime_minutes":30,"power_w":1000,"target_soc_percent":70,"manual_priority":True})
    assert "manual_start_time_invalid" in evaluate(snapshot)["blockers"]

def test_store_not_loaded_blocks():
    snapshot=store.new_store_snapshot(NOW)
    result=manual.build_do_plan_manual_interface(store_snapshot=snapshot,store_summary={**SUMMARY,"persistence_loaded":False},selected_slot="slot_1",now=NOW)
    assert result["status"]=="blocked"; assert "store_not_loaded" in result["blockers"]

def test_invalid_selection_blocks():
    result=evaluate(store.new_store_snapshot(NOW),"slot_4"); assert result["status"]=="blocked"; assert "selected_slot_invalid" in result["blockers"]

def test_all_execution_and_write_rights_stay_closed():
    result=evaluate(store.new_store_snapshot(NOW))
    assert result["shadow_only"] is True
    for key in ("manual_interface_write","shadow_store_write","operational_plan_store_write","plan_store_mutated","scheduler_invoked","safety_chain_invoked","execution_handoff_performed","service_calls_performed","physical_execution_authority","mode_switch_performed","command_dispatched"):
        assert result[key] is False
