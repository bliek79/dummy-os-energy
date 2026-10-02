"""Native Open-Meteo solar forecast provider for Dummy OS Data."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SOLAR_ACTUAL_NORTH_DC_ENTITY,
    CONF_SOLAR_ACTUAL_SOUTH_DC_ENTITY,
    CONF_SOLAR_ACTUAL_TOTAL_ENTITY,
    CONF_SOLAR_LATITUDE,
    CONF_SOLAR_LONGITUDE,
    CONF_SOLAR_NORTH_AC_KW,
    CONF_SOLAR_NORTH_AZIMUTH,
    CONF_SOLAR_NORTH_DC_KWP,
    CONF_SOLAR_NORTH_FACTOR,
    CONF_SOLAR_NORTH_HORIZON_PROFILE,
    CONF_SOLAR_NORTH_TILT,
    CONF_SOLAR_SOUTH_AC_KW,
    CONF_SOLAR_SOUTH_AZIMUTH,
    CONF_SOLAR_SOUTH_DC_KWP,
    CONF_SOLAR_SOUTH_FACTOR,
    CONF_SOLAR_SOUTH_HORIZON_PROFILE,
    CONF_SOLAR_SOUTH_TILT,
    DEFAULT_SOLAR_ACTUAL_NORTH_DC_ENTITY,
    DEFAULT_SOLAR_ACTUAL_SOUTH_DC_ENTITY,
    DEFAULT_SOLAR_ACTUAL_TOTAL_ENTITY,
    FORECAST_SLOTS,
    MAX_HISTORY_DAYS,
    QUARTER_MINUTES,
    SOLAR_MIN_VALID_COVERAGE,
    SOLAR_STORAGE_KEY,
    SOLAR_STORAGE_VERSION,
)
from .solar_evaluation import ROOFS, build_quarter_evaluation
from .solar_temperature_ab import (
    add_temperature_ab_sample,
    build_temperature_ab_pair,
    new_temperature_ab_day,
    summarize_temperature_ab_history,
)
from .solar_multimodel_validation import (
    add_multimodel_sample,
    build_multimodel_pair,
    classify_solar_azimuth,
    classify_solar_elevation,
    classify_weather_regime,
    new_multimodel_day,
    summarize_multimodel_history,
)
from .solar_partial_shading_validation import (
    add_partial_shading_sample,
    build_partial_shading_pair,
    new_partial_shading_day,
    summarize_partial_shading_history,
)
from .solar_residual_learning import (
    F6_BIN_CONTRACT,
    F6_MODEL,
    F6_PARENT_MODEL,
    add_training_sample,
    apply_factor_with_ac_cap,
    build_parent_signature,
    build_revision,
    build_training_sample,
    condition_key,
    factor_for_bin,
    revision_diagnostics,
    thresholds as residual_learning_thresholds,
    validate_learning_state,
)
from .solar_residual_learning_validation import (
    add_residual_learning_sample,
    build_residual_learning_pair,
    new_residual_learning_day,
    summarize_residual_learning_history,
)
from .solar_model import (
    SOLAR_TEMPERATURE_ALPHA_REFERENCE,
    SOLAR_TEMPERATURE_CELL_STC_C,
    SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
    backward_average_slot_start,
    cell_temperature_c,
    floor_slot_start,
    horizon_effective_irradiance_wm2,
    interpolate_horizon_elevation_deg,
    next_complete_slot,
    next_future_slot_index,
    parse_horizon_profile,
    partial_shading_effective_irradiance_wm2,
    pv_power_kw,
    slot_energy_kwh,
    solar_position_degrees,
    split_ac_power,
    temperature_corrected_pv_power_kw,
    temperature_factor,
)

_LOGGER = logging.getLogger(__name__)

OPEN_METEO_SOLAR_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_SOLAR_TIMEZONE = "UTC"
OPEN_METEO_SOLAR_MODEL = "best_match"
SOLAR_RESOLUTION_MINUTES = 15
SOLAR_BUFFER_SLOTS = 4
SOLAR_REQUEST_EXTRA_SLOTS = 7
SOLAR_STORAGE_SAVE_DELAY_SECONDS = 30
SOLAR_HORIZON_HOURS = (1, 6, 24, 48, 72)
SOLAR_TEMPERATURE_CANDIDATE_MODEL = "open_meteo_gti_temperature_candidate_v0.1"
SOLAR_HORIZON_CANDIDATE_MODEL = "open_meteo_gti_horizon_temperature_candidate_v0.1"
SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL = "open_meteo_gti_horizon_partial_temperature_candidate_v0.1"
SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL = F6_MODEL


@dataclass(frozen=True, slots=True)
class RoofConfig:
    """One independently forecast PV roof plane."""

    key: str
    dc_capacity_kwp: float
    ac_limit_kw: float
    tilt_deg: float
    open_meteo_azimuth_deg: float
    performance_factor: float


@dataclass(frozen=True, slots=True)
class SolarPoint:
    """Normalized forecast point."""

    start: datetime
    north_kwh: float
    south_kwh: float
    total_kwh: float
    north_kw: float
    south_kw: float
    total_kw: float
    north_irradiance_wm2: float
    south_irradiance_wm2: float

    def as_list(self) -> list[int | float]:
        return [
            int(self.start.timestamp() * 1000),
            self.north_kwh,
            self.south_kwh,
            self.total_kwh,
            self.north_kw,
            self.south_kw,
            self.total_kw,
            self.north_irradiance_wm2,
            self.south_irradiance_wm2,
        ]


@dataclass(frozen=True, slots=True)
class SolarTemperatureCandidatePoint:
    """Parallel F1 temperature-corrected Solar candidate point."""

    start: datetime
    north_kwh: float
    south_kwh: float
    total_kwh: float
    north_kw: float
    south_kw: float
    total_kw: float
    north_irradiance_wm2: float
    south_irradiance_wm2: float
    north_ambient_temperature_c: float
    south_ambient_temperature_c: float
    north_cell_temperature_c: float
    south_cell_temperature_c: float
    north_temperature_factor: float
    south_temperature_factor: float

    def as_list(self) -> list[int | float]:
        return [
            int(self.start.timestamp() * 1000),
            self.north_kwh,
            self.south_kwh,
            self.total_kwh,
            self.north_kw,
            self.south_kw,
            self.total_kw,
            self.north_irradiance_wm2,
            self.south_irradiance_wm2,
            self.north_ambient_temperature_c,
            self.south_ambient_temperature_c,
            self.north_cell_temperature_c,
            self.south_cell_temperature_c,
            self.north_temperature_factor,
            self.south_temperature_factor,
        ]


@dataclass(frozen=True, slots=True)
class SolarHorizonCandidatePoint:
    """Parallel F3 horizon/direct-diffuse plus temperature candidate point."""

    start: datetime
    north_kwh: float
    south_kwh: float
    total_kwh: float
    north_kw: float
    south_kw: float
    total_kw: float
    north_gti_wm2: float
    south_gti_wm2: float
    north_direct_radiation_wm2: float
    south_direct_radiation_wm2: float
    north_diffuse_radiation_wm2: float
    south_diffuse_radiation_wm2: float
    solar_azimuth_deg: float
    solar_elevation_deg: float
    north_horizon_elevation_deg: float
    south_horizon_elevation_deg: float
    north_horizon_blocked: bool
    south_horizon_blocked: bool
    north_effective_irradiance_wm2: float
    south_effective_irradiance_wm2: float
    north_ambient_temperature_c: float
    south_ambient_temperature_c: float
    north_cell_temperature_c: float
    south_cell_temperature_c: float
    north_temperature_factor: float
    south_temperature_factor: float

    def as_list(self) -> list[int | float | bool]:
        return [
            int(self.start.timestamp() * 1000),
            self.north_kwh,
            self.south_kwh,
            self.total_kwh,
            self.north_kw,
            self.south_kw,
            self.total_kw,
            self.north_gti_wm2,
            self.south_gti_wm2,
            self.north_direct_radiation_wm2,
            self.south_direct_radiation_wm2,
            self.north_diffuse_radiation_wm2,
            self.south_diffuse_radiation_wm2,
            self.solar_azimuth_deg,
            self.solar_elevation_deg,
            self.north_horizon_elevation_deg,
            self.south_horizon_elevation_deg,
            self.north_horizon_blocked,
            self.south_horizon_blocked,
            self.north_effective_irradiance_wm2,
            self.south_effective_irradiance_wm2,
            self.north_ambient_temperature_c,
            self.south_ambient_temperature_c,
            self.north_cell_temperature_c,
            self.south_cell_temperature_c,
            self.north_temperature_factor,
            self.south_temperature_factor,
        ]


@dataclass(frozen=True, slots=True)
class SolarPartialShadingCandidatePoint:
    """Parallel F5 experimental partial-shading observer point."""

    start: datetime
    north_kwh: float
    south_kwh: float
    total_kwh: float
    north_kw: float
    south_kw: float
    total_kw: float
    north_gti_wm2: float
    south_gti_wm2: float
    north_direct_radiation_wm2: float
    south_direct_radiation_wm2: float
    north_diffuse_radiation_wm2: float
    south_diffuse_radiation_wm2: float
    solar_azimuth_deg: float
    solar_elevation_deg: float
    north_horizon_elevation_deg: float
    south_horizon_elevation_deg: float
    north_horizon_blocked: bool
    south_horizon_blocked: bool
    north_partial_factor: float
    south_partial_factor: float
    north_effective_irradiance_wm2: float
    south_effective_irradiance_wm2: float
    north_ambient_temperature_c: float
    south_ambient_temperature_c: float
    north_cell_temperature_c: float
    south_cell_temperature_c: float
    north_temperature_factor: float
    south_temperature_factor: float

    def as_list(self) -> list[int | float | bool]:
        return [
            int(self.start.timestamp() * 1000),
            self.north_kwh,
            self.south_kwh,
            self.total_kwh,
            self.north_kw,
            self.south_kw,
            self.total_kw,
            self.north_gti_wm2,
            self.south_gti_wm2,
            self.north_direct_radiation_wm2,
            self.south_direct_radiation_wm2,
            self.north_diffuse_radiation_wm2,
            self.south_diffuse_radiation_wm2,
            self.solar_azimuth_deg,
            self.solar_elevation_deg,
            self.north_horizon_elevation_deg,
            self.south_horizon_elevation_deg,
            self.north_horizon_blocked,
            self.south_horizon_blocked,
            self.north_partial_factor,
            self.south_partial_factor,
            self.north_effective_irradiance_wm2,
            self.south_effective_irradiance_wm2,
            self.north_ambient_temperature_c,
            self.south_ambient_temperature_c,
            self.north_cell_temperature_c,
            self.south_cell_temperature_c,
            self.north_temperature_factor,
            self.south_temperature_factor,
        ]


@dataclass(frozen=True, slots=True)
class SolarResidualLearningCandidatePoint:
    """Parallel F6 residual-learning candidate above the frozen F5 parent."""

    start: datetime
    north_kwh: float
    south_kwh: float
    total_kwh: float
    north_kw: float
    south_kw: float
    total_kw: float
    parent_north_kwh: float
    parent_south_kwh: float
    parent_total_kwh: float
    solar_azimuth_deg: float
    solar_elevation_deg: float
    solar_elevation_band: str | None
    solar_azimuth_sector: str | None
    weather_regime: str | None
    north_bin: str | None
    south_bin: str | None
    north_bin_status: str
    south_bin_status: str
    north_applied_factor: float
    south_applied_factor: float
    model_revision: str
    parent_signature: str

    def as_list(self) -> list[int | float | str | None]:
        return [
            int(self.start.timestamp() * 1000),
            self.north_kwh, self.south_kwh, self.total_kwh,
            self.north_kw, self.south_kw, self.total_kw,
            self.parent_north_kwh, self.parent_south_kwh, self.parent_total_kwh,
            self.solar_azimuth_deg, self.solar_elevation_deg,
            self.solar_elevation_band, self.solar_azimuth_sector, self.weather_regime,
            self.north_bin, self.south_bin,
            self.north_bin_status, self.south_bin_status,
            self.north_applied_factor, self.south_applied_factor,
            self.model_revision, self.parent_signature,
        ]


class DummyOSSolarCoordinator:
    """Fetch two roof forecasts and publish one source-neutral solar timeline."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self._source_points: list[SolarPoint] = []
        self._temperature_candidate_points: list[SolarTemperatureCandidatePoint] = []
        self._horizon_candidate_points: list[SolarHorizonCandidatePoint] = []
        self.horizon_candidate_last_error: str | None = None
        self.last_horizon_candidate_evaluation: dict[str, Any] | None = None
        self._horizon_candidate_snapshot: dict[str, Any] | None = None
        self._partial_shading_candidate_points: list[SolarPartialShadingCandidatePoint] = []
        self.partial_shading_candidate_last_error: str | None = None
        self.last_partial_shading_candidate_evaluation: dict[str, Any] | None = None
        self._partial_shading_candidate_snapshot: dict[str, Any] | None = None
        self.partial_shading_history: list[dict[str, Any]] = []
        self.partial_shading_last_pair_status = "waiting"
        self.partial_shading_last_slot_id: str | None = None
        self._residual_learning_candidate_points: list[
            SolarResidualLearningCandidatePoint
        ] = []
        self.residual_learning_candidate_last_error: str | None = None
        self.last_residual_learning_candidate_evaluation: dict[str, Any] | None = None
        self._residual_learning_candidate_snapshot: dict[str, Any] | None = None
        self.residual_learning_validation_history: list[dict[str, Any]] = []
        self.residual_learning_last_pair_status = "waiting"
        self.residual_learning_last_slot_id: str | None = None
        self.residual_learning_state: dict[str, Any] = {}
        self.residual_learning_state_status = "initializing"
        self.temperature_candidate_last_error: str | None = None
        self.last_temperature_candidate_evaluation: dict[str, Any] | None = None
        self._temperature_candidate_snapshot: dict[str, Any] | None = None
        self.temperature_ab_history: list[dict[str, Any]] = []
        self.temperature_ab_last_pair_status = "waiting"
        self.temperature_ab_last_slot_id: str | None = None
        self.multimodel_history: list[dict[str, Any]] = []
        self.multimodel_last_pair_status = "waiting"
        self.multimodel_last_slot_id: str | None = None
        self.last_successful_update: datetime | None = None
        self.last_attempt: datetime | None = None
        self.last_error: str | None = None
        self.source_generation_time_ms: dict[str, float | None] = {}
        self.listeners: list[callback] = []
        self._unsubs: list[Any] = []
        self.store: Store[dict[str, Any]] = Store(
            hass,
            SOLAR_STORAGE_VERSION,
            SOLAR_STORAGE_KEY,
        )
        self.last_evaluation: dict[str, Any] | None = None
        self.last_horizon_evaluations: list[dict[str, Any]] = []
        self._horizon_snapshots: dict[str, dict[str, Any]] = {}
        self._quarter_start: datetime | None = None
        self._forecast_snapshot: dict[str, Any] | None = None
        self._energy_ws: dict[str, float] = {roof: 0.0 for roof in ROOFS}
        self._covered_seconds: dict[str, float] = {roof: 0.0 for roof in ROOFS}
        self._last_sample_time: datetime | None = None
        self._last_actual: dict[str, float | None] = {roof: None for roof in ROOFS}
        self._sample_count = 0

    @property
    def points(self) -> list[SolarPoint]:
        """Return a rolling 72-hour window aligned to the next complete slot."""
        if not self._source_points:
            return []
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff = dt_util.as_utc(next_complete_slot(local_now, QUARTER_MINUTES))
        return [point for point in self._source_points if point.start >= cutoff][:FORECAST_SLOTS]

    @property
    def temperature_candidate_points(self) -> list[SolarTemperatureCandidatePoint]:
        """Return the parallel F1 candidate on the same rolling 72-hour window."""
        if not self._temperature_candidate_points:
            return []
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff = dt_util.as_utc(next_complete_slot(local_now, QUARTER_MINUTES))
        return [
            point
            for point in self._temperature_candidate_points
            if point.start >= cutoff
        ][:FORECAST_SLOTS]

    @property
    def temperature_candidate_status(self) -> str:
        """Return readiness without affecting the raw Solar source status."""
        return (
            "ready"
            if len(self.temperature_candidate_points) == FORECAST_SLOTS
            else "not_ready"
        )

    @property
    def temperature_candidate_source_point_count(self) -> int:
        """Return retained candidate buffer size."""
        return len(self._temperature_candidate_points)

    @property
    def horizon_candidate_points(self) -> list[SolarHorizonCandidatePoint]:
        """Return F3 candidate on the same rolling native 72-hour window."""
        if not self._horizon_candidate_points:
            return []
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff = dt_util.as_utc(next_complete_slot(local_now, QUARTER_MINUTES))
        return [
            point for point in self._horizon_candidate_points if point.start >= cutoff
        ][:FORECAST_SLOTS]

    @property
    def horizon_candidate_status(self) -> str:
        """Return F3 readiness without affecting raw or F1."""
        return "ready" if len(self.horizon_candidate_points) == FORECAST_SLOTS else "not_ready"

    @property
    def horizon_candidate_source_point_count(self) -> int:
        return len(self._horizon_candidate_points)

    @property
    def partial_shading_candidate_points(self) -> list[SolarPartialShadingCandidatePoint]:
        """Return F5 observer on the same rolling native 72-hour window."""
        if not self._partial_shading_candidate_points:
            return []
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff = dt_util.as_utc(next_complete_slot(local_now, QUARTER_MINUTES))
        return [
            point
            for point in self._partial_shading_candidate_points
            if point.start >= cutoff
        ][:FORECAST_SLOTS]

    @property
    def partial_shading_candidate_status(self) -> str:
        """Return F5 readiness without affecting raw/F1/F3/F4."""
        return (
            "ready"
            if len(self.partial_shading_candidate_points) == FORECAST_SLOTS
            else "not_ready"
        )

    @property
    def partial_shading_candidate_source_point_count(self) -> int:
        return len(self._partial_shading_candidate_points)

    @property
    def residual_learning_candidate_points(
        self,
    ) -> list[SolarResidualLearningCandidatePoint]:
        """Return F6 candidate on the native rolling 72-hour window."""
        if not self._residual_learning_candidate_points:
            return []
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff = dt_util.as_utc(next_complete_slot(local_now, QUARTER_MINUTES))
        return [
            point for point in self._residual_learning_candidate_points
            if point.start >= cutoff
        ][:FORECAST_SLOTS]

    @property
    def residual_learning_candidate_status(self) -> str:
        return (
            "ready"
            if len(self.residual_learning_candidate_points) == FORECAST_SLOTS
            else "not_ready"
        )

    @property
    def residual_learning_candidate_source_point_count(self) -> int:
        return len(self._residual_learning_candidate_points)

    @property
    def residual_parent_signature(self) -> str:
        """Fingerprint the frozen F5 physical parent semantics."""
        return build_parent_signature(
            {
                "parent_model": F6_PARENT_MODEL,
                "north": {
                    "dc_capacity_kwp": self.north.dc_capacity_kwp,
                    "ac_limit_kw": self.north.ac_limit_kw,
                    "tilt_deg": self.north.tilt_deg,
                    "open_meteo_azimuth_deg": self.north.open_meteo_azimuth_deg,
                    "performance_factor": self.north.performance_factor,
                    "horizon_profile": self.north_horizon_profile,
                },
                "south": {
                    "dc_capacity_kwp": self.south.dc_capacity_kwp,
                    "ac_limit_kw": self.south.ac_limit_kw,
                    "tilt_deg": self.south.tilt_deg,
                    "open_meteo_azimuth_deg": self.south.open_meteo_azimuth_deg,
                    "performance_factor": self.south.performance_factor,
                    "horizon_profile": self.south_horizon_profile,
                },
                "partial_rule": "blocked diffuse share; unblocked GTI",
                "temperature_model": "F1_Ross_temperature_v0.1",
                "ac_cap": "existing_per_array_ac_limit_kw",
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            }
        )

    @property
    def residual_learning_revision(self) -> dict[str, Any]:
        revision = self.residual_learning_state.get("revision", {})
        return dict(revision) if isinstance(revision, dict) else {}

    @property
    def residual_learning_mode(self) -> str:
        if (
            self.north_horizon_profile is None
            or self.south_horizon_profile is None
            or self.partial_shading_candidate_status != "ready"
        ):
            return "blocked_physical_gate"
        if not isinstance(self.residual_learning_state, dict):
            return "fallback_parent"
        return "candidate_observe"

    @property
    def residual_learning_status_summary(self) -> dict[str, Any]:
        revision = self.residual_learning_revision
        return {
            "phase": "F6",
            "mode": self.residual_learning_mode,
            "state_status": self.residual_learning_state_status,
            "parent_model": F6_PARENT_MODEL,
            "parent_signature": self.residual_parent_signature,
            "model_revision": revision.get("model_revision"),
            "training_cutoff": revision.get("training_cutoff"),
            "bin_contract": F6_BIN_CONTRACT,
            "thresholds": residual_learning_thresholds(),
            **revision_diagnostics(revision),
            "promotion_authority": False,
        }

    @property
    def planner_points(self) -> list[SolarPoint]:
        """Return the already-fetched source buffer for exact planner-hour joins."""
        return list(self._source_points)

    def planner_points_for_window(self, contract: dict[str, Any]) -> list[SolarPoint]:
        """Select the supplied window from the retained source buffer."""
        from .planner_time_contract import select_points
        return select_points(self._source_points, contract)

    @property
    def source_point_count(self) -> int:
        """Return raw aligned points retained for rolling-window continuity."""
        return len(self._source_points)

    @property
    def active_quarter_start(self) -> datetime | None:
        """Return the quarter currently collecting actual power."""
        return self._quarter_start

    @property
    def active_forecast_snapshot_available(self) -> bool:
        """Return whether the active quarter has a valid pre-actual forecast."""
        return self._forecast_snapshot is not None

    @property
    def pending_horizon_snapshot_count(self) -> int:
        """Return the number of immutable future horizon snapshots awaiting actuals."""
        return len(self._horizon_snapshots)

    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    def _num(self, key: str, default: float) -> float:
        try:
            return float(self._option(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def latitude(self) -> float:
        return self._num(CONF_SOLAR_LATITUDE, 51.828981)

    @property
    def longitude(self) -> float:
        return self._num(CONF_SOLAR_LONGITUDE, 4.839871)

    @property
    def north(self) -> RoofConfig:
        return RoofConfig(
            "north",
            self._num(CONF_SOLAR_NORTH_DC_KWP, 2.96),
            self._num(CONF_SOLAR_NORTH_AC_KW, 2.45),
            self._num(CONF_SOLAR_NORTH_TILT, 37.0),
            self._num(CONF_SOLAR_NORTH_AZIMUTH, 180.0),
            self._num(CONF_SOLAR_NORTH_FACTOR, 0.9),
        )

    @property
    def south(self) -> RoofConfig:
        return RoofConfig(
            "south",
            self._num(CONF_SOLAR_SOUTH_DC_KWP, 1.48),
            self._num(CONF_SOLAR_SOUTH_AC_KW, 1.23),
            self._num(CONF_SOLAR_SOUTH_TILT, 37.0),
            self._num(CONF_SOLAR_SOUTH_AZIMUTH, 0.0),
            self._num(CONF_SOLAR_SOUTH_FACTOR, 0.9),
        )

    def _horizon_profile(self, key: str) -> tuple[tuple[float, float], ...] | None:
        return parse_horizon_profile(self._option(key, "[]"))

    @property
    def north_horizon_profile(self) -> tuple[tuple[float, float], ...] | None:
        return self._horizon_profile(CONF_SOLAR_NORTH_HORIZON_PROFILE)

    @property
    def south_horizon_profile(self) -> tuple[tuple[float, float], ...] | None:
        return self._horizon_profile(CONF_SOLAR_SOUTH_HORIZON_PROFILE)

    @property
    def actual_entities(self) -> tuple[str, str, str]:
        return (
            str(self._option(CONF_SOLAR_ACTUAL_TOTAL_ENTITY, DEFAULT_SOLAR_ACTUAL_TOTAL_ENTITY)),
            str(self._option(CONF_SOLAR_ACTUAL_NORTH_DC_ENTITY, DEFAULT_SOLAR_ACTUAL_NORTH_DC_ENTITY)),
            str(self._option(CONF_SOLAR_ACTUAL_SOUTH_DC_ENTITY, DEFAULT_SOLAR_ACTUAL_SOUTH_DC_ENTITY)),
        )

    async def async_setup(self) -> None:
        """Load evaluation state, fetch Solar data and start listeners."""
        stored = await self.store.async_load() or {}
        self.last_evaluation = stored.get("last_evaluation")
        raw_candidate_evaluation = stored.get("last_temperature_candidate_evaluation")
        self.last_temperature_candidate_evaluation = (
            raw_candidate_evaluation
            if isinstance(raw_candidate_evaluation, dict)
            else None
        )
        raw_horizon_candidate_evaluation = stored.get("last_horizon_candidate_evaluation")
        self.last_horizon_candidate_evaluation = (
            raw_horizon_candidate_evaluation
            if isinstance(raw_horizon_candidate_evaluation, dict)
            else None
        )
        raw_partial_candidate_evaluation = stored.get(
            "last_partial_shading_candidate_evaluation"
        )
        self.last_partial_shading_candidate_evaluation = (
            raw_partial_candidate_evaluation
            if isinstance(raw_partial_candidate_evaluation, dict)
            else None
        )
        raw_temperature_ab_history = stored.get("temperature_ab_history")
        if isinstance(raw_temperature_ab_history, list):
            self.temperature_ab_history = sorted(
                [
                    item
                    for item in raw_temperature_ab_history
                    if isinstance(item, dict) and isinstance(item.get("date"), str)
                ],
                key=lambda item: str(item.get("date")),
            )[-MAX_HISTORY_DAYS:]
        raw_pair_status = stored.get("temperature_ab_last_pair_status")
        if isinstance(raw_pair_status, str):
            self.temperature_ab_last_pair_status = raw_pair_status
        raw_pair_slot = stored.get("temperature_ab_last_slot_id")
        if isinstance(raw_pair_slot, str):
            self.temperature_ab_last_slot_id = raw_pair_slot

        raw_multimodel_history = stored.get("multimodel_history")
        if isinstance(raw_multimodel_history, list):
            self.multimodel_history = sorted(
                [
                    item
                    for item in raw_multimodel_history
                    if isinstance(item, dict) and isinstance(item.get("date"), str)
                ],
                key=lambda item: str(item.get("date")),
            )[-MAX_HISTORY_DAYS:]
        raw_multimodel_status = stored.get("multimodel_last_pair_status")
        if isinstance(raw_multimodel_status, str):
            self.multimodel_last_pair_status = raw_multimodel_status
        raw_multimodel_slot = stored.get("multimodel_last_slot_id")
        if isinstance(raw_multimodel_slot, str):
            self.multimodel_last_slot_id = raw_multimodel_slot

        raw_partial_history = stored.get("partial_shading_history")
        if isinstance(raw_partial_history, list):
            self.partial_shading_history = sorted(
                [
                    item
                    for item in raw_partial_history
                    if isinstance(item, dict) and isinstance(item.get("date"), str)
                ],
                key=lambda item: str(item.get("date")),
            )[-MAX_HISTORY_DAYS:]
        raw_partial_status = stored.get("partial_shading_last_pair_status")
        if isinstance(raw_partial_status, str):
            self.partial_shading_last_pair_status = raw_partial_status
        raw_partial_slot = stored.get("partial_shading_last_slot_id")
        if isinstance(raw_partial_slot, str):
            self.partial_shading_last_slot_id = raw_partial_slot

        raw_residual_candidate_evaluation = stored.get(
            "last_residual_learning_candidate_evaluation"
        )
        self.last_residual_learning_candidate_evaluation = (
            raw_residual_candidate_evaluation
            if isinstance(raw_residual_candidate_evaluation, dict)
            else None
        )
        raw_residual_history = stored.get("residual_learning_validation_history")
        if isinstance(raw_residual_history, list):
            self.residual_learning_validation_history = sorted(
                [
                    item
                    for item in raw_residual_history
                    if isinstance(item, dict) and isinstance(item.get("date"), str)
                ],
                key=lambda item: str(item.get("date")),
            )[-MAX_HISTORY_DAYS:]
        raw_residual_pair_status = stored.get("residual_learning_last_pair_status")
        if isinstance(raw_residual_pair_status, str):
            self.residual_learning_last_pair_status = raw_residual_pair_status
        raw_residual_slot = stored.get("residual_learning_last_slot_id")
        if isinstance(raw_residual_slot, str):
            self.residual_learning_last_slot_id = raw_residual_slot

        state_ok, learning_state = validate_learning_state(
            stored.get("residual_learning_state"),
            F6_PARENT_MODEL,
            self.residual_parent_signature,
        )
        self.residual_learning_state = learning_state
        self.residual_learning_state_status = (
            "restored" if state_ok else "initialized_safe_fallback"
        )
        self._maybe_build_residual_revision(dt_util.utcnow())

        raw_horizon_evaluations = stored.get("last_horizon_evaluations")
        if isinstance(raw_horizon_evaluations, list):
            self.last_horizon_evaluations = [
                item for item in raw_horizon_evaluations if isinstance(item, dict)
            ]
        raw_horizon_snapshots = stored.get("horizon_snapshots")
        if isinstance(raw_horizon_snapshots, dict):
            self._horizon_snapshots = {
                str(key): value
                for key, value in raw_horizon_snapshots.items()
                if isinstance(value, dict)
            }
        await self.async_refresh()

        now = dt_util.utcnow()
        self._restore_or_start_quarter(stored.get("active_quarter"), now)
        self._prune_horizon_snapshots(self._quarter_start or now)
        self._set_actual_sample(now)

        self._unsubs.append(async_track_time_change(self.hass, self._async_hourly_refresh, minute=0, second=20))
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._async_quarter_boundary,
                minute=[0, 15, 30, 45],
                second=0,
            )
        )
        self._unsubs.append(async_track_state_change_event(self.hass, list(self.actual_entities), self._actual_changed))
        await self.store.async_save(self._storage_data())

    async def async_shutdown(self) -> None:
        self._integrate_actual_until(dt_util.utcnow())
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.store.async_save(self._storage_data())

    def async_add_listener(self, listener: callback) -> callback:
        self.listeners.append(listener)

        @callback
        def remove_listener() -> None:
            if listener in self.listeners:
                self.listeners.remove(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in list(self.listeners):
            listener()

    @callback
    def _actual_changed(self, _event: Event) -> None:
        now = dt_util.utcnow()
        self._integrate_actual_until(now)
        self._set_actual_sample(now)
        self.store.async_delay_save(
            self._storage_data,
            SOLAR_STORAGE_SAVE_DELAY_SECONDS,
        )
        self._notify()

    async def _async_quarter_boundary(self, now: datetime) -> None:
        """Finalize actual energy, capture future horizons and freeze the new slot."""
        now_utc = dt_util.as_utc(now)
        boundary_utc = floor_slot_start(now_utc, QUARTER_MINUTES)
        self._integrate_actual_until(boundary_utc)
        self._finalize_quarter(boundary_utc)
        if self._maybe_build_residual_revision(boundary_utc):
            self._rebuild_residual_learning_candidate()
        self._capture_horizon_snapshots(boundary_utc)
        if self.last_evaluation is not None:
            self.last_evaluation["pending_horizon_snapshot_count"] = len(self._horizon_snapshots)
            self.last_evaluation["horizon_capture_boundary"] = boundary_utc.isoformat()
        self._start_quarter(boundary_utc, scheduled_boundary=True)
        self._set_actual_sample(boundary_utc)
        await self.store.async_save(self._storage_data())
        self._notify()

    def _restore_or_start_quarter(
        self,
        stored: dict[str, Any] | None,
        now_utc: datetime,
    ) -> None:
        """Restore only the active local quarter; never bridge an offline gap."""
        local = dt_util.as_local(now_utc)
        minute = (local.minute // QUARTER_MINUTES) * QUARTER_MINUTES
        current_start = dt_util.as_utc(
            local.replace(minute=minute, second=0, microsecond=0)
        )
        if isinstance(stored, dict) and stored.get("start") == current_start.isoformat():
            self._quarter_start = current_start
            self._forecast_snapshot = (
                stored.get("forecast_snapshot")
                if isinstance(stored.get("forecast_snapshot"), dict)
                else None
            )
            self._temperature_candidate_snapshot = (
                stored.get("temperature_candidate_snapshot")
                if isinstance(stored.get("temperature_candidate_snapshot"), dict)
                else None
            )
            self._horizon_candidate_snapshot = (
                stored.get("horizon_candidate_snapshot")
                if isinstance(stored.get("horizon_candidate_snapshot"), dict)
                else None
            )
            self._partial_shading_candidate_snapshot = (
                stored.get("partial_shading_candidate_snapshot")
                if isinstance(stored.get("partial_shading_candidate_snapshot"), dict)
                else None
            )
            self._residual_learning_candidate_snapshot = (
                stored.get("residual_learning_candidate_snapshot")
                if isinstance(stored.get("residual_learning_candidate_snapshot"), dict)
                else None
            )
            for roof in ROOFS:
                try:
                    self._energy_ws[roof] = max(
                        0.0,
                        float(stored.get("energy_ws", {}).get(roof, 0.0)),
                    )
                    self._covered_seconds[roof] = max(
                        0.0,
                        float(stored.get("covered_seconds", {}).get(roof, 0.0)),
                    )
                except (AttributeError, TypeError, ValueError):
                    self._energy_ws[roof] = 0.0
                    self._covered_seconds[roof] = 0.0
            try:
                self._sample_count = max(0, int(stored.get("sample_count", 0)))
            except (TypeError, ValueError):
                self._sample_count = 0
            self._last_sample_time = now_utc
            return
        self._start_quarter(now_utc)

    def _start_quarter(
        self,
        now_utc: datetime,
        *,
        scheduled_boundary: bool = False,
    ) -> None:
        """Start the quarter containing now and freeze its current forecast."""
        local = dt_util.as_local(now_utc)
        minute = (local.minute // QUARTER_MINUTES) * QUARTER_MINUTES
        local_start = local.replace(minute=minute, second=0, microsecond=0)
        self._quarter_start = dt_util.as_utc(local_start)
        captured_at = self._quarter_start if scheduled_boundary else now_utc
        self._forecast_snapshot = self._snapshot_for_slot(
            self._quarter_start,
            captured_at,
        )
        self._temperature_candidate_snapshot = (
            self._temperature_candidate_snapshot_for_slot(
                self._quarter_start,
                captured_at,
            )
        )
        self._horizon_candidate_snapshot = (
            self._horizon_candidate_snapshot_for_slot(
                self._quarter_start,
                captured_at,
            )
        )
        self._partial_shading_candidate_snapshot = (
            self._partial_shading_candidate_snapshot_for_slot(
                self._quarter_start,
                captured_at,
            )
        )
        self._residual_learning_candidate_snapshot = (
            self._residual_learning_candidate_snapshot_for_slot(
                self._quarter_start,
                captured_at,
            )
        )
        self._energy_ws = {roof: 0.0 for roof in ROOFS}
        self._covered_seconds = {roof: 0.0 for roof in ROOFS}
        self._last_sample_time = now_utc
        self._sample_count = 0

    def _snapshot_for_slot(
        self,
        slot_start: datetime,
        captured_at: datetime,
    ) -> dict[str, Any] | None:
        """Freeze one forecast before any actual energy for that slot is known."""
        point = next(
            (
                item
                for item in self._source_points
                if item.start == dt_util.as_utc(slot_start)
            ),
            None,
        )
        captured = dt_util.as_utc(captured_at)
        if point is None or captured > dt_util.as_utc(slot_start):
            return None
        return {
            "start": point.start.isoformat(),
            "end": (point.start + timedelta(minutes=QUARTER_MINUTES)).isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "total_kwh": point.total_kwh,
            "provider": "open_meteo",
            "model": "open_meteo_gti_physical_v0.1",
            "source_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
            "captured_at": captured.isoformat(),
        }

    def _temperature_candidate_snapshot_for_slot(
        self,
        slot_start: datetime,
        captured_at: datetime,
    ) -> dict[str, Any] | None:
        """Freeze the F1 candidate at the identical pre-actual lock time."""
        point = next(
            (
                item
                for item in self._temperature_candidate_points
                if item.start == dt_util.as_utc(slot_start)
            ),
            None,
        )
        captured = dt_util.as_utc(captured_at)
        if point is None or captured > dt_util.as_utc(slot_start):
            return None
        return {
            "start": point.start.isoformat(),
            "end": (point.start + timedelta(minutes=QUARTER_MINUTES)).isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "total_kwh": point.total_kwh,
            "provider": "open_meteo",
            "model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "source_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
            "captured_at": captured.isoformat(),
            "ross_coefficient": SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
            "temperature_coefficient_per_c": SOLAR_TEMPERATURE_ALPHA_REFERENCE,
            "stc_cell_temperature_c": SOLAR_TEMPERATURE_CELL_STC_C,
            "north_ambient_temperature_c": point.north_ambient_temperature_c,
            "south_ambient_temperature_c": point.south_ambient_temperature_c,
            "north_cell_temperature_c": point.north_cell_temperature_c,
            "south_cell_temperature_c": point.south_cell_temperature_c,
            "north_temperature_factor": point.north_temperature_factor,
            "south_temperature_factor": point.south_temperature_factor,
        }

    def _horizon_candidate_snapshot_for_slot(
        self,
        slot_start: datetime,
        captured_at: datetime,
    ) -> dict[str, Any] | None:
        """Freeze F3 at the identical pre-actual lock time."""
        point = next(
            (
                item
                for item in self._horizon_candidate_points
                if item.start == dt_util.as_utc(slot_start)
            ),
            None,
        )
        captured = dt_util.as_utc(captured_at)
        if point is None or captured > dt_util.as_utc(slot_start):
            return None
        return {
            "start": point.start.isoformat(),
            "end": (point.start + timedelta(minutes=QUARTER_MINUTES)).isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "total_kwh": point.total_kwh,
            "provider": "open_meteo",
            "model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "source_update": self.last_successful_update.isoformat() if self.last_successful_update else None,
            "captured_at": captured.isoformat(),
            "solar_azimuth_deg": point.solar_azimuth_deg,
            "solar_elevation_deg": point.solar_elevation_deg,
            "north_horizon_elevation_deg": point.north_horizon_elevation_deg,
            "south_horizon_elevation_deg": point.south_horizon_elevation_deg,
            "north_horizon_blocked": point.north_horizon_blocked,
            "south_horizon_blocked": point.south_horizon_blocked,
            "north_effective_irradiance_wm2": point.north_effective_irradiance_wm2,
            "south_effective_irradiance_wm2": point.south_effective_irradiance_wm2,
            "north_direct_radiation_wm2": point.north_direct_radiation_wm2,
            "south_direct_radiation_wm2": point.south_direct_radiation_wm2,
            "north_diffuse_radiation_wm2": point.north_diffuse_radiation_wm2,
            "south_diffuse_radiation_wm2": point.south_diffuse_radiation_wm2,
            "north_ambient_temperature_c": point.north_ambient_temperature_c,
            "south_ambient_temperature_c": point.south_ambient_temperature_c,
            "north_cell_temperature_c": point.north_cell_temperature_c,
            "south_cell_temperature_c": point.south_cell_temperature_c,
            "north_temperature_factor": point.north_temperature_factor,
            "south_temperature_factor": point.south_temperature_factor,
        }

    def _partial_shading_candidate_snapshot_for_slot(
        self,
        slot_start: datetime,
        captured_at: datetime,
    ) -> dict[str, Any] | None:
        """Freeze F5 at the identical pre-actual lock time."""
        point = next(
            (
                item
                for item in self._partial_shading_candidate_points
                if item.start == dt_util.as_utc(slot_start)
            ),
            None,
        )
        captured = dt_util.as_utc(captured_at)
        if point is None or captured > dt_util.as_utc(slot_start):
            return None
        return {
            "start": point.start.isoformat(),
            "end": (point.start + timedelta(minutes=QUARTER_MINUTES)).isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "total_kwh": point.total_kwh,
            "provider": "open_meteo",
            "model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
            "source_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
            "captured_at": captured.isoformat(),
            "physical_parent_signature": self.residual_parent_signature,
            "solar_azimuth_deg": point.solar_azimuth_deg,
            "solar_elevation_deg": point.solar_elevation_deg,
            "north_horizon_elevation_deg": point.north_horizon_elevation_deg,
            "south_horizon_elevation_deg": point.south_horizon_elevation_deg,
            "north_horizon_blocked": point.north_horizon_blocked,
            "south_horizon_blocked": point.south_horizon_blocked,
            "north_partial_factor": point.north_partial_factor,
            "south_partial_factor": point.south_partial_factor,
            "north_effective_irradiance_wm2": point.north_effective_irradiance_wm2,
            "south_effective_irradiance_wm2": point.south_effective_irradiance_wm2,
            "north_direct_radiation_wm2": point.north_direct_radiation_wm2,
            "south_direct_radiation_wm2": point.south_direct_radiation_wm2,
            "north_diffuse_radiation_wm2": point.north_diffuse_radiation_wm2,
            "south_diffuse_radiation_wm2": point.south_diffuse_radiation_wm2,
            "north_ambient_temperature_c": point.north_ambient_temperature_c,
            "south_ambient_temperature_c": point.south_ambient_temperature_c,
            "north_cell_temperature_c": point.north_cell_temperature_c,
            "south_cell_temperature_c": point.south_cell_temperature_c,
            "north_temperature_factor": point.north_temperature_factor,
            "south_temperature_factor": point.south_temperature_factor,
        }

    def _residual_learning_candidate_snapshot_for_slot(
        self,
        slot_start: datetime,
        captured_at: datetime,
    ) -> dict[str, Any] | None:
        """Freeze the F6 revision and factors before target-slot actuals exist."""
        point = next(
            (
                item
                for item in self._residual_learning_candidate_points
                if item.start == dt_util.as_utc(slot_start)
            ),
            None,
        )
        captured = dt_util.as_utc(captured_at)
        if point is None or captured > dt_util.as_utc(slot_start):
            return None
        return {
            "start": point.start.isoformat(),
            "end": (
                point.start + timedelta(minutes=QUARTER_MINUTES)
            ).isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "total_kwh": point.total_kwh,
            "provider": "open_meteo",
            "model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
            "parent_model": F6_PARENT_MODEL,
            "parent_signature": point.parent_signature,
            "source_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
            "captured_at": captured.isoformat(),
            "model_revision": point.model_revision,
            "solar_azimuth_deg": point.solar_azimuth_deg,
            "solar_elevation_deg": point.solar_elevation_deg,
            "solar_elevation_band": point.solar_elevation_band,
            "solar_azimuth_sector": point.solar_azimuth_sector,
            "weather_regime": point.weather_regime,
            "north_bin": point.north_bin,
            "south_bin": point.south_bin,
            "north_bin_status": point.north_bin_status,
            "south_bin_status": point.south_bin_status,
            "north_applied_factor": point.north_applied_factor,
            "south_applied_factor": point.south_applied_factor,
            "parent_north_kwh": point.parent_north_kwh,
            "parent_south_kwh": point.parent_south_kwh,
            "parent_total_kwh": point.parent_total_kwh,
        }

    def _maybe_build_residual_revision(self, now_utc: datetime) -> bool:
        """Fit at most once for each closed local calendar day."""
        local_now = dt_util.as_local(now_utc)
        local_date = local_now.date().isoformat()
        if self.residual_learning_state.get("last_revision_local_date") == local_date:
            return False
        local_midnight = local_now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        build_revision(
            self.residual_learning_state,
            training_cutoff=local_midnight.isoformat(),
            cutoff_local_date=local_date,
        )
        return True

    def _capture_horizon_snapshots(self, captured_at: datetime) -> None:
        """Freeze the forecast for each configured future validation horizon."""
        captured = dt_util.as_utc(captured_at)
        self._prune_horizon_snapshots(captured)
        for horizon_hours in SOLAR_HORIZON_HOURS:
            target_start = captured + timedelta(hours=horizon_hours)
            snapshot = self._snapshot_for_slot(target_start, captured)
            if snapshot is None:
                continue
            snapshot["horizon_hours"] = horizon_hours
            snapshot["snapshot_id"] = (
                f"{target_start.isoformat()}|{horizon_hours}h"
            )
            self._horizon_snapshots.setdefault(snapshot["snapshot_id"], snapshot)

    def _prune_horizon_snapshots(self, current_slot_start: datetime) -> None:
        """Discard stale pending snapshots that can no longer receive an actual."""
        current = dt_util.as_utc(current_slot_start)
        stale: list[str] = []
        for key, snapshot in self._horizon_snapshots.items():
            try:
                target = datetime.fromisoformat(str(snapshot.get("start")))
                if target.tzinfo is None:
                    target = target.replace(tzinfo=dt_util.UTC)
                if dt_util.as_utc(target) < current:
                    stale.append(key)
            except (TypeError, ValueError):
                stale.append(key)
        for key in stale:
            self._horizon_snapshots.pop(key, None)

    def _set_actual_sample(self, now_utc: datetime) -> None:
        """Store the power values that apply from now onward."""
        actual = self.actual_power
        self._last_actual = {roof: actual[roof] for roof in ROOFS}
        self._last_sample_time = now_utc
        self._sample_count += 1

    def _integrate_actual_until(self, now_utc: datetime) -> None:
        """Integrate the previous sample with zero-order hold inside one slot."""
        if self._quarter_start is None or self._last_sample_time is None:
            self._last_sample_time = now_utc
            return
        quarter_end = self._quarter_start + timedelta(minutes=QUARTER_MINUTES)
        interval_start = max(self._last_sample_time, self._quarter_start)
        interval_end = min(now_utc, quarter_end)
        seconds = max(0.0, (interval_end - interval_start).total_seconds())
        if seconds > 0:
            for roof in ROOFS:
                power_w = self._last_actual.get(roof)
                if power_w is None:
                    continue
                self._energy_ws[roof] += max(0.0, power_w) * seconds
                self._covered_seconds[roof] += seconds
        self._last_sample_time = interval_end

    def _finalize_quarter(self, end_utc: datetime) -> None:
        """Publish the direct quarter record and any due horizon evaluations."""
        if self._quarter_start is None:
            return
        expected_end = self._quarter_start + timedelta(minutes=QUARTER_MINUTES)
        if end_utc < expected_end:
            return
        self.last_evaluation = build_quarter_evaluation(
            self._quarter_start,
            self._forecast_snapshot,
            self._energy_ws,
            self._covered_seconds,
            self._sample_count,
            SOLAR_MIN_VALID_COVERAGE,
        )
        self.last_temperature_candidate_evaluation = build_quarter_evaluation(
            self._quarter_start,
            self._temperature_candidate_snapshot,
            self._energy_ws,
            self._covered_seconds,
            self._sample_count,
            SOLAR_MIN_VALID_COVERAGE,
        )
        self.last_temperature_candidate_evaluation["candidate_model"] = (
            SOLAR_TEMPERATURE_CANDIDATE_MODEL
        )
        self.last_temperature_candidate_evaluation["candidate_status"] = (
            "locked"
            if self._temperature_candidate_snapshot is not None
            else "not_ready"
        )
        self.last_temperature_candidate_evaluation["raw_forecast_model"] = (
            self.last_evaluation.get("forecast_model")
        )
        if self._temperature_candidate_snapshot is not None:
            for field in (
                "north_ambient_temperature_c",
                "south_ambient_temperature_c",
                "north_cell_temperature_c",
                "south_cell_temperature_c",
                "north_temperature_factor",
                "south_temperature_factor",
            ):
                self.last_temperature_candidate_evaluation[field] = (
                    self._temperature_candidate_snapshot.get(field)
                )
        self.last_horizon_candidate_evaluation = build_quarter_evaluation(
            self._quarter_start,
            self._horizon_candidate_snapshot,
            self._energy_ws,
            self._covered_seconds,
            self._sample_count,
            SOLAR_MIN_VALID_COVERAGE,
        )
        self.last_horizon_candidate_evaluation["candidate_model"] = SOLAR_HORIZON_CANDIDATE_MODEL
        self.last_horizon_candidate_evaluation["candidate_status"] = (
            "locked" if self._horizon_candidate_snapshot is not None else "not_ready"
        )
        self.last_horizon_candidate_evaluation["raw_forecast_model"] = self.last_evaluation.get("forecast_model")
        self.last_horizon_candidate_evaluation["temperature_candidate_model"] = SOLAR_TEMPERATURE_CANDIDATE_MODEL
        if self._horizon_candidate_snapshot is not None:
            for field in (
                "solar_azimuth_deg",
                "solar_elevation_deg",
                "north_horizon_elevation_deg",
                "south_horizon_elevation_deg",
                "north_horizon_blocked",
                "south_horizon_blocked",
                "north_effective_irradiance_wm2",
                "south_effective_irradiance_wm2",
                "north_direct_radiation_wm2",
                "south_direct_radiation_wm2",
                "north_diffuse_radiation_wm2",
                "south_diffuse_radiation_wm2",
                "north_ambient_temperature_c",
                "south_ambient_temperature_c",
                "north_cell_temperature_c",
                "south_cell_temperature_c",
                "north_temperature_factor",
                "south_temperature_factor",
            ):
                self.last_horizon_candidate_evaluation[field] = self._horizon_candidate_snapshot.get(field)

        self.last_partial_shading_candidate_evaluation = build_quarter_evaluation(
            self._quarter_start,
            self._partial_shading_candidate_snapshot,
            self._energy_ws,
            self._covered_seconds,
            self._sample_count,
            SOLAR_MIN_VALID_COVERAGE,
        )
        self.last_partial_shading_candidate_evaluation["candidate_model"] = (
            SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL
        )
        self.last_partial_shading_candidate_evaluation["candidate_status"] = (
            "locked"
            if self._partial_shading_candidate_snapshot is not None
            else "not_ready"
        )
        self.last_partial_shading_candidate_evaluation["horizon_candidate_model"] = (
            SOLAR_HORIZON_CANDIDATE_MODEL
        )
        if self._partial_shading_candidate_snapshot is not None:
            for field in (
                "solar_azimuth_deg",
                "solar_elevation_deg",
                "north_horizon_elevation_deg",
                "south_horizon_elevation_deg",
                "north_horizon_blocked",
                "south_horizon_blocked",
                "north_partial_factor",
                "south_partial_factor",
                "north_effective_irradiance_wm2",
                "south_effective_irradiance_wm2",
                "north_direct_radiation_wm2",
                "south_direct_radiation_wm2",
                "north_diffuse_radiation_wm2",
                "south_diffuse_radiation_wm2",
                "north_ambient_temperature_c",
                "south_ambient_temperature_c",
                "north_cell_temperature_c",
                "south_cell_temperature_c",
                "north_temperature_factor",
                "south_temperature_factor",
                "physical_parent_signature",
            ):
                self.last_partial_shading_candidate_evaluation[field] = (
                    self._partial_shading_candidate_snapshot.get(field)
                )

        self.last_residual_learning_candidate_evaluation = build_quarter_evaluation(
            self._quarter_start,
            self._residual_learning_candidate_snapshot,
            self._energy_ws,
            self._covered_seconds,
            self._sample_count,
            SOLAR_MIN_VALID_COVERAGE,
        )
        self.last_residual_learning_candidate_evaluation["candidate_model"] = (
            SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL
        )
        self.last_residual_learning_candidate_evaluation["candidate_status"] = (
            "locked"
            if self._residual_learning_candidate_snapshot is not None
            else "not_ready"
        )
        self.last_residual_learning_candidate_evaluation["parent_model"] = (
            F6_PARENT_MODEL
        )
        if self._residual_learning_candidate_snapshot is not None:
            for field in (
                "parent_model",
                "parent_signature",
                "model_revision",
                "solar_azimuth_deg",
                "solar_elevation_deg",
                "solar_elevation_band",
                "solar_azimuth_sector",
                "weather_regime",
                "north_bin",
                "south_bin",
                "north_bin_status",
                "south_bin_status",
                "north_applied_factor",
                "south_applied_factor",
                "parent_north_kwh",
                "parent_south_kwh",
                "parent_total_kwh",
            ):
                self.last_residual_learning_candidate_evaluation[field] = (
                    self._residual_learning_candidate_snapshot.get(field)
                )

        self._record_temperature_ab_validation()
        self._record_multimodel_validation()
        self._record_partial_shading_validation()
        self._record_residual_learning_training()
        self._record_residual_learning_validation()

        slot_id = self._quarter_start.isoformat()
        due: list[tuple[str, dict[str, Any]]] = [
            (key, snapshot)
            for key, snapshot in self._horizon_snapshots.items()
            if snapshot.get("start") == slot_id
        ]
        horizon_evaluations: list[dict[str, Any]] = []
        for key, snapshot in due:
            evaluation = build_quarter_evaluation(
                self._quarter_start,
                snapshot,
                self._energy_ws,
                self._covered_seconds,
                self._sample_count,
                SOLAR_MIN_VALID_COVERAGE,
            )
            evaluation["evaluation_method"] = "horizon_snapshot_vs_completed_quarter_v1"
            evaluation["horizon_hours"] = int(snapshot.get("horizon_hours", 0))
            evaluation["snapshot_id"] = snapshot.get("snapshot_id", key)
            horizon_evaluations.append(evaluation)
            self._horizon_snapshots.pop(key, None)

        horizon_evaluations.sort(key=lambda item: int(item.get("horizon_hours", 0)))
        self.last_horizon_evaluations = horizon_evaluations
        self.last_evaluation["horizon_evaluations"] = horizon_evaluations
        self.last_evaluation["horizon_evaluation_count"] = len(horizon_evaluations)
        self.last_evaluation["horizon_hours_supported"] = list(SOLAR_HORIZON_HOURS)
        self.last_evaluation["pending_horizon_snapshot_count"] = len(self._horizon_snapshots)
        for evaluation in horizon_evaluations:
            hours = int(evaluation["horizon_hours"])
            prefix = f"horizon_{hours}h_"
            for field in (
                "status",
                "valid",
                "forecast_captured_at",
                "forecast_source_update",
                "forecast_provider",
                "forecast_model",
                "forecast_total_kwh",
                "actual_total_kwh",
                "error_total_kwh",
                "absolute_error_total_kwh",
                "bias_total_percent",
                "accuracy_total_percent",
                "coverage_total_percent",
            ):
                self.last_evaluation[prefix + field] = evaluation.get(field)

    def _record_temperature_ab_validation(self) -> None:
        """Persist one exact-lock F2 raw/candidate A/B sample when valid."""
        status, sample = build_temperature_ab_pair(
            self.last_evaluation,
            self.last_temperature_candidate_evaluation,
        )
        self.temperature_ab_last_pair_status = status
        if status != "ok" or sample is None or self._quarter_start is None:
            return

        slot_id = str(sample["slot_id"])
        if slot_id == self.temperature_ab_last_slot_id:
            return
        if self.temperature_ab_last_slot_id is not None:
            try:
                current_slot = datetime.fromisoformat(slot_id)
                previous_slot = datetime.fromisoformat(self.temperature_ab_last_slot_id)
                if current_slot <= previous_slot:
                    return
            except ValueError:
                return

        date_key = dt_util.as_local(self._quarter_start).date().isoformat()
        day = next(
            (
                item
                for item in self.temperature_ab_history
                if item.get("date") == date_key
            ),
            None,
        )
        if day is None:
            day = new_temperature_ab_day(date_key)
            self.temperature_ab_history.append(day)
        add_temperature_ab_sample(day, sample)
        self.temperature_ab_history.sort(key=lambda item: str(item.get("date")))
        self.temperature_ab_history = self.temperature_ab_history[-MAX_HISTORY_DAYS:]
        self.temperature_ab_last_slot_id = slot_id

    @property
    def temperature_ab_validation_summary(self) -> dict[str, Any]:
        """Return compact F2 validation evidence without promotion logic."""
        summary = summarize_temperature_ab_history(self.temperature_ab_history)
        summary["status"] = (
            "collecting"
            if int(summary.get("sample_count", 0)) > 0
            else "waiting_for_valid_pair"
        )
        summary["phase"] = "F2"
        summary["last_pair_status"] = self.temperature_ab_last_pair_status
        summary["last_slot_id"] = self.temperature_ab_last_slot_id
        return summary

    def _record_multimodel_validation(self) -> None:
        """Persist one exact-lock F4 raw/temperature/horizon sample when valid."""
        status, sample = build_multimodel_pair(
            self.last_evaluation,
            self.last_temperature_candidate_evaluation,
            self.last_horizon_candidate_evaluation,
        )
        self.multimodel_last_pair_status = status
        if status != "ok" or sample is None or self._quarter_start is None:
            return

        slot_id = str(sample["slot_id"])
        if slot_id == self.multimodel_last_slot_id:
            return
        if self.multimodel_last_slot_id is not None:
            try:
                current_slot = datetime.fromisoformat(slot_id)
                previous_slot = datetime.fromisoformat(self.multimodel_last_slot_id)
                if current_slot <= previous_slot:
                    return
            except ValueError:
                return

        date_key = dt_util.as_local(self._quarter_start).date().isoformat()
        day = next(
            (
                item
                for item in self.multimodel_history
                if item.get("date") == date_key
            ),
            None,
        )
        if day is None:
            day = new_multimodel_day(date_key)
            self.multimodel_history.append(day)
        add_multimodel_sample(day, sample)
        self.multimodel_history.sort(key=lambda item: str(item.get("date")))
        self.multimodel_history = self.multimodel_history[-MAX_HISTORY_DAYS:]
        self.multimodel_last_slot_id = slot_id

    @property
    def multimodel_validation_summary(self) -> dict[str, Any]:
        """Return compact F4 validation evidence without winner/promotion logic."""
        summary = summarize_multimodel_history(self.multimodel_history)
        summary["status"] = (
            "collecting"
            if int(summary.get("sample_count", 0)) > 0
            else "waiting_for_valid_triple"
        )
        summary["phase"] = "F4"
        summary["last_pair_status"] = self.multimodel_last_pair_status
        summary["last_slot_id"] = self.multimodel_last_slot_id
        return summary

    def _record_partial_shading_validation(self) -> None:
        """Persist one exact-lock F5 horizon-simple versus partial sample."""
        status, sample = build_partial_shading_pair(
            self.last_horizon_candidate_evaluation,
            self.last_partial_shading_candidate_evaluation,
        )
        self.partial_shading_last_pair_status = status
        if status != "ok" or sample is None or self._quarter_start is None:
            return

        slot_id = str(sample["slot_id"])
        if slot_id == self.partial_shading_last_slot_id:
            return
        if self.partial_shading_last_slot_id is not None:
            try:
                current_slot = datetime.fromisoformat(slot_id)
                previous_slot = datetime.fromisoformat(
                    self.partial_shading_last_slot_id
                )
                if current_slot <= previous_slot:
                    return
            except ValueError:
                return

        date_key = dt_util.as_local(self._quarter_start).date().isoformat()
        day = next(
            (
                item
                for item in self.partial_shading_history
                if item.get("date") == date_key
            ),
            None,
        )
        if day is None:
            day = new_partial_shading_day(date_key)
            self.partial_shading_history.append(day)
        add_partial_shading_sample(day, sample)
        self.partial_shading_history.sort(key=lambda item: str(item.get("date")))
        self.partial_shading_history = self.partial_shading_history[-MAX_HISTORY_DAYS:]
        self.partial_shading_last_slot_id = slot_id

    def _record_residual_learning_training(self) -> None:
        """Collect eligible F5 residual ratios without hindsight/backfill."""
        evaluation = self.last_partial_shading_candidate_evaluation
        if not isinstance(evaluation, dict) or self._quarter_start is None:
            return

        elevation_band = classify_solar_elevation(
            evaluation.get("solar_elevation_deg")
        )
        azimuth_sector = classify_solar_azimuth(
            evaluation.get("solar_azimuth_deg")
        )
        north_direct = self._as_float(
            evaluation.get("north_direct_radiation_wm2")
        )
        south_direct = self._as_float(
            evaluation.get("south_direct_radiation_wm2")
        )
        north_diffuse = self._as_float(
            evaluation.get("north_diffuse_radiation_wm2")
        )
        south_diffuse = self._as_float(
            evaluation.get("south_diffuse_radiation_wm2")
        )
        weather_regime = None
        if None not in (
            north_direct,
            south_direct,
            north_diffuse,
            south_diffuse,
        ):
            weather_regime, _ = classify_weather_regime(
                (float(north_direct) + float(south_direct)) / 2.0,
                (float(north_diffuse) + float(south_diffuse)) / 2.0,
            )

        local_start = dt_util.as_local(self._quarter_start)
        locked_signature = evaluation.get("physical_parent_signature")
        for array, ac_limit_kw in (
            ("north", self.north.ac_limit_kw),
            ("south", self.south.ac_limit_kw),
        ):
            status, sample = build_training_sample(
                evaluation,
                array=array,
                solar_elevation_band=elevation_band,
                solar_azimuth_sector=azimuth_sector,
                weather_regime=weather_regime,
                ac_limit_kw=ac_limit_kw,
                local_date=local_start.date().isoformat(),
                local_month=local_start.month,
                parent_signature=str(locked_signature or ""),
                expected_parent_signature=self.residual_parent_signature,
            )
            if status not in {"ok", "plausibility_outlier"} or sample is None:
                continue
            add_training_sample(self.residual_learning_state, sample)

    def _record_residual_learning_validation(self) -> None:
        """Persist one F5 parent versus F6 learned exact-lock sample."""
        status, sample = build_residual_learning_pair(
            self.last_partial_shading_candidate_evaluation,
            self.last_residual_learning_candidate_evaluation,
        )
        self.residual_learning_last_pair_status = status
        if status != "ok" or sample is None or self._quarter_start is None:
            return

        slot_id = str(sample["slot_id"])
        if slot_id == self.residual_learning_last_slot_id:
            return
        if self.residual_learning_last_slot_id is not None:
            try:
                current_slot = datetime.fromisoformat(slot_id)
                previous_slot = datetime.fromisoformat(
                    self.residual_learning_last_slot_id
                )
                if current_slot <= previous_slot:
                    return
            except ValueError:
                return

        date_key = dt_util.as_local(self._quarter_start).date().isoformat()
        day = next(
            (
                item
                for item in self.residual_learning_validation_history
                if item.get("date") == date_key
            ),
            None,
        )
        if day is None:
            day = new_residual_learning_day(date_key)
            self.residual_learning_validation_history.append(day)
        add_residual_learning_sample(day, sample)
        self.residual_learning_validation_history.sort(
            key=lambda item: str(item.get("date"))
        )
        self.residual_learning_validation_history = (
            self.residual_learning_validation_history[-MAX_HISTORY_DAYS:]
        )
        self.residual_learning_last_slot_id = slot_id

    @property
    def residual_learning_validation_summary(self) -> dict[str, Any]:
        summary = summarize_residual_learning_history(
            self.residual_learning_validation_history
        )
        summary["status"] = (
            "collecting"
            if int(summary.get("sample_count", 0)) > 0
            else "waiting_for_valid_pair"
        )
        summary["phase"] = "F6"
        summary["last_pair_status"] = self.residual_learning_last_pair_status
        summary["last_slot_id"] = self.residual_learning_last_slot_id
        summary["promotion_authority"] = False
        return summary

    @property
    def partial_shading_validation_summary(self) -> dict[str, Any]:
        """Return persistent F5 evidence without winner/promotion logic."""
        summary = summarize_partial_shading_history(self.partial_shading_history)
        summary["status"] = (
            "collecting"
            if int(summary.get("sample_count", 0)) > 0
            else "waiting_for_valid_pair"
        )
        summary["phase"] = "F5"
        summary["last_pair_status"] = self.partial_shading_last_pair_status
        summary["last_slot_id"] = self.partial_shading_last_slot_id
        return summary

    def _storage_data(self) -> dict[str, Any]:
        """Return compact JSON-safe evaluation state."""
        active = None
        if self._quarter_start is not None:
            active = {
                "start": self._quarter_start.isoformat(),
                "forecast_snapshot": self._forecast_snapshot,
                "temperature_candidate_snapshot": self._temperature_candidate_snapshot,
                "horizon_candidate_snapshot": self._horizon_candidate_snapshot,
                "partial_shading_candidate_snapshot": self._partial_shading_candidate_snapshot,
                "residual_learning_candidate_snapshot": self._residual_learning_candidate_snapshot,
                "energy_ws": dict(self._energy_ws),
                "covered_seconds": dict(self._covered_seconds),
                "sample_count": self._sample_count,
            }
        return {
            "active_quarter": active,
            "last_evaluation": self.last_evaluation,
            "last_temperature_candidate_evaluation": self.last_temperature_candidate_evaluation,
            "last_horizon_candidate_evaluation": self.last_horizon_candidate_evaluation,
            "last_partial_shading_candidate_evaluation": self.last_partial_shading_candidate_evaluation,
            "last_residual_learning_candidate_evaluation": self.last_residual_learning_candidate_evaluation,
            "residual_learning_state": self.residual_learning_state,
            "residual_learning_validation_history": self.residual_learning_validation_history,
            "residual_learning_last_pair_status": self.residual_learning_last_pair_status,
            "residual_learning_last_slot_id": self.residual_learning_last_slot_id,
            "temperature_ab_history": self.temperature_ab_history,
            "temperature_ab_last_pair_status": self.temperature_ab_last_pair_status,
            "temperature_ab_last_slot_id": self.temperature_ab_last_slot_id,
            "multimodel_history": self.multimodel_history,
            "multimodel_last_pair_status": self.multimodel_last_pair_status,
            "multimodel_last_slot_id": self.multimodel_last_slot_id,
            "partial_shading_history": self.partial_shading_history,
            "partial_shading_last_pair_status": self.partial_shading_last_pair_status,
            "partial_shading_last_slot_id": self.partial_shading_last_slot_id,
            "last_horizon_evaluations": self.last_horizon_evaluations,
            "horizon_snapshots": self._horizon_snapshots,
        }

    async def _async_hourly_refresh(self, _now: datetime) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Refresh both orientations while retaining the last valid timeline on failure."""
        last_error: Exception | None = None
        for attempt, delay in enumerate((0, 5, 15), start=1):
            if delay:
                await asyncio.sleep(delay)
            self.last_attempt = dt_util.utcnow()
            try:
                north_payload, south_payload = await asyncio.gather(
                    self._fetch_roof(self.north), self._fetch_roof(self.south)
                )
                self._apply_payloads(north_payload, south_payload)
                self.last_successful_update = dt_util.utcnow()
                self.last_error = None
                self._notify()
                return
            except (ClientError, asyncio.TimeoutError, ValueError, TypeError, KeyError) as err:
                last_error = err
                _LOGGER.warning("Open-Meteo solar refresh attempt %s/3 failed: %s", attempt, err)

        self.last_error = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown_error"
        self._notify()

    async def _fetch_roof(self, roof: RoofConfig) -> dict[str, Any]:
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "minutely_15": "temperature_2m,global_tilted_irradiance,direct_radiation,diffuse_radiation",
            # Extra stamps cover backward-average alignment plus four rolling
            # quarter advances until the next hourly refresh.
            "forecast_minutely_15": FORECAST_SLOTS + SOLAR_REQUEST_EXTRA_SLOTS,
            "tilt": roof.tilt_deg,
            "azimuth": roof.open_meteo_azimuth_deg,
            "models": OPEN_METEO_SOLAR_MODEL,
            "timezone": "UTC",
        }
        session = async_get_clientsession(self.hass)
        async with session.get(OPEN_METEO_SOLAR_ENDPOINT, params=params, timeout=20) as response:
            response.raise_for_status()
            return await response.json()

    def _apply_payloads(self, north_payload: dict[str, Any], south_payload: dict[str, Any]) -> None:
        local_now = dt_util.as_local(dt_util.utcnow())
        cutoff_utc = dt_util.as_utc(
            next_complete_slot(local_now, QUARTER_MINUTES)
        )
        north_values = self._normalize_irradiance(north_payload, cutoff_utc)
        south_values = self._normalize_irradiance(south_payload, cutoff_utc)
        if set(north_values) != set(south_values):
            raise ValueError("North and south Open-Meteo timelines do not align")

        points: list[SolarPoint] = []
        for start in sorted(north_values):
            north_irradiance = north_values[start]
            south_irradiance = south_values[start]
            north_kw = pv_power_kw(north_irradiance, self.north.dc_capacity_kwp, self.north.ac_limit_kw, self.north.performance_factor)
            south_kw = pv_power_kw(south_irradiance, self.south.dc_capacity_kwp, self.south.ac_limit_kw, self.south.performance_factor)
            north_kwh = slot_energy_kwh(north_kw)
            south_kwh = slot_energy_kwh(south_kw)
            points.append(SolarPoint(start, north_kwh, south_kwh, round(north_kwh + south_kwh, 6), north_kw, south_kw, round(north_kw + south_kw, 6), north_irradiance, south_irradiance))

        if len(points) < FORECAST_SLOTS:
            raise ValueError(
                f"Open-Meteo solar produced {len(points)} aligned slots; "
                f"expected at least {FORECAST_SLOTS}"
            )

        # Raw remains authoritative. Publish it before attempting the optional
        # F1 candidate so bad/missing temperature data cannot regress raw.
        self._source_points = points

        try:
            north_temperatures = self._normalize_interval_temperature(
                north_payload,
                cutoff_utc,
            )
            south_temperatures = self._normalize_interval_temperature(
                south_payload,
                cutoff_utc,
            )
            raw_starts = set(north_values)
            if (
                set(north_temperatures) != raw_starts
                or set(south_temperatures) != raw_starts
            ):
                raise ValueError(
                    "Temperature candidate timeline does not align with raw GTI"
                )

            candidate_points: list[SolarTemperatureCandidatePoint] = []
            for start in sorted(north_values):
                north_irradiance = north_values[start]
                south_irradiance = south_values[start]
                north_ambient = north_temperatures[start]
                south_ambient = south_temperatures[start]
                north_cell = cell_temperature_c(
                    north_ambient,
                    north_irradiance,
                )
                south_cell = cell_temperature_c(
                    south_ambient,
                    south_irradiance,
                )
                north_temp_factor = temperature_factor(north_cell)
                south_temp_factor = temperature_factor(south_cell)
                north_kw = temperature_corrected_pv_power_kw(
                    north_irradiance,
                    north_ambient,
                    self.north.dc_capacity_kwp,
                    self.north.ac_limit_kw,
                    self.north.performance_factor,
                )
                south_kw = temperature_corrected_pv_power_kw(
                    south_irradiance,
                    south_ambient,
                    self.south.dc_capacity_kwp,
                    self.south.ac_limit_kw,
                    self.south.performance_factor,
                )
                if None in (
                    north_cell,
                    south_cell,
                    north_temp_factor,
                    south_temp_factor,
                    north_kw,
                    south_kw,
                ):
                    raise ValueError(
                        f"Invalid temperature candidate inputs at {start.isoformat()}"
                    )
                north_kwh = slot_energy_kwh(north_kw)
                south_kwh = slot_energy_kwh(south_kw)
                candidate_points.append(
                    SolarTemperatureCandidatePoint(
                        start=start,
                        north_kwh=north_kwh,
                        south_kwh=south_kwh,
                        total_kwh=round(north_kwh + south_kwh, 6),
                        north_kw=north_kw,
                        south_kw=south_kw,
                        total_kw=round(north_kw + south_kw, 6),
                        north_irradiance_wm2=north_irradiance,
                        south_irradiance_wm2=south_irradiance,
                        north_ambient_temperature_c=north_ambient,
                        south_ambient_temperature_c=south_ambient,
                        north_cell_temperature_c=north_cell,
                        south_cell_temperature_c=south_cell,
                        north_temperature_factor=north_temp_factor,
                        south_temperature_factor=south_temp_factor,
                    )
                )
            if len(candidate_points) < FORECAST_SLOTS:
                raise ValueError(
                    f"Temperature candidate produced {len(candidate_points)} aligned slots; "
                    f"expected at least {FORECAST_SLOTS}"
                )
            self._temperature_candidate_points = candidate_points
            self.temperature_candidate_last_error = None
        except (ValueError, TypeError, KeyError) as err:
            self._temperature_candidate_points = []
            self.temperature_candidate_last_error = (
                f"{type(err).__name__}: {err}"
            )

        # F3 is isolated from raw/F1. Invalid profiles or direct/diffuse inputs
        # make only the horizon candidate not_ready.
        try:
            north_profile = self.north_horizon_profile
            south_profile = self.south_horizon_profile
            if north_profile is None or south_profile is None:
                raise ValueError("Both north and south physical horizon profiles are required")

            north_direct = self._normalize_radiation(north_payload, cutoff_utc, "direct_radiation")
            south_direct = self._normalize_radiation(south_payload, cutoff_utc, "direct_radiation")
            north_diffuse = self._normalize_radiation(north_payload, cutoff_utc, "diffuse_radiation")
            south_diffuse = self._normalize_radiation(south_payload, cutoff_utc, "diffuse_radiation")
            north_temperatures = self._normalize_interval_temperature(north_payload, cutoff_utc)
            south_temperatures = self._normalize_interval_temperature(south_payload, cutoff_utc)
            raw_starts = set(north_values)
            for values in (
                north_direct,
                south_direct,
                north_diffuse,
                south_diffuse,
                north_temperatures,
                south_temperatures,
            ):
                if set(values) != raw_starts:
                    raise ValueError("F3 candidate timeline does not align with raw GTI")

            horizon_points: list[SolarHorizonCandidatePoint] = []
            for start in sorted(north_values):
                # Match upstream/source semantics: solar geometry is evaluated at
                # the backward-average source stamp, i.e. slot end.
                geometry_time = start + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)
                solar_azimuth, solar_elevation = solar_position_degrees(
                    geometry_time,
                    self.latitude,
                    self.longitude,
                )
                if solar_azimuth is None or solar_elevation is None:
                    raise ValueError(f"Invalid solar position at {start.isoformat()}")
                north_horizon = interpolate_horizon_elevation_deg(north_profile, solar_azimuth)
                south_horizon = interpolate_horizon_elevation_deg(south_profile, solar_azimuth)
                if north_horizon is None or south_horizon is None:
                    raise ValueError(f"Invalid horizon interpolation at {start.isoformat()}")

                north_effective, north_blocked = horizon_effective_irradiance_wm2(
                    north_values[start], north_diffuse[start], solar_elevation, north_horizon
                )
                south_effective, south_blocked = horizon_effective_irradiance_wm2(
                    south_values[start], south_diffuse[start], solar_elevation, south_horizon
                )
                if None in (north_effective, south_effective, north_blocked, south_blocked):
                    raise ValueError(f"Invalid F3 irradiance at {start.isoformat()}")

                north_ambient = north_temperatures[start]
                south_ambient = south_temperatures[start]
                north_cell = cell_temperature_c(north_ambient, north_effective)
                south_cell = cell_temperature_c(south_ambient, south_effective)
                north_temp_factor = temperature_factor(north_cell)
                south_temp_factor = temperature_factor(south_cell)
                north_kw = temperature_corrected_pv_power_kw(
                    north_effective,
                    north_ambient,
                    self.north.dc_capacity_kwp,
                    self.north.ac_limit_kw,
                    self.north.performance_factor,
                )
                south_kw = temperature_corrected_pv_power_kw(
                    south_effective,
                    south_ambient,
                    self.south.dc_capacity_kwp,
                    self.south.ac_limit_kw,
                    self.south.performance_factor,
                )
                if None in (
                    north_cell,
                    south_cell,
                    north_temp_factor,
                    south_temp_factor,
                    north_kw,
                    south_kw,
                ):
                    raise ValueError(f"Invalid F3 temperature/power inputs at {start.isoformat()}")
                north_kwh = slot_energy_kwh(north_kw)
                south_kwh = slot_energy_kwh(south_kw)
                horizon_points.append(
                    SolarHorizonCandidatePoint(
                        start=start,
                        north_kwh=north_kwh,
                        south_kwh=south_kwh,
                        total_kwh=round(north_kwh + south_kwh, 6),
                        north_kw=north_kw,
                        south_kw=south_kw,
                        total_kw=round(north_kw + south_kw, 6),
                        north_gti_wm2=north_values[start],
                        south_gti_wm2=south_values[start],
                        north_direct_radiation_wm2=north_direct[start],
                        south_direct_radiation_wm2=south_direct[start],
                        north_diffuse_radiation_wm2=north_diffuse[start],
                        south_diffuse_radiation_wm2=south_diffuse[start],
                        solar_azimuth_deg=solar_azimuth,
                        solar_elevation_deg=solar_elevation,
                        north_horizon_elevation_deg=north_horizon,
                        south_horizon_elevation_deg=south_horizon,
                        north_horizon_blocked=bool(north_blocked),
                        south_horizon_blocked=bool(south_blocked),
                        north_effective_irradiance_wm2=north_effective,
                        south_effective_irradiance_wm2=south_effective,
                        north_ambient_temperature_c=north_ambient,
                        south_ambient_temperature_c=south_ambient,
                        north_cell_temperature_c=north_cell,
                        south_cell_temperature_c=south_cell,
                        north_temperature_factor=north_temp_factor,
                        south_temperature_factor=south_temp_factor,
                    )
                )
            if len(horizon_points) < FORECAST_SLOTS:
                raise ValueError(
                    f"Horizon candidate produced {len(horizon_points)} aligned slots; expected at least {FORECAST_SLOTS}"
                )
            self._horizon_candidate_points = horizon_points
            self.horizon_candidate_last_error = None
        except (ValueError, TypeError, KeyError) as err:
            self._horizon_candidate_points = []
            self.horizon_candidate_last_error = f"{type(err).__name__}: {err}"

        # F5 is isolated from raw/F1/F3/F4. It reuses the exact F3
        # geometry/horizon trigger and adds only the experimental partial factor.
        try:
            if len(self._horizon_candidate_points) < FORECAST_SLOTS:
                raise ValueError("F3 horizon candidate must be ready before F5")

            partial_points: list[SolarPartialShadingCandidatePoint] = []
            for horizon_point in self._horizon_candidate_points:
                north_effective, north_partial_factor = (
                    partial_shading_effective_irradiance_wm2(
                        horizon_point.north_gti_wm2,
                        horizon_point.north_diffuse_radiation_wm2,
                        horizon_point.north_direct_radiation_wm2,
                        horizon_point.north_horizon_blocked,
                    )
                )
                south_effective, south_partial_factor = (
                    partial_shading_effective_irradiance_wm2(
                        horizon_point.south_gti_wm2,
                        horizon_point.south_diffuse_radiation_wm2,
                        horizon_point.south_direct_radiation_wm2,
                        horizon_point.south_horizon_blocked,
                    )
                )
                if None in (
                    north_effective,
                    south_effective,
                    north_partial_factor,
                    south_partial_factor,
                ):
                    raise ValueError(
                        f"Invalid F5 partial irradiance at {horizon_point.start.isoformat()}"
                    )

                north_cell = cell_temperature_c(
                    horizon_point.north_ambient_temperature_c,
                    north_effective,
                )
                south_cell = cell_temperature_c(
                    horizon_point.south_ambient_temperature_c,
                    south_effective,
                )
                north_temp_factor = temperature_factor(north_cell)
                south_temp_factor = temperature_factor(south_cell)
                north_kw = temperature_corrected_pv_power_kw(
                    north_effective,
                    horizon_point.north_ambient_temperature_c,
                    self.north.dc_capacity_kwp,
                    self.north.ac_limit_kw,
                    self.north.performance_factor,
                )
                south_kw = temperature_corrected_pv_power_kw(
                    south_effective,
                    horizon_point.south_ambient_temperature_c,
                    self.south.dc_capacity_kwp,
                    self.south.ac_limit_kw,
                    self.south.performance_factor,
                )
                if None in (
                    north_cell,
                    south_cell,
                    north_temp_factor,
                    south_temp_factor,
                    north_kw,
                    south_kw,
                ):
                    raise ValueError(
                        f"Invalid F5 temperature/power inputs at {horizon_point.start.isoformat()}"
                    )
                north_kwh = slot_energy_kwh(north_kw)
                south_kwh = slot_energy_kwh(south_kw)
                partial_points.append(
                    SolarPartialShadingCandidatePoint(
                        start=horizon_point.start,
                        north_kwh=north_kwh,
                        south_kwh=south_kwh,
                        total_kwh=round(north_kwh + south_kwh, 6),
                        north_kw=north_kw,
                        south_kw=south_kw,
                        total_kw=round(north_kw + south_kw, 6),
                        north_gti_wm2=horizon_point.north_gti_wm2,
                        south_gti_wm2=horizon_point.south_gti_wm2,
                        north_direct_radiation_wm2=horizon_point.north_direct_radiation_wm2,
                        south_direct_radiation_wm2=horizon_point.south_direct_radiation_wm2,
                        north_diffuse_radiation_wm2=horizon_point.north_diffuse_radiation_wm2,
                        south_diffuse_radiation_wm2=horizon_point.south_diffuse_radiation_wm2,
                        solar_azimuth_deg=horizon_point.solar_azimuth_deg,
                        solar_elevation_deg=horizon_point.solar_elevation_deg,
                        north_horizon_elevation_deg=horizon_point.north_horizon_elevation_deg,
                        south_horizon_elevation_deg=horizon_point.south_horizon_elevation_deg,
                        north_horizon_blocked=horizon_point.north_horizon_blocked,
                        south_horizon_blocked=horizon_point.south_horizon_blocked,
                        north_partial_factor=north_partial_factor,
                        south_partial_factor=south_partial_factor,
                        north_effective_irradiance_wm2=north_effective,
                        south_effective_irradiance_wm2=south_effective,
                        north_ambient_temperature_c=horizon_point.north_ambient_temperature_c,
                        south_ambient_temperature_c=horizon_point.south_ambient_temperature_c,
                        north_cell_temperature_c=north_cell,
                        south_cell_temperature_c=south_cell,
                        north_temperature_factor=north_temp_factor,
                        south_temperature_factor=south_temp_factor,
                    )
                )
            if len(partial_points) < FORECAST_SLOTS:
                raise ValueError(
                    f"F5 partial shading candidate produced {len(partial_points)} aligned slots; "
                    f"expected at least {FORECAST_SLOTS}"
                )
            self._partial_shading_candidate_points = partial_points
            self.partial_shading_candidate_last_error = None
        except (ValueError, TypeError, KeyError) as err:
            self._partial_shading_candidate_points = []
            self.partial_shading_candidate_last_error = (
                f"{type(err).__name__}: {err}"
            )

        self._rebuild_residual_learning_candidate()

        self.source_generation_time_ms = {
            "north": self._as_float(north_payload.get("generationtime_ms")),
            "south": self._as_float(south_payload.get("generationtime_ms")),
        }

    def _rebuild_residual_learning_candidate(self) -> None:
        """Build F6 solely from the already-computed F5 parent and frozen revision."""
        try:
            if len(self._partial_shading_candidate_points) < FORECAST_SLOTS:
                raise ValueError("F5 partial parent must be ready before F6")
            if (
                self.north_horizon_profile is None
                or self.south_horizon_profile is None
            ):
                raise ValueError("Physical horizon profiles are required for F6")

            revision = self.residual_learning_revision
            revision_id = str(
                revision.get("model_revision") or "f6-no-revision"
            )
            allow_application = (
                self.residual_learning_mode == "candidate_observe"
            )
            points: list[SolarResidualLearningCandidatePoint] = []
            for parent in self._partial_shading_candidate_points:
                elevation_band = classify_solar_elevation(
                    parent.solar_elevation_deg
                )
                azimuth_sector = classify_solar_azimuth(
                    parent.solar_azimuth_deg
                )
                weather_regime, _ = classify_weather_regime(
                    (
                        parent.north_direct_radiation_wm2
                        + parent.south_direct_radiation_wm2
                    )
                    / 2.0,
                    (
                        parent.north_diffuse_radiation_wm2
                        + parent.south_diffuse_radiation_wm2
                    )
                    / 2.0,
                )
                north_key = condition_key(
                    "north",
                    str(elevation_band),
                    str(azimuth_sector),
                    str(weather_regime),
                )
                south_key = condition_key(
                    "south",
                    str(elevation_band),
                    str(azimuth_sector),
                    str(weather_regime),
                )
                north_fit = factor_for_bin(
                    revision,
                    north_key,
                    allow_application=allow_application,
                )
                south_fit = factor_for_bin(
                    revision,
                    south_key,
                    allow_application=allow_application,
                )
                north_kwh = apply_factor_with_ac_cap(
                    parent.north_kwh,
                    north_fit["applied_factor"],
                    self.north.ac_limit_kw,
                )
                south_kwh = apply_factor_with_ac_cap(
                    parent.south_kwh,
                    south_fit["applied_factor"],
                    self.south.ac_limit_kw,
                )
                if north_kwh is None or south_kwh is None:
                    raise ValueError(
                        f"Invalid F6 factor application at {parent.start.isoformat()}"
                    )
                north_kw = round(north_kwh * 4.0, 6)
                south_kw = round(south_kwh * 4.0, 6)
                points.append(
                    SolarResidualLearningCandidatePoint(
                        start=parent.start,
                        north_kwh=north_kwh,
                        south_kwh=south_kwh,
                        total_kwh=round(north_kwh + south_kwh, 6),
                        north_kw=north_kw,
                        south_kw=south_kw,
                        total_kw=round(north_kw + south_kw, 6),
                        parent_north_kwh=parent.north_kwh,
                        parent_south_kwh=parent.south_kwh,
                        parent_total_kwh=parent.total_kwh,
                        solar_azimuth_deg=parent.solar_azimuth_deg,
                        solar_elevation_deg=parent.solar_elevation_deg,
                        solar_elevation_band=elevation_band,
                        solar_azimuth_sector=azimuth_sector,
                        weather_regime=weather_regime,
                        north_bin=north_key,
                        south_bin=south_key,
                        north_bin_status=str(north_fit["status"]),
                        south_bin_status=str(south_fit["status"]),
                        north_applied_factor=float(
                            north_fit["applied_factor"]
                        ),
                        south_applied_factor=float(
                            south_fit["applied_factor"]
                        ),
                        model_revision=revision_id,
                        parent_signature=self.residual_parent_signature,
                    )
                )
            if len(points) < FORECAST_SLOTS:
                raise ValueError(
                    f"F6 residual candidate produced {len(points)} aligned slots; "
                    f"expected at least {FORECAST_SLOTS}"
                )
            self._residual_learning_candidate_points = points
            self.residual_learning_candidate_last_error = None
        except (ValueError, TypeError, KeyError) as err:
            self._residual_learning_candidate_points = []
            self.residual_learning_candidate_last_error = (
                f"{type(err).__name__}: {err}"
            )

    @staticmethod
    def _normalize_irradiance(
        payload: dict[str, Any],
        cutoff_utc: datetime,
    ) -> dict[datetime, float]:
        minutely = payload.get("minutely_15")
        if not isinstance(minutely, dict):
            raise ValueError("Open-Meteo response missing minutely_15")
        times = minutely.get("time")
        values = minutely.get("global_tilted_irradiance")
        if not isinstance(times, list) or not isinstance(values, list):
            raise ValueError("Open-Meteo response missing solar time axis or irradiance")

        timezone = ZoneInfo(str(payload.get("timezone") or OPEN_METEO_SOLAR_TIMEZONE))
        result: dict[datetime, float] = {}
        for index, raw_time in enumerate(times):
            if index >= len(values) or not isinstance(raw_time, str):
                continue
            local_dt = datetime.fromisoformat(raw_time)
            if local_dt.tzinfo is None:
                local_dt = local_dt.replace(tzinfo=timezone)
            # Open-Meteo radiation values are backward averages. A value stamped
            # 10:15 therefore represents the 10:00-10:15 energy interval.
            slot_start_utc = backward_average_slot_start(
                local_dt.astimezone(dt_util.UTC), SOLAR_RESOLUTION_MINUTES
            )
            if slot_start_utc < cutoff_utc:
                continue
            try:
                if values[index] is None:
                    raise ValueError
                irradiance = float(values[index])
                if not math.isfinite(irradiance):
                    raise ValueError
                result[slot_start_utc] = max(0.0, irradiance)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid irradiance at {raw_time}") from None
            if len(result) >= FORECAST_SLOTS + SOLAR_BUFFER_SLOTS:
                break
        return result

    @staticmethod
    def _normalize_radiation(
        payload: dict[str, Any],
        cutoff_utc: datetime,
        field: str,
    ) -> dict[datetime, float]:
        """Normalize one backward-average Open-Meteo radiation field."""
        minutely = payload.get("minutely_15")
        if not isinstance(minutely, dict):
            raise ValueError("Open-Meteo response missing minutely_15")
        times = minutely.get("time")
        values = minutely.get(field)
        if not isinstance(times, list) or not isinstance(values, list):
            raise ValueError(f"Open-Meteo response missing {field} time series")
        timezone = ZoneInfo(str(payload.get("timezone") or OPEN_METEO_SOLAR_TIMEZONE))
        result: dict[datetime, float] = {}
        for index, raw_time in enumerate(times):
            if index >= len(values) or not isinstance(raw_time, str):
                continue
            local_dt = datetime.fromisoformat(raw_time)
            if local_dt.tzinfo is None:
                local_dt = local_dt.replace(tzinfo=timezone)
            slot_start_utc = backward_average_slot_start(
                local_dt.astimezone(dt_util.UTC), SOLAR_RESOLUTION_MINUTES
            )
            if slot_start_utc < cutoff_utc:
                continue
            try:
                value = float(values[index])
                if not math.isfinite(value):
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {field} at {raw_time}") from None
            result[slot_start_utc] = max(0.0, value)
            if len(result) >= FORECAST_SLOTS + SOLAR_BUFFER_SLOTS:
                break
        return result

    @staticmethod
    def _normalize_interval_temperature(
        payload: dict[str, Any],
        cutoff_utc: datetime,
    ) -> dict[datetime, float]:
        """Map boundary temperatures to interval-average 15-minute slots."""
        minutely = payload.get("minutely_15")
        if not isinstance(minutely, dict):
            raise ValueError("Open-Meteo response missing minutely_15")
        times = minutely.get("time")
        temperatures = minutely.get("temperature_2m")
        if not isinstance(times, list) or not isinstance(temperatures, list):
            raise ValueError("Open-Meteo response missing temperature time axis")

        timezone = ZoneInfo(str(payload.get("timezone") or OPEN_METEO_SOLAR_TIMEZONE))
        result: dict[datetime, float] = {}
        for index in range(1, len(times)):
            raw_time = times[index]
            if (
                index >= len(temperatures)
                or not isinstance(raw_time, str)
                or temperatures[index - 1] is None
                or temperatures[index] is None
            ):
                continue
            local_dt = datetime.fromisoformat(raw_time)
            if local_dt.tzinfo is None:
                local_dt = local_dt.replace(tzinfo=timezone)
            slot_start_utc = backward_average_slot_start(
                local_dt.astimezone(dt_util.UTC),
                SOLAR_RESOLUTION_MINUTES,
            )
            if slot_start_utc < cutoff_utc:
                continue
            try:
                previous = float(temperatures[index - 1])
                current = float(temperatures[index])
                if not all(math.isfinite(value) for value in (previous, current)):
                    raise ValueError
                result[slot_start_utc] = round((previous + current) / 2.0, 6)
            except (TypeError, ValueError):
                continue
            if len(result) >= FORECAST_SLOTS + SOLAR_BUFFER_SLOTS:
                break
        return result

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _state_number(self, entity_id: str) -> float | None:
        state: State | None = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable", "none", "None", ""}:
            return None
        try:
            value = float(state.state)
        except ValueError:
            return None
        if not math.isfinite(value):
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == "kW":
            return value * 1000.0
        if unit == "W" or unit is None:
            return value
        _LOGGER.warning(
            "Unsupported Solar power unit %s for %s; expected W or kW",
            unit,
            entity_id,
        )
        return None

    @property
    def actual_power(self) -> dict[str, Any]:
        total_entity, north_entity, south_entity = self.actual_entities
        total = self._state_number(total_entity)
        north_dc = self._state_number(north_entity)
        south_dc = self._state_number(south_entity)
        total = max(0.0, total) if total is not None else None
        north, south = split_ac_power(total, north_dc, south_dc)
        return {"total": total, "north": north, "south": south, "method": "total_ac_x_dc_input_ratio"}

    def energy_for_local_date(self, date, roof: str = "total") -> float:
        field = {"north": "north_kwh", "south": "south_kwh", "total": "total_kwh"}[roof]
        return round(sum(getattr(point, field) for point in self.points if dt_util.as_local(point.start).date() == date), 3)

    def next_quarter_point(self, now_utc: datetime | None = None) -> SolarPoint | None:
        """Return the first Solar slot strictly after the current quarter."""
        if not self.points:
            return None
        reference = dt_util.as_utc(now_utc or dt_util.utcnow())
        index = next_future_slot_index(
            [point.start for point in self.points],
            reference,
            QUARTER_MINUTES,
        )
        return self.points[index] if index is not None else None

    def temperature_candidate_next_quarter_point(
        self,
        now_utc: datetime | None = None,
    ) -> SolarTemperatureCandidatePoint | None:
        """Return the first F1 candidate slot strictly after the current quarter."""
        points = self.temperature_candidate_points
        if not points:
            return None
        reference = dt_util.as_utc(now_utc or dt_util.utcnow())
        index = next_future_slot_index(
            [point.start for point in points],
            reference,
            QUARTER_MINUTES,
        )
        return points[index] if index is not None else None

    def horizon_candidate_next_quarter_point(
        self,
        now_utc: datetime | None = None,
    ) -> SolarHorizonCandidatePoint | None:
        """Return the first F3 candidate slot strictly after the current quarter."""
        points = self.horizon_candidate_points
        if not points:
            return None
        reference = dt_util.as_utc(now_utc or dt_util.utcnow())
        index = next_future_slot_index(
            [point.start for point in points],
            reference,
            QUARTER_MINUTES,
        )
        return points[index] if index is not None else None

    @property
    def age_minutes(self) -> float | None:
        if self.last_successful_update is None:
            return None
        return round(max(0.0, (dt_util.utcnow() - self.last_successful_update).total_seconds()) / 60.0, 1)

    def residual_learning_candidate_next_quarter_point(
        self,
    ) -> SolarResidualLearningCandidatePoint | None:
        points = self.residual_learning_candidate_points
        if not points:
            return None
        starts = [point.start for point in points]
        index = next_future_slot_index(
            starts,
            dt_util.as_utc(dt_util.utcnow()),
            SOLAR_RESOLUTION_MINUTES,
        )
        return points[index] if index is not None else None

    def partial_shading_candidate_next_quarter_point(
        self,
    ) -> SolarPartialShadingCandidatePoint | None:
        points = self.partial_shading_candidate_points
        if not points:
            return None
        starts = [point.start for point in points]
        index = next_future_slot_index(
            starts,
            dt_util.as_utc(dt_util.utcnow()),
            SOLAR_RESOLUTION_MINUTES,
        )
        return points[index] if index is not None else None

    @property
    def source_status(self) -> str:
        if self.last_successful_update is None:
            return "error" if self.last_error else "not_loaded"
        if (self.age_minutes or 0) >= 180 or not self.points:
            return "expired"
        if (
            self.last_error
            or (self.age_minutes or 0) >= 90
            or len(self.points) < FORECAST_SLOTS
        ):
            return "stale"
        return "ok"
