from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing patch anchor in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))

# forecast.py: default remains 288; explicit internal extension bounded to +3 quarters.
replace_once(
    "custom_components/dummy_os_data/forecast.py",
    'RECENCY_HALF_LIFE_DAYS = 28.0\n',
    'RECENCY_HALF_LIFE_DAYS = 28.0\nMAX_INTERNAL_FORECAST_SLOTS = FORECAST_SLOTS + 3\n',
)
replace_once(
    "custom_components/dummy_os_data/forecast.py",
    '    def build(self, profile: str, now: datetime | None = None) -> list[ForecastSlot]:\n        """Build 288 native 15-minute forecast slots from historical data.\n',
    '    def build(\n        self,\n        profile: str,\n        now: datetime | None = None,\n        *,\n        slot_count: int = FORECAST_SLOTS,\n    ) -> list[ForecastSlot]:\n        """Build native 15-minute forecast slots from historical data.\n\n        The public/default contract remains exactly 288 slots. Step 14 may\n        explicitly request at most three additional native quarters solely to\n        complete 72 full planner hours without padding.\n',
)
replace_once(
    "custom_components/dummy_os_data/forecast.py",
    '        exact, day_type, quarter, all_values = self._history(profile)\n',
    '        if slot_count < 1 or slot_count > MAX_INTERNAL_FORECAST_SLOTS:\n            raise ValueError(\n                f"slot_count must be between 1 and {MAX_INTERNAL_FORECAST_SLOTS}"\n            )\n\n        exact, day_type, quarter, all_values = self._history(profile)\n',
)
replace_once(
    "custom_components/dummy_os_data/forecast.py",
    '        for offset in range(FORECAST_SLOTS):\n',
    '        for offset in range(slot_count):\n',
)

# sensor.py: register and implement one validation/interface sensor.
replace_once(
    "custom_components/dummy_os_data/sensor.py",
    'from .model_health import calculate_model_health_readiness\n',
    'from .model_health import calculate_model_health_readiness\nfrom .planner_hours import (\n    aggregate_planner_hours,\n    required_generated_slot_count,\n)\n',
)
replace_once(
    "custom_components/dummy_os_data/sensor.py",
    '            DummyOSHomeForecastTimelineSensor(coordinator),\n            DummyOSHomeForecastNextQuarterSensor(coordinator),\n',
    '            DummyOSHomeForecastTimelineSensor(coordinator),\n            DummyOSEnergyForecastPlannerHoursSensor(coordinator),\n            DummyOSHomeForecastNextQuarterSensor(coordinator),\n',
)
anchor = '''class DummyOSHomeForecastNextQuarterSensor(DummyOSBaseSensor):\n'''
planner_class = '''class DummyOSEnergyForecastPlannerHoursSensor(DummyOSBaseSensor):\n    \"\"\"Step 14 exact 72 complete planner-hour forecast interface.\"\"\"\n\n    _attr_name = \"DO Energy Forecast Planner Hours\"\n    _attr_unique_id = \"do_energy_forecast_planner_hours\"\n    _attr_suggested_object_id = \"do_energy_forecast_planner_hours\"\n    _attr_icon = \"mdi:clock-outline\"\n    _unrecorded_attributes = frozenset({\"hours\"})\n\n    def _result(self) -> dict[str, Any]:\n        now = dt_util.utcnow()\n        model = HomeBaselineForecast(self.coordinator.records)\n        public_slots = model.build(self.coordinator.profile, now=now)\n        if not public_slots:\n            return aggregate_planner_hours(\n                [], profile=self.coordinator.profile, localize=dt_util.as_local\n            )\n        generated_count = required_generated_slot_count(\n            public_slots[0].start, dt_util.as_local\n        )\n        extended_slots = model.build(\n            self.coordinator.profile, now=now, slot_count=generated_count\n        )\n        result = aggregate_planner_hours(\n            extended_slots, profile=self.coordinator.profile, localize=dt_util.as_local\n        )\n        if not self._profile_learnable:\n            result[\"status\"] = \"profile_unclassified\"\n        return result\n\n    @property\n    def native_value(self) -> int:\n        return int(self._result()[\"valid_hour_count\"])\n\n    @property\n    def extra_state_attributes(self) -> dict[str, Any]:\n        return dict(self._result())\n\n\n'''
replace_once("custom_components/dummy_os_data/sensor.py", anchor, planner_class + anchor)

# Canonical ID route from the first release.
replace_once(
    "custom_components/dummy_os_data/entity_migrations.py",
    '    "do_energy_forecast_quality_by_horizon": "sensor.dummy_os_forecast_do_energy_forecast_quality_by_horizon",\n',
    '    "do_energy_forecast_quality_by_horizon": "sensor.dummy_os_forecast_do_energy_forecast_quality_by_horizon",\n    "do_energy_forecast_planner_hours": "sensor.dummy_os_forecast_do_energy_forecast_planner_hours",\n',
)
replace_once(
    "custom_components/dummy_os_data/__init__.py",
    '    ("sensor", "do_energy_forecast_quality_by_horizon", "sensor.do_energy_forecast_quality_by_horizon"),\n',
    '    ("sensor", "do_energy_forecast_quality_by_horizon", "sensor.do_energy_forecast_quality_by_horizon"),\n    ("sensor", "do_energy_forecast_planner_hours", "sensor.do_energy_forecast_planner_hours"),\n',
)

# Step 12 text-contract test follows the now-explicit default slot_count contract.
replace_once(
    "tests/test_horizon_quality_sensor_contract.py",
    "    assert 'for offset in range(FORECAST_SLOTS):' in FORECAST\n",
    "    assert 'slot_count: int = FORECAST_SLOTS' in FORECAST\n    assert 'for offset in range(slot_count):' in FORECAST\n",
)

