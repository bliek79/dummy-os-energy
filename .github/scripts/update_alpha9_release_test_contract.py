from pathlib import Path

path = Path("tests/test_release_consistency.py")
text = path.read_text()
old = '''        for class_name, expected_name in (\n            ("DummyOSEnergyPeakLearningSensor", "DO Energy Peak Learning"),\n            ("DummyOSEnergyTimeWindowsSensor", "DO Energy Time Windows"),\n            ("DummyOSEnergyRecencyWeightingSensor", "DO Energy Recency Weighting"),\n        ):\n            start = sensor_source.index(f"class {class_name}(DummyOSBaseSensor):")\n'''
new = '''        for class_name, base_class, expected_name in (\n            ("DummyOSEnergyPeakLearningSensor", "DummyOSAsyncPlannerResultSensor", "DO Energy Peak Learning"),\n            ("DummyOSEnergyTimeWindowsSensor", "DummyOSBaseSensor", "DO Energy Time Windows"),\n            ("DummyOSEnergyRecencyWeightingSensor", "DummyOSBaseSensor", "DO Energy Recency Weighting"),\n        ):\n            start = sensor_source.index(f"class {class_name}({base_class}):")\n'''
if old not in text:
    raise SystemExit("expected observer runtime name test block not found")
path.write_text(text.replace(old, new, 1))
