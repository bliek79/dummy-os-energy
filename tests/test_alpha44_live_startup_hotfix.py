"""Prevent former Home Forecast startup workload from returning."""
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components/dummy_os_data"

def test_no_home_forecast_exec_jobs():
    for name in ("sensor.py", "home_input_sensor.py", "coordinator.py"):
        text = (MODULE / name).read_text()
        assert "calculate_recency_weighting" not in text
        assert "calculate_fallback_hierarchy" not in text
        assert "HomeBaselineForecast" not in text
        assert "DummyOSAsyncForecastResultSensor" not in text

def test_solar_still_uses_unchanged_72_hour_timeline():
    solar = (MODULE / "solar.py").read_text()
    assert "FORECAST_SLOTS" in solar
    assert "_rebuild_residual_learning_candidate" in solar
    assert "_record_residual_learning_validation" in solar

def test_solar_and_weather_remain_background_sources():
    init = (MODULE / "__init__.py").read_text()
    assert '"Dummy OS Data retained cloud sources"' in init
    assert "eager_start=False" in init
    assert "entry.async_create_background_task(" in init
