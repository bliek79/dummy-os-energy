from pathlib import Path
p = Path('tests/test_energy_profile_contract_step9.py')
text = p.read_text()
old = '    assert "for offset in range(FORECAST_SLOTS):" in forecast\n'
new = '    assert "slot_count: int = FORECAST_SLOTS" in forecast\n    assert "for offset in range(slot_count):" in forecast\n'
if old not in text:
    raise SystemExit('legacy Step 9 forecast loop assertion not found')
p.write_text(text.replace(old, new, 1))
