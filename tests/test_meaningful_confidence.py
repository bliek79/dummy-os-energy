from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/meaningful_confidence.py"
SPEC = importlib.util.spec_from_file_location("meaningful_confidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_candidate_confidence = MODULE._candidate_confidence
_historical_components = MODULE._historical_components


def _samples(values):
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    return now, [(now - timedelta(days=i), value, 1.0) for i, value in enumerate(values)]


def test_stable_history_scores_higher_than_volatile_history():
    now, stable = _samples([0.10, 0.101, 0.099, 0.10, 0.102, 0.098])
    _, volatile = _samples([0.02, 0.20, 0.03, 0.18, 0.04, 0.22])
    stable_components = _historical_components(stable, captured_at=now)
    volatile_components = _historical_components(volatile, captured_at=now)
    assert stable_components["stability_factor"] > volatile_components["stability_factor"]
    stable_score = _candidate_confidence(source="weekday_quarter", components=stable_components, recent_error_factor=0.8)
    volatile_score = _candidate_confidence(source="weekday_quarter", components=volatile_components, recent_error_factor=0.8)
    assert stable_score > volatile_score


def test_deeper_fallback_reduces_confidence():
    now, samples = _samples([0.10, 0.11, 0.09, 0.10, 0.10, 0.09])
    components = _historical_components(samples, captured_at=now)
    exact = _candidate_confidence(source="weekday_quarter", components=components, recent_error_factor=0.8)
    broad = _candidate_confidence(source="profile_mean", components=components, recent_error_factor=0.8)
    assert exact > broad
