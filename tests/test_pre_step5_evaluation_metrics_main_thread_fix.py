from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_evaluation_family_uses_executor_backed_shared_base():
    sensor=(ROOT/"custom_components/dummy_os_data/sensor.py").read_text()
    start=sensor.index("class DummyOSEvaluationBaseSensor(DummyOSBaseSensor):")
    end=sensor.index("\n\nclass DummyOSWeatherBaseSensor", start)
    block=sensor[start:end]
    assert "async_add_executor_job" in block
    assert "calculate_metrics, evaluations, profile" in block
    assert "self._cached_metrics" in block
    assert "self.coordinator.evaluation_metrics" not in block
    for cls in ("DummyOSHomeForecastAccuracySensor", "DummyOSHomeForecastMaeSensor", "DummyOSHomeForecastBiasSensor", "DummyOSHomeForecastEvaluationSamplesSensor"):
        assert f"class {cls}(DummyOSEvaluationBaseSensor):" in block
    for uid in ("do_energy_forecast_accuracy", "do_energy_forecast_mae", "do_energy_forecast_bias", "do_energy_forecast_evaluation_samples"):
        assert uid in block

def test_safety_invariants_remain_unchanged():
    preview=(ROOT/"custom_components/dummy_os_data/do_plan_preview.py").read_text()
    assert '"shadow_only": True' in preview
    assert '"active_use_permitted": False' in preview
    assert '"physical_execution_authority": False' in preview
