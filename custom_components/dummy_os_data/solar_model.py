"""Pure calculation helpers for the Dummy OS Solar forecast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Sequence


# F1 Energy Solar temperature-candidate reference parameters.
# These are explicit observer/candidate parameters derived from the physical
# Ross-model reference documented in the Solar Forecast optimisation workdoc.
# They are not promoted DOEMS defaults and must remain visible in diagnostics.
SOLAR_TEMPERATURE_ROSS_K_REFERENCE = 0.0342  # degC per W/m2
SOLAR_TEMPERATURE_ALPHA_REFERENCE = -0.004  # 1/degC
SOLAR_TEMPERATURE_CELL_STC_C = 25.0
SOLAR_IRRADIANCE_STC_WM2 = 1000.0


def cell_temperature_c(
    ambient_temperature_c: float | int | None,
    irradiance_wm2: float | int | None,
    ross_coefficient: float = SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
) -> float | None:
    """Estimate PV cell temperature with the Ross reference model."""
    try:
        ambient = float(ambient_temperature_c)
        irradiance = float(irradiance_wm2)
        coefficient = float(ross_coefficient)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (ambient, irradiance, coefficient)):
        return None
    if coefficient < 0.0:
        return None
    irradiance = max(0.0, irradiance)
    return round(ambient + irradiance * coefficient, 6)


def temperature_factor(
    cell_temperature: float | int | None,
    alpha_per_c: float = SOLAR_TEMPERATURE_ALPHA_REFERENCE,
    stc_cell_temperature_c: float = SOLAR_TEMPERATURE_CELL_STC_C,
) -> float | None:
    """Return the non-negative PV power multiplier for cell temperature."""
    try:
        cell = float(cell_temperature)
        alpha = float(alpha_per_c)
        stc_cell = float(stc_cell_temperature_c)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (cell, alpha, stc_cell)):
        return None
    return round(max(0.0, 1.0 + alpha * (cell - stc_cell)), 6)


def temperature_corrected_pv_power_kw(
    irradiance_wm2: float | int | None,
    ambient_temperature_c: float | int | None,
    dc_capacity_kwp: float,
    ac_limit_kw: float,
    performance_factor: float,
    ross_coefficient: float = SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
    alpha_per_c: float = SOLAR_TEMPERATURE_ALPHA_REFERENCE,
    stc_cell_temperature_c: float = SOLAR_TEMPERATURE_CELL_STC_C,
    irradiance_stc_wm2: float = SOLAR_IRRADIANCE_STC_WM2,
) -> float | None:
    """Return F1 temperature-candidate power using the existing Energy AC cap."""
    try:
        irradiance = float(irradiance_wm2)
        dc_capacity = float(dc_capacity_kwp)
        ac_limit = float(ac_limit_kw)
        performance = float(performance_factor)
        irradiance_stc = float(irradiance_stc_wm2)
    except (TypeError, ValueError):
        return None
    if not all(
        math.isfinite(value)
        for value in (irradiance, dc_capacity, ac_limit, performance, irradiance_stc)
    ):
        return None
    if irradiance_stc <= 0.0:
        return None

    irradiance = max(0.0, irradiance)
    dc_capacity = max(0.0, dc_capacity)
    ac_limit = max(0.0, ac_limit)
    performance = max(0.0, performance)
    cell = cell_temperature_c(
        ambient_temperature_c,
        irradiance,
        ross_coefficient,
    )
    factor = temperature_factor(cell, alpha_per_c, stc_cell_temperature_c)
    if cell is None or factor is None:
        return None

    uncapped_kw = (
        dc_capacity
        * (irradiance / irradiance_stc)
        * factor
        * performance
    )
    return round(min(ac_limit, max(0.0, uncapped_kw)), 6)


def pv_power_kw(
    irradiance_wm2: float | int | None,
    dc_capacity_kwp: float,
    ac_limit_kw: float,
    performance_factor: float,
) -> float:
    """Convert plane-of-array irradiance to capped AC-equivalent power."""
    try:
        irradiance = float(irradiance_wm2 or 0.0)
        dc_capacity = float(dc_capacity_kwp)
        ac_limit = float(ac_limit_kw)
        factor = float(performance_factor)
    except (TypeError, ValueError):
        return 0.0
    if not all(math.isfinite(value) for value in (irradiance, dc_capacity, ac_limit, factor)):
        return 0.0
    irradiance = max(0.0, irradiance)
    dc_capacity = max(0.0, dc_capacity)
    ac_limit = max(0.0, ac_limit)
    factor = max(0.0, factor)

    uncapped_kw = irradiance / 1000.0 * dc_capacity * factor
    return round(min(ac_limit, uncapped_kw), 6)


def slot_energy_kwh(power_kw: float, resolution_minutes: int = 15) -> float:
    """Convert average slot power to energy."""
    try:
        power = float(power_kw)
        resolution = int(resolution_minutes)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(power) or resolution <= 0:
        return 0.0
    return round(max(0.0, power) * resolution / 60.0, 6)


def backward_average_slot_start(timestamp: datetime, resolution_minutes: int = 15) -> datetime:
    """Map a backward-average source timestamp to the energy-slot start."""
    return timestamp - timedelta(minutes=resolution_minutes)


def floor_slot_start(timestamp: datetime, resolution_minutes: int = 15) -> datetime:
    """Return the exact start boundary of the slot containing timestamp."""
    floor_minute = (timestamp.minute // resolution_minutes) * resolution_minutes
    return timestamp.replace(minute=floor_minute, second=0, microsecond=0)


def next_complete_slot(timestamp: datetime, resolution_minutes: int = 15) -> datetime:
    """Elapsed-time UTC arithmetic, preserving local offset only for presentation."""
    if timestamp.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    reference = timestamp.astimezone(timezone.utc)
    floor = floor_slot_start(reference, resolution_minutes)
    result = floor if reference == floor else floor + timedelta(minutes=resolution_minutes)
    return result.astimezone(timestamp.tzinfo)


def next_future_slot(timestamp: datetime, resolution_minutes: int = 15) -> datetime:
    """Return the first slot boundary strictly after the current quarter."""
    floor_minute = (timestamp.minute // resolution_minutes) * resolution_minutes
    floor = timestamp.replace(minute=floor_minute, second=0, microsecond=0)
    return floor + timedelta(minutes=resolution_minutes)


def next_future_slot_index(
    starts: Sequence[datetime],
    timestamp: datetime,
    resolution_minutes: int = 15,
) -> int | None:
    """Return the first timeline index at or after the next future boundary."""
    target = next_future_slot(timestamp, resolution_minutes)
    for index, slot_start in enumerate(starts):
        if slot_start >= target:
            return index
    return None


def split_ac_power(
    total_ac_w: float | int | None,
    north_dc_w: float | int | None,
    south_dc_w: float | int | None,
) -> tuple[float | None, float | None]:
    """Split inverter AC power using the two DC-input proportions."""
    try:
        total = float(total_ac_w)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(total):
        return None, None
    total = max(0.0, total)

    # With zero AC output both roof contributions are unambiguously zero; a
    # missing/asleep DC-input sensor must not invalidate an overnight quarter.
    if total <= 0.0:
        return 0.0, 0.0

    try:
        north = float(north_dc_w)
        south = float(south_dc_w)
    except (TypeError, ValueError):
        return None, None
    if not all(math.isfinite(value) for value in (north, south)):
        return None, None
    north = max(0.0, north)
    south = max(0.0, south)

    dc_total = north + south
    if dc_total <= 0.0:
        return None, None

    north_ac = total * north / dc_total
    return round(north_ac, 3), round(total - north_ac, 3)
