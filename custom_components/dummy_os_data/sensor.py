"""Source, Weather, Solar, and Degree Days sensors - no Home Forecast."""
from __future__ import annotations
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FORECAST_SLOTS, NAME, VERSION
from .coordinator import DummyOSDataCoordinator
from .degree_days_sensor import build_degree_days_sensors
from .home_input_sensor import build_home_input_sensors
from .solar_sensor import build_solar_sensors
from .weather import (
    OPEN_METEO_LATITUDE, OPEN_METEO_LONGITUDE, OPEN_METEO_MODEL,
    OPEN_METEO_TIMEZONE, POINT_FIELDS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: DummyOSDataCoordinator = entry.runtime_data
    async_add_entities([
        *build_home_input_sensors(coordinator),
        DummyOSWeatherCurrentSensor(coordinator, "temperature_2m", "Temperature", "°C", "mdi:thermometer", SensorDeviceClass.TEMPERATURE),
        DummyOSWeatherCurrentSensor(coordinator, "apparent_temperature", "Apparent Temperature", "°C", "mdi:thermometer-lines"),
        DummyOSWeatherCurrentSensor(coordinator, "relative_humidity_2m", "Relative Humidity", "%", "mdi:water-percent", SensorDeviceClass.HUMIDITY),
        DummyOSWeatherCurrentSensor(coordinator, "precipitation", "Precipitation", "mm", "mdi:weather-rainy"),
        DummyOSWeatherCurrentSensor(coordinator, "cloud_cover", "Cloud Cover", "%", "mdi:weather-cloudy"),
        DummyOSWeatherCurrentSensor(coordinator, "wind_speed_10m", "Wind Speed", "km/h", "mdi:weather-windy"),
        DummyOSWeatherCurrentSensor(coordinator, "wind_direction_10m", "Wind Direction", "°", "mdi:compass-outline"),
        DummyOSWeatherCurrentSensor(coordinator, "wind_gusts_10m", "Wind Gusts", "km/h", "mdi:weather-windy-variant"),
        DummyOSWeatherCurrentSensor(coordinator, "weather_code", "Weather Code", None, "mdi:weather-partly-cloudy"),
        DummyOSWeatherTimelineSensor(coordinator),
        DummyOSWeatherSourceStatusSensor(coordinator),
        DummyOSWeatherFreshnessSensor(coordinator),
        DummyOSWeatherLastUpdateSensor(coordinator),
        DummyOSWeatherModelSensor(coordinator),
        *build_solar_sensors(coordinator),
        *build_degree_days_sensors(coordinator),
    ])


class DummyOSWeatherBaseSensor(SensorEntity):
    """Base for Open-Meteo-backed Weather entities."""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator: DummyOSDataCoordinator) -> None:
        self.coordinator = coordinator
        self.weather = coordinator.weather
        self._remove_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Forecast Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.weather.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()




