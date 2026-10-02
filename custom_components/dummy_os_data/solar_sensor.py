"""Sensor entities for the native Dummy OS Solar forecast."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FORECAST_SLOTS, NAME, SOLAR_MIN_VALID_COVERAGE, VERSION
from .solar import (
    OPEN_METEO_SOLAR_MODEL,
    SOLAR_HORIZON_CANDIDATE_MODEL,
    SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
    SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
    SOLAR_HORIZON_HOURS,
    SOLAR_RESOLUTION_MINUTES,
    SOLAR_TEMPERATURE_CANDIDATE_MODEL,
)
from .solar_model import (
    SOLAR_TEMPERATURE_ALPHA_REFERENCE,
    SOLAR_TEMPERATURE_CELL_STC_C,
    SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
)


def build_solar_sensors(coordinator) -> list[SensorEntity]:
    """Return all Solar shadow entities."""
    return [
        DummyOSSolarStatusSensor(coordinator),
        DummyOSSolarTimelineSensor(coordinator),
        DummyOSSolarTemperatureCandidateTimelineSensor(coordinator),
        DummyOSSolarTemperatureCandidateNextQuarterSensor(coordinator),
        DummyOSSolarTemperatureCandidateLastCompletedQuarterSensor(coordinator),
        DummyOSSolarTemperatureABValidationSensor(coordinator),
        DummyOSSolarHorizonCandidateTimelineSensor(coordinator),
        DummyOSSolarHorizonCandidateNextQuarterSensor(coordinator),
        DummyOSSolarHorizonCandidateLastCompletedQuarterSensor(coordinator),
        DummyOSSolarMultiModelValidationSensor(coordinator),
        DummyOSSolarPartialShadingCandidateTimelineSensor(coordinator),
        DummyOSSolarPartialShadingCandidateNextQuarterSensor(coordinator),
        DummyOSSolarPartialShadingCandidateLastCompletedQuarterSensor(coordinator),
        DummyOSSolarPartialShadingValidationSensor(coordinator),
        DummyOSSolarResidualLearningStatusSensor(coordinator),
        DummyOSSolarResidualLearningCandidateTimelineSensor(coordinator),
        DummyOSSolarResidualLearningCandidateNextQuarterSensor(coordinator),
        DummyOSSolarResidualLearningCandidateLastCompletedQuarterSensor(coordinator),
        DummyOSSolarResidualLearningValidationSensor(coordinator),
        DummyOSSolarDailySensor(coordinator, "today", "north"),
        DummyOSSolarDailySensor(coordinator, "today", "south"),
        DummyOSSolarDailySensor(coordinator, "today", "total"),
        DummyOSSolarDailySensor(coordinator, "tomorrow", "north"),
        DummyOSSolarDailySensor(coordinator, "tomorrow", "south"),
        DummyOSSolarDailySensor(coordinator, "tomorrow", "total"),
        DummyOSSolarNextQuarterSensor(coordinator),
        DummyOSSolarActualPowerSensor(coordinator, "north"),
        DummyOSSolarActualPowerSensor(coordinator, "south"),
        DummyOSSolarActualPowerSensor(coordinator, "total"),
        DummyOSSolarLastCompletedQuarterSensor(coordinator),
        *[
            DummyOSSolarHorizonEvaluationSensor(coordinator, horizon_hours)
            for horizon_hours in SOLAR_HORIZON_HOURS
        ],
        DummyOSSolarModelSensor(coordinator),
    ]


class DummyOSSolarBaseSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator) -> None:
        self.solar = coordinator.solar
        self._remove_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Forecast Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.solar.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class DummyOSSolarStatusSensor(DummyOSSolarBaseSensor):
    _attr_name = "DO Solar Source Status"
    _attr_unique_id = "do_solar_status"
    _attr_suggested_object_id = "do_solar_status"
    _attr_icon = "mdi:solar-power-variant-outline"

    @property
    def native_value(self) -> str:
        return self.solar.source_status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        actual = self.solar.actual_power
        evaluation = self.solar.last_evaluation
        return {
            "provider": "Open-Meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "endpoint": "api.open-meteo.com/v1/forecast",
            "last_attempt": self.solar.last_attempt.isoformat() if self.solar.last_attempt else None,
            "last_successful_update": self.solar.last_successful_update.isoformat() if self.solar.last_successful_update else None,
            "age_minutes": self.solar.age_minutes,
            "last_error": self.solar.last_error,
            "slot_count": len(self.solar.points),
            "source_buffer_slot_count": self.solar.source_point_count,
            "refresh_schedule": "hourly at :00:20",
            "retry_backoff_seconds": [0, 5, 15],
            "actual_total_available": actual["total"] is not None,
            "actual_roof_split_available": (
                actual["north"] is not None and actual["south"] is not None
            ),
            "active_evaluation_quarter": (
                self.solar.active_quarter_start.isoformat()
                if self.solar.active_quarter_start
                else None
            ),
            "active_forecast_snapshot_available": self.solar.active_forecast_snapshot_available,
            "last_evaluation_status": evaluation.get("status") if evaluation else None,
            "last_evaluation_slot": evaluation.get("slot_id") if evaluation else None,
            "temperature_candidate_status": self.solar.temperature_candidate_status,
            "temperature_candidate_point_count": len(self.solar.temperature_candidate_points),
            "temperature_candidate_last_error": self.solar.temperature_candidate_last_error,
            "horizon_candidate_status": self.solar.horizon_candidate_status,
            "horizon_candidate_point_count": len(self.solar.horizon_candidate_points),
            "horizon_candidate_last_error": self.solar.horizon_candidate_last_error,
            "partial_shading_candidate_status": self.solar.partial_shading_candidate_status,
            "partial_shading_candidate_point_count": len(
                self.solar.partial_shading_candidate_points
            ),
            "partial_shading_candidate_last_error": (
                self.solar.partial_shading_candidate_last_error
            ),
            "mode": "observation_parallel",
        }


class DummyOSSolarTimelineSensor(DummyOSSolarBaseSensor):
    _attr_name = "DO Solar Forecast Timeline"
    _attr_unique_id = "do_solar_forecast_timeline"
    _attr_suggested_object_id = "do_solar_forecast_timeline"
    _attr_icon = "mdi:chart-timeline-variant-shimmer"
    _unrecorded_attributes = frozenset({"points"})

    @property
    def native_value(self) -> int:
        return len(self.solar.points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.solar.points
        return {
            "source": "open_meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "model": OPEN_METEO_SOLAR_MODEL,
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "source_buffer_point_count": self.solar.source_point_count,
            "point_format": "[unix_ms, north_kwh, south_kwh, total_kwh, north_kw, south_kw, total_kw, north_gti_wm2, south_gti_wm2]",
            "interval_semantics": "slot_start; Open-Meteo backward-average timestamp shifted by 15 minutes",
            "forecast_start": points[0].start.isoformat() if points else None,
            "last_slot_start": points[-1].start.isoformat() if points else None,
            "forecast_end": (
                (points[-1].start + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)).isoformat()
                if points
                else None
            ),
            "recorder_points": "excluded",
            "points": [point.as_list() for point in points],
        }


class DummyOSSolarTemperatureCandidateTimelineSensor(DummyOSSolarBaseSensor):
    """Expose the F1 temperature candidate without replacing raw Solar."""

    _attr_name = "DO Solar Temperature Candidate Timeline"
    _attr_unique_id = "do_solar_temperature_candidate_timeline"
    _attr_suggested_object_id = "do_solar_temperature_candidate_timeline"
    _attr_icon = "mdi:thermometer-sun"
    _unrecorded_attributes = frozenset({"points"})

    @property
    def native_value(self) -> int:
        return len(self.solar.temperature_candidate_points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.solar.temperature_candidate_points
        return {
            "candidate_status": self.solar.temperature_candidate_status,
            "candidate_role": "parallel_observer",
            "source": "open_meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "raw_reference_model": OPEN_METEO_SOLAR_MODEL,
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "source_buffer_point_count": self.solar.temperature_candidate_source_point_count,
            "last_error": self.solar.temperature_candidate_last_error,
            "ross_coefficient": SOLAR_TEMPERATURE_ROSS_K_REFERENCE,
            "temperature_coefficient_per_c": SOLAR_TEMPERATURE_ALPHA_REFERENCE,
            "stc_cell_temperature_c": SOLAR_TEMPERATURE_CELL_STC_C,
            "temperature_semantics": "ambient interval average from adjacent temperature_2m boundaries",
            "calculation": "Tcell=Tamb_avg+GTI*k; factor=1+alpha*(Tcell-25C); then existing performance factor and Energy AC cap",
            "point_format": "[unix_ms, north_kwh, south_kwh, total_kwh, north_kw, south_kw, total_kw, north_gti_wm2, south_gti_wm2, north_ambient_c, south_ambient_c, north_cell_c, south_cell_c, north_temp_factor, south_temp_factor]",
            "interval_semantics": "slot_start; GTI backward-average timestamp shifted by 15 minutes",
            "forecast_start": points[0].start.isoformat() if points else None,
            "last_slot_start": points[-1].start.isoformat() if points else None,
            "forecast_end": (
                (points[-1].start + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)).isoformat()
                if points
                else None
            ),
            "recorder_points": "excluded",
            "points": [point.as_list() for point in points],
        }


class DummyOSSolarTemperatureCandidateNextQuarterSensor(DummyOSSolarBaseSensor):
    """Expose the next F1 candidate slot for live inspection."""

    _attr_name = "DO Solar Temperature Candidate Next Quarter"
    _attr_unique_id = "do_solar_temperature_candidate_next_quarter"
    _attr_suggested_object_id = "do_solar_temperature_candidate_next_quarter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:thermometer-lines"

    @property
    def native_value(self) -> float | None:
        point = self.solar.temperature_candidate_next_quarter_point()
        return point.total_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.solar.temperature_candidate_next_quarter_point()
        if point is None:
            return {
                "candidate_status": self.solar.temperature_candidate_status,
                "last_error": self.solar.temperature_candidate_last_error,
                "model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            }
        return {
            "candidate_status": self.solar.temperature_candidate_status,
            "model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "start": point.start.isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "north_ambient_temperature_c": point.north_ambient_temperature_c,
            "south_ambient_temperature_c": point.south_ambient_temperature_c,
            "north_cell_temperature_c": point.north_cell_temperature_c,
            "south_cell_temperature_c": point.south_cell_temperature_c,
            "north_temperature_factor": point.north_temperature_factor,
            "south_temperature_factor": point.south_temperature_factor,
            "selection": "first_future_slot",
        }


class DummyOSSolarTemperatureCandidateLastCompletedQuarterSensor(DummyOSSolarBaseSensor):
    """Expose the locked F1 candidate versus the same completed actual quarter."""

    _attr_name = "DO Solar Temperature Candidate Evaluation Last Completed Quarter"
    _attr_unique_id = "do_solar_temperature_candidate_evaluation_last_completed_quarter"
    _attr_suggested_object_id = "do_solar_temperature_candidate_evaluation_last_completed_quarter"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self) -> str | None:
        evaluation = self.solar.last_temperature_candidate_evaluation
        return evaluation.get("slot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.solar.last_temperature_candidate_evaluation
        if evaluation is None:
            return {
                "status": "waiting_for_first_completed_quarter",
                "candidate_status": self.solar.temperature_candidate_status,
                "model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            }
        return dict(evaluation)


class DummyOSSolarTemperatureABValidationSensor(DummyOSSolarBaseSensor):
    """Expose persistent F2 raw-versus-temperature-candidate validation."""

    _attr_name = "DO Solar Temperature A/B Validation"
    _attr_unique_id = "do_solar_temperature_ab_validation"
    _attr_suggested_object_id = "do_solar_temperature_ab_validation"
    _attr_icon = "mdi:compare-horizontal"
    _unrecorded_attributes = frozenset({"recent_days"})

    @property
    def native_value(self) -> int:
        summary = self.solar.temperature_ab_validation_summary
        return int(summary.get("sample_count", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.solar.temperature_ab_validation_summary
        return {
            "phase": "F2",
            "role": "ab_validation",
            "status": summary.get("status"),
            "sample_count": summary.get("sample_count"),
            "day_count": summary.get("day_count"),
            "first_date": summary.get("first_date"),
            "last_date": summary.get("last_date"),
            "last_pair_status": summary.get("last_pair_status"),
            "last_slot_id": summary.get("last_slot_id"),
            "raw_model": OPEN_METEO_SOLAR_MODEL,
            "candidate_model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            "metrics": summary.get("components"),
            "temperature_range": summary.get("temperature_range"),
            "recent_days": summary.get("recent_days"),
            "promotion_authority": False,
            "scope": "F2 exact-lock temperature A/B validation only",
        }


class DummyOSSolarMultiModelValidationSensor(DummyOSSolarBaseSensor):
    """Expose persistent F4 raw/temperature/horizon validation."""

    _attr_name = "DO Solar Multi-Model Validation"
    _attr_unique_id = "do_solar_multimodel_validation"
    _attr_suggested_object_id = "do_solar_multimodel_validation"
    _attr_icon = "mdi:compare-horizontal"
    _unrecorded_attributes = frozenset(
        {
            "recent_days",
            "breakdown_by_solar_elevation",
            "breakdown_by_solar_azimuth",
            "breakdown_by_weather_regime",
        }
    )

    @property
    def native_value(self) -> int:
        summary = self.solar.multimodel_validation_summary
        return int(summary.get("sample_count", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.solar.multimodel_validation_summary
        return {
            "phase": "F4",
            "role": "multimodel_validation",
            "status": summary.get("status"),
            "sample_count": summary.get("sample_count"),
            "day_count": summary.get("day_count"),
            "first_date": summary.get("first_date"),
            "last_date": summary.get("last_date"),
            "last_pair_status": summary.get("last_pair_status"),
            "last_slot_id": summary.get("last_slot_id"),
            "raw_model": "open_meteo_gti_physical_v0.1",
            "temperature_model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "horizon_model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            "metrics": summary.get("components"),
            "breakdown_by_solar_elevation": summary.get(
                "breakdown_by_solar_elevation"
            ),
            "breakdown_by_solar_azimuth": summary.get(
                "breakdown_by_solar_azimuth"
            ),
            "breakdown_by_weather_regime": summary.get(
                "breakdown_by_weather_regime"
            ),
            "recent_days": summary.get("recent_days"),
            "solar_elevation_bands": {
                "below_horizon": "<0deg",
                "low": "0..<10deg",
                "medium": "10..<25deg",
                "high": ">=25deg",
            },
            "solar_azimuth_sectors": {
                "north": "315..360 or 0..<45deg",
                "east": "45..<135deg",
                "south": "135..<225deg",
                "west": "225..<315deg",
            },
            "weather_regime_semantics": (
                "mean locked north/south direct+diffuse; dark<=1W/m2; "
                "diffuse_dominant diffuse_fraction>=0.75; mixed 0.35..0.75; "
                "direct_dominant<0.35"
            ),
            "promotion_authority": False,
            "scope": (
                "F4 exact-lock raw vs temperature vs horizon validation only; "
                "no forecast-formula change"
            ),
        }


class DummyOSSolarPartialShadingCandidateTimelineSensor(DummyOSSolarBaseSensor):
    """Expose F5 experimental partial-shading observer timeline."""

    _attr_name = "DO Solar Partial Shading Candidate Timeline"
    _attr_unique_id = "do_solar_partial_shading_candidate_timeline"
    _attr_suggested_object_id = "do_solar_partial_shading_candidate_timeline"
    _attr_icon = "mdi:weather-partly-cloudy"
    _unrecorded_attributes = frozenset({"points"})

    @property
    def native_value(self) -> int:
        return len(self.solar.partial_shading_candidate_points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.solar.partial_shading_candidate_points
        return {
            "phase": "F5",
            "candidate_status": self.solar.partial_shading_candidate_status,
            "candidate_role": "parallel_observer",
            "source": "open_meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
            "horizon_reference_model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "source_buffer_point_count": (
                self.solar.partial_shading_candidate_source_point_count
            ),
            "last_error": self.solar.partial_shading_candidate_last_error,
            "partial_shading_semantics": (
                "only when F3 horizon_blocked; factor=diffuse/(diffuse+direct); "
                "effective=diffuse*factor; unblocked=GTI"
            ),
            "fallback_when_diffuse_plus_direct_zero": "factor=1",
            "horizon_trigger": "reuses_F3_per_array_physical_horizon",
            "ac_cap_semantics": "existing_energy_per_array_ac_limit_kw_unchanged",
            "point_format": (
                "[unix_ms,north_kwh,south_kwh,total_kwh,north_kw,south_kw,total_kw,"
                "north_gti,south_gti,north_direct,south_direct,north_diffuse,south_diffuse,"
                "solar_azimuth,solar_elevation,north_horizon,south_horizon,"
                "north_blocked,south_blocked,north_partial_factor,south_partial_factor,"
                "north_effective,south_effective,north_ambient,south_ambient,"
                "north_cell,south_cell,north_temp_factor,south_temp_factor]"
            ),
            "forecast_start": points[0].start.isoformat() if points else None,
            "last_slot_start": points[-1].start.isoformat() if points else None,
            "forecast_end": (
                (
                    points[-1].start
                    + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)
                ).isoformat()
                if points
                else None
            ),
            "recorder_points": "excluded",
            "promotion_authority": False,
            "points": [point.as_list() for point in points],
        }


class DummyOSSolarPartialShadingCandidateNextQuarterSensor(DummyOSSolarBaseSensor):
    """Expose the first future F5 observer slot."""

    _attr_name = "DO Solar Partial Shading Candidate Next Quarter"
    _attr_unique_id = "do_solar_partial_shading_candidate_next_quarter"
    _attr_suggested_object_id = "do_solar_partial_shading_candidate_next_quarter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:weather-partly-cloudy"

    @property
    def native_value(self) -> float | None:
        point = self.solar.partial_shading_candidate_next_quarter_point()
        return point.total_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.solar.partial_shading_candidate_next_quarter_point()
        if point is None:
            return {
                "phase": "F5",
                "candidate_status": self.solar.partial_shading_candidate_status,
                "last_error": self.solar.partial_shading_candidate_last_error,
                "model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
                "promotion_authority": False,
            }
        return {
            "phase": "F5",
            "candidate_status": self.solar.partial_shading_candidate_status,
            "model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
            "start": point.start.isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "solar_azimuth_deg": point.solar_azimuth_deg,
            "solar_elevation_deg": point.solar_elevation_deg,
            "north_horizon_elevation_deg": point.north_horizon_elevation_deg,
            "south_horizon_elevation_deg": point.south_horizon_elevation_deg,
            "north_horizon_blocked": point.north_horizon_blocked,
            "south_horizon_blocked": point.south_horizon_blocked,
            "north_partial_factor": point.north_partial_factor,
            "south_partial_factor": point.south_partial_factor,
            "north_gti_wm2": point.north_gti_wm2,
            "south_gti_wm2": point.south_gti_wm2,
            "north_direct_radiation_wm2": point.north_direct_radiation_wm2,
            "south_direct_radiation_wm2": point.south_direct_radiation_wm2,
            "north_diffuse_radiation_wm2": point.north_diffuse_radiation_wm2,
            "south_diffuse_radiation_wm2": point.south_diffuse_radiation_wm2,
            "north_effective_irradiance_wm2": point.north_effective_irradiance_wm2,
            "south_effective_irradiance_wm2": point.south_effective_irradiance_wm2,
            "selection": "first_future_slot",
            "promotion_authority": False,
        }


class DummyOSSolarPartialShadingCandidateLastCompletedQuarterSensor(
    DummyOSSolarBaseSensor
):
    """Expose locked F5 observer versus the completed actual quarter."""

    _attr_name = "DO Solar Partial Shading Candidate Evaluation Last Completed Quarter"
    _attr_unique_id = "do_solar_partial_shading_candidate_evaluation_last_completed_quarter"
    _attr_suggested_object_id = "do_solar_partial_shading_candidate_evaluation_last_completed_quarter"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self) -> str | None:
        evaluation = self.solar.last_partial_shading_candidate_evaluation
        return evaluation.get("slot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.solar.last_partial_shading_candidate_evaluation
        if evaluation is None:
            return {
                "phase": "F5",
                "status": "waiting_for_first_completed_quarter",
                "candidate_status": self.solar.partial_shading_candidate_status,
                "model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
                "promotion_authority": False,
            }
        result = dict(evaluation)
        result["phase"] = "F5"
        result["promotion_authority"] = False
        return result


class DummyOSSolarPartialShadingValidationSensor(DummyOSSolarBaseSensor):
    """Expose persistent F5 horizon-simple versus partial validation."""

    _attr_name = "DO Solar Partial Shading Validation"
    _attr_unique_id = "do_solar_partial_shading_validation"
    _attr_suggested_object_id = "do_solar_partial_shading_validation"
    _attr_icon = "mdi:compare-horizontal"
    _unrecorded_attributes = frozenset({"recent_days"})

    @property
    def native_value(self) -> int:
        summary = self.solar.partial_shading_validation_summary
        return int(summary.get("sample_count", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.solar.partial_shading_validation_summary
        return {
            "phase": "F5",
            "role": "partial_shading_validation",
            "status": summary.get("status"),
            "sample_count": summary.get("sample_count"),
            "day_count": summary.get("day_count"),
            "first_date": summary.get("first_date"),
            "last_date": summary.get("last_date"),
            "last_pair_status": summary.get("last_pair_status"),
            "last_slot_id": summary.get("last_slot_id"),
            "horizon_model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "partial_model": SOLAR_PARTIAL_SHADING_CANDIDATE_MODEL,
            "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            "metrics": summary.get("components"),
            "recent_days": summary.get("recent_days"),
            "effect_scope": (
                "blocked_effect is evaluated separately per roof; total blocked "
                "when either roof horizon trigger is active"
            ),
            "promotion_authority": False,
            "scope": (
                "F5 exact-lock horizon-simple vs partial observer validation only"
            ),
        }


class DummyOSSolarResidualLearningStatusSensor(DummyOSSolarBaseSensor):
    """Expose compact F6 learner health and qualification state."""

    _attr_name = "DO Solar Residual Learning Status"
    _attr_unique_id = "do_solar_residual_learning_status"
    _attr_suggested_object_id = "do_solar_residual_learning_status"
    _attr_icon = "mdi:brain"

    @property
    def native_value(self) -> str:
        return self.solar.residual_learning_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.solar.residual_learning_status_summary)


class DummyOSSolarResidualLearningCandidateTimelineSensor(DummyOSSolarBaseSensor):
    """Expose the F6 learned candidate without replacing any physical model."""

    _attr_name = "DO Solar Residual Learning Candidate Timeline"
    _attr_unique_id = "do_solar_residual_learning_candidate_timeline"
    _attr_suggested_object_id = "do_solar_residual_learning_candidate_timeline"
    _attr_icon = "mdi:chart-timeline-variant-shimmer"
    _unrecorded_attributes = frozenset({"points"})

    @property
    def native_value(self) -> int:
        return len(self.solar.residual_learning_candidate_points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.solar.residual_learning_candidate_points
        status = self.solar.residual_learning_status_summary
        return {
            "phase": "F6",
            "candidate_status": self.solar.residual_learning_candidate_status,
            "candidate_role": "parallel_observer",
            "source": "open_meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
            "parent_model": status.get("parent_model"),
            "parent_signature": status.get("parent_signature"),
            "model_revision": status.get("model_revision"),
            "learner_mode": status.get("mode"),
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "source_buffer_point_count": (
                self.solar.residual_learning_candidate_source_point_count
            ),
            "last_error": self.solar.residual_learning_candidate_last_error,
            "factor_semantics": (
                "qualified condition-bin median residual ratio only; "
                "all insufficient/unstable/saturated/invalid states use 1.0"
            ),
            "ac_cap_semantics": (
                "existing Energy per-array ac_limit_kw reapplied after factor"
            ),
            "point_format": (
                "[unix_ms,north_kwh,south_kwh,total_kwh,north_kw,south_kw,total_kw,"
                "parent_north_kwh,parent_south_kwh,parent_total_kwh,"
                "solar_azimuth,solar_elevation,elevation_band,azimuth_sector,"
                "weather_regime,north_bin,south_bin,north_bin_status,south_bin_status,"
                "north_factor,south_factor,model_revision,parent_signature]"
            ),
            "forecast_start": points[0].start.isoformat() if points else None,
            "last_slot_start": points[-1].start.isoformat() if points else None,
            "forecast_end": (
                (
                    points[-1].start
                    + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)
                ).isoformat()
                if points
                else None
            ),
            "recorder_points": "excluded",
            "promotion_authority": False,
            "points": [point.as_list() for point in points],
        }


class DummyOSSolarResidualLearningCandidateNextQuarterSensor(DummyOSSolarBaseSensor):
    """Expose the first future F6 slot and its frozen learning decision."""

    _attr_name = "DO Solar Residual Learning Candidate Next Quarter"
    _attr_unique_id = "do_solar_residual_learning_candidate_next_quarter"
    _attr_suggested_object_id = "do_solar_residual_learning_candidate_next_quarter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:solar-power-variant-outline"

    @property
    def native_value(self) -> float | None:
        point = self.solar.residual_learning_candidate_next_quarter_point()
        return point.total_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.solar.residual_learning_candidate_next_quarter_point()
        if point is None:
            return {
                "phase": "F6",
                "candidate_status": self.solar.residual_learning_candidate_status,
                "last_error": self.solar.residual_learning_candidate_last_error,
                "model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
                "promotion_authority": False,
            }
        return {
            "phase": "F6",
            "candidate_status": self.solar.residual_learning_candidate_status,
            "model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
            "start": point.start.isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "parent_north_kwh": point.parent_north_kwh,
            "parent_south_kwh": point.parent_south_kwh,
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
            "model_revision": point.model_revision,
            "parent_signature": point.parent_signature,
            "selection": "first_future_slot",
            "promotion_authority": False,
        }


class DummyOSSolarResidualLearningCandidateLastCompletedQuarterSensor(
    DummyOSSolarBaseSensor
):
    """Expose the immutable F6 lock versus actual."""

    _attr_name = "DO Solar Residual Learning Candidate Evaluation Last Completed Quarter"
    _attr_unique_id = "do_solar_residual_learning_candidate_evaluation_last_completed_quarter"
    _attr_suggested_object_id = "do_solar_residual_learning_candidate_evaluation_last_completed_quarter"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self) -> str | None:
        evaluation = self.solar.last_residual_learning_candidate_evaluation
        return evaluation.get("slot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.solar.last_residual_learning_candidate_evaluation
        if evaluation is None:
            return {
                "phase": "F6",
                "status": "waiting_for_first_completed_quarter",
                "candidate_status": self.solar.residual_learning_candidate_status,
                "model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
                "promotion_authority": False,
            }
        result = dict(evaluation)
        result["phase"] = "F6"
        result["promotion_authority"] = False
        return result


class DummyOSSolarResidualLearningValidationSensor(DummyOSSolarBaseSensor):
    """Expose persistent exact-lock F5 parent versus F6 learned validation."""

    _attr_name = "DO Solar Residual Learning Validation"
    _attr_unique_id = "do_solar_residual_learning_validation"
    _attr_suggested_object_id = "do_solar_residual_learning_validation"
    _attr_icon = "mdi:compare-horizontal"
    _unrecorded_attributes = frozenset(
        {"recent_days", "breakdown_by_condition_bin"}
    )

    @property
    def native_value(self) -> int:
        summary = self.solar.residual_learning_validation_summary
        return int(summary.get("sample_count", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.solar.residual_learning_validation_summary
        status = self.solar.residual_learning_status_summary
        return {
            "phase": "F6",
            "role": "residual_learning_validation",
            "status": summary.get("status"),
            "sample_count": summary.get("sample_count"),
            "daylight_sample_count": summary.get("daylight_sample_count"),
            "day_count": summary.get("day_count"),
            "daylight_day_count": summary.get("daylight_day_count"),
            "first_date": summary.get("first_date"),
            "last_date": summary.get("last_date"),
            "last_pair_status": summary.get("last_pair_status"),
            "last_slot_id": summary.get("last_slot_id"),
            "parent_model": status.get("parent_model"),
            "learned_model": SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL,
            "model_revision": status.get("model_revision"),
            "metrics": summary.get("components"),
            "breakdown_by_condition_bin": summary.get(
                "breakdown_by_condition_bin"
            ),
            "recent_days": summary.get("recent_days"),
            "exit_evidence": {
                "minimum_complete_live_days": 14,
                "minimum_daylight_ab_samples_per_array": 300,
                "purpose": "F6-green/F7 assessment only; not a build gate",
            },
            "promotion_authority": False,
            "scope": (
                "F6 exact-lock F5-parent vs learned candidate validation only"
            ),
        }


class DummyOSSolarHorizonCandidateTimelineSensor(DummyOSSolarBaseSensor):
    """Expose F3 physical horizon/direct-diffuse candidate timeline."""

    _attr_name = "DO Solar Horizon Candidate Timeline"
    _attr_unique_id = "do_solar_horizon_candidate_timeline"
    _attr_suggested_object_id = "do_solar_horizon_candidate_timeline"
    _attr_icon = "mdi:weather-sunset"
    _unrecorded_attributes = frozenset({"points"})

    @property
    def native_value(self) -> int:
        return len(self.solar.horizon_candidate_points)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.solar.horizon_candidate_points
        north_profile = self.solar.north_horizon_profile
        south_profile = self.solar.south_horizon_profile
        return {
            "phase": "F3",
            "candidate_status": self.solar.horizon_candidate_status,
            "candidate_role": "parallel_observer",
            "source": "open_meteo",
            "attribution": "Weather data by Open-Meteo.com",
            "model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "raw_reference_model": OPEN_METEO_SOLAR_MODEL,
            "temperature_candidate_model": SOLAR_TEMPERATURE_CANDIDATE_MODEL,
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "source_buffer_point_count": self.solar.horizon_candidate_source_point_count,
            "last_error": self.solar.horizon_candidate_last_error,
            "north_horizon_profile": [list(point) for point in north_profile] if north_profile else None,
            "south_horizon_profile": [list(point) for point in south_profile] if south_profile else None,
            "horizon_profile_semantics": "compass azimuth 0=N 90=E 180=S 270=W 360=N; linear interpolation",
            "solar_position_semantics": "evaluated at slot_end/open_meteo backward-average source stamp",
            "irradiance_rule": "solar_elevation>=local_horizon: GTI; below local_horizon: diffuse_radiation",
            "direct_radiation_role": "diagnostic_only_in_F3; partial shading deferred",
            "ac_cap_semantics": "existing_energy_per_array_ac_limit_kw_unchanged",
            "point_format": "[unix_ms,north_kwh,south_kwh,total_kwh,north_kw,south_kw,total_kw,north_gti,south_gti,north_direct,south_direct,north_diffuse,south_diffuse,solar_azimuth,solar_elevation,north_horizon,south_horizon,north_blocked,south_blocked,north_effective,south_effective,north_ambient,south_ambient,north_cell,south_cell,north_temp_factor,south_temp_factor]",
            "forecast_start": points[0].start.isoformat() if points else None,
            "last_slot_start": points[-1].start.isoformat() if points else None,
            "forecast_end": (
                (points[-1].start + timedelta(minutes=SOLAR_RESOLUTION_MINUTES)).isoformat()
                if points else None
            ),
            "recorder_points": "excluded",
            "promotion_authority": False,
            "points": [point.as_list() for point in points],
        }


class DummyOSSolarHorizonCandidateNextQuarterSensor(DummyOSSolarBaseSensor):
    """Expose next F3 candidate slot for physical inspection."""

    _attr_name = "DO Solar Horizon Candidate Next Quarter"
    _attr_unique_id = "do_solar_horizon_candidate_next_quarter"
    _attr_suggested_object_id = "do_solar_horizon_candidate_next_quarter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:weather-sunset-up"

    @property
    def native_value(self) -> float | None:
        point = self.solar.horizon_candidate_next_quarter_point()
        return point.total_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.solar.horizon_candidate_next_quarter_point()
        if point is None:
            return {
                "phase": "F3",
                "candidate_status": self.solar.horizon_candidate_status,
                "last_error": self.solar.horizon_candidate_last_error,
                "model": SOLAR_HORIZON_CANDIDATE_MODEL,
                "promotion_authority": False,
            }
        return {
            "phase": "F3",
            "candidate_status": self.solar.horizon_candidate_status,
            "model": SOLAR_HORIZON_CANDIDATE_MODEL,
            "start": point.start.isoformat(),
            "north_kwh": point.north_kwh,
            "south_kwh": point.south_kwh,
            "solar_azimuth_deg": point.solar_azimuth_deg,
            "solar_elevation_deg": point.solar_elevation_deg,
            "north_horizon_elevation_deg": point.north_horizon_elevation_deg,
            "south_horizon_elevation_deg": point.south_horizon_elevation_deg,
            "north_horizon_blocked": point.north_horizon_blocked,
            "south_horizon_blocked": point.south_horizon_blocked,
            "north_gti_wm2": point.north_gti_wm2,
            "south_gti_wm2": point.south_gti_wm2,
            "north_direct_radiation_wm2": point.north_direct_radiation_wm2,
            "south_direct_radiation_wm2": point.south_direct_radiation_wm2,
            "north_diffuse_radiation_wm2": point.north_diffuse_radiation_wm2,
            "south_diffuse_radiation_wm2": point.south_diffuse_radiation_wm2,
            "north_effective_irradiance_wm2": point.north_effective_irradiance_wm2,
            "south_effective_irradiance_wm2": point.south_effective_irradiance_wm2,
            "north_ambient_temperature_c": point.north_ambient_temperature_c,
            "south_ambient_temperature_c": point.south_ambient_temperature_c,
            "north_cell_temperature_c": point.north_cell_temperature_c,
            "south_cell_temperature_c": point.south_cell_temperature_c,
            "north_temperature_factor": point.north_temperature_factor,
            "south_temperature_factor": point.south_temperature_factor,
            "selection": "first_future_slot",
            "promotion_authority": False,
        }


class DummyOSSolarHorizonCandidateLastCompletedQuarterSensor(DummyOSSolarBaseSensor):
    """Expose locked F3 candidate versus the same completed actual quarter."""

    _attr_name = "DO Solar Horizon Candidate Evaluation Last Completed Quarter"
    _attr_unique_id = "do_solar_horizon_candidate_evaluation_last_completed_quarter"
    _attr_suggested_object_id = "do_solar_horizon_candidate_evaluation_last_completed_quarter"
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self) -> str | None:
        evaluation = self.solar.last_horizon_candidate_evaluation
        return evaluation.get("slot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.solar.last_horizon_candidate_evaluation
        if evaluation is None:
            return {
                "phase": "F3",
                "status": "waiting_for_first_completed_quarter",
                "candidate_status": self.solar.horizon_candidate_status,
                "model": SOLAR_HORIZON_CANDIDATE_MODEL,
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
                "promotion_authority": False,
            }
        result = dict(evaluation)
        result["phase"] = "F3"
        result["promotion_authority"] = False
        return result


class DummyOSSolarDailySensor(DummyOSSolarBaseSensor):
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator, day: str, roof: str) -> None:
        super().__init__(coordinator)
        self.day = day
        self.roof = roof
        self._cached_value: float | None = None
        self._refresh_task = None
        self._refresh_pending = False
        object_id = f"do_solar_forecast_{day}_{roof}"
        self._attr_name = f"DO Solar Forecast {day.title()} {roof.title()}"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_refresh()

    async def async_will_remove_from_hass(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self._schedule_refresh()

    @callback
    def _schedule_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_pending = True
            return
        self._refresh_task = self.solar.hass.async_create_task(self._async_refresh_value())

    async def _async_refresh_value(self) -> None:
        while True:
            self._refresh_pending = False
            points = list(self.solar.points)
            local_today = dt_util.as_local(dt_util.utcnow()).date()
            target = local_today if self.day == "today" else local_today + timedelta(days=1)
            self._cached_value = await self.solar.hass.async_add_executor_job(
                self._calculate_value, points, target, self.roof
            )
            self.async_write_ha_state()
            if not self._refresh_pending:
                return

    @staticmethod
    def _calculate_value(points, target, roof: str) -> float | None:
        if not points:
            return None
        field = {"north": "north_kwh", "south": "south_kwh", "total": "total_kwh"}[roof]
        return round(sum(getattr(point, field) for point in points if dt_util.as_local(point.start).date() == target), 3)

    @property
    def native_value(self) -> float | None:
        return self._cached_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        roof = getattr(self.solar, self.roof) if self.roof != "total" else None
        return {
            "provider": "open_meteo",
            "roof": self.roof,
            "source_status": self.solar.source_status,
            "dc_capacity_kwp": roof.dc_capacity_kwp if roof else round(self.solar.north.dc_capacity_kwp + self.solar.south.dc_capacity_kwp, 3),
            "ac_limit_kw": roof.ac_limit_kw if roof else round(self.solar.north.ac_limit_kw + self.solar.south.ac_limit_kw, 3),
        }


class DummyOSSolarNextQuarterSensor(DummyOSSolarBaseSensor):
    _attr_name = "DO Solar Forecast Next Quarter"
    _attr_unique_id = "do_solar_forecast_next_quarter"
    _attr_suggested_object_id = "do_solar_forecast_next_quarter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:solar-power-variant"

    @property
    def native_value(self) -> float | None:
        point = self.solar.next_quarter_point()
        return point.total_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.solar.next_quarter_point()
        return {
            "start": point.start.isoformat() if point else None,
            "north_kwh": point.north_kwh if point else None,
            "south_kwh": point.south_kwh if point else None,
            "selection": "first_future_slot",
            "refresh_schedule": "quarter-hourly at :00",
        }


class DummyOSSolarActualPowerSensor(DummyOSSolarBaseSensor):
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:solar-panel"

    def __init__(self, coordinator, roof: str) -> None:
        super().__init__(coordinator)
        self.roof = roof
        object_id = f"do_solar_actual_power_{roof}"
        self._attr_name = f"DO Solar Actual Power {roof.title()}"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id

    @property
    def native_value(self) -> float | None:
        return self.solar.actual_power[self.roof]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"method": self.solar.actual_power["method"], "source_entities": list(self.solar.actual_entities)}


class DummyOSSolarLastCompletedQuarterSensor(DummyOSSolarBaseSensor):
    """Expose one immutable, flat record for automation and Sheets export."""

    _attr_name = "DO Solar Evaluation Last Completed Quarter"
    _attr_unique_id = "do_solar_evaluation_last_completed_quarter"
    _attr_suggested_object_id = "do_solar_evaluation_last_completed_quarter"
    _attr_icon = "mdi:chart-box-outline"

    @property
    def native_value(self) -> str | None:
        evaluation = self.solar.last_evaluation
        return evaluation.get("slot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self.solar.last_evaluation
        if evaluation is None:
            return {
                "status": "waiting_for_first_completed_quarter",
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            }
        return dict(evaluation)


class DummyOSSolarHorizonEvaluationSensor(DummyOSSolarBaseSensor):
    """Expose the latest completed evaluation for one fixed forecast horizon."""

    _attr_icon = "mdi:timeline-clock-outline"

    def __init__(self, coordinator, horizon_hours: int) -> None:
        super().__init__(coordinator)
        self.horizon_hours = horizon_hours
        object_id = f"do_solar_evaluation_horizon_{horizon_hours}h"
        self._attr_name = f"Solar Evaluation Horizon {horizon_hours}h"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id

    def _evaluation(self) -> dict[str, Any] | None:
        for evaluation in self.solar.last_horizon_evaluations:
            if int(evaluation.get("horizon_hours", 0)) == self.horizon_hours:
                return evaluation
        return None

    @property
    def native_value(self) -> str | None:
        evaluation = self._evaluation()
        return evaluation.get("snapshot_id") if evaluation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        evaluation = self._evaluation()
        if evaluation is None:
            return {
                "status": "waiting_for_first_completed_horizon",
                "horizon_hours": self.horizon_hours,
                "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
                "minimum_coverage_percent": SOLAR_MIN_VALID_COVERAGE * 100.0,
            }
        return dict(evaluation)


class DummyOSSolarModelSensor(DummyOSSolarBaseSensor):
    _attr_name = "DO Solar Forecast Model"
    _attr_unique_id = "do_solar_model"
    _attr_suggested_object_id = "do_solar_model"
    _attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str:
        return "open_meteo_gti_physical_v0.1"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "provider": "Open-Meteo",
            "source_variable": "global_tilted_irradiance",
            "source_timezone": "UTC",
            "resolution_minutes": SOLAR_RESOLUTION_MINUTES,
            "horizon_hours": 72,
            "forecast_slots": FORECAST_SLOTS,
            "north": asdict(self.solar.north),
            "south": asdict(self.solar.south),
            "azimuth_convention": "Open-Meteo: 0=south, +/-180=north",
            "calculation": "gti/1000 x dc_kwp x performance_factor; capped per roof at ac_limit_kw",
            "actual_energy_calculation": "zero-order-hold integration of total AC; north/south split by SMA DC input ratio",
            "evaluation": "forecast frozen at slot start and compared after a completed quarter with at least 90% coverage",
            "mode": "observation_parallel",
        }
