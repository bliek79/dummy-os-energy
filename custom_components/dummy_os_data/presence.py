"""Pure Presence/Away schedule contract for Dummy OS Energy."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

PROFILE_NORMAL = "normal"
PROFILE_AWAY = "away"
PROFILE_UNCLASSIFIED = "unclassified"
VALID_PROFILES = {PROFILE_NORMAL, PROFILE_AWAY, PROFILE_UNCLASSIFIED}


def parse_aware_datetime(value: Any) -> datetime | None:
    """Parse an aware datetime and normalize it to UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def schedule_validation(start: Any, end: Any) -> dict[str, Any]:
    """Validate the configured schedule without inventing missing values."""
    parsed_start = parse_aware_datetime(start)
    parsed_end = parse_aware_datetime(end)
    blockers: list[str] = []
    if start is None:
        blockers.append("schedule_start_missing")
    elif parsed_start is None:
        blockers.append("schedule_time_invalid")
    if end is None:
        blockers.append("schedule_end_missing")
    elif parsed_end is None:
        blockers.append("schedule_time_invalid")
    if parsed_start is not None and parsed_end is not None and parsed_end <= parsed_start:
        blockers.append("schedule_end_not_after_start")
    valid = not blockers
    return {
        "valid": valid,
        "start": parsed_start,
        "end": parsed_end,
        "blockers": sorted(set(blockers)),
    }


def active_window_id(start: datetime, end: datetime) -> str:
    """Return a deterministic identity for one exact Away schedule window."""
    payload = f"{start.astimezone(timezone.utc).isoformat()}|{end.astimezone(timezone.utc).isoformat()}"
    return sha256(payload.encode("utf-8")).hexdigest()


def build_presence_state(
    *,
    now: datetime,
    schedule_enabled: bool,
    schedule_start: Any,
    schedule_end: Any,
    current_profile: str,
    pre_schedule_profile: str | None,
    schedule_applied_window_id: str | None,
    manual_override_window_id: str | None,
    storage_valid: bool = True,
    runtime_ready: bool = True,
) -> dict[str, Any]:
    """Build a deterministic Presence context snapshot.

    This function is side-effect free. The Home Assistant runtime owns transitions.
    """
    now_utc = parse_aware_datetime(now)
    if now_utc is None:
        raise ValueError("now must be timezone-aware")

    if current_profile not in VALID_PROFILES:
        return {
            "status": "blocked",
            "presence_context": "unresolved",
            "effective_profile": None,
            "schedule_valid": False,
            "schedule_active": False,
            "active_window_id": None,
            "manual_override_active": False,
            "next_transition_at": None,
            "blockers": ["profile_unresolved"],
        }
    if not storage_valid:
        return {
            "status": "blocked",
            "presence_context": "storage_invalid",
            "effective_profile": current_profile,
            "schedule_valid": False,
            "schedule_active": False,
            "active_window_id": None,
            "manual_override_active": False,
            "next_transition_at": None,
            "blockers": ["storage_invalid"],
        }
    if not runtime_ready:
        return {
            "status": "blocked",
            "presence_context": "runtime_not_ready",
            "effective_profile": current_profile,
            "schedule_valid": False,
            "schedule_active": False,
            "active_window_id": None,
            "manual_override_active": False,
            "next_transition_at": None,
            "blockers": ["runtime_not_ready"],
        }

    validation = schedule_validation(schedule_start, schedule_end)
    start = validation["start"]
    end = validation["end"]
    schedule_valid = bool(validation["valid"])

    if not schedule_enabled:
        return {
            "status": "inactive",
            "presence_context": "manual",
            "effective_profile": current_profile,
            "schedule_valid": schedule_valid,
            "schedule_active": False,
            "active_window_id": active_window_id(start, end) if schedule_valid else None,
            "manual_override_active": False,
            "next_transition_at": None,
            "blockers": [],
        }

    if not schedule_valid:
        return {
            "status": "blocked",
            "presence_context": "invalid_schedule",
            "effective_profile": current_profile,
            "schedule_valid": False,
            "schedule_active": False,
            "active_window_id": None,
            "manual_override_active": False,
            "next_transition_at": None,
            "blockers": validation["blockers"],
        }

    assert start is not None and end is not None
    window_id = active_window_id(start, end)
    active = start <= now_utc < end
    manual_override = active and manual_override_window_id == window_id

    if now_utc < start:
        next_transition = start.isoformat()
    elif active:
        next_transition = end.isoformat()
    else:
        next_transition = None

    if active and manual_override:
        context = "manual_override"
        status = "ready"
    elif active:
        context = "away_schedule"
        status = "ready"
    else:
        context = "manual"
        status = "inactive"

    return {
        "status": status,
        "presence_context": context,
        "effective_profile": current_profile,
        "schedule_valid": True,
        "schedule_active": active,
        "active_window_id": window_id,
        "schedule_applied": schedule_applied_window_id == window_id,
        "manual_override_active": manual_override,
        "pre_schedule_profile": pre_schedule_profile,
        "next_transition_at": next_transition,
        "blockers": [],
    }
