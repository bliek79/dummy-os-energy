from pathlib import Path
R=Path(__file__).parents[1]
def test_wiring():
 s=(R/'custom_components/dummy_os_data/sensor.py').read_text(); x=(R/'custom_components/dummy_os_data/do_plan_safety_sensor.py').read_text(); assert 'SOC_ENTITY = "sensor.do_plan_soc_contract"' in s; assert 'SOC_ENTITY = "sensor.do_plan_soc_contract"' in x; assert '*build_do_plan_soc_contract_sensors(coordinator)' in s; assert 'central_soc_contract_v1' in s
