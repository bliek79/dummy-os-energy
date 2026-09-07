from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "custom_components/dummy_os_data/home_input_sensor.py").read_text()
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
MIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()
COORDINATOR = (ROOT / "custom_components/dummy_os_data/coordinator.py").read_text()
FORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()

def test_step12_sensor_identity_and_registry_route():
    assert '_attr_unique_id = "do_energy_forecast_quality_by_horizon"' in SOURCE
    assert '_attr_suggested_object_id = "do_energy_forecast_quality_by_horizon"' in SOURCE
    assert 'DummyOSEnergyForecastQualityByHorizonSensor(coordinator)' in SOURCE
    assert '("sensor", "do_energy_forecast_quality_by_horizon", "sensor.do_energy_forecast_quality_by_horizon")' in INIT
    assert '"do_energy_forecast_quality_by_horizon": "sensor.dummy_os_forecast_do_energy_forecast_quality_by_horizon"' in MIGRATIONS

def test_step12_store_and_capture_are_observer_only_extensions():
    assert 'self._capture_horizon_probes(' in COORDINATOR
    assert 'self._evaluate_horizon_completed_quarter(result)' in COORDINATOR
    assert '"horizon_pending_probes": self.horizon_pending_probes' in COORDINATOR
    assert '"horizon_daily_stats": self.horizon_daily_stats' in COORDINATOR

def test_production_forecast_contract_remains_native_288():
    assert 'for offset in range(FORECAST_SLOTS):' in FORECAST
    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST
    assert 'horizon_quality' not in FORECAST
