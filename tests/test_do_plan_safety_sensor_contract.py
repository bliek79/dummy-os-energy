from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_safety_prestart_entities_are_registered_once():
    adapter=(ROOT/"custom_components/dummy_os_data/do_plan_safety_sensor.py").read_text()
    bundle=(ROOT/"custom_components/dummy_os_data/do_plan_grid_support_sensor.py").read_text()
    assert '_attr_unique_id = "do_plan_safety"' in adapter
    assert '_attr_unique_id = "do_plan_prestart"' in adapter
    assert bundle.count("build_do_plan_safety_sensors(coordinator)")==1


def test_safety_prestart_reuses_scheduler_and_plan_store_runtime():
    adapter=(ROOT/"custom_components/dummy_os_data/do_plan_safety_sensor.py").read_text()
    assert "get_do_plan_scheduler_runtime(coordinator)" in adapter
    assert "scheduler_runtime.store_runtime" in adapter
    assert "async_save_snapshot" not in adapter
    assert "async_apply_bridge_candidates" not in adapter


def test_safety_prestart_contains_no_physical_control_path():
    core=(ROOT/"custom_components/dummy_os_data/do_plan_safety.py").read_text()
    adapter=(ROOT/"custom_components/dummy_os_data/do_plan_safety_sensor.py").read_text()
    combined=core+adapter
    for needle in ('"shadow_only": True','"active_use_permitted": False','"physical_execution_authority": False','"operational_plan_store_write": False','"execution_handoff_performed": False','"service_calls_performed": False','"plan_store_mutated": False','"mode_switch_performed": False'):
        assert needle in combined
    for forbidden in ("async_call(","services.async_call","third_party_control","self_consumption"):
        assert forbidden not in combined


def test_safety_consumes_existing_reserve_entity_without_second_planner_calculation():
    adapter=(ROOT/"custom_components/dummy_os_data/do_plan_safety_sensor.py").read_text()
    assert 'RESERVE_ENTITY = "sensor.dummy_os_energy_do_plan_reserve_soc"' in adapter
    assert "hass.states.get(RESERVE_ENTITY)" in adapter
    assert "_build_reserve_from_snapshot" not in adapter
    assert "_planner_runtime_snapshot" not in adapter
    assert "HomeBaselineForecast" not in adapter
