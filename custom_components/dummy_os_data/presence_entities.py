"""Presence/Away sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NAME, VERSION
from .presence_runtime import get_presence_runtime


class _PresenceBase:
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.runtime = get_presence_runtime(coordinator)
        self._remove_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Energy Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.runtime.add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class DummyOSPresenceContextSensor(_PresenceBase, SensorEntity):
    _attr_name = "DO Presence Context"
    _attr_unique_id = "do_presence_context"
    _attr_suggested_object_id = "do_presence_context"
    _attr_icon = "mdi:home-account"

    @property
    def native_value(self) -> str:
        return self.runtime.snapshot()["status"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.snapshot()


class DummyOSPresenceAwayScheduleValid(_PresenceBase, BinarySensorEntity):
    _attr_name = "DO Presence Away Schedule Valid"
    _attr_unique_id = "do_presence_away_schedule_valid"
    _attr_suggested_object_id = "do_presence_away_schedule_valid"
    _attr_icon = "mdi:calendar-check"

    @property
    def is_on(self) -> bool:
        return bool(self.runtime.snapshot()["schedule_valid"])


class DummyOSPresenceAwayActive(_PresenceBase, BinarySensorEntity):
    _attr_name = "DO Presence Away Active"
    _attr_unique_id = "do_presence_away_active"
    _attr_suggested_object_id = "do_presence_away_active"
    _attr_icon = "mdi:home-export-outline"

    @property
    def is_on(self) -> bool:
        return bool(self.runtime.snapshot()["schedule_active"])


def build_presence_sensors(coordinator: Any) -> list[SensorEntity]:
    return [DummyOSPresenceContextSensor(coordinator)]


def build_presence_binary_sensors(coordinator: Any) -> list[BinarySensorEntity]:
    return [DummyOSPresenceAwayScheduleValid(coordinator), DummyOSPresenceAwayActive(coordinator)]
