"""Step 14 exact 72 complete planner-hour aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Callable, Sequence

NATIVE_PUBLIC_SLOTS = 288
PLANNER_HOUR_COUNT = 72
QUARTERS_PER_HOUR = 4
MAX_ALIGNMENT_EXTRA_QUARTERS = 3
SUPPORTED_SOURCES = {"weekday_quarter", "day_type_quarter", "quarter_of_day"}


def leading_quarter_offset(
    first_slot_start: datetime,
    localize: Callable[[datetime], datetime],
) -> int:
    """Return quarters to skip until the next complete local clock hour."""
    local = localize(first_slot_start)
    if local.minute == 0:
        return 0
    if local.minute not in {15, 30, 45}:
        raise ValueError("native forecast start is not aligned to a 15-minute boundary")
    return (60 - local.minute) // 15


def required_generated_slot_count(
    first_slot_start: datetime,
    localize: Callable[[datetime], datetime],
) -> int:
    """Return bounded internal slots required for exactly 72 planner hours."""
    return NATIVE_PUBLIC_SLOTS + leading_quarter_offset(first_slot_start, localize)


def aggregate_planner_hours(
    slots: Sequence[Any],
    *,
    profile: str,
    localize: Callable[[datetime], datetime],
) -> dict[str, Any]:
    """Aggregate an extended native-quarter forecast into exactly 72 full hours."""
    if not slots:
        return {
            "status": "unavailable",
            "profile": profile,
            "model": "historical_baseline",
            "model_version": "0.4",
            "native_resolution_minutes": 15,
            "native_public_slots": NATIVE_PUBLIC_SLOTS,
            "planner_hour_count": 0,
            "valid_hour_count": 0,
            "quarters_per_hour": QUARTERS_PER_HOUR,
            "planner_start": None,
            "planner_end": None,
            "leading_quarter_offset": None,
            "extra_quarters_generated": None,
            "generated_quarter_count": len(slots),
            "padding_used": False,
            "second_forecast_architecture": False,
            "hours": [],
        }

    offset = leading_quarter_offset(slots[0].start, localize)
    required = NATIVE_PUBLIC_SLOTS + offset
    if len(slots) < required:
        raise ValueError(
            f"insufficient native quarters for planner hours: need {required}, got {len(slots)}"
        )

    selected = list(slots[offset : offset + NATIVE_PUBLIC_SLOTS])
    if len(selected) != NATIVE_PUBLIC_SLOTS:
        raise ValueError("planner selection must contain exactly 288 native quarters")

    hours: list[dict[str, Any]] = []
    for hour_index in range(PLANNER_HOUR_COUNT):
        quarter_group = selected[
            hour_index * QUARTERS_PER_HOUR : (hour_index + 1) * QUARTERS_PER_HOUR
        ]
        if len(quarter_group) != QUARTERS_PER_HOUR:
            raise ValueError("planner hour must contain exactly four native quarters")

        for previous, current in zip(quarter_group, quarter_group[1:]):
            if previous.end != current.start:
                raise ValueError("planner hour contains non-contiguous native quarters")

        populated = [slot for slot in quarter_group if slot.energy_kwh is not None]
        supported = [slot for slot in quarter_group if slot.source in SUPPORTED_SOURCES]
        energy = (
            round(sum(float(slot.energy_kwh) for slot in quarter_group), 6)
            if len(populated) == QUARTERS_PER_HOUR
            else None
        )
        confidences = [float(slot.confidence) for slot in populated]
        sources = Counter(str(slot.source) for slot in quarter_group)
        hours.append(
            {
                "index": hour_index,
                "start": quarter_group[0].start.isoformat(),
                "end": quarter_group[-1].end.isoformat(),
                "energy_kwh": energy,
                "quarter_count": QUARTERS_PER_HOUR,
                "populated_quarters": len(populated),
                "supported_quarters": len(supported),
                "minimum_confidence": round(min(confidences), 3) if confidences else None,
                "average_confidence": (
                    round(sum(confidences) / len(confidences), 3) if confidences else None
                ),
                "source_distribution": dict(sorted(sources.items())),
                "profile": profile,
            }
        )

    for previous, current in zip(hours, hours[1:]):
        if previous["end"] != current["start"]:
            raise ValueError("planner hours are not chronologically contiguous")

    valid_hours = sum(1 for hour in hours if hour["energy_kwh"] is not None)
    planner_start = selected[0].start
    planner_end = selected[-1].end
    elapsed_seconds = (planner_end - planner_start).total_seconds()
    if elapsed_seconds != PLANNER_HOUR_COUNT * 3600:
        raise ValueError("planner window is not exactly 72 real hours")

    return {
        "status": "ok" if valid_hours == PLANNER_HOUR_COUNT else "partial",
        "profile": profile,
        "model": "historical_baseline",
        "model_version": "0.4",
        "native_resolution_minutes": 15,
        "native_public_slots": NATIVE_PUBLIC_SLOTS,
        "planner_hour_count": PLANNER_HOUR_COUNT,
        "valid_hour_count": valid_hours,
        "quarters_per_hour": QUARTERS_PER_HOUR,
        "planner_start": planner_start.isoformat(),
        "planner_end": planner_end.isoformat(),
        "leading_quarter_offset": offset,
        "extra_quarters_generated": offset,
        "generated_quarter_count": required,
        "padding_used": False,
        "second_forecast_architecture": False,
        "hours": hours,
    }
