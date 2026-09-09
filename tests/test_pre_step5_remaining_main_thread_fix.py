from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_remaining_main_thread_paths_are_executor_backed():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    solar = (ROOT / "custom_components/dummy_os_data/solar_sensor.py").read_text()
    assert "class DummyOSHomeForecastNextQuarterSensor(DummyOSAsyncPlannerResultSensor)" in sensor
    assert "class DummyOSHomeForecastConfidenceSensor(DummyOSAsyncPlannerResultSensor)" in sensor
    assert "class DummyOSAsyncQualitySensor(DummyOSAsyncPlannerResultSensor)" in sensor
    for name in ("DummyOSHomeForecastQualityByDaypartSensor", "DummyOSHomeForecastQualityByDayTypeSensor", "DummyOSHomeForecastQualityByDayTypeAndDaypartSensor", "DummyOSHomeForecastQualityByHourSensor"):
        assert f"class {name}(DummyOSAsyncQualitySensor)" in sensor
    assert "async_add_executor_job" in solar
    assert "def _calculate_value(points, target, roof: str)" in solar
    assert "return self.solar.energy_for_local_date(target, self.roof)" not in solar

def test_identity_and_safety_invariants_remain_present():
    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()
    preview = (ROOT / "custom_components/dummy_os_data/do_plan_preview.py").read_text()
    for unique_id in ("do_energy_forecast_next_quarter", "do_energy_forecast_confidence", "do_energy_forecast_quality_by_daypart"):
        assert unique_id in sensor
    solar = (ROOT / "custom_components/dummy_os_data/solar_sensor.py").read_text()
    for day, roof in (("today", "north"), ("today", "south"), ("today", "total"), ("tomorrow", "north"), ("tomorrow", "south"), ("tomorrow", "total")):
        assert f'DummyOSSolarDailySensor(coordinator, "{day}", "{roof}")' in solar
    assert 'object_id = f"do_solar_forecast_{day}_{roof}"' in solar
    assert '"shadow_only": True' in preview
    assert '"active_use_permitted": False' in preview
    assert '"physical_execution_authority": False' in preview
