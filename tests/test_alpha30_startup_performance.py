"""Startup contract for reduced integration, retaining cloud-background startup."""
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components/dummy_os_data"

def test_platform_first_then_background_cloud():
    init = (ROOT / "__init__.py").read_text()
    setup = init.split("async def async_setup_entry", 1)[1]
    assert setup.index("async_forward_entry_setups") < setup.index("async_create_background_task")
    assert "eager_start=False" in setup

def test_cloud_sources_are_weather_solar_only():
    init = (ROOT / "__init__.py").read_text()
    helper = init.split("async def _async_setup_cloud_sources", 1)[1].split("def _is_obsolete_home_input_state", 1)[0]
    assert "asyncio.gather" in helper
    assert "coordinator.weather.async_setup()" in helper
    assert "coordinator.solar.async_setup()" in helper
    assert "coordinator.degree_days.async_setup()" in helper
    assert "coordinator.prices" not in helper

def test_cancel_background_wave_before_unload():
    init = (ROOT / "__init__.py").read_text()
    unload = init.split("async def async_unload_entry", 1)[1]
    assert "source_task.cancel()" in unload
    assert "await source_task" in unload
