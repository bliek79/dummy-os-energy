from pathlib import Path
p=Path('custom_components/dummy_os_data/do_plan_grid_support.py')
t=p.read_text()
old="'estimated_solar_displacement_kwh':0.0,'selection_reason':'lowest_true_import_price_then_low_solar_then_later_safe'})"
new="'estimated_solar_displacement_kwh':0.0,'selection_reason':'lowest_true_import_price_then_low_solar_then_later_safe','source_resolution_minutes':slot.get('source_resolution_minutes'),'kind':slot.get('kind')})"
if old not in t:
    raise SystemExit('expected selected-slot block not found')
p.write_text(t.replace(old,new,1))
