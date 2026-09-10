from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "dummy_os_data"


def test_preview_consumes_published_upstream_contracts_only():
    source = (ROOT / "do_plan_preview_sensor.py").read_text(encoding="utf-8")
    assert "_build_plan_input_from_snapshot" not in source
    assert "_build_reserve_from_snapshot" not in source
    assert '"dependency_mode"] = "published_upstream_contracts"' in source
    assert 'async_get_entity_id("sensor", DOMAIN, unique_id)' in source


def test_grid_support_entity_does_not_rebuild_dependencies():
    source = (ROOT / "do_plan_grid_support_sensor.py").read_text(encoding="utf-8")
    grid_class, bridge_class = source.split("class DummyOSPlanStoreBridgeSensor", 1)
    assert "_build_plan_input_from_snapshot(snapshot)" not in grid_class
    assert "_build_energy_need_from_snapshot(snapshot)" not in grid_class
    assert '"dependency_mode"]="published_upstream_contracts"' in grid_class
    # The cached Bridge intentionally retains its one material-change rebuild path.
    assert "_build_plan_input_from_snapshot(snapshot)" in bridge_class
    assert "build_plan_store_bridge_refresh_key(snapshot)" in bridge_class


def test_performance_hotfix_does_not_add_control_authority():
    preview = (ROOT / "do_plan_preview_sensor.py").read_text(encoding="utf-8")
    grid = (ROOT / "do_plan_grid_support_sensor.py").read_text(encoding="utf-8")
    for source in (preview, grid):
        assert "async_call(" not in source
        assert "command_dispatched=True" not in source
        assert "physical_execution_authority=True" not in source
