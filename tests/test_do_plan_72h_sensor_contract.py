from pathlib import Path
ROOT=Path(__file__).parents[1]

def test_sensor_registered_and_executor_backed():
    sensor=(ROOT/'custom_components/dummy_os_data/sensor.py').read_text(); adapter=(ROOT/'custom_components/dummy_os_data/do_plan_72h_sensor.py').read_text()
    assert 'build_do_plan_72h_sensors' in sensor and '*build_do_plan_72h_sensors(coordinator)' in sensor
    assert '_attr_unique_id = "do_plan_72h"' in adapter
    assert 'DummyOSPlanReserveSOCSensor' in adapter

def test_no_execution_authority_in_step5_module():
    text=(ROOT/'custom_components/dummy_os_data/do_plan_72h.py').read_text()
    for needle in ('"shadow_only": True','"active_use_permitted": False','"physical_execution_authority": False','"plan_store_write": False','"scheduler_invoked": False','"safety_chain_invoked": False','"service_calls_performed": False'):
        assert needle in text
