"""Keep Source, Weather, Solar and Degree Days entity naming stable."""
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components/dummy_os_data"

def text(name):
    return (ROOT / name).read_text()

def test_retained_public_entity_bases_use_full_name_semantics():
    for name in ("home_input_sensor.py", "sensor.py", "solar_sensor.py", "degree_days_sensor.py"):
        assert "_attr_has_entity_name = False" in text(name)

def test_retained_canonical_entity_names():
    assert "do_source_home_power" in text("home_input_sensor.py")
    assert "do_solar_forecast_timeline" in text("solar_sensor.py")
    assert "do_degree_days_status" in text("degree_days_sensor.py")
    assert "do_weather_forecast_timeline" in text("sensor.py")

def test_device_identity_is_stable():
    assert 'DOMAIN = "dummy_os_data"' in text("const.py")
    assert 'NAME = "Dummy OS Energy"' in text("const.py")
