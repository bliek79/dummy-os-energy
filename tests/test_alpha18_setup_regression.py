from pathlib import Path

ROOT = Path(__file__).parents[1]
GRID_ADAPTER = ROOT / "custom_components/dummy_os_data/do_plan_grid_support_sensor.py"
STORE_ADAPTER = ROOT / "custom_components/dummy_os_data/do_plan_store_sensor.py"


def test_plan_store_sensor_builder_signature_and_call_match():
    grid = GRID_ADAPTER.read_text()
    store = STORE_ADAPTER.read_text()

    assert "def build_do_plan_store_sensors(coordinator: Any)" in store
    assert "build_do_plan_store_sensors(coordinator,runtime)" not in grid
    assert "build_do_plan_store_sensors(coordinator, runtime)" not in grid
    assert "*build_do_plan_store_sensors(coordinator)" in grid


def test_alpha18_setup_fix_preserves_shared_store_runtime():
    grid = GRID_ADAPTER.read_text()
    assert "runtime = get_do_plan_store_runtime(coordinator)" in grid
    assert "DummyOSPlanStoreBridgeSensor(coordinator)" in grid


def test_alpha18_setup_fix_keeps_shadow_safety_contracts_present():
    grid = GRID_ADAPTER.read_text()
    for marker in (
        '"shadow_only":True',
        '"operational_plan_store_write":False',
        '"physical_execution_authority":False',
        '"service_calls_performed":False',
    ):
        assert marker in grid
