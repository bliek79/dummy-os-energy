"""Scope regression: Source, Weather, Solar and Degree Days only."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "custom_components/dummy_os_data"

def source(name):
    return (MODULE / name).read_text(encoding="utf-8")

def test_only_sensor_platform_exists():
    assert 'PLATFORMS = ["sensor"]' in source("const.py")
    assert not (MODULE / "select.py").exists()

def test_legacy_home_and_price_modules_are_absent():
    for name in (
        "forecast.py", "evaluation.py", "energy_store.py",
        "time_windows.py", "recency_weighting.py", "fallback_hierarchy.py",
        "meaningful_confidence.py", "horizon_quality.py", "model_health.py",
        "prices.py", "select.py",
    ):
        assert not (MODULE / name).exists(), name

def test_runtime_only_registers_retained_sensors():
    sensor = source("sensor.py")
    assert "*build_home_input_sensors(coordinator)" in sensor
    assert "*build_solar_sensors(coordinator)" in sensor
    assert "*build_degree_days_sensors(coordinator)" in sensor
    assert "DummyOSWeatherTimelineSensor(coordinator)" in sensor
    for unwanted in ("DummyOSHomeForecast", "DummyOSEnergy", "calculate_recency_weighting", "do_prices_"):
        assert unwanted not in sensor

def test_startup_has_no_home_learning_or_price_tasks():
    init = source("__init__.py")
    coordinator = source("coordinator.py")
    assert "await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)" in init
    assert "_async_setup_cloud_sources(coordinator)" in init
    assert "coordinator.weather.async_setup()" in init
    assert "coordinator.solar.async_setup()" in init
    assert "coordinator.degree_days.async_setup()" in init
    assert "async_create_background_task" in init
    assert "coordinator.prices" not in init
    assert "DummyOSHomeDataCoordinator" not in init
    assert "DummyOSHomeDataCoordinator" not in coordinator
    assert "forecast_snapshots" not in coordinator

def test_preserved_native_forecast_contract():
    const = source("const.py")
    assert "QUARTER_MINUTES = 15" in const
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const
    assert "SOLAR_STORAGE_KEY" in const

def test_version_consistency():
    version = "0.2.0-alpha.52"
    assert f'VERSION = "{version}"' in source("const.py")
    manifest = json.loads(source("manifest.json"))
    assert manifest["version"] == version
    assert (ROOT / f"RELEASE_NOTES_{version}.md").exists()
