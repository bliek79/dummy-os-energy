from datetime import datetime, timedelta, timezone
from custom_components.dummy_os_data.do_plan_store import new_store_snapshot, set_manual_plan, sync_automatic_candidates
from custom_components.dummy_os_data.do_plan_store_reconcile import prune_obsolete_automatic_pending
NOW=datetime(2026,9,10,8,0,tzinfo=timezone.utc)

def candidate(signature="sig-1",identity="id-1"):
    return {"candidate_id":signature,"planner_identity":identity,"planner_signature":signature,"action":"charge","reason":"grid_support","start_time":(NOW+timedelta(hours=2)).isoformat(),"planned_end_time":(NOW+timedelta(hours=2,minutes=30)).isoformat(),"max_runtime_minutes":30,"max_start_delay_minutes":10,"power_w":1000,"planned_energy_kwh":0.5,"target_soc_percent":60}

def manual():
    return {"action":"charge","start_time":(NOW+timedelta(hours=3)).isoformat(),"max_runtime_minutes":30,"power_w":800,"target_soc_percent":60}

def test_obsolete_automatic_pending_is_released():
    store,_=sync_automatic_candidates(new_store_snapshot(NOW),[candidate()],NOW)
    result,meta=prune_obsolete_automatic_pending(store,[],NOW+timedelta(minutes=5))
    assert meta["released_slots"]==[1]
    assert result["slots"][0]["status"]=="empty"

def test_current_signature_is_retained():
    c=candidate(); store,_=sync_automatic_candidates(new_store_snapshot(NOW),[c],NOW)
    result,meta=prune_obsolete_automatic_pending(store,[c],NOW+timedelta(minutes=5))
    assert meta["changed"] is False
    assert result["slots"][0]["planner_signature"]=="sig-1"

def test_manual_plan_is_never_pruned_by_bridge_membership():
    store,_=set_manual_plan(new_store_snapshot(NOW),1,manual(),NOW)
    result,meta=prune_obsolete_automatic_pending(store,[],NOW+timedelta(minutes=5))
    assert meta["changed"] is False
    assert result["slots"][0]["origin"]=="manual"