class DummyOSWeatherCurrentSensor(DummyOSWeatherBaseSensor):
    def __init__(self, coordinator: DummyOSDataCoordinator, key: str, label: str, unit: str | None, icon: str, device_class: SensorDeviceClass | None = None) -> None:
        super().__init__(coordinator)
        self.key = key
        object_id = f"do_weather_{key.removesuffix('_2m').removesuffix('_10m')}"
        self._attr_name = f"DO Weather {label}"
        self._attr_unique_id = object_id
        self._attr_suggested_object_id = object_id
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if device_class is not None:
            self._attr_device_class = device_class

    @property
    def native_value(self) -> Any:
        return self.weather.current.get(self.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source": "open_meteo", "source_status": self.weather.source_status, "last_successful_update": self.weather.last_successful_update.isoformat() if self.weather.last_successful_update else None}


class DummyOSWeatherTimelineSensor(DummyOSWeatherBaseSensor):
    _attr_name = "DO Weather Forecast Timeline"
    _attr_unique_id = "do_weather_forecast_timeline"
    _attr_suggested_object_id = "do_weather_forecast_timeline"
    _attr_icon = "mdi:weather-partly-cloudy"
    _unrecorded_attributes = frozenset({"points", "daily"})

    @property
    def native_value(self) -> int:
        return len(self.weather.timeline)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        points = self.weather.timeline
        return {
            "source": "open_meteo",
            "model": OPEN_METEO_MODEL,
            "resolution_minutes": 15,
            "horizon_hours": 72,
            "slot_count": FORECAST_SLOTS,
            "point_count": len(points),
            "point_format": "[unix_ms, temperature_c, humidity_pct, dew_point_c, apparent_temperature_c, precipitation_mm, rain_mm, weather_code, wind_speed_kmh, wind_direction_deg, wind_gusts_kmh, ghi_wm2, sunshine_duration_s, dhi_wm2, dni_wm2, is_day, direct_radiation_wm2]",
            "fields": ["unix_ms", *POINT_FIELDS],
            "forecast_start": datetime.fromtimestamp(points[0][0] / 1000, tz=dt_util.UTC).isoformat() if points else None,
            "forecast_end": datetime.fromtimestamp(points[-1][0] / 1000, tz=dt_util.UTC).isoformat() if points else None,
            "requested_latitude": OPEN_METEO_LATITUDE,
            "requested_longitude": OPEN_METEO_LONGITUDE,
            "source_latitude": self.weather.source_latitude,
            "source_longitude": self.weather.source_longitude,
            "source_elevation_m": self.weather.source_elevation,
            "timezone": OPEN_METEO_TIMEZONE,
            "recorder_points": "excluded",
            "daily": self.weather.daily,
            "points": points,
        }


class DummyOSWeatherSourceStatusSensor(DummyOSWeatherBaseSensor):
    _attr_name = "DO Weather Source Status"
    _attr_unique_id = "do_weather_source_status"
    _attr_suggested_object_id = "do_weather_source_status"
    _attr_icon = "mdi:cloud-check-outline"

    @property
    def native_value(self) -> str:
        return self.weather.source_status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source": "Open-Meteo", "endpoint": "api.open-meteo.com/v1/forecast", "requested_latitude": OPEN_METEO_LATITUDE, "requested_longitude": OPEN_METEO_LONGITUDE, "timezone": OPEN_METEO_TIMEZONE, "last_attempt": self.weather.last_attempt.isoformat() if self.weather.last_attempt else None, "last_successful_update": self.weather.last_successful_update.isoformat() if self.weather.last_successful_update else None, "last_error": self.weather.last_error, "age_minutes": self.weather.age_minutes, "refresh_schedule": "hourly at :00:05", "retry_backoff_seconds": [0, 5, 15]}


class DummyOSWeatherFreshnessSensor(DummyOSWeatherBaseSensor):
    _attr_name = "DO Weather Source Freshness"
    _attr_unique_id = "do_weather_source_freshness"
    _attr_suggested_object_id = "do_weather_source_freshness"
    _attr_icon = "mdi:clock-check-outline"

    @property
    def native_value(self) -> str:
        return self.weather.freshness

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"age_minutes": self.weather.age_minutes, "fresh_under_minutes": 90, "expired_from_minutes": 180}


class DummyOSWeatherLastUpdateSensor(DummyOSWeatherBaseSensor):
    _attr_name = "DO Weather Last Update"
    _attr_unique_id = "do_weather_last_update"
    _attr_suggested_object_id = "do_weather_last_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:update"

    @property
    def native_value(self) -> datetime | None:
        return self.weather.last_successful_update


class DummyOSWeatherModelSensor(DummyOSWeatherBaseSensor):
    _attr_name = "DO Weather Model"
    _attr_unique_id = "do_weather_model"
    _attr_suggested_object_id = "do_weather_model"
    _attr_icon = "mdi:cloud-sync-outline"

    @property
    def native_value(self) -> str:
        return OPEN_METEO_MODEL

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"provider": "Open-Meteo", "resolution_minutes": 15, "horizon_hours": 72, "forecast_slots": FORECAST_SLOTS, "current_variables": list(self.weather.current.keys()), "timeline_fields": list(POINT_FIELDS), "daily_days": len(self.weather.daily), "generation_time_ms": self.weather.generation_time_ms}


