from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "dummy_os_data"


def read(name: str) -> str:
    return (COMP / name).read_text(encoding="utf-8")


def test_public_operating_mode_entities_are_registered() -> None:
    select_py = read("select.py")
    aggregate = read("do_plan_grid_support_sensor.py")
    assert 'do_plan_operating_mode' in select_py
    assert 'OPERATING_MODE_OPTIONS' in select_py
    assert 'DummyOSPlanOperatingModeSelect' in select_py
    assert 'build_do_plan_operating_mode_sensors' in aggregate


def test_scheduler_safety_prestart_are_wired_to_same_mode_runtime() -> None:
    scheduler = read("do_plan_scheduler_sensor.py")
    safety = read("do_plan_safety_sensor.py")
    assert 'get_do_plan_operating_mode_runtime' in scheduler
    assert 'gate_store_for_scheduler' in scheduler
    assert 'apply_scheduler_mode_metadata' in scheduler
    assert 'mode_runtime' in scheduler
    assert 'apply_safety_mode_gate' in safety
    assert 'apply_prestart_mode_gate' in safety
    assert 'operating_mode_signature' in safety


def test_no_physical_execution_path_is_added() -> None:
    operating = read("do_plan_operating_mode.py")
    runtime = read("do_plan_operating_mode_sensor.py")
    assert 'physical_execution_authority": False' in operating
    assert 'service_calls_performed": False' in operating
    assert 'mode_switch_performed": False' in operating
    assert 'third_party_control' not in runtime


def test_native_forecast_architecture_is_untouched() -> None:
    const = read("const.py")
    assert 'QUARTER_MINUTES = 15' in const
    assert 'FORECAST_HORIZON_HOURS = 72' in const
    assert 'FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES' in const
