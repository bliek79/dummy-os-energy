"""Tests for the pure Presence/Away state contract."""

from datetime import datetime, timezone

from custom_components.dummy_os_data.presence import (
    active_window_id,
    build_presence_state,
    schedule_validation,
)

UTC = timezone.utc
START = datetime(2026, 9, 12, 8, 7, tzinfo=UTC)
END = datetime(2026, 9, 14, 18, 3, tzinfo=UTC)


def state(now, **kwargs):
    defaults = dict(
        schedule_enabled=True,
        schedule_start=START,
        schedule_end=END,
        current_profile="normal",
        pre_schedule_profile=None,
        schedule_applied_window_id=None,
        manual_override_window_id=None,
    )
    defaults.update(kwargs)
    return build_presence_state(now=now, **defaults)


def test_disabled_never_changes_context():
    result = state(START, schedule_enabled=False)
    assert result["status"] == "inactive"
    assert result["schedule_active"] is False
    assert result["effective_profile"] == "normal"


def test_future_window_points_to_start():
    result = state(datetime(2026, 9, 12, 7, 0, tzinfo=UTC))
    assert result["status"] == "inactive"
    assert result["schedule_valid"] is True
    assert result["schedule_active"] is False
    assert result["next_transition_at"] == START.isoformat()


def test_active_window_is_half_open_and_ready():
    result = state(START)
    assert result["status"] == "ready"
    assert result["presence_context"] == "away_schedule"
    assert result["schedule_active"] is True
    assert result["next_transition_at"] == END.isoformat()
    assert state(END)["schedule_active"] is False


def test_manual_override_is_scoped_to_exact_window():
    window = active_window_id(START, END)
    result = state(START, current_profile="unclassified", manual_override_window_id=window)
    assert result["manual_override_active"] is True
    assert result["presence_context"] == "manual_override"
    changed_end = datetime(2026, 9, 14, 19, 3, tzinfo=UTC)
    result = state(START, schedule_end=changed_end, manual_override_window_id=window)
    assert result["manual_override_active"] is False


def test_invalid_schedule_blocks_without_forcing_normal():
    result = state(START, schedule_start=END, schedule_end=START, current_profile="away")
    assert result["status"] == "blocked"
    assert result["effective_profile"] == "away"
    assert "schedule_end_not_after_start" in result["blockers"]


def test_missing_and_naive_times_are_explicitly_invalid():
    assert schedule_validation(None, END)["blockers"] == ["schedule_start_missing"]
    naive = datetime(2026, 9, 12, 8, 7)
    assert "schedule_time_invalid" in schedule_validation(naive, END)["blockers"]


def test_unresolved_profile_fails_closed():
    result = state(START, current_profile="mixed")
    assert result["status"] == "blocked"
    assert result["effective_profile"] is None
    assert result["blockers"] == ["profile_unresolved"]


def test_storage_and_runtime_fail_closed():
    storage = state(START, storage_valid=False)
    runtime = state(START, runtime_ready=False)
    assert storage["blockers"] == ["storage_invalid"]
    assert runtime["blockers"] == ["runtime_not_ready"]
