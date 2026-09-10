from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "dummy_os_data"

FILES = (
    "do_plan_safety_sensor.py",
    "do_plan_scheduler_sensor.py",
    "do_plan_execution_preview_sensor.py",
    "do_plan_manual_interface_sensor.py",
    "do_plan_store_sensor.py",
)


def _source(name: str) -> str:
    return (COMPONENT / name).read_text(encoding="utf-8")


def test_planner_callback_adapters_import_home_assistant_callback_marker() -> None:
    for name in FILES:
        imports = [line for line in _source(name).splitlines() if line.startswith("from homeassistant.core import ")]
        assert any("callback" in line for line in imports), name


def test_safety_source_change_handler_is_event_loop_callback() -> None:
    source = _source("do_plan_safety_sensor.py")
    assert "@callback\n    def _handle_source_update" in source
    assert "@callback\n    def _handle_update" in source


def test_scheduler_execution_manual_and_store_listeners_are_callbacks() -> None:
    for name in (
        "do_plan_scheduler_sensor.py",
        "do_plan_execution_preview_sensor.py",
        "do_plan_manual_interface_sensor.py",
        "do_plan_store_sensor.py",
    ):
        source = _source(name)
        assert "@callback\n    def _handle_update" in source, name


def test_plan_store_runtime_notification_is_callback_owned() -> None:
    source = _source("do_plan_store_sensor.py")
    assert "@callback\n    def _notify" in source


def test_no_direct_listener_registration_of_async_write_ha_state_remains() -> None:
    for name in FILES:
        source = _source(name)
        assert "add_listener(self.async_write_ha_state)" not in source, name


def test_thread_safety_hotfix_does_not_open_physical_control_path() -> None:
    combined = "\n".join(_source(name) for name in FILES)
    assert "hass.services.async_call" not in combined
    assert "physical_execution_authority\": True" not in combined
    assert "active_use_permitted\": True" not in combined
