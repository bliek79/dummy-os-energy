from pathlib import Path
import json
import re

ROOT = Path(__file__).parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_live_forecast_cache_no_longer_calls_removed_planner_helpers():
    sensor = _read("custom_components/dummy_os_data/sensor.py")
    block = sensor.split("    def _forecast(self):", 1)[1].split("\n\nclass DummyOSActualQuarterSensor", 1)[0]
    assert "window_start = ceil_quarter(reference)" in block
    assert "window_start=window_start" in block
    assert "build_time_contract(" not in block
    assert 'utc(contract["window_start"])' not in block


def test_heavy_forecast_refreshes_wait_until_home_assistant_started():
    sensor = _read("custom_components/dummy_os_data/sensor.py")
    home = _read("custom_components/dummy_os_data/home_input_sensor.py")
    for source in (sensor, home):
        assert "CoreState.running" in source
        assert "async_at_started" in source
        assert ".entry.async_create_background_task(" in source
        assert "self.hass.async_create_task(" not in source
        assert "eager_start=False" in source


def test_cloud_source_wave_is_a_true_background_config_entry_task():
    init = _read("custom_components/dummy_os_data/__init__.py")
    setup = init.split("async def async_setup_entry", 1)[1]
    assert "entry.async_create_background_task(" in setup
    assert '"Dummy OS Data cloud sources"' in setup
    assert "eager_start=False" in setup
    assert "hass.async_create_task(" not in setup


def test_forecast_only_boundary_stays_closed():
    sensor = _read("custom_components/dummy_os_data/sensor.py")
    home = _read("custom_components/dummy_os_data/home_input_sensor.py")
    init = _read("custom_components/dummy_os_data/__init__.py")
    combined = "\n".join((sensor, home, init))
    for marker in (
        "do_plan_",
        "presence_runtime",
        "DummyOSPlanOperatingMode",
        "manual_plan_",
    ):
        assert marker not in combined


def test_alpha44_version_is_consistent():
    const = _read("custom_components/dummy_os_data/const.py")
    manifest = json.loads(_read("custom_components/dummy_os_data/manifest.json"))
    match = re.search(r'^VERSION = "([^"]+)"$', const, re.MULTILINE)
    assert match is not None
    assert match.group(1) == manifest["version"] == "0.2.0-alpha.44"
