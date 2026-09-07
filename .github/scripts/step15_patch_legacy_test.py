from pathlib import Path

p = Path("tests/test_model_health_sensor_contract.py")
text = p.read_text()
old = '    assert "calculate_model_health_readiness" in block\n'
new = '    assert "_build_model_health_result(self.coordinator, self._forecast())" in block\n'
if old not in text:
    raise SystemExit("legacy Model Health test anchor missing")
p.write_text(text.replace(old, new, 1))
