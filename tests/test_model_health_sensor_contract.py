from pathlib import Path

SENSOR = Path(__file__).parents[1] / "custom_components" / "dummy_os_data" / "sensor.py"
MODEL_HEALTH = Path(__file__).parents[1] / "custom_components" / "dummy_os_data" / "model_health.py"


def test_existing_public_model_health_identity_is_preserved():
    text = SENSOR.read_text()
    block = text[text.index("class DummyOSHomeForecastModelHealthSensor"):text.index("class DummyOSEvaluationBaseSensor")]
    assert '_attr_name = "DO Energy Forecast Model Health"' in block
    assert '_attr_unique_id = "do_energy_forecast_model_health"' in block
    assert '_attr_suggested_object_id = "do_energy_forecast_model_health"' in block
    assert "_build_model_health_from_snapshot(snapshot)" in block
    assert "class DummyOSHomeForecastModelHealthSensor(DummyOSAsyncPlannerResultSensor):" in block
    assert 'return "source_unavailable"' not in block


def test_readiness_contract_keeps_runtime_source_separate():
    text = MODEL_HEALTH.read_text()
    assert 'READINESS_ALGORITHM_VERSION = "model_health_readiness_v1"' in text
    assert '"runtime_input_status"' in text
    assert '"forecast_operational_input_ok"' in text
    assert '"readiness_blockers"' in text
    assert '"runtime_blockers"' in text
