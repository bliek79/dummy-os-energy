from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

MODULE_PATH = Path(__file__).parents[1] / "custom_components/dummy_os_data/forecast_planner_contract.py"
SPEC = importlib.util.spec_from_file_location("forecast_planner_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

def hours():
    start = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)
    out = []
    for i in range(72):
        s = start + timedelta(hours=i)
        out.append({
            "index": i,
            "start": s.isoformat(),
            "end": (s + timedelta(hours=1)).isoformat(),
            "energy_kwh": 0.4,
            "quarter_count": 4,
            "populated_quarters": 4,
            "supported_quarters": 4,
            "minimum_confidence": 0.66,
            "average_confidence": 0.72,
            "source_distribution": {"weekday_quarter": 4},
            "profile": "normal",
        })
    return out

def planner(**overrides):
    base = {
        "status": "ok",
        "profile": "normal",
        "native_resolution_minutes": 15,
        "native_public_slots": 288,
        "planner_hour_count": 72,
        "valid_hour_count": 72,
        "quarters_per_hour": 4,
        "planner_start": "2026-09-07T20:00:00+00:00",
        "planner_end": "2026-09-10T20:00:00+00:00",
        "leading_quarter_offset": 2,
        "extra_quarters_generated": 2,
        "generated_quarter_count": 290,
        "padding_used": False,
        "second_forecast_architecture": False,
        "hours": hours(),
    }
    base.update(overrides)
    return base

def health(status="usable", **overrides):
    base = {
        "profile": "normal",
        "readiness_status": status,
        "history_days": 14,
        "valid_quarters": 1140,
        "forecast_coverage_percent": 100.0,
        "average_confidence_percent": 71.4,
        "evaluation_samples": 1116,
        "accuracy_percent": 47.4,
        "mae_kwh": 0.072587,
        "bias_kwh": -0.000444,
        "absolute_bias_kwh": 0.000444,
        "horizon_evidence_status": "collecting",
        "runtime_input_status": "source_unavailable",
        "forecast_operational_input_ok": False,
        "runtime_blockers": ["source_unavailable"],
    }
    base.update(overrides)
    return base

def test_ready_contract_accepts_usable_even_if_runtime_source_unavailable():
    result = MODULE.build_forecast_planner_contract(planner_hours=planner(), model_health=health())
    assert result["status"] == "ready"
    assert result["ready_for_planner"] is True
    assert result["blockers"] == []
    assert result["contract_name"] == "dummy_os_forecast_to_planner"
    assert result["contract_version"] == 1
    assert result["schema_version"] == 1
    assert result["native_slot_count"] == 288
    assert result["planner_hour_count"] == 72
    assert result["quarters_per_hour"] == 4
    assert result["forecast_operational_input_ok"] is False
    assert len(result["hours"]) == 72

def test_learning_model_health_blocks_contract():
    result = MODULE.build_forecast_planner_contract(planner_hours=planner(), model_health=health("learning"))
    assert result["status"] == "blocked"
    assert result["ready_for_planner"] is False
    assert "model_health_learning" in result["blockers"]

def test_padding_or_partial_hour_blocks_contract():
    p = planner(padding_used=True)
    p["hours"][5]["energy_kwh"] = None
    p["hours"][5]["populated_quarters"] = 3
    result = MODULE.build_forecast_planner_contract(planner_hours=p, model_health=health())
    assert result["status"] == "blocked"
    assert "padding_detected" in result["blockers"]
    assert "hour_5_not_fully_populated" in result["blockers"]
    assert "hour_5_energy_unavailable" in result["blockers"]

def test_unclassified_profile_is_explicit():
    result = MODULE.build_forecast_planner_contract(
        planner_hours=planner(profile="unclassified", status="profile_unclassified"),
        model_health=health(profile="unclassified", readiness_status="profile_unclassified"),
    )
    assert result["status"] == "profile_unclassified"
    assert result["ready_for_planner"] is False
    assert "profile_unclassified" in result["blockers"]

def test_wrong_window_and_second_architecture_are_blocked():
    result = MODULE.build_forecast_planner_contract(
        planner_hours=planner(
            planner_end="2026-09-10T19:00:00+00:00",
            second_forecast_architecture=True,
        ),
        model_health=health(),
    )
    assert "planner_window_not_72h" in result["blockers"]
    assert "second_forecast_architecture_detected" in result["blockers"]
