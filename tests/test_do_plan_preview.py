from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/do_plan_preview.py"
SPEC = importlib.util.spec_from_file_location("do_plan_preview", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

BASE = datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc)


def _input(rows=None, **overrides):
    if rows is None:
        rows = []
        for idx in range(72):
            start = BASE + timedelta(hours=idx)
            solar = 0.0 if idx < 4 else (1.0 if idx < 10 else 0.0)
            home = 0.4
            rows.append(
                {
                    "index": idx,
                    "start": start.isoformat(),
                    "end": (start + timedelta(hours=1)).isoformat(),
                    "home_kwh": home,
                    "solar_kwh": solar,
                    "import_price": 0.20 + idx * 0.001,
                    "export_price": 0.10 + idx * 0.001,
                    "fully_valid": True,
                }
            )
    result = {
        "status": "ready",
        "fully_valid_hours": 72,
        "rows_signature": "sig-step1",
        "rows": rows,
    }
    result.update(overrides)
    return result


def _reserve(**overrides):
    result = {
        "status": "ready",
        "valid": True,
        "reason": "reserve_deficit",
        "first_usable_solar": (BASE + timedelta(hours=4)).isoformat(),
        "battery_capacity_kwh": 7.2,
        "soc_percent": 21.0,
        "reserve_soc_target_percent": 23.569,
        "reserve_deficit_kwh": 0.185,
        "free_above_reserve_kwh": 0.0,
    }
    result.update(overrides)
    return result


def test_safety_charge_uses_step3_deficit_and_efficiency() -> None:
    result = MOD.build_do_plan_preview(
        input_result=_input(),
        reserve_result=_reserve(),
        now=BASE + timedelta(minutes=30),
    )
    assert result["status"] == "ready"
    assert result["decision"] == "safety_charge"
    assert result["reserve_recalculated"] is False
    assert result["safety_charge_battery_kwh"] == 0.185
    assert result["safety_charge_grid_input_kwh"] == 0.201
    assert result["safety_schedule_sufficient"] is True
    assert result["safety_charge_hour_count"] == 1
    assert result["shadow_only"] is True
    assert result["active_use_permitted"] is False
    assert result["physical_execution_authority"] is False


def test_missing_price_blocks_instead_of_falling_back() -> None:
    rows = _input()["rows"]
    rows[3] = {**rows[3], "export_price": None}
    result = MOD.build_do_plan_preview(
        input_result=_input(rows=rows),
        reserve_result=_reserve(),
        now=BASE,
    )
    assert result["status"] == "blocked"
    assert "row_3_invalid" in result["blockers"]
    assert result["prices_fallback_used"] is False
    assert result["missing_as_zero_used"] is False


def test_runtime_blocked_input_is_not_used_for_action_preview() -> None:
    result = MOD.build_do_plan_preview(
        input_result=_input(status="runtime_blocked"),
        reserve_result=_reserve(),
        now=BASE,
    )
    assert result["status"] == "blocked"
    assert "planner_input_not_runtime_ready" in result["blockers"]


def test_solar_headroom_protection_can_block_trade_charging() -> None:
    result = MOD.build_do_plan_preview(
        input_result=_input(),
        reserve_result=_reserve(
            reason="reserve_covered",
            soc_percent=80.0,
            reserve_deficit_kwh=0.0,
            free_above_reserve_kwh=1.0,
        ),
        now=BASE,
    )
    assert result["solar_protection_kwh"] > 0
    assert result["trade_charge_headroom_kwh"] >= 0
    assert result["safety_charge_needed"] is False


def test_import_avoidance_and_export_trade_are_separate() -> None:
    rows = _input()["rows"]
    rows[0] = {**rows[0], "import_price": 0.05, "export_price": 0.01}
    rows[8] = {**rows[8], "import_price": 0.60, "export_price": 0.30}
    result = MOD.build_do_plan_preview(
        input_result=_input(rows=rows),
        reserve_result=_reserve(
            reason="reserve_surplus",
            soc_percent=40.0,
            reserve_deficit_kwh=0.0,
            free_above_reserve_kwh=1.0,
        ),
        now=BASE,
        minimum_trade_margin=0.10,
    )
    assert result["best_import_avoidance"] is not None
    assert result["best_export_trade"] is not None
    assert result["best_import_avoidance"]["avoided_import_price"] != result["best_export_trade"]["export_price"]
    assert result["import_avoidance_profitable"] is True


def test_real_zero_prices_and_energy_are_valid() -> None:
    rows = _input()["rows"]
    rows[0] = {**rows[0], "home_kwh": 0.0, "solar_kwh": 0.0, "import_price": 0.0, "export_price": 0.0}
    result = MOD.build_do_plan_preview(
        input_result=_input(rows=rows),
        reserve_result=_reserve(reserve_deficit_kwh=0.0, free_above_reserve_kwh=0.0),
        now=BASE,
    )
    assert result["status"] == "ready"
    assert result["valid"] is True


def test_invalid_reserve_blocks() -> None:
    result = MOD.build_do_plan_preview(
        input_result=_input(),
        reserve_result=_reserve(status="infeasible", valid=False),
        now=BASE,
    )
    assert result["status"] == "blocked"
    assert "reserve_soc_not_ready" in result["blockers"]
