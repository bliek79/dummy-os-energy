"""Home Assistant adapter for the shadow-only manual planslot interface."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NAME, VERSION
from .do_plan_manual_interface import VALID_SLOT_OPTIONS, build_do_plan_manual_interface
from .do_plan_store_sensor import get_do_plan_store_runtime

_RUNTIME_ATTR = "_dummy_os_do_plan_manual_interface_runtime"


class DummyOSManualInterfaceRuntime:
    """In-memory slot selection only; never writes the Plan Store."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.selected_slot = VALID_SLOT_OPTIONS[0]
        self._listeners: set[Callable[[], None]] = set()

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(callback)
        def remove() -> None: self._listeners.discard(callback)
        return remove

    def select(self, option: str) -> None:
        if option not in VALID_SLOT_OPTIONS: raise ValueError(f"Unsupported manual planslot: {option}")
        self.selected_slot = option
        for callback in tuple(self._listeners): callback()


def get_do_plan_manual_interface_runtime(coordinator: Any) -> DummyOSManualInterfaceRuntime:
    runtime = getattr(coordinator, _RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSManualInterfaceRuntime): return runtime
    runtime = DummyOSManualInterfaceRuntime(coordinator)
    setattr(coordinator, _RUNTIME_ATTR, runtime)
    return runtime


class DummyOSManualPlanInterfaceSensor(SensorEntity):
    _attr_name = "DO Plan Manual Interface"
    _attr_unique_id = "do_plan_manual_interface"
    _attr_suggested_object_id = "do_plan_manual_interface"
    _attr_icon = "mdi:playlist-edit"
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.store_runtime = get_do_plan_store_runtime(coordinator)
        self.manual_runtime = get_do_plan_manual_interface_runtime(coordinator)
        self._remove_store_listener = None
        self._remove_manual_listener = None

    def _result(self) -> dict[str, Any]:
        return build_do_plan_manual_interface(store_snapshot=deepcopy(self.store_runtime.snapshot), store_summary=self.store_runtime.summary(), selected_slot=self.manual_runtime.selected_slot, now=datetime.now(timezone.utc))

    @property
    def native_value(self) -> str:
        return str(self._result().get("status", "blocked"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._result()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Energy Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_store_listener = self.store_runtime.add_listener(self.async_write_ha_state)
        self._remove_manual_listener = self.manual_runtime.add_listener(self.async_write_ha_state)
        await self.store_runtime.async_ensure_loaded()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_store_listener is not None: self._remove_store_listener()
        if self._remove_manual_listener is not None: self._remove_manual_listener()
        await super().async_will_remove_from_hass()


def build_do_plan_manual_interface_sensors(coordinator: Any) -> list[SensorEntity]:
    return [DummyOSManualPlanInterfaceSensor(coordinator)]
