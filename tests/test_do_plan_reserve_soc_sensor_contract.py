from pathlib import Path

ROOT = Path(__file__).parents[1]
SENSOR = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
MODULE = (ROOT / "custom_components/dummy_os_data/do_plan_reserve_soc.py").read_text()


def test_reserve_soc_sensor_is_registered_observer_only() -> None:
    assert 'from .do_plan_reserve_soc import build_do_plan_reserve_soc' in SENSOR
    assert 'DummyOSPlanReserveSOCSensor(coordinator)' in SENSOR
    assert 'class DummyOSPlanReserveSOCSensor(DummyOSPlanEnergyNeedSensor):' in SENSOR
    assert '_attr_unique_id = "do_plan_reserve_soc"' in SENSOR
    assert '_attr_suggested_object_id = "do_plan_reserve_soc"' in SENSOR
    assert 'build_do_plan_reserve_soc(' in SENSOR
    assert 'physical_execution_authority' in MODULE
    assert 'active_use_permitted' in MODULE
    assert 'shadow_only' in MODULE


def test_step3_reuses_step2_live_soc_path_and_keeps_identity_cleanup_deferred() -> None:
    assert 'def _build_reserve_from_snapshot(' in SENSOR
    assert 'energy_need_result = _build_energy_need_from_snapshot(snapshot)' in SENSOR
    assert 'soc_source_entity' in SENSOR
    assert 'class DummyOSPlanReserveSOCSensor(DummyOSPlanEnergyNeedSensor):' in SENSOR
    init_source = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
    assert '("sensor", "do_plan_reserve_soc", "sensor.do_plan_reserve_soc")' not in init_source
