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
        "status": "ready",
        "valid": True,
        "reason": "additional_energy_required_for_need_plus_reserve",
        "input_rows_signature": "sig-step2",
        "battery_capacity_kwh": 7.2,
        "min_soc_percent": 5.0,
        "safety_reserve_percent": 7.0,
        "soc_percent": 20.0,
        "energy_need_until_solar_kwh": 0.6,
        "safety_reserve_kwh": 0.504,
        "required_including_reserve_kwh": 1.104,
    }
    result.update(overrides)
    return result


def test_current_live_example_matches_independent_calculation() -> None:
    result = MOD.build_do_plan_reserve_soc(energy_need_result=_energy_need())
    assert result["status"] == "ready"
    assert result["valid"] is True
    assert result["reason"] == "reserve_deficit"
    assert result["current_usable_above_min_kwh"] == 1.08
    assert result["max_usable_above_min_kwh"] == 6.84
    assert result["reserve_soc_target_percent"] == 20.333
    assert result["reserve_deficit_kwh"] == 0.024
    assert result["reserve_deficit_percent"] == 0.333
    assert result["free_above_reserve_kwh"] == 0.0
    assert result["free_above_reserve_percent"] == 0.0
    assert result["unmet_reserve_at_full_soc_kwh"] == 0.0
    assert result["input_rows_signature"] == "sig-step2"


def test_surplus_is_reported_without_action_authority() -> None:
    result = MOD.build_do_plan_reserve_soc(
        energy_need_result=_energy_need(
            soc_percent=50.0,
            required_including_reserve_kwh=2.0,
        )
    )
    assert result["status"] == "ready"
    assert result["reason"] == "reserve_surplus"
    assert result["reserve_deficit_kwh"] == 0.0
    assert result["free_above_reserve_kwh"] == 1.24
    assert result["shadow_only"] is True
    assert result["active_use_permitted"] is False
    assert result["physical_execution_authority"] is False
    assert result["efficiency_applied"] is False


def test_exact_cover_is_ready() -> None:
    result = MOD.build_do_plan_reserve_soc(
        energy_need_result=_energy_need(
            soc_percent=20.3333333333,
            required_including_reserve_kwh=1.104,
        )
    )
    assert result["status"] == "ready"
    assert result["reason"] == "reserve_covered"
    assert result["reserve_deficit_kwh"] == 0.0
    assert result["free_above_reserve_kwh"] == 0.0


def test_unready_step2_blocks_instead_of_using_missing_as_zero() -> None:
    result = MOD.build_do_plan_reserve_soc(
        energy_need_result=_energy_need(
            status="blocked",
            valid=False,
            energy_need_until_solar_kwh=None,
            safety_reserve_kwh=None,
            required_including_reserve_kwh=None,
        )
    )
    assert result["status"] == "blocked"
    assert result["valid"] is False
    assert "energy_need_not_ready" in result["blockers"]
    assert result["reserve_soc_target_percent"] is None
    assert result["reserve_deficit_kwh"] is None


def test_real_zero_is_valid() -> None:
    result = MOD.build_do_plan_reserve_soc(
        energy_need_result=_energy_need(
            soc_percent=12.0,
            energy_need_until_solar_kwh=0.0,
            safety_reserve_kwh=0.504,
            required_including_reserve_kwh=0.504,
        )
    )
    assert result["status"] == "ready"
    assert result["valid"] is True
    assert result["reserve_soc_target_percent"] == 12.0
    assert result["reserve_deficit_kwh"] == 0.0
    assert result["free_above_reserve_kwh"] == 0.0


def test_infeasible_when_full_battery_cannot_hold_required_energy_above_min() -> None:
    result = MOD.build_do_plan_reserve_soc(
        energy_need_result=_energy_need(
            soc_percent=100.0,
            energy_need_until_solar_kwh=7.0,
            safety_reserve_kwh=0.504,
            required_including_reserve_kwh=7.504,
        )
    )
    assert result["status"] == "infeasible"
    assert result["valid"] is False
    assert result["reason"] == "required_reserve_exceeds_usable_capacity_at_full_soc"
    assert result["reserve_soc_target_percent"] == 100.0
    assert result["unmet_reserve_at_full_soc_kwh"] == 0.664
    assert "reserve_not_achievable_within_battery_capacity" in result["blockers"]
