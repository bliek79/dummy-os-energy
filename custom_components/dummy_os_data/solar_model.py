"""Pure calculation helpers for the Dummy OS Solar forecast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any, Sequence


# F1 Energy Solar temperature-candidate reference parameters.
# These are explicit observer/candidate parameters derived from the physical
# Ross-model reference documented in the Solar Forecast optimisation workdoc.
# They are not promoted DOEMS defaults and must remain visible in diagnostics.
SOLAR_TEMPERATURE_ROSS_K_REFERENCE = 0.0342  # degC per W/m2
SOLAR_TEMPERATURE_ALPHA_REFERENCE = -0.004  # 1/degC
SOLAR_TEMPERATURE_CELL_STC_C = 25.0
SOLAR_IRRADIANCE_STC_WM2 = 1000.0


def parse_horizon_profile(
    value: str | Sequence[Sequence[float | int]] | None,
) -> tuple[tuple[float, float], ...] | None:
    """Parse and validate one physical horizon profile.

    The F3 contract uses compass azimuth (0=N, 90=E, 180=S, 270=W,
    360=N) and requires explicit 0/360 wrap points with equal elevation.
    Empty input is allowed at configuration level and means that the F3
    candidate is not ready; it is never replaced by a learned/default curve.
    """
    if value is None:
        return None
    raw: Any = value
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "[]":
            return None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as err:
            raise ValueError("horizon profile must be valid JSON") from err
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise ValueError("horizon profile must contain at least two points")

    points: list[tuple[float, float]] = []
    previous_azimuth: float | None = None
    for point in raw:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("each horizon point must be [azimuth_deg, elevation_deg]")
        try:
            azimuth = float(point[0])
            elevation = float(point[1])
        except (TypeError, ValueError) as err:
            raise ValueError("horizon profile values must be numeric") from err
        if not math.isfinite(azimuth) or not math.isfinite(elevation):
            raise ValueError("horizon profile values must be finite")
        if not 0.0 <= azimuth <= 360.0:
            raise ValueError("horizon azimuth must be within 0..360 degrees")
        if not -90.0 <= elevation <= 90.0:
            raise ValueError("horizon elevation must be within -90..90 degrees")
        if previous_azimuth is not None and azimuth <= previous_azimuth:
            raise ValueError("horizon azimuths must be strictly increasing")
        points.append((round(azimuth, 6), round(elevation, 6)))
        previous_azimuth = azimuth

    if not math.isclose(points[0][0], 0.0, abs_tol=1e-9):
        raise ValueError("horizon profile must start at azimuth 0")
    if not math.isclose(points[-1][0], 360.0, abs_tol=1e-9):
        raise ValueError("horizon profile must end at azimuth 360")
    if not math.isclose(points[0][1], points[-1][1], abs_tol=1e-6):
        raise ValueError("horizon elevations at azimuth 0 and 360 must match")
    return tuple(points)


def interpolate_horizon_elevation_deg(
    profile: Sequence[Sequence[float | int]] | None,
    azimuth_deg: float | int | None,
) -> float | None:
    """Linearly interpolate physical horizon elevation at compass azimuth."""
    if profile is None:
        return None
    try:
        azimuth = float(azimuth_deg)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(azimuth):
        return None
    parsed = parse_horizon_profile(profile)
    if parsed is None:
        return None
    if math.isclose(azimuth, 360.0, abs_tol=1e-9):
        normalized = 360.0
    else:
        normalized = azimuth % 360.0
    for index in range(1, len(parsed)):
        left_azimuth, left_elevation = parsed[index - 1]
        right_azimuth, right_elevation = parsed[index]
        if normalized <= right_azimuth:
            span = right_azimuth - left_azimuth
            if span <= 0.0:
                return None
            ratio = (normalized - left_azimuth) / span
            return round(left_elevation + ratio * (right_elevation - left_elevation), 6)
    return round(parsed[-1][1], 6)


def solar_position_degrees(
    timestamp: datetime,
    latitude_deg: float | int,
    longitude_deg: float | int,
) -> tuple[float | None, float | None]:
    """Return deterministic compass azimuth and solar elevation in degrees.

    F3 evaluates geometry at the Open-Meteo backward-average source stamp,
    i.e. slot_start + 15 minutes. This pure implementation uses standard
    solar-coordinate equations and requires a timezone-aware timestamp.
    """
    if timestamp.tzinfo is None:
        return None, None
    try:
        latitude = float(latitude_deg)
        longitude = float(longitude_deg)
    except (TypeError, ValueError):
        return None, None
    if not all(math.isfinite(v) for v in (latitude, longitude)):
        return None, None
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        return None, None

    utc = timestamp.astimezone(timezone.utc)
    # Days since J2000.0 (2000-01-01 12:00 UTC).
    days = utc.timestamp() / 86400.0 - 10957.5
    mean_anomaly = math.radians((357.5291 + 0.98560028 * days) % 360.0)
    ecliptic_longitude = math.radians(
        (
            math.degrees(mean_anomaly)
            + 1.9148 * math.sin(mean_anomaly)
            + 0.0200 * math.sin(2.0 * mean_anomaly)
            + 102.9372
            + 180.0
        )
        % 360.0
    )
    obliquity = math.radians(23.4397)
    right_ascension = math.atan2(
        math.sin(ecliptic_longitude) * math.cos(obliquity),
        math.cos(ecliptic_longitude),
    )
    declination = math.asin(
        math.sin(ecliptic_longitude) * math.sin(obliquity)
    )
    right_ascension_deg = math.degrees(right_ascension) % 360.0
    sidereal_deg = (280.16 + 360.9856235 * days + longitude) % 360.0
    hour_angle_deg = (sidereal_deg - right_ascension_deg + 180.0) % 360.0 - 180.0
    hour_angle = math.radians(hour_angle_deg)
    latitude_rad = math.radians(latitude)

    sin_elevation = (
        math.sin(latitude_rad) * math.sin(declination)
        + math.cos(latitude_rad) * math.cos(declination) * math.cos(hour_angle)
    )
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, sin_elevation))))
    azimuth = (
        math.degrees(
            math.atan2(
                math.sin(hour_angle),
                math.cos(hour_angle) * math.sin(latitude_rad)
                - math.tan(declination) * math.cos(latitude_rad),
            )
        )
        + 180.0
    ) % 360.0
    return round(azimuth, 6), round(elevation, 6)


def horizon_effective_irradiance_wm2(
    gti_wm2: float | int | None,
    diffuse_radiation_wm2: float | int | None,
    solar_elevation_deg: float | int | None,
    local_horizon_elevation_deg: float | int | None,
) -> tuple[float | None, bool | None]:
    """Apply the F3 simple physical horizon rule.

    When the solar elevation is below the local physical horizon, direct
    sunlight is treated as blocked and effective irradiance is the Open-Meteo
    diffuse_radiation contribution. Otherwise GTI remains authoritative.
    """
    try:
        gti = float(gti_wm2)
        diffuse = float(diffuse_radiation_wm2)
        solar_elevation = float(solar_elevation_deg)
        horizon_elevation = float(local_horizon_elevation_deg)
    except (TypeError, ValueError):
        return None, None
    if not all(
        math.isfinite(value)
        for value in (gti, diffuse, solar_elevation, horizon_elevation)
    ):
        return None, None
    blocked = solar_elevation < horizon_elevation
    effective = max(0.0, diffuse if blocked else gti)
    return round(effective, 6), blocked


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
