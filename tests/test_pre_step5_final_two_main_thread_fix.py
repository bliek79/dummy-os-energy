from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_coverage_and_peak_learning_are_executor_backed():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    assert "class DummyOSHomeForecastCoverageSensor(DummyOSAsyncForecastResultSensor)" in sensor
    assert "class DummyOSEnergyPeakLearningSensor(DummyOSAsyncForecastResultSensor)" in sensor
    assert "return calculate_peak_learning(snapshot[\"evaluations\"], profile, dt_util.as_local)" in sensor
    coverage_block = sensor.split("class DummyOSHomeForecastCoverageSensor", 1)[1].split("class DummyOSHomeForecastConfidenceSensor", 1)[0]
    assert "self._forecast()" not in coverage_block
    peak_block = sensor.split("class DummyOSEnergyPeakLearningSensor", 1)[1]
    assert "calculate_peak_learning(self.coordinator.evaluations" not in peak_block

def test_forecast_entities_remain_present():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    for entity_id in ("do_energy_forecast_coverage", "do_energy_peak_learning"):
        assert entity_id in sensor
