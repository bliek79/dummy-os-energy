from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
from zoneinfo import ZoneInfo

MODULE_PATH = Path(__file__).parents[1] / "custom_components/dummy_os_data/planner_hours.py"
SPEC = importlib.util.spec_from_file_location("planner_hours", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

@dataclass
class Slot:
    start: datetime
    end: datetime
    energy_kwh: float | None
    sample_count: int = 4
    source: str = "weekday_quarter"
    confidence: float = 0.8

def local_ams(value: datetime) -> datetime:
    return value.astimezone(ZoneInfo("Europe/Amsterdam"))

def make_slots(start: datetime, count: int, missing: int | None = None):
    out = []
    for i in range(count):
        s = start + timedelta(minutes=15 * i)
        out.append(Slot(s, s + timedelta(minutes=15), None if i == missing else 0.1))
    return out

def test_alignment_offsets_and_exact_72_hours():
    base = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)
    for minutes, expected in ((0, 0), (15, 3), (30, 2), (45, 1)):
        start = base.replace(minute=minutes)
        count = 288 + expected
        result = MODULE.aggregate_planner_hours(make_slots(start, count), profile="normal", localize=local_ams)
        assert result["planner_hour_count"] == 72
        assert len(result["hours"]) == 72
        assert result["leading_quarter_offset"] == expected
        assert result["extra_quarters_generated"] == expected
        assert result["generated_quarter_count"] == count
        assert result["padding_used"] is False
        assert result["second_forecast_architecture"] is False
        first = datetime.fromisoformat(result["planner_start"])
        last = datetime.fromisoformat(result["planner_end"])
        assert last - first == timedelta(hours=72)
        assert all(hour["quarter_count"] == 4 for hour in result["hours"])
        assert all(len(hour["quarters"]) == 4 for hour in result["hours"])
        assert result["hours"][0]["quarters"][0]["energy_kwh"] == 0.1

def test_missing_quarter_never_becomes_partial_sum():
    start = datetime(2026, 9, 7, 16, 0, tzinfo=timezone.utc)
    result = MODULE.aggregate_planner_hours(make_slots(start, 288, missing=2), profile="normal", localize=local_ams)
    assert result["hours"][0]["energy_kwh"] is None
    assert result["hours"][0]["populated_quarters"] == 3
    assert result["valid_hour_count"] == 71
    assert result["status"] == "partial"

def test_dst_spring_forward_remains_72_real_hours():
    start = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)
    result = MODULE.aggregate_planner_hours(make_slots(start, 288), profile="normal", localize=local_ams)
    assert len(result["hours"]) == 72
    first = datetime.fromisoformat(result["planner_start"])
    last = datetime.fromisoformat(result["planner_end"])
    assert last - first == timedelta(hours=72)
    starts = [datetime.fromisoformat(h["start"]) for h in result["hours"]]
    assert all((b - a) == timedelta(hours=1) for a, b in zip(starts, starts[1:]))

def test_requires_real_quarters_no_padding():
    start = datetime(2026, 9, 7, 16, 15, tzinfo=timezone.utc)
    try:
        MODULE.aggregate_planner_hours(make_slots(start, 290), profile="normal", localize=local_ams)
    except ValueError as exc:
        assert "insufficient native quarters" in str(exc)
    else:
        raise AssertionError("expected insufficient-quarter failure")
