from pathlib import Path

# Apply the original feature patch first.
exec(Path('.github/scripts/step12_bootstrap.py').read_text(), {})

# Preserve the existing Energy Store normalization contract/schema.
p = Path('custom_components/dummy_os_data/energy_store.py')
t = p.read_text()
t = t.replace('    payload.setdefault("horizon_pending_probes", {})\n', '')
t = t.replace('    payload.setdefault("horizon_daily_stats", {})\n', '')
p.write_text(t)

# The coordinator reads absent legacy fields safely with .get(..., {}).
p = Path('tests/test_horizon_quality_sensor_contract.py')
t = p.read_text()
t = t.replace('STORE = (ROOT / "custom_components/dummy_os_data/energy_store.py").read_text()\n', '')
t = t.replace('    assert \'payload.setdefault("horizon_pending_probes", {})\' in STORE\n', '')
t = t.replace('    assert \'payload.setdefault("horizon_daily_stats", {})\' in STORE\n', '')
p.write_text(t)
