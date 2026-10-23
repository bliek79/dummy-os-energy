"""Reject accidental recreation of Home Forecast and Prices processing."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
MOD = ROOT / "custom_components/dummy_os_data"

def test_no_home_coordinator_event_loop():
    coordinator = (MOD / "coordinator.py").read_text()
    assert "_async_quarter_boundary" not in coordinator
    assert "forecast_snapshots" not in coordinator
    assert "history" not in coordinator
    assert "DummyOSWeatherCoordinator(hass)" in coordinator

def test_source_states_do_not_trigger_legacy_forecast():
    source = (MOD / "home_input_sensor.py").read_text()
    assert "async_track_state_change_event" in source
    assert "async_write_ha_state" in source
    assert "DummyOSEnergyFallbackHierarchySensor" not in source
    assert "calculate_meaningful_confidence" not in source

def test_price_polling_removed():
    init = (MOD / "__init__.py").read_text()
    assert "DummyOSPricesCoordinator" not in init
    assert "prices.async_setup" not in init
    assert not (MOD / "prices.py").exists()
