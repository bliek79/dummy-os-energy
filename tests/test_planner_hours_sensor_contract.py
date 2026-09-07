from pathlib import Path

ROOT = Path(__file__).parents[1]
SENSOR = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
FORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
MIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()
PLANNER = (ROOT / "custom_components/dummy_os_data/planner_hours.py").read_text()

def test_step14_sensor_identity_and_registry_route():
    assert '_attr_name = "DO Energy Forecast Planner Hours"' in SENSOR
    assert '_attr_unique_id = "do_energy_forecast_planner_hours"' in SENSOR
    assert '_attr_suggested_object_id = "do_energy_forecast_planner_hours"' in SENSOR
    assert 'DummyOSEnergyForecastPlannerHoursSensor(coordinator)' in SENSOR
    assert '("sensor", "do_energy_forecast_planner_hours", "sensor.do_energy_forecast_planner_hours")' in INIT
    assert '"do_energy_forecast_planner_hours": "sensor.dummy_os_forecast_do_energy_forecast_planner_hours"' in MIGRATIONS

def test_step14_production_default_and_internal_bound():
    assert 'slot_count: int = FORECAST_SLOTS' in FORECAST
    assert 'MAX_INTERNAL_FORECAST_SLOTS = FORECAST_SLOTS + 3' in FORECAST
    assert 'for offset in range(slot_count):' in FORECAST
    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST

def test_step14_no_padding_or_second_architecture():
    assert '"padding_used": False' in PLANNER
    assert '"second_forecast_architecture": False' in PLANNER
    assert 'NATIVE_PUBLIC_SLOTS = 288' in PLANNER
    assert 'PLANNER_HOUR_COUNT = 72' in PLANNER
    assert 'QUARTERS_PER_HOUR = 4' in PLANNER
