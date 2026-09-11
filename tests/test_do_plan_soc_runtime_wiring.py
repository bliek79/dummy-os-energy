from pathlib import Path
ROOT = Path(__file__).parents[1]
def test_energy_need_uses_shared_soc_runtime_not_entity_lookup():
    source = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    assert 'get_do_plan_soc_contract_runtime(self.coordinator).result()' in source
    assert 'snapshot["soc_source_entity"] = "runtime:do_plan_soc_contract_v1"' in source
    assert '[RAW_SOC_ENTITY],' in source
def test_safety_uses_shared_soc_runtime_and_raw_source_listener():
    source = (ROOT / "custom_components/dummy_os_data/do_plan_safety_sensor.py").read_text()
    assert 'get_do_plan_soc_contract_runtime(self.coordinator).result()' in source
    assert '[RAW_SOC_ENTITY, RESERVE_ENTITY]' in source
    assert 'safety["soc_source_entity"] = "runtime:do_plan_soc_contract_v1"' in source
def test_contract_sensor_and_consumers_share_one_runtime():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_soc_contract_sensor.py").read_text()
    assert 'class DummyOSPlanSOCContractRuntime' in adapter
    assert '_RUNTIME_ATTR = "_dummy_os_do_plan_soc_contract_runtime"' in adapter
    assert 'self.runtime = get_do_plan_soc_contract_runtime(coordinator)' in adapter
