from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_execution_preview_entities_registered_once():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_execution_preview_sensor.py").read_text()
    bundle = (ROOT / "custom_components/dummy_os_data/do_plan_grid_support_sensor.py").read_text()
    binary = (ROOT / "custom_components/dummy_os_data/binary_sensor.py").read_text()
    assert '_attr_unique_id = "do_plan_execution_preview"' in adapter
    assert '_attr_unique_id = "do_plan_execution_preview_ready"' in adapter
    assert bundle.count("build_do_plan_execution_preview_sensors(coordinator)") == 1
    assert binary.count("build_do_plan_execution_preview_binary_sensors(coordinator)") == 1


def test_execution_preview_reuses_existing_shared_runtimes():
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_execution_preview_sensor.py").read_text()
    assert "get_do_plan_safety_runtime(coordinator)" in adapter
    assert "safety_runtime.scheduler_runtime" in adapter
    assert "safety_runtime.store_runtime" in adapter
    assert "build_do_plan_72h" not in adapter
    assert "_build_reserve_from_snapshot" not in adapter
    assert "_planner_runtime_snapshot" not in adapter


def test_execution_preview_has_no_physical_control_or_store_write_path():
    core = (ROOT / "custom_components/dummy_os_data/do_plan_execution_preview.py").read_text()
    adapter = (ROOT / "custom_components/dummy_os_data/do_plan_execution_preview_sensor.py").read_text()
    combined = core + adapter
    for needle in (
        '"shadow_only": True',
        '"active_use_permitted": False',
        '"physical_execution_authority": False',
        '"operational_plan_store_write": False',
        '"execution_handoff_performed": False',
        '"service_calls_performed": False',
        '"plan_store_mutated": False',
        '"mode_switch_performed": False',
        '"command_dispatched": False',
    ):
        assert needle in combined
    for forbidden in (
        "async_call(", "services.async_call", "async_save_snapshot", "async_apply_bridge_candidates",
        "set_manual_plan", "apply_manual_edit", "third_party_control", "self_consumption",
    ):
        assert forbidden not in combined
