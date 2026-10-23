"""Lean runtime container; Home Forecast and Prices removed."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .weather import DummyOSWeatherCoordinator

class DummyOSDataCoordinator:
    """Keep the independent Source, Weather, Solar and Degree Days providers."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.weather = DummyOSWeatherCoordinator(hass)
        self.solar = None
        self.degree_days = None
        self._source_setup_task = None
