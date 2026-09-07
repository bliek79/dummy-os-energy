from pathlib import Path

ROOT = Path(__file__).parents[1]
SENSOR = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
MIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()
CONTRACT = (ROOT / "custom_components/dummy_os_data/forecast_planner_contract.py").read_text()
FORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()

def test_step15_canonical_sensor_and_registry_route():
    assert '_attr_name = "DO Energy Forecast Planner Contract"' in SENSOR
    assert '_attr_unique_id = "do_energy_forecast_planner_contract"' in SENSOR
    assert '_attr_suggested_object_id = "do_energy_forecast_planner_contract"' in SENSOR
    assert 'DummyOSEnergyForecastPlannerContractSensor(coordinator)' in SENSOR
    assert '("sensor", "do_energy_forecast_planner_contract", "sensor.do_energy_forecast_planner_contract")' in INIT
    assert '"do_energy_forecast_planner_contract": "sensor.dummy_os_forecast_do_energy_forecast_planner_contract"' in MIGRATIONS

def test_step15_uses_shared_step13_and_step14_results():
    assert 'def _build_planner_hours_result(' in SENSOR
    assert 'def _build_model_health_result(' in SENSOR
    assert 'build_forecast_planner_contract(' in SENSOR
    assert 'return _build_planner_hours_result(self.coordinator)' in SENSOR
    assert 'return _build_model_health_result(self.coordinator, self._forecast())' in SENSOR

def test_step15_contract_is_versioned_and_model_agnostic():
    assert 'CONTRACT_NAME = "dummy_os_forecast_to_planner"' in CONTRACT
    assert 'CONTRACT_VERSION = 1' in CONTRACT
    assert 'SCHEMA_VERSION = 1' in CONTRACT
    assert 'NATIVE_SLOT_COUNT = 288' in CONTRACT
    assert 'PLANNER_HOUR_COUNT = 72' in CONTRACT
    assert 'physical_execution_authority": False' in CONTRACT
    assert 'fallback_hierarchy' not in CONTRACT
    assert 'RECENCY_HALF_LIFE_DAYS' not in CONTRACT

def test_native_forecast_contract_remains_step14_default():
    assert 'slot_count: int = FORECAST_SLOTS' in FORECAST
    assert 'MAX_INTERNAL_FORECAST_SLOTS = FORECAST_SLOTS + 3' in FORECAST
    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST
