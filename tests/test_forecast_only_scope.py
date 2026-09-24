from pathlib import Path
import json
import re

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/dummy_os_data"


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_only_forecast_platforms_are_active():
    const = _read("custom_components/dummy_os_data/const.py")
    assert 'PLATFORMS = ["sensor", "select"]' in const


def test_sensor_and_select_runtime_have_no_ems_planner_or_presence_layer():
    sensor = _read("custom_components/dummy_os_data/sensor.py")
    select = _read("custom_components/dummy_os_data/select.py")
    init = _read("custom_components/dummy_os_data/__init__.py")
    combined = "\n".join((sensor, select, init))
    for marker in (
        "do_plan_",
        "forecast_planner_contract",
        "DummyOSEnergyForecastPlanner",
        "DummyOSPlanOperatingMode",
        "PresenceAway",
        "presence_runtime",
        "manual_plan_",
    ):
        assert marker not in combined
    assert "class DummyOSEnergyProfileSelect" in select
    assert "class DummyOSAsyncForecastResultSensor" in sensor
    assert "DummyOSAsyncPlannerResultSensor" not in sensor


def test_retired_runtime_modules_are_absent():
    retired = (
        "binary_sensor.py",
        "switch.py",
        "datetime.py",
        "number.py",
        "services.yaml",
        "presence.py",
        "presence_runtime.py",
        "forecast_planner_contract.py",
        "planner_hours.py",
        "planner_time_views.py",
        "planner_time_runtime.py",
        "planner_time_input.py",
        "planner_native_need.py",
        "planner_soc_bridge.py",
        "do_plan_input.py",
        "do_plan_energy_need.py",
        "do_plan_reserve_soc.py",
        "do_plan_preview.py",
        "do_plan_72h.py",
        "do_plan_grid_support.py",
        "do_plan_store.py",
        "do_plan_scheduler.py",
        "do_plan_safety.py",
        "do_plan_operating_mode.py",
    )
    for name in retired:
        assert not (COMPONENT / name).exists(), name


def test_forecast_contract_and_quality_entities_remain():
    const = _read("custom_components/dummy_os_data/const.py")
    sensor = _read("custom_components/dummy_os_data/sensor.py")
    home = _read("custom_components/dummy_os_data/home_input_sensor.py")
    select = _read("custom_components/dummy_os_data/select.py")
    assert "QUARTER_MINUTES = 15" in const
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const
    for marker in (
        "do_energy_forecast_timeline",
        "do_energy_forecast_next_quarter",
        "do_energy_forecast_coverage",
        "do_energy_forecast_confidence",
        "do_energy_forecast_model_health",
        "do_energy_peak_learning",
        "do_energy_time_windows",
        "do_energy_recency_weighting",
    ):
        assert marker in sensor
    for marker in (
        "do_energy_fallback_hierarchy",
        "do_energy_meaningful_confidence",
        "do_energy_forecast_quality_by_horizon",
    ):
        assert marker in home
    assert '_attr_unique_id = "do_energy_profile"' in select


def test_normal_away_unclassified_profile_contract_remains():
    const = _read("custom_components/dummy_os_data/const.py")
    assert 'PROFILE_NORMAL = "normal"' in const
    assert 'PROFILE_AWAY = "away"' in const
    assert 'PROFILE_UNCLASSIFIED = "unclassified"' in const
    assert "PROFILE_LEARNING_OPTIONS = [PROFILE_NORMAL, PROFILE_AWAY]" in const
    assert "PROFILE_OPTIONS = [PROFILE_NORMAL, PROFILE_AWAY, PROFILE_UNCLASSIFIED]" in const


def test_non_blocking_forecast_source_startup_is_preserved():
    init = _read("custom_components/dummy_os_data/__init__.py")
    setup = init.split("async def async_setup_entry", 1)[1]
    assert setup.index("async_forward_entry_setups") < setup.index("_async_setup_cloud_sources")
    assert "await asyncio.gather(" in init
    assert "weather_setup()" in init
    assert "coordinator.prices.async_setup()" in init
    assert "coordinator.solar.async_setup()" in init
    assert "coordinator._source_setup_task = source_setup_task" in init


def test_release_version_is_consistent():
    const = _read("custom_components/dummy_os_data/const.py")
    manifest = json.loads(_read("custom_components/dummy_os_data/manifest.json"))
    match = re.search(r'^VERSION = "([^"]+)"$', const, re.MULTILINE)
    assert match is not None
    assert match.group(1) == manifest["version"]
    assert manifest["version"].startswith("0.2.0-alpha.")
