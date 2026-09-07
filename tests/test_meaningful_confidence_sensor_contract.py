from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "custom_components/dummy_os_data/home_input_sensor.py").read_text()
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()
MIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()
CORE = (ROOT / "custom_components/dummy_os_data/meaningful_confidence.py").read_text()
FORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()
CONST = (ROOT / "custom_components/dummy_os_data/const.py").read_text()


def test_step11_sensor_identity_and_registration():
    assert '_attr_name = "DO Energy Meaningful Confidence"' in SOURCE
    assert '_attr_unique_id = "do_energy_meaningful_confidence"' in SOURCE
    assert '_attr_suggested_object_id = "do_energy_meaningful_confidence"' in SOURCE
    assert 'DummyOSEnergyMeaningfulConfidenceSensor(coordinator)' in SOURCE
    assert '("sensor", "do_energy_meaningful_confidence", "sensor.do_energy_meaningful_confidence")' in INIT
    assert '"do_energy_meaningful_confidence": "sensor.dummy_os_forecast_do_energy_meaningful_confidence"' in MIGRATIONS


def test_step11_is_observer_only_and_cannot_promote_itself():
    assert '"observer_only": True' in CORE
    assert '"forecast_influence_enabled": False' in CORE
    assert '"production_confidence_unchanged": True' in CORE
    assert '"promotion_ready": False' in CORE
    assert '"live_shadow_required": True' in CORE
    assert 'ALGORITHM_VERSION = "meaningful_confidence_observer_v1"' in CORE


def test_step11_preserves_native_production_contract():
    assert 'QUARTER_MINUTES = 15' in CONST
    assert 'FORECAST_HORIZON_HOURS = 72' in CONST
    assert 'FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES' in CONST
    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST
    assert 'confidence = min(0.98, 0.58 + 0.08 * min(samples, 5))' in FORECAST
    assert 'confidence = min(0.78, 0.42 + 0.07 * min(samples, 5))' in FORECAST
