from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_step7c_dashboard_replacements_are_exact_and_registered():
    sensor_adapter = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    binary_platform = (ROOT / "custom_components/dummy_os_data/binary_sensor.py").read_text()
    normalized = "".join(sensor_adapter.split())
    assert '_attr_unique_id="do_plan_scheduler"' in normalized
    assert '_attr_suggested_object_id="do_plan_scheduler"' in normalized
    assert '_attr_unique_id="do_plan_scheduler_ready"' in normalized
    assert '_attr_suggested_object_id="do_plan_scheduler_ready"' in normalized
    assert "build_do_plan_scheduler_binary_sensors" in binary_platform


def test_step7c_readiness_is_derived_from_same_scheduler_runtime():
    text = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    assert "runtime = get_do_plan_scheduler_runtime(coordinator)" in text
    assert "return [DummyOSPlanSchedulerSensor(runtime)]" in text
    assert "return [DummyOSPlanSchedulerReadyBinarySensor(runtime)]" in text
    assert 'self.runtime.result().get("scheduler_ready") is True' in text


def test_step7c_keeps_scheduler_dashboard_shadow_only():
    text = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    for needle in (
        '"shadow_only": True',
        '"active_use_permitted": False',
        '"physical_execution_authority": False',
        '"operational_plan_store_write": False',
        '"scheduler_invoked": False',
        '"safety_chain_invoked": False',
        '"service_calls_performed": False',
    ):
        assert needle in text


def test_step7c_does_not_create_parallel_scheduler_dashboard_entities():
    text = (ROOT / "custom_components/dummy_os_data/do_plan_scheduler_sensor.py").read_text()
    unique_ids = [line for line in text.splitlines() if "_attr_unique_id" in line]
    assert len(unique_ids) == 2
    assert any('"do_plan_scheduler"' in line for line in unique_ids)
    assert any('"do_plan_scheduler_ready"' in line for line in unique_ids)
