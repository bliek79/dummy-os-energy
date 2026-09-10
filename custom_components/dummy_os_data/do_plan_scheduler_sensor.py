"""Home Assistant shadow adapter for Planner Step 7 Scheduler."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NAME, VERSION
from .do_plan_scheduler import build_do_plan_scheduler
from .do_plan_store_sensor import DummyOSShadowPlanStoreRuntime, get_do_plan_store_runtime


class DummyOSPlanSchedulerRuntime:
    """Pure Scheduler view over the shared shadow Plan Store runtime."""

    def __init__(self, coordinator: Any, store_runtime: DummyOSShadowPlanStoreRuntime) -> None:
        self.coordinator = coordinator
        self.store_runtime = store_runtime
        self._cached_result: dict[str, Any] | None = None
        self._cache_key: tuple[Any, ...] | None = None

    def result(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        summary = self.store_runtime.summary()
        snapshot = self.store_runtime.snapshot
        key = (
            current.astimezone(timezone.utc).isoformat(),
            repr(snapshot),
            summary.get("status"),
            summary.get("store_valid"),
            summary.get("persistence_loaded"),
            summary.get("manual_priority_ok"),
        )
        if key != self._cache_key or self._cached_result is None:
            result = build_do_plan_scheduler(
                store_snapshot=deepcopy(snapshot),
                store_summary=summary,
                now=current,
            )
            result["store_status"] = summary.get("status")
            result["store_valid"] = summary.get("store_valid")
            result["persistence_loaded"] = summary.get("persistence_loaded")
            self._cached_result = result
            self._cache_key = key
        return deepcopy(self._cached_result)


_SCHEDULER_RUNTIME_ATTR = "_dummy_os_do_plan_scheduler_runtime"


def get_do_plan_scheduler_runtime(coordinator: Any) -> DummyOSPlanSchedulerRuntime:
    runtime = getattr(coordinator, _SCHEDULER_RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSPlanSchedulerRuntime):
        return runtime
    runtime = DummyOSPlanSchedulerRuntime(coordinator, get_do_plan_store_runtime(coordinator))
    setattr(coordinator, _SCHEDULER_RUNTIME_ATTR, runtime)
    return runtime


class _SchedulerEntityMixin:
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, runtime: DummyOSPlanSchedulerRuntime) -> None:
        self.runtime = runtime
        self.coordinator = runtime.coordinator
        self._remove_store_listener = None
        self._remove_coordinator_listener = None

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
        await self.runtime.store_runtime.async_ensure_loaded()
        self._remove_store_listener = self.runtime.store_runtime.add_listener(self._handle_update)
        self._remove_coordinator_listener = self.coordinator.async_add_listener(self._handle_update)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_store_listener is not None:
            self._remove_store_listener()
        if self._remove_coordinator_listener is not None:
            self._remove_coordinator_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        """Handle event-loop owned coordinator/store updates."""
        self.async_write_ha_state()


class DummyOSPlanSchedulerSensor(_SchedulerEntityMixin, SensorEntity):
    _attr_name = "DO Plan Scheduler"
    _attr_unique_id = "do_plan_scheduler"
    _attr_suggested_object_id = "do_plan_scheduler"
    _attr_icon = "mdi:calendar-clock"
    _unrecorded_attributes = frozenset({"slot_states"})

    @property
    def native_value(self) -> str:
        return str(self.runtime.result().get("scheduler_status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.result()


class DummyOSPlanSchedulerReadyBinarySensor(_SchedulerEntityMixin, BinarySensorEntity):
    _attr_name = "DO Plan Scheduler Ready"
    _attr_unique_id = "do_plan_scheduler_ready"
    _attr_suggested_object_id = "do_plan_scheduler_ready"
    _attr_icon = "mdi:calendar-check-outline"

    @property
    def is_on(self) -> bool:
        return self.runtime.result().get("scheduler_ready") is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self.runtime.result()
        return {
            "scheduler_status": result.get("scheduler_status"),
            "selected_slot_id": result.get("selected_slot_id"),
            "selected_plan_id": result.get("selected_plan_id"),
            "decision_signature": result.get("decision_signature"),
            "blockers": result.get("blockers", []),
            "shadow_only": True,
            "active_use_permitted": False,
            "physical_execution_authority": False,
            "operational_plan_store_write": False,
            "scheduler_invoked": False,
            "safety_chain_invoked": False,
            "service_calls_performed": False,
        }


def build_do_plan_scheduler_sensors(coordinator: Any) -> list[SensorEntity]:
    runtime = get_do_plan_scheduler_runtime(coordinator)
    return [DummyOSPlanSchedulerSensor(runtime)]


def build_do_plan_scheduler_binary_sensors(coordinator: Any) -> list[BinarySensorEntity]:
    runtime = get_do_plan_scheduler_runtime(coordinator)
    return [DummyOSPlanSchedulerReadyBinarySensor(runtime)]