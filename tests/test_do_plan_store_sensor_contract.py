from pathlib import Path
ROOT=Path(__file__).parents[1]

def test_step6_store_entities_are_registered_via_planner_sensor_bundle():
    adapter=(ROOT/'custom_components/dummy_os_data/do_plan_grid_support_sensor.py').read_text()
    store_adapter=(ROOT/'custom_components/dummy_os_data/do_plan_store_sensor.py').read_text()
    assert 'build_do_plan_store_sensors' in adapter
    assert '_attr_unique_id = "do_plan_store"' in store_adapter
    assert 'f"do_plan_store_slot_{slot_id}"' in store_adapter

def test_step6_keeps_all_operational_rights_closed():
    text=(ROOT/'custom_components/dummy_os_data/do_plan_store.py').read_text()
    for needle in (
        '"shadow_only": True',
        '"shadow_store_write": True',
        '"operational_plan_store_write": False',
        '"active_use_permitted": False',
        '"physical_execution_authority": False',
        '"scheduler_invoked": False',
        '"safety_chain_invoked": False',
        '"service_calls_performed": False',
    ):
        assert needle in text
