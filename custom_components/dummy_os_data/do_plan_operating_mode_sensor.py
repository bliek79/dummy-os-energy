"""Persistent Operating Mode runtime and Home Assistant status sensor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN, NAME, VERSION
from .do_plan_operating_mode import MODE_SELF_CONSUMPTION, OPERATING_MODE_OPTIONS, build_operating_mode_status

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.operating_mode"
_RUNTIME_ATTR = "_dummy_os_do_plan_operating_mode_runtime"


class DummyOSPlanOperatingModeRuntime:
    """Own the restart-persistent logical planner operating mode."""

    def __init__(self, hass: Any, coordinator: Any) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.mode = MODE_SELF_CONSUMPTION
        self.previous_mode: str | None = None
        self.changed_at: str | None = None
        self.mode_source = "initial_default"
        self.runtime_ready = False
        self._load_lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []

    async def async_ensure_loaded(self) -> None:
        if self.runtime_ready:
            return
        async with self._load_lock:
            if self.runtime_ready:
                return
            stored = await self.store.async_load()
            if isinstance(stored, dict) and stored.get("mode") in OPERATING_MODE_OPTIONS:
                self.mode = stored["mode"]
                self.previous_mode = stored.get("previous_mode")
                self.changed_at = stored.get("changed_at")
                self.mode_source = "startup_restore"
            self.runtime_ready = True
        self._notify()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def result(self) -> dict[str, Any]:
        return build_operating_mode_status(
            mode=self.mode,
            previous_mode=self.previous_mode,
            changed_at=self.changed_at,
            mode_source=self.mode_source,
            runtime_ready=self.runtime_ready,
        )

    async def async_set_mode(self, mode: str, *, source: str = "manual_select") -> None:
        if mode not in OPERATING_MODE_OPTIONS:
            raise ValueError(f"Unsupported operating mode: {mode}")
        await self.async_ensure_loaded()
        if mode == self.mode:
            return
        self.previous_mode = self.mode
        self.mode = mode
        self.changed_at = datetime.now(timezone.utc).isoformat()
        self.mode_source = source
        await self.store.async_save(
            {
                "mode": self.mode,
                "previous_mode": self.previous_mode,
                "changed_at": self.changed_at,
            }
        )
        self._notify()
        # Existing downstream observer entities also listen to the coordinator.
        # Use the coordinator's established notification path; Operating Mode
        # never changes forecast data or grants execution authority.
        self.coordinator._notify()


def get_do_plan_operating_mode_runtime(coordinator: Any) -> DummyOSPlanOperatingModeRuntime:
    runtime = getattr(coordinator, _RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSPlanOperatingModeRuntime):
        return runtime
    runtime = DummyOSPlanOperatingModeRuntime(coordinator.hass, coordinator)
    setattr(coordinator, _RUNTIME_ATTR, runtime)
    return runtime


class DummyOSPlanOperatingModeStatusSensor(SensorEntity):
    _attr_name = "DO Plan Operating Mode Status"
    _attr_unique_id = "do_plan_operating_mode_status"
    _attr_suggested_object_id = "do_plan_operating_mode_status"
    _attr_icon = "mdi:state-machine"
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.runtime = get_do_plan_operating_mode_runtime(coordinator)
        self._remove_listener = None

    @property
    def native_value(self) -> str:
        return str(self.runtime.result().get("status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.result()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "main")},
            name=NAME,
            manufacturer="Dummy OS",
            model="Energy Platform",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.runtime.add_listener(self._handle_update)
        await self.runtime.async_ensure_loaded()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


def build_do_plan_operating_mode_sensors(coordinator: Any) -> list[SensorEntity]:
    return [DummyOSPlanOperatingModeStatusSensor(coordinator)]
