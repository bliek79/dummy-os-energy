from datetime import datetime, timedelta, timezone

from custom_components.dummy_os_data.do_plan_store_bridge import build_do_plan_store_bridge

NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)


def plan72(hours):
    return {"status": "ready", "valid": True, "hours": hours}


def hour(offset, *, action="baseline", grid_charge=0.0, grid_discharge=0.0, soc=50.0):
    start = NOW + timedelta(hours=offset)
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(hours=1)).isoformat(),
        "start_soc_percent": soc,
        "action": action,
        "grid_to_battery_kwh": grid_charge,
        "battery_to_grid_kwh": grid_discharge,
    }


def grid_support(slots=None):
    slots = slots or []
    return {
        "status": "ready", "valid": True, "grid_charge_triggered": bool(slots),
        "soc_percent": 50.0, "selected_charge_slots": slots,
    }


def quarter(offset_minutes, energy=0.2, projected=55.0):
    start = NOW + timedelta(minutes=offset_minutes)
    return {
        "start": start.isoformat(), "end": (start + timedelta(minutes=15)).isoformat(),
        "allocated_charge_input_kwh": energy, "projected_soc_after_percent": projected,
    }


def test_bridge_merges_contiguous_safety_hours():
    result = build_do_plan_store_bridge(
        plan72_result=plan72([hour(1, grid_charge=0.4), hour(2, grid_charge=0.3)]),
        grid_support_result=grid_support(), now=NOW,
    )
    assert result["status"] == "ready"
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["reason"] == "safety_charge"
    assert candidate["planned_energy_kwh"] == 0.7
    assert candidate["max_runtime_minutes"] == 120.0


def test_bridge_merges_contiguous_native_grid_support_slots():
    result = build_do_plan_store_bridge(
        plan72_result=plan72([]),
        grid_support_result=grid_support([quarter(60), quarter(75, projected=58.0)]), now=NOW,
    )
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["reason"] == "grid_support"
    assert candidate["planned_energy_kwh"] == 0.4
    assert candidate["max_runtime_minutes"] == 30.0
    assert candidate["target_soc_percent"] == 58.0


def test_grid_support_suppresses_overlapping_trade_charge():
    result = build_do_plan_store_bridge(
        plan72_result=plan72([hour(1, action="trade_charge", grid_charge=0.5)]),
        grid_support_result=grid_support([quarter(60), quarter(75)]), now=NOW,
    )
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["reason"] == "grid_support"
    assert result["suppressed_candidate_count"] == 1
    assert result["suppressed_candidates"][0]["reason"] == "overlap_lower_priority"


def test_bridge_never_exposes_more_than_three_candidates():
    result = build_do_plan_store_bridge(
        plan72_result=plan72([
            hour(1, grid_charge=0.2),
            hour(3, action="trade_charge", grid_charge=0.2),
            hour(5, action="trade_discharge", grid_discharge=0.2),
            hour(7, grid_charge=0.2),
        ]),
        grid_support_result=grid_support(), now=NOW,
    )
    assert result["candidate_count"] == 3
    assert any(item["reason"] == "store_capacity_three" for item in result["suppressed_candidates"])


def test_past_candidates_are_suppressed_not_silently_used():
    result = build_do_plan_store_bridge(
        plan72_result=plan72([hour(-1, grid_charge=0.3)]),
        grid_support_result=grid_support(), now=NOW,
    )
    assert result["candidate_count"] == 0
    assert result["suppressed_candidates"][0]["reason"] == "candidate_not_future"


def test_all_execution_rights_remain_closed():
    result = build_do_plan_store_bridge(plan72_result=plan72([]), grid_support_result=grid_support(), now=NOW)
    assert result["shadow_only"] is True
    assert result["shadow_store_write"] is True
    assert result["operational_plan_store_write"] is False
    assert result["active_use_permitted"] is False
    assert result["physical_execution_authority"] is False
    assert result["scheduler_invoked"] is False
    assert result["safety_chain_invoked"] is False
    assert result["service_calls_performed"] is False
