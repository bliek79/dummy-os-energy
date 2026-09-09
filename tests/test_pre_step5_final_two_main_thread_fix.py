from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_coverage_and_peak_learning_are_executor_backed():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    assert "class DummyOSHomeForecastCoverageSensor(DummyOSAsyncPlannerResultSensor)" in sensor
    assert "class DummyOSEnergyPeakLearningSensor(DummyOSAsyncPlannerResultSensor)" in sensor
    assert "return calculate_peak_learning(snapshot[\"evaluations\"], profile, dt_util.as_local)" in sensor
    coverage_block = sensor.split("class DummyOSHomeForecastCoverageSensor", 1)[1].split("class DummyOSHomeForecastConfidenceSensor", 1)[0]
    assert "self._forecast()" not in coverage_block
    peak_block = sensor.split("class DummyOSEnergyPeakLearningSensor", 1)[1]
    assert "calculate_peak_learning(self.coordinator.evaluations" not in peak_block

def test_pre_step5_safety_and_identity_invariants_remain_present():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    preview = (ROOT / "custom_components/dummy_os_data/do_plan_preview.py").read_text()
    for entity_id in ("do_energy_forecast_coverage", "do_energy_peak_learning"):
        assert entity_id in sensor
    assert '"shadow_only": True' in preview
    assert '"active_use_permitted": False' in preview
    assert '"physical_execution_authority": False' in preview
