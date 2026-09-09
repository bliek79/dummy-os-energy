from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_slot_count_validation_location() -> None:
    source = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()
    profile_block = source.split("def profile_statistics", 1)[1].split("def all_profile_statistics", 1)[0]
    build_block = source.split("def build(", 1)[1].split("def average_confidence", 1)[0]
    assert "slot_count < 1" not in profile_block
    assert "slot_count < 1 or slot_count > MAX_INTERNAL_FORECAST_SLOTS" in build_block

def test_heavy_observers_are_executor_backed() -> None:
    home = (ROOT / "custom_components/dummy_os_data/home_input_sensor.py").read_text()
    assert home.count("async_add_executor_job(") >= 2
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    block = sensor.split("class DummyOSEnergyRecencyWeightingSensor", 1)[1].split("class DummyOSEnergyPeakLearningSensor", 1)[0]
    assert "async_add_executor_job(" in block
    assert "observer_calculation_pending" in home
    assert "observer_calculation_pending" in block
