"""Home Assistant adapter for observer-only Planner Step 6 shadow Plan Store."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN, NAME, VERSION
from .do_plan_store import (
    SLOT_COUNT,
    cleanup_automatic_slots,
    new_store_snapshot,
    summarize_store,
    sync_automatic_candidates,
    validate_store_snapshot,
)
from .do_plan_store_reconcile import prune_obsolete_automatic_pending

STORE_VERSION = 1
_RUNTIME_ATTR = "_dummy_os_do_plan_store_runtime"


class DummyOSShadowPlanStoreRuntime:
    """Shared persistent runtime for the isolated Step-6 shadow store."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.entry_id = coordinator.entry.entry_id
        self._store: Store[dict[str, Any]] = Store(
            self.hass,
            STORE_VERSION,
            f"{DOMAIN}.{self.entry_id}.do_plan_store_shadow",
        )
        self.snapshot: dict[str, Any] = new_store_snapshot()
        self.loaded = False
        self.persistence_error: str | None = None
        self._load_task = None
        self._listeners: set[Callable[[], None]] = set()
        self.last_bridge_result: dict[str, Any] | None = None

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(callback)

        def remove() -> None:
            self._listeners.discard(callback)

        return remove

    def _notify(self) -> None:
        for callback in tuple(self._listeners):
            callback()

    async def async_ensure_loaded(self) -> None:
        if self.loaded:
            return
        if self._load_task is None:
            self._load_task = self.hass.async_create_task(self._async_load())
        await self._load_task

    async def _async_load(self) -> None:
        raw = await self._store.async_load()
        self.snapshot = (
            new_store_snapshot()
            if raw is None
            else (deepcopy(raw) if isinstance(raw, dict) else raw)
        )
        self.loaded = True
        self._notify()

    async def async_save_snapshot(self, snapshot: dict[str, Any]) -> bool:
        valid, _ = validate_store_snapshot(snapshot)
        if not valid:
            return False
        try:
            await self._store.async_save(deepcopy(snapshot))
        except Exception as err:
            self.persistence_error = type(err).__name__
            self._notify()
            return False
        self.snapshot = deepcopy(snapshot)
        self.persistence_error = None
        self.loaded = True
        self._notify()
        return True

    async def async_apply_bridge_candidates(
        self,
        candidates: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        """Persist one atomic isolated shadow-store bridge refresh."""
        await self.async_ensure_loaded()
        valid, blockers = validate_store_snapshot(self.snapshot)
        if not valid:
            result = {"status": "blocked", "changed": False, "blockers": blockers}
            self.last_bridge_result = result
            self._notify()
            return result

        cleaned, cleanup = cleanup_automatic_slots(self.snapshot, now)
        pruned, reconcile = prune_obsolete_automatic_pending(cleaned, candidates, now)
        updated, sync = sync_automatic_candidates(pruned, candidates, now)
        changed = bool(
            cleanup.get("changed") or reconcile.get("changed") or sync.get("changed")
        )
        saved = True
        if changed:
            saved = await self.async_save_snapshot(updated)
        result = {
            "status": "ready" if saved else "blocked",
            "changed": changed,
            "persistence_saved": saved,
            "cleanup": cleanup,
            "sync": sync,
            "reconcile": reconcile,
            "blockers": [] if saved else ["persistence_write_failed"],
            "operational_plan_store_write": False,
            "scheduler_invoked": False,
            "safety_chain_invoked": False,
            "service_calls_performed": False,
            "physical_execution_authority": False,
        }
        self.last_bridge_result = result
        self._notify()
        return result

    def summary(self) -> dict[str, Any]:
        result = summarize_store(
            self.snapshot,
            loaded=self.loaded,
            persistence_error=self.persistence_error,
        )
        if self.last_bridge_result is not None:
            result["last_bridge_status"] = self.last_bridge_result.get("status")
            result["last_bridge_changed"] = self.last_bridge_result.get("changed")
        return result

    def slot(self, slot_id: int) -> dict[str, Any]:
        slots = self.snapshot.get("slots", []) if isinstance(self.snapshot, dict) else []
        if (
            isinstance(slots, list)
            and 1 <= slot_id <= len(slots)
            and isinstance(slots[slot_id - 1], dict)
        ):
            return deepcopy(slots[slot_id - 1])
        return {
            "slot_id": slot_id,
            "status": "blocked",
            "blockers": ["slot_structure_invalid"],
        }


def get_do_plan_store_runtime(coordinator: Any) -> DummyOSShadowPlanStoreRuntime:
    """Return the single Plan Store runtime shared by all HA platforms."""
    runtime = getattr(coordinator, _RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSShadowPlanStoreRuntime):
        return runtime
    runtime = DummyOSShadowPlanStoreRuntime(coordinator)
    setattr(coordinator, _RUNTIME_ATTR, runtime)
    return runtime


class DummyOSPlanStoreBaseSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, runtime: DummyOSShadowPlanStoreRuntime) -> None:
        self.runtime = runtime
        self._remove_listener = None

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
        self._remove_listener = self.runtime.add_listener(self.async_write_ha_state)
        await self.runtime.async_ensure_loaded()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()


class DummyOSPlanStoreSensor(DummyOSPlanStoreBaseSensor):
    _attr_name = "DO Plan Store"
    _attr_unique_id = "do_plan_store"
    _attr_suggested_object_id = "do_plan_store"
    _attr_icon = "mdi:database-clock-outline"

    @property
    def native_value(self) -> str:
        return str(self.runtime.summary().get("status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.summary()


class DummyOSPlanStoreSlotSensor(DummyOSPlanStoreBaseSensor):
    def __init__(self, runtime: DummyOSShadowPlanStoreRuntime, slot_id: int) -> None:
        super().__init__(runtime)
        self.slot_id = slot_id
        self._attr_name = f"DO Plan Store Slot {slot_id}"
        self._attr_unique_id = f"do_plan_store_slot_{slot_id}"
        self._attr_suggested_object_id = f"do_plan_store_slot_{slot_id}"
        self._attr_icon = f"mdi:numeric-{slot_id}-circle-outline"

    @property
    def native_value(self) -> str:
        return str(self.runtime.slot(self.slot_id).get("status", "blocked"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slot = self.runtime.slot(self.slot_id)
        slot.update(
            {
                "shadow_only": True,
                "operational_plan_store_write": False,
                "scheduler_invoked": False,
                "safety_chain_invoked": False,
                "service_calls_performed": False,
                "physical_execution_authority": False,
            }
        )
        return slot


def build_do_plan_store_sensors(
    coordinator: Any,
    runtime: DummyOSShadowPlanStoreRuntime | None = None,
) -> list[SensorEntity]:
    runtime = runtime or get_do_plan_store_runtime(coordinator)
    return [
        DummyOSPlanStoreSensor(runtime),
        *[
            DummyOSPlanStoreSlotSensor(runtime, slot)
            for slot in range(1, SLOT_COUNT + 1)
        ],
    ]
