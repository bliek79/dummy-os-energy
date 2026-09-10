from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

MODULE=Path(__file__).parents[1]/"custom_components/dummy_os_data/do_plan_safety.py"
spec=importlib.util.spec_from_file_location("do_plan_safety_pure",MODULE)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
build_do_plan_safety=mod.build_do_plan_safety
build_do_plan_prestart=mod.build_do_plan_prestart

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _slot(action="charge", target=70.0, power=2000.0):
    return {"slot_id":1,"plan_id":"plan-1","origin":"automatic","status":"pending","action":action,"start_time":NOW.isoformat(),"planned_end_time":(NOW+timedelta(hours=1)).isoformat(),"max_runtime_minutes":60,"max_start_delay_minutes":10,"power_w":power,"planned_energy_kwh":2.0,"target_soc_percent":target}


def _store(slot=None):
    return {"slots":[slot or _slot(), {"slot_id":2,"status":"empty"}, {"slot_id":3,"status":"empty"}]}


def _scheduler(action="charge"):
    return {"scheduler_status":"ready","scheduler_ready":True,"selected_slot_id":1,"selected_plan_id":"plan-1","selected_action":action,"selected_origin":"automatic","selected_start_time":NOW.isoformat(),"selected_window_end":(NOW+timedelta(minutes=10)).isoformat(),"decision_signature":"sched-1"}


def _reserve(target=40.0):
    return {"status":"ready","valid":True,"reserve_soc_target_percent":target}


def _safety(slot=None, scheduler=None, soc=50.0, reserve=None, now=NOW):
    return build_do_plan_safety(scheduler_result=scheduler or _scheduler((slot or _slot())["action"]),store_snapshot=_store(slot),reserve_result=reserve or _reserve(),soc_percent=soc,now=now)


def test_charge_ready_and_all_rights_remain_closed():
    result=_safety()
    assert result["safety_status"]=="ready" and result["safety_ready"] is True
    assert result["execution_floor_soc_percent"]==42.0
    for key in ("active_use_permitted","physical_execution_authority","operational_plan_store_write","scheduler_invoked","safety_chain_invoked","execution_handoff_performed","service_calls_performed","plan_store_mutated","mode_switch_performed"):
        assert result[key] is False


def test_charge_target_must_be_above_current_soc():
    result=_safety(slot=_slot(target=50.0),soc=50.0)
    assert "charge_target_not_above_current_soc" in result["blockers"]


def test_power_above_3200_is_blocked():
    result=_safety(slot=_slot(power=3201.0))
    assert "power_above_limit" in result["blockers"]


def test_discharge_respects_execution_floor_current_and_target():
    slot=_slot(action="discharge",target=41.0)
    result=_safety(slot=slot,soc=42.0,reserve=_reserve(40.0))
    assert "discharge_current_soc_at_or_below_floor" in result["blockers"]
    assert "discharge_target_below_execution_floor" in result["blockers"]


def test_unknown_soc_and_reserve_are_explicit_blockers_not_zero():
    result=_safety(soc=None,reserve={"status":"blocked","valid":False})
    assert "soc_unavailable" in result["blockers"]
    assert "reserve_not_ready" in result["blockers"]
    assert result["current_soc_percent"] is None


def test_stale_selected_plan_identity_is_blocked():
    scheduler=_scheduler(); scheduler["selected_plan_id"]="stale"
    result=_safety(scheduler=scheduler)
    assert "selected_plan_identity_mismatch" in result["blockers"]


def test_prestart_ready_only_for_same_safe_plan_inside_window():
    store=_store(); scheduler=_scheduler(); safety=_safety()
    result=build_do_plan_prestart(scheduler_result=scheduler,safety_result=safety,store_snapshot=store,now=NOW+timedelta(minutes=5))
    assert result["prestart_status"]=="ready" and result["prestart_ready"] is True
    assert result["physical_execution_authority"] is False
    assert result["service_calls_performed"] is False


def test_prestart_expired_window_is_blocked():
    result=build_do_plan_prestart(scheduler_result=_scheduler(),safety_result=_safety(),store_snapshot=_store(),now=NOW+timedelta(minutes=11))
    assert "prestart_window_expired" in result["blockers"]
    assert result["prestart_ready"] is False


def test_naive_prestart_time_is_blocked():
    result=build_do_plan_prestart(scheduler_result=_scheduler(),safety_result=_safety(),store_snapshot=_store(),now=datetime(2026,9,10,12,5))
    assert "prestart_time_invalid" in result["blockers"]


def test_pure_functions_do_not_mutate_plan_store():
    store=_store(); before=deepcopy(store); scheduler=_scheduler()
    safety=build_do_plan_safety(scheduler_result=scheduler,store_snapshot=store,reserve_result=_reserve(),soc_percent=50.0,now=NOW)
    build_do_plan_prestart(scheduler_result=scheduler,safety_result=safety,store_snapshot=store,now=NOW)
    assert store==before
