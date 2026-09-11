from pathlib import Path

ROOT = Path(__file__).parents[1]
SENSOR = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()


def test_energy_need_sensor_is_registered_observer_only() -> None:
    assert 'DummyOSPlanEnergyNeedSensor(coordinator)' in SENSOR
    assert '_attr_unique_id = "do_plan_energy_need"' in SENSOR
    assert '_attr_suggested_object_id = "do_plan_energy_need"' in SENSOR
    assert 'build_do_plan_energy_need(' in SENSOR
    assert 'SOC_ENTITY = "sensor.do_plan_soc_contract"' in SENSOR
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_soc_contract_sensor.py").read_text()
    assert 'RAW_SOC_ENTITY = "sensor.anker_solix_solarbank_max_ac_185_soc"' in adapter
    assert 'physical_execution_authority' in (ROOT / "custom_components/dummy_os_data/do_plan_energy_need.py").read_text()


def test_planner_identity_cleanup_is_deferred() -> None:
    init_source = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
    assert '("sensor", "do_plan_energy_need", "sensor.do_plan_energy_need")' not in init_source
