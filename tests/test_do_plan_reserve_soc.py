from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/do_plan_reserve_soc.py"
SPEC = importlib.util.spec_from_file_location("do_plan_reserve_soc", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _energy_need(**overrides):
    result = {
        "status": "ready", "valid": True,
        "reason": "additional_energy_required_for_need_plus_reserve",
        "input_status": "ready", "input_rows_signature": "sig-step2",
        "first_usable_solar": "2026-09-09T07:00:00+00:00",
        "battery_capacity_kwh": 7.2, "min_soc_percent": 5.0,
        "safety_reserve_percent": 7.0, "soc_percent": 20.0,
        "energy_need_until_solar_kwh": 0.6, "safety_reserve_kwh": 0.504,
        "required_including_reserve_kwh": 1.104,
    }
    result.update(overrides)
    return result


def test_current_live_example_matches_independent_calculation_and_contract():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need())
    assert r["status"] == "ready" and r["valid"] is True and r["reason"] == "reserve_deficit"
    assert r["available_battery_kwh"] == 1.08
    assert r["usable_capacity_above_min_kwh"] == 6.84
    assert r["reserve_soc_target_percent"] == 20.333
    assert r["reserve_deficit_kwh"] == 0.024
    assert r["grid_support_required"] is True


def test_surplus_is_reported_without_action_authority():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need(soc_percent=50.0, required_including_reserve_kwh=2.0))
    assert r["status"] == "ready" and r["reason"] == "reserve_surplus"
    assert r["reserve_deficit_kwh"] == 0.0 and r["free_above_reserve_kwh"] == 1.24
    assert r["shadow_only"] is True and r["active_use_permitted"] is False
    assert r["physical_execution_authority"] is False and r["efficiency_applied"] is False


def test_exact_cover_is_ready():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need(soc_percent=20.3333333333, required_including_reserve_kwh=1.104))
    assert r["status"] == "ready" and r["reason"] == "reserve_covered" and r["reserve_deficit_kwh"] == 0.0


def test_unready_step2_blocks_instead_of_using_missing_as_zero():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need(status="blocked", valid=False, energy_need_until_solar_kwh=None, safety_reserve_kwh=None, required_including_reserve_kwh=None))
    assert r["status"] == "blocked" and r["valid"] is False
    assert "energy_need_not_ready" in r["blockers"] and r["reserve_deficit_kwh"] is None


def test_real_zero_is_valid():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need(soc_percent=12.0, energy_need_until_solar_kwh=0.0, safety_reserve_kwh=0.504, required_including_reserve_kwh=0.504))
    assert r["status"] == "ready" and r["valid"] is True
    assert r["reserve_soc_target_percent"] == 12.0 and r["reserve_deficit_kwh"] == 0.0


def test_over_capacity_need_routes_to_grid_support_instead_of_fatal_reserve_block():
    r = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need(soc_percent=95.0, energy_need_until_solar_kwh=8.688, safety_reserve_kwh=0.504, required_including_reserve_kwh=9.192))
    assert r["status"] == "ready" and r["valid"] is True
    assert r["reason"] == "grid_support_required_beyond_static_battery_capacity"
    assert r["reserve_soc_raw_percent"] == 132.667
    assert r["reserve_soc_target_percent"] == 100.0
    assert r["reserve_deficit_kwh"] == 2.712
    assert r["unmet_reserve_at_full_soc_kwh"] == 2.352
    assert r["grid_support_required"] is True
    assert r["grid_support_deficit_kwh"] == 2.712
    assert r["static_capacity_shortfall_kwh"] == 2.352
    assert r["feasibility_deferred_to_charge_window_planner"] is True
    assert r["blockers"] == []
