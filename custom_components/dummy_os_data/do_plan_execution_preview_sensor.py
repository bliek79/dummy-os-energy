"""Home Assistant observer-only adapter for DO Plan Execution Preview."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NAME, VERSION
from .do_plan_execution_preview import build_do_plan_execution_preview
from .do_plan_safety_sensor import DummyOSPlanSafetyRuntime, get_do_plan_safety_runtime


class DummyOSPlanExecutionPreviewRuntime:
    """Read-only Execution Preview over the shared Safety/Scheduler/Store runtime."""

    def __init__(self, coordinator: Any, safety_runtime: DummyOSPlanSafetyRuntime) -> None:
        self.coordinator = coordinator
        self.safety_runtime = safety_runtime
        self.scheduler_runtime = safety_runtime.scheduler_runtime
        self.store_runtime = safety_runtime.store_runtime

    def result(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        scheduler = self.scheduler_runtime.result(current)
        safety, prestart = self.safety_runtime.results(current)
        snapshot = deepcopy(self.store_runtime.snapshot)
        return build_do_plan_execution_preview(
            scheduler_result=scheduler,
            safety_result=safety,
            prestart_result=prestart,
            store_snapshot=snapshot,
            now=current,
        )


_EXECUTION_RUNTIME_ATTR = "_dummy_os_do_plan_execution_preview_runtime"


def get_do_plan_execution_preview_runtime(coordinator: Any) -> DummyOSPlanExecutionPreviewRuntime:
    runtime = getattr(coordinator, _EXECUTION_RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSPlanExecutionPreviewRuntime):
        return runtime
    runtime = DummyOSPlanExecutionPreviewRuntime(coordinator, get_do_plan_safety_runtime(coordinator))
    setattr(coordinator, _EXECUTION_RUNTIME_ATTR, runtime)
    return runtime


class _ExecutionPreviewEntityMixin:
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, runtime: DummyOSPlanExecutionPreviewRuntime) -> None:
        self.runtime = runtime
        self.coordinator = runtime.coordinator
        self._remove_store_listener = None
        self._remove_coordinator_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Energy Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.runtime.store_runtime.async_ensure_loaded()
        self._remove_store_listener = self.runtime.store_runtime.add_listener(self._handle_update)
        self._remove_coordinator_listener = self.coordinator.async_add_listener(self._handle_update)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        for remove in (self._remove_store_listener, self._remove_coordinator_listener):
            if remove is not None:
                remove()
        await super().async_will_remove_from_hass()

    def _handle_update(self) -> None:
        self.async_write_ha_state()


class DummyOSPlanExecutionPreviewSensor(_ExecutionPreviewEntityMixin, SensorEntity):
    _attr_name = "DO Plan Execution Preview"
    _attr_unique_id = "do_plan_execution_preview"
    _attr_suggested_object_id = "do_plan_execution_preview"
    _attr_icon = "mdi:play-box-lock-outline"

    @property
    def native_value(self) -> str:
        return str(self.runtime.result().get("execution_preview_status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.result()


class DummyOSPlanExecutionPreviewReadyBinarySensor(_ExecutionPreviewEntityMixin, BinarySensorEntity):
    _attr_name = "DO Plan Execution Preview Ready"
    _attr_unique_id = "do_plan_execution_preview_ready"
    _attr_suggested_object_id = "do_plan_execution_preview_ready"
    _attr_icon = "mdi:play-circle-outline"

    @property
    def is_on(self) -> bool:
        return self.runtime.result().get("execution_preview_ready") is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self.runtime.result()
        return {
            "execution_preview_status": result.get("execution_preview_status"),
            "selected_slot_id": result.get("selected_slot_id"),
            "selected_plan_id": result.get("selected_plan_id"),
            "blockers": result.get("blockers", []),
            "shadow_only": True,
            "active_use_permitted": False,
            "physical_execution_authority": False,
        }


def build_do_plan_execution_preview_sensors(coordinator: Any) -> list[SensorEntity]:
    runtime = get_do_plan_execution_preview_runtime(coordinator)
    return [DummyOSPlanExecutionPreviewSensor(runtime)]


def build_do_plan_execution_preview_binary_sensors(coordinator: Any) -> list[BinarySensorEntity]:
    runtime = get_do_plan_execution_preview_runtime(coordinator)
    return [DummyOSPlanExecutionPreviewReadyBinarySensor(runtime)]
