"""Regression contract for alpha.26 native manual plan controls."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMP = ROOT / "custom_components" / "dummy_os_data"


def text(name: str) -> str:
    return (COMP / name).read_text(encoding="utf-8")


def test_alpha26_version_and_platform_contract() -> None:
    const = text("const.py")
    manifest = text("manifest.json")
    assert 'VERSION = "0.2.0-alpha.26"' in const
    assert '"version": "0.2.0-alpha.26"' in manifest
    assert '"number"' in const
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const


def test_three_slots_expose_all_six_native_controls() -> None:
    select = text("select.py")
    datetime = text("datetime.py")
    number = text("number.py")
    assert "range(1, SLOT_COUNT + 1)" in select
    assert "DummyOSManualPlanActionSelect" in select
    assert "DummyOSManualPlanStart" in datetime
    for field in (
        '"power_w"',
        '"target_soc_percent"',
        '"max_start_delay_minutes"',
        '"max_runtime_minutes"',
    ):
        assert field in number


def test_controls_use_manual_lifecycle_and_persistence() -> None:
    adapter = text("do_plan_manual_interface_sensor.py")
    for symbol in (
        "new_manual_draft",
        "edit_manual_draft",
        "patch_manual_draft",
        "validate_manual_draft",
        "finalize_manual_draft",
        "clear_manual_slot",
    ):
        assert symbol in adapter
    assert "do_plan_manual_controls" in adapter
    assert "Store[dict[str, Any]]" in adapter
    assert '"drafts"' in adapter
    assert '"controls"' in adapter


def test_safety_boundary_remains_shadow_only() -> None:
    adapter = text("do_plan_manual_interface_sensor.py")
    assert '"operational_plan_store_write": False' in adapter
    assert '"scheduler_invoked": False' in adapter
    assert '"safety_chain_invoked": False' in adapter
    assert '"external_service_calls_performed": False' in adapter
    assert '"physical_execution_authority": False' in adapter