Path("tests/test_planner_hours.py").write_text('''from dataclasses import dataclass\nfrom datetime import datetime, timedelta, timezone\nfrom pathlib import Path\nimport importlib.util\nfrom zoneinfo import ZoneInfo\n\nMODULE_PATH = Path(__file__).parents[1] / "custom_components/dummy_os_data/planner_hours.py"\nSPEC = importlib.util.spec_from_file_location("planner_hours", MODULE_PATH)\nassert SPEC is not None and SPEC.loader is not None\nMODULE = importlib.util.module_from_spec(SPEC)\nSPEC.loader.exec_module(MODULE)\n\n@dataclass\nclass Slot:\n    start: datetime\n    end: datetime\n    energy_kwh: float | None\n    sample_count: int = 4\n    source: str = "weekday_quarter"\n    confidence: float = 0.8\n\ndef local_ams(value: datetime) -> datetime:\n    return value.astimezone(ZoneInfo("Europe/Amsterdam"))\n\ndef make_slots(start: datetime, count: int, missing: int | None = None):\n    out = []\n    for i in range(count):\n        s = start + timedelta(minutes=15 * i)\n        out.append(Slot(s, s + timedelta(minutes=15), None if i == missing else 0.1))\n    return out\n\ndef test_alignment_offsets_and_exact_72_hours():\n    base = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)\n    for minutes, expected in ((0, 0), (15, 3), (30, 2), (45, 1)):\n        start = base.replace(minute=minutes)\n        count = 288 + expected\n        result = MODULE.aggregate_planner_hours(make_slots(start, count), profile="normal", localize=local_ams)\n        assert result["planner_hour_count"] == 72\n        assert len(result["hours"]) == 72\n        assert result["leading_quarter_offset"] == expected\n        assert result["extra_quarters_generated"] == expected\n        assert result["generated_quarter_count"] == count\n        assert result["padding_used"] is False\n        assert result["second_forecast_architecture"] is False\n        first = datetime.fromisoformat(result["planner_start"])\n        last = datetime.fromisoformat(result["planner_end"])\n        assert last - first == timedelta(hours=72)\n        assert all(hour["quarter_count"] == 4 for hour in result["hours"])\n\ndef test_missing_quarter_never_becomes_partial_sum():\n    start = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)\n    result = MODULE.aggregate_planner_hours(make_slots(start, 288, missing=2), profile="normal", localize=local_ams)\n    assert result["hours"][0]["energy_kwh"] is None\n    assert result["hours"][0]["populated_quarters"] == 3\n    assert result["valid_hour_count"] == 71\n    assert result["status"] == "partial"\n\ndef test_dst_spring_forward_remains_72_real_hours():\n    start = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)\n    result = MODULE.aggregate_planner_hours(make_slots(start, 288), profile="normal", localize=local_ams)\n    assert len(result["hours"]) == 72\n    first = datetime.fromisoformat(result["planner_start"])\n    last = datetime.fromisoformat(result["planner_end"])\n    assert last - first == timedelta(hours=72)\n    starts = [datetime.fromisoformat(h["start"]) for h in result["hours"]]\n    assert all((b - a) == timedelta(hours=1) for a, b in zip(starts, starts[1:]))\n\ndef test_requires_real_quarters_no_padding():\n    start = datetime(2026, 9, 7, 16, 15, tzinfo=timezone.utc)\n    try:\n        MODULE.aggregate_planner_hours(make_slots(start, 290), profile="normal", localize=local_ams)\n    except ValueError as exc:\n        assert "insufficient native quarters" in str(exc)\n    else:\n        raise AssertionError("expected insufficient-quarter failure")\n''')

Path("tests/test_planner_hours_sensor_contract.py").write_text('''from pathlib import Path\n\nROOT = Path(__file__).parents[1]\nSENSOR = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()\nFORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()\nINIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()\nMIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()\nPLANNER = (ROOT / "custom_components/dummy_os_data/planner_hours.py").read_text()\n\ndef test_step14_sensor_identity_and_registry_route():\n    assert '_attr_name = "DO Energy Forecast Planner Hours"' in SENSOR\n    assert '_attr_unique_id = "do_energy_forecast_planner_hours"' in SENSOR\n    assert '_attr_suggested_object_id = "do_energy_forecast_planner_hours"' in SENSOR\n    assert 'DummyOSEnergyForecastPlannerHoursSensor(coordinator)' in SENSOR\n    assert '("sensor", "do_energy_forecast_planner_hours", "sensor.do_energy_forecast_planner_hours")' in INIT\n    assert '"do_energy_forecast_planner_hours": "sensor.dummy_os_forecast_do_energy_forecast_planner_hours"' in MIGRATIONS\n\ndef test_step14_production_default_and_internal_bound():\n    assert 'slot_count: int = FORECAST_SLOTS' in FORECAST\n    assert 'MAX_INTERNAL_FORECAST_SLOTS = FORECAST_SLOTS + 3' in FORECAST\n    assert 'for offset in range(slot_count):' in FORECAST\n    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST\n\ndef test_step14_no_padding_or_second_architecture():\n    assert '"padding_used": False' in PLANNER\n    assert '"second_forecast_architecture": False' in PLANNER\n    assert 'NATIVE_PUBLIC_SLOTS = 288' in PLANNER\n    assert 'PLANNER_HOUR_COUNT = 72' in PLANNER\n    assert 'QUARTERS_PER_HOUR = 4' in PLANNER\n''')
