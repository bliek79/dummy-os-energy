"""Home Assistant adapter for the shadow-only manual planslot interface."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import ServiceCall, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import DOMAIN, NAME, VERSION
from .do_plan_manual_diagnostic import run_manual_lifecycle_diagnostic
from .do_plan_manual_interface import VALID_SLOT_OPTIONS, build_do_plan_manual_interface
from .do_plan_manual_lifecycle import (
    clear_manual_slot,
    edit_manual_draft,
    finalize_manual_draft,
    new_manual_draft,
    patch_manual_draft,
    validate_manual_draft,
)
from .do_plan_store import ORIGIN_MANUAL, SLOT_COUNT, STATUS_EMPTY
from .do_plan_store_sensor import get_do_plan_store_runtime

_RUNTIME_ATTR = "_dummy_os_do_plan_manual_interface_runtime"
SERVICE_DRAFT = "manual_plan_draft"
SERVICE_EDIT = "manual_plan_edit"
SERVICE_VALIDATE = "manual_plan_validate"
SERVICE_FINALIZE = "manual_plan_finalize"
SERVICE_CLEAR = "manual_plan_clear"
SERVICE_DIAGNOSTIC = "manual_plan_lifecycle_test"
CONTROL_STORE_VERSION = 1
CONTROL_FIELDS = (
    "action",
    "start_time",
    "power_w",
    "target_soc_percent",
    "max_runtime_minutes",
    "max_start_delay_minutes",
)
DEFAULT_CONTROLS: dict[str, Any] = {
    "action": None,
    "start_time": None,
    "power_w": 100.0,
    "target_soc_percent": 80.0,
    "max_runtime_minutes": 60.0,
    "max_start_delay_minutes": 10.0,
}


class DummyOSManualInterfaceRuntime:
    """Persistent per-slot dashboard controls backed by the existing manual lifecycle."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.entry_id = coordinator.entry.entry_id
        self.store_runtime = get_do_plan_store_runtime(coordinator)
        self.selected_slot = VALID_SLOT_OPTIONS[0]
        self.drafts: dict[int, dict[str, Any]] = {}
        self.controls: dict[int, dict[str, Any]] = {
            slot_id: deepcopy(DEFAULT_CONTROLS) for slot_id in range(1, SLOT_COUNT + 1)
        }
        self.last_result: dict[str, Any] | None = None
        self.last_diagnostic: dict[str, Any] | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._control_store: Store[dict[str, Any]] = Store(
            self.hass,
            CONTROL_STORE_VERSION,
            f"{DOMAIN}.{self.entry_id}.do_plan_manual_controls",
        )
        self._controls_loaded = False
        self._control_load_task = None

    @property
    def draft(self) -> dict[str, Any] | None:
        return self.drafts.get(self._slot_id())

    @draft.setter
    def draft(self, value: dict[str, Any] | None) -> None:
        slot_id = self._slot_id()
        if slot_id not in range(1, SLOT_COUNT + 1):
            return
        if value is None:
            self.drafts.pop(slot_id, None)
        else:
            self.drafts[slot_id] = deepcopy(value)

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_ensure_controls_loaded(self) -> None:
        if self._controls_loaded:
            return
        if self._control_load_task is None:
            self._control_load_task = self.hass.async_create_task(self._async_load_controls())
        await self._control_load_task

    async def _async_load_controls(self) -> None:
        raw = await self._control_store.async_load()
        if isinstance(raw, dict):
            raw_controls = raw.get("controls")
            if isinstance(raw_controls, dict):
                for slot_id in range(1, SLOT_COUNT + 1):
                    stored = raw_controls.get(str(slot_id))
                    if isinstance(stored, dict):
                        values = deepcopy(DEFAULT_CONTROLS)
                        for field in CONTROL_FIELDS:
                            if field in stored:
                                values[field] = stored[field]
                        self.controls[slot_id] = values
            raw_drafts = raw.get("drafts")
            if isinstance(raw_drafts, dict):
                for slot_id in range(1, SLOT_COUNT + 1):
                    stored = raw_drafts.get(str(slot_id))
                    if isinstance(stored, dict):
                        self.drafts[slot_id] = deepcopy(stored)
            selected = raw.get("selected_slot")
            if selected in VALID_SLOT_OPTIONS:
                self.selected_slot = selected
        self._controls_loaded = True
        self._notify()

    async def _async_save_controls(self) -> None:
        payload = {
            "schema_version": 1,
            "selected_slot": self.selected_slot,
            "controls": {str(slot_id): deepcopy(values) for slot_id, values in self.controls.items()},
            "drafts": {str(slot_id): deepcopy(draft) for slot_id, draft in self.drafts.items()},
        }
        await self._control_store.async_save(payload)

    def select(self, option: str) -> None:
        if option not in VALID_SLOT_OPTIONS:
            raise ValueError(f"Unsupported manual planslot: {option}")
        self.selected_slot = option
        self.last_result = {"status": "selection_changed", "blockers": []}
        if self._controls_loaded:
            self.hass.async_create_task(self._async_save_controls())
        self._notify()

    def _slot_id(self, data: dict[str, Any] | None = None) -> int:
        raw = (data or {}).get("slot_id")
        if raw is None:
            raw = self.selected_slot
        value = str(raw).strip().lower().replace("slot_", "").replace("slot ", "")
        try:
            return int(value)
        except ValueError:
            return 0

    @staticmethod
    def _changes(data: dict[str, Any]) -> dict[str, Any]:
        return {key: data[key] for key in CONTROL_FIELDS if key in data}

    def control_value(self, slot_id: int, field: str) -> Any:
        return self.controls.get(slot_id, DEFAULT_CONTROLS).get(field)

    def _sync_controls_from_draft(self, slot_id: int, draft: dict[str, Any]) -> None:
        values = self.controls.setdefault(slot_id, deepcopy(DEFAULT_CONTROLS))
        for field in CONTROL_FIELDS:
            if field in draft:
                values[field] = draft.get(field)

    async def _ensure_draft_for_slot(self, slot_id: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        await self.store_runtime.async_ensure_loaded()
        if slot_id in self.drafts:
            return self.drafts[slot_id], {"status": "draft", "blockers": []}
        current = self.store_runtime.slot(slot_id)
        now = datetime.now(timezone.utc)
        if current.get("status") == STATUS_EMPTY:
            draft, result = new_manual_draft(deepcopy(self.store_runtime.snapshot), slot_id, now)
        elif current.get("origin") == ORIGIN_MANUAL:
            draft, result = edit_manual_draft(deepcopy(self.store_runtime.snapshot), slot_id, now)
        else:
            return None, {"status": "blocked", "blockers": ["selected_slot_not_manual_or_empty"]}
        if draft:
            draft = patch_manual_draft(draft, deepcopy(self.controls[slot_id]), now)
            self.drafts[slot_id] = draft
        return draft or None, result

    async def async_set_control(self, slot_id: int, field: str, value: Any) -> dict[str, Any]:
        if slot_id not in range(1, SLOT_COUNT + 1):
            raise ValueError(f"Unsupported manual planslot: {slot_id}")
        if field not in CONTROL_FIELDS:
            raise ValueError(f"Unsupported manual control field: {field}")
        await self.async_ensure_controls_loaded()
        self.selected_slot = f"slot_{slot_id}"
        self.controls[slot_id][field] = value
        draft, result = await self._ensure_draft_for_slot(slot_id)
        if draft is not None:
            self.drafts[slot_id] = patch_manual_draft(
                draft,
                {field: value},
                datetime.now(timezone.utc),
            )
            result = {"status": "draft_updated", "blockers": []}
        self.last_result = result
        await self._async_save_controls()
        self._notify()
        return result

    async def async_draft(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        draft, result = new_manual_draft(
            deepcopy(self.store_runtime.snapshot), slot_id, datetime.now(timezone.utc)
        )
        if draft:
            changes = self._changes(data)
            self.controls[slot_id].update(changes)
            draft = patch_manual_draft(draft, deepcopy(self.controls[slot_id]), datetime.now(timezone.utc))
            self.drafts[slot_id] = draft
            self.selected_slot = f"slot_{slot_id}"
            self._sync_controls_from_draft(slot_id, draft)
            await self._async_save_controls()
        self.last_result = result
        self._notify()
        return result

    async def async_edit(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        draft, result = edit_manual_draft(
            deepcopy(self.store_runtime.snapshot), slot_id, datetime.now(timezone.utc)
        )
        if draft:
            self._sync_controls_from_draft(slot_id, draft)
            changes = self._changes(data)
            self.controls[slot_id].update(changes)
            draft = patch_manual_draft(draft, changes, datetime.now(timezone.utc)) if changes else draft
            self.drafts[slot_id] = draft
            self.selected_slot = f"slot_{slot_id}"
            await self._async_save_controls()
        self.last_result = result
        self._notify()
        return result

    async def async_validate(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        self.selected_slot = f"slot_{slot_id}" if slot_id in range(1, SLOT_COUNT + 1) else self.selected_slot
        draft, draft_result = await self._ensure_draft_for_slot(slot_id)
        if draft is None:
            result = {"status": "invalid", "valid": False, "blockers": draft_result.get("blockers", ["draft_missing"])}
        else:
            changes = self._changes(data)
            if changes:
                self.controls[slot_id].update(changes)
                draft = patch_manual_draft(draft, changes, datetime.now(timezone.utc))
                self.drafts[slot_id] = draft
            result = validate_manual_draft(
                draft, deepcopy(self.store_runtime.snapshot), datetime.now(timezone.utc)
            )
            draft["validation_status"] = result["status"]
            draft["validation_blockers"] = result["blockers"]
            draft["draft_signature"] = result.get("draft_signature")
            if result.get("normalized"):
                draft["planned_end_time"] = result["normalized"].get("planned_end_time")
                draft["planned_energy_kwh"] = result["normalized"].get("planned_energy_kwh")
            self.drafts[slot_id] = draft
            await self._async_save_controls()
        self.last_result = result
        self._notify()
        return result

    async def async_finalize(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        self.selected_slot = f"slot_{slot_id}" if slot_id in range(1, SLOT_COUNT + 1) else self.selected_slot
        draft, draft_result = await self._ensure_draft_for_slot(slot_id)
        if draft is None:
            result = {"changed": False, "status": "blocked", "blockers": draft_result.get("blockers", ["draft_missing"])}
        else:
            changes = self._changes(data)
            if changes:
                self.controls[slot_id].update(changes)
                draft = patch_manual_draft(draft, changes, datetime.now(timezone.utc))
                self.drafts[slot_id] = draft
            async with self.store_runtime.transaction_lock:
                updated, result = finalize_manual_draft(
                    deepcopy(self.store_runtime.snapshot), draft, datetime.now(timezone.utc)
                )
                if result.get("changed"):
                    saved = await self.store_runtime.async_save_snapshot(updated)
                    if not saved:
                        result = {
                            "changed": False,
                            "status": "blocked",
                            "blockers": ["persistence_write_failed"],
                            "rollback_preserved": True,
                        }
                    else:
                        result["persistence_saved"] = True
                        self.drafts.pop(slot_id, None)
                        await self._async_save_controls()
        self.last_result = result
        self._notify()
        return result

    async def async_clear(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        async with self.store_runtime.transaction_lock:
            current = self.store_runtime.slot(slot_id)
            updated, result = clear_manual_slot(
                deepcopy(self.store_runtime.snapshot),
                slot_id,
                datetime.now(timezone.utc),
                expected_plan_id=data.get("expected_plan_id") or current.get("plan_id"),
                expected_updated_at=data.get("expected_updated_at") or current.get("updated_at"),
            )
            if result.get("changed"):
                saved = await self.store_runtime.async_save_snapshot(updated)
                if not saved:
                    result = {
                        "changed": False,
                        "status": "blocked",
                        "blockers": ["persistence_write_failed"],
                        "rollback_preserved": True,
                    }
                else:
                    result["persistence_saved"] = True
                    self.drafts.pop(slot_id, None)
                    self.controls[slot_id] = deepcopy(DEFAULT_CONTROLS)
                    await self._async_save_controls()
        self.last_result = result
        self._notify()
        return result

    async def async_diagnostic(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_controls_loaded()
        await self.store_runtime.async_ensure_loaded()
        slot_id = self._slot_id(data)
        now = datetime.now(timezone.utc)
        kwargs = {
            key: data[key]
            for key in (
                "start_time",
                "action",
                "power_w",
                "edited_power_w",
                "target_soc_percent",
                "max_runtime_minutes",
                "max_start_delay_minutes",
            )
            if key in data
        }
        async with self.store_runtime.transaction_lock:
            updated, result = run_manual_lifecycle_diagnostic(
                deepcopy(self.store_runtime.snapshot), slot_id=slot_id, now=now, **kwargs
            )
            if result.get("passed"):
                saved = await self.store_runtime.async_save_snapshot(updated)
                if not saved:
                    result = {
                        **result,
                        "status": "blocked",
                        "passed": False,
                        "blockers": ["persistence_write_failed"],
                        "rollback_preserved": True,
                    }
                else:
                    result["persistence_saved"] = True
        self.selected_slot = f"slot_{slot_id}"
        self.drafts.pop(slot_id, None)
        self.last_diagnostic = result
        self.last_result = {
            "status": "diagnostic_" + str(result.get("status")),
            "blockers": result.get("blockers", []),
        }
        await self._async_save_controls()
        self._notify()
        return result

    def attributes(self) -> dict[str, Any]:
        return {
            "selected_slot": self.selected_slot,
            "draft": deepcopy(self.draft),
            "drafts": deepcopy(self.drafts),
            "controls": deepcopy(self.controls),
            "control_persistence_loaded": self._controls_loaded,
            "last_manual_operation": deepcopy(self.last_result),
            "last_manual_diagnostic": deepcopy(self.last_diagnostic),
            "manual_interface_write": True,
            "shadow_store_write": True,
            "operational_plan_store_write": False,
            "scheduler_invoked": False,
            "safety_chain_invoked": False,
            "external_service_calls_performed": False,
            "physical_execution_authority": False,
        }


def get_do_plan_manual_interface_runtime(coordinator: Any) -> DummyOSManualInterfaceRuntime:
    runtime = getattr(coordinator, _RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSManualInterfaceRuntime):
        return runtime
    runtime = DummyOSManualInterfaceRuntime(coordinator)
    setattr(coordinator, _RUNTIME_ATTR, runtime)
    return runtime


def register_manual_plan_services(hass: Any, runtime: DummyOSManualInterfaceRuntime) -> None:
    handlers = {
        SERVICE_DRAFT: runtime.async_draft,
        SERVICE_EDIT: runtime.async_edit,
        SERVICE_VALIDATE: runtime.async_validate,
        SERVICE_FINALIZE: runtime.async_finalize,
        SERVICE_CLEAR: runtime.async_clear,
        SERVICE_DIAGNOSTIC: runtime.async_diagnostic,
    }
    for service, handler in handlers.items():
        if hass.services.has_service(DOMAIN, service):
            continue

        async def handle(call: ServiceCall, _handler=handler) -> None:
            await _handler(dict(call.data))

        hass.services.async_register(DOMAIN, service, handle)


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
        result = build_do_plan_manual_interface(
            store_snapshot=deepcopy(self.store_runtime.snapshot),
            store_summary=self.store_runtime.summary(),
            selected_slot=self.manual_runtime.selected_slot,
            now=datetime.now(timezone.utc),
        )
        result.update(self.manual_runtime.attributes())
        return result

    @property
    def native_value(self) -> str:
        return str(self._result().get("status", "blocked"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._result()

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
        self._remove_store_listener = self.store_runtime.add_listener(self._handle_update)
        self._remove_manual_listener = self.manual_runtime.add_listener(self._handle_update)
        await self.store_runtime.async_ensure_loaded()
        await self.manual_runtime.async_ensure_controls_loaded()
        register_manual_plan_services(self.hass, self.manual_runtime)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_store_listener is not None:
            self._remove_store_listener()
        if self._remove_manual_listener is not None:
            self._remove_manual_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


def build_do_plan_manual_interface_sensors(coordinator: Any) -> list[SensorEntity]:
    return [DummyOSManualPlanInterfaceSensor(coordinator)]
