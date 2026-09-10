from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_step7b_registers_status_and_ready_entities():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    bundle = (ROOT / "custom_components/dummy_os_data/do_plan_grid_support_sensor.py").read_text()
    binary = (ROOT / "custom_components/dummy_os_data/binary_sensor.py").read_text()
    const = (ROOT / "custom_components/dummy_os_data/const.py").read_text()

    assert '_attr_unique_id = "do_plan_scheduler"' in adapter
    assert '_attr_unique_id = "do_plan_scheduler_ready"' in adapter
    assert "build_do_plan_scheduler_sensors(coordinator)" in bundle
    assert "build_do_plan_scheduler_binary_sensors(coordinator)" in binary
    assert '"binary_sensor"' in const


def test_step7b_uses_one_shared_plan_store_runtime():
    store = (ROOT / "custom_components/dummy_os_data/do_plan_store_sensor.py").read_text()
    bridge = (ROOT / "custom_components/dummy_os_data/do_plan_grid_support_sensor.py").read_text()
    scheduler = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()

    assert "def get_do_plan_store_runtime" in store
    assert "runtime = get_do_plan_store_runtime(coordinator)" in bridge
    assert "get_do_plan_store_runtime(coordinator)" in scheduler
    assert "DummyOSShadowPlanStoreRuntime(coordinator)" not in bridge


def test_step7b_keeps_operational_rights_closed():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    core = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler.py").read_text()
    combined = adapter + core
    for needle in (
        '"shadow_only": True',
        '"active_use_permitted": False',
        '"physical_execution_authority": False',
        '"operational_plan_store_write": False',
        '"scheduler_invoked": False',
        '"safety_chain_invoked": False',
        '"service_calls_performed": False',
    ):
        assert needle in combined
    assert "async_call(" not in adapter
    assert "async_services" not in adapter


def test_step7b_scheduler_is_pure_plan_store_consumer():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    assert "store_runtime.snapshot" in adapter
    assert "store_runtime.summary()" in adapter
    for forbidden in ("solar_points", "price_points", "HomeBaselineForecast", "build_do_plan_72h"):
        assert forbidden not in adapter


def test_step7b_does_not_cache_across_start_window_time():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    assert "current.astimezone(timezone.utc).isoformat()" in adapter
    assert "max_start_delay_minutes exactly" in adapter
