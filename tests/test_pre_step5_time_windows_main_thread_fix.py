from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_time_windows_is_executor_backed_without_identity_change():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    start = sensor.index("class DummyOSEnergyTimeWindowsSensor(DummyOSBaseSensor):")
    end = sensor.index("\n\nclass DummyOSEnergyRecencyWeightingSensor", start)
    block = sensor[start:end]
    assert '_attr_unique_id = "do_energy_time_windows"' in block
    assert '_attr_suggested_object_id = "do_energy_time_windows"' in block
    assert 'return "DO Energy Time Windows"' in block
    assert "async_add_executor_job" in block
    assert "self._cached_result" in block
    assert "self._refresh_pending" in block
    assert "calculate_peak_learning(evaluations, profile, dt_util.as_local)" in block
    assert "calculate_time_windows(peak_result, profile, dt_util.as_local)" in block
    assert "calculate_peak_learning(self.coordinator.evaluations" not in block


def test_time_windows_fix_preserves_safety_invariants():
    preview = (ROOT / "custom_components/dummy_os_data/do_plan_preview.py").read_text()
    assert '"shadow_only": True' in preview
    assert '"active_use_permitted": False' in preview
    assert '"physical_execution_authority": False' in preview
