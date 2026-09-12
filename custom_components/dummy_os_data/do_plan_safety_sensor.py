"""Home Assistant shadow adapter for Safety and Prestart."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, NAME, VERSION
from .do_plan_operating_mode import apply_prestart_mode_gate, apply_safety_mode_gate
from .do_plan_safety import build_do_plan_prestart, build_do_plan_safety
from .do_plan_scheduler_sensor import DummyOSPlanSchedulerRuntime, get_do_plan_scheduler_runtime
from .do_plan_soc_contract_sensor import RAW_SOC_ENTITY, get_do_plan_soc_contract_runtime

SOC_ENTITY = "sensor.do_plan_soc_contract"
RESERVE_ENTITY = "sensor.dummy_os_energy_do_plan_reserve_soc"


class DummyOSPlanSafetyRuntime:
    """Cached observer-only Safety/Prestart view; never writes the Plan Store."""

    def __init__(self, coordinator: Any, scheduler_runtime: DummyOSPlanSchedulerRuntime) -> None:
        self.coordinator = coordinator
        self.scheduler_runtime = scheduler_runtime
        self.store_runtime = scheduler_runtime.store_runtime
        self.mode_runtime = scheduler_runtime.mode_runtime
        self._cached_safety: dict[str, Any] | None = None
        self._cached_prestart: dict[str, Any] | None = None
        self._cache_key: tuple[Any, ...] | None = None

    def _soc_contract(self) -> dict[str, Any]:
        return get_do_plan_soc_contract_runtime(self.coordinator).result()

    def _soc_percent(self) -> float | None:
        contract = self._soc_contract()
        if contract.get("status") != "ready" or contract.get("valid") is not True:
            return None
        try:
            value = float(contract.get("soc_percent"))
        except (TypeError, ValueError):
            return None
        return value if 0.0 <= value <= 100.0 else None

    def _reserve_result(self) -> dict[str, Any]:
        state = self.coordinator.hass.states.get(RESERVE_ENTITY)
        if state is None or state.state in {"unknown", "unavailable", "none", "None", ""}:
            return {"status": "unavailable", "valid": False, "reserve_soc_target_percent": None}
        result = dict(state.attributes)
        result["status"] = state.state
        return result

    def results(self, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        scheduler = self.scheduler_runtime.result(current)
        snapshot = deepcopy(self.store_runtime.snapshot)
        soc = self._soc_percent()
        reserve = self._reserve_result()
        mode = self.mode_runtime.result()
        key = (
            current.astimezone(timezone.utc).isoformat(),
            repr(snapshot),
            repr(scheduler),
            soc,
            repr(reserve),
            mode.get("operating_mode_signature"),
            mode.get("status"),
        )
        if key != self._cache_key or self._cached_safety is None or self._cached_prestart is None:
            safety = build_do_plan_safety(
                scheduler_result=scheduler,
                store_snapshot=snapshot,
                reserve_result=reserve,
                soc_percent=soc,
                now=current,
            )
            safety = apply_safety_mode_gate(safety, mode)
            prestart = build_do_plan_prestart(
                scheduler_result=scheduler,
                safety_result=safety,
                store_snapshot=snapshot,
                now=current,
            )
            prestart = apply_prestart_mode_gate(prestart, scheduler, safety, mode)
            safety["reserve_status"] = reserve.get("status")
            safety["reserve_valid"] = reserve.get("valid")
            safety["reserve_source_entity"] = RESERVE_ENTITY
            contract = self._soc_contract()
            safety["soc_source_entity"] = "runtime:do_plan_soc_contract_v1"
            safety["soc_contract_entity"] = SOC_ENTITY
            safety["soc_contract_status"] = contract.get("status")
            safety["soc_contract_valid"] = contract.get("valid")
            safety["soc_raw_source_entity"] = contract.get("source_entity")
            self._cached_safety = safety
            self._cached_prestart = prestart
            self._cache_key = key
        return deepcopy(self._cached_safety), deepcopy(self._cached_prestart)


_SAFETY_RUNTIME_ATTR = "_dummy_os_do_plan_safety_runtime"


def get_do_plan_safety_runtime(coordinator: Any) -> DummyOSPlanSafetyRuntime:
    runtime = getattr(coordinator, _SAFETY_RUNTIME_ATTR, None)
    if isinstance(runtime, DummyOSPlanSafetyRuntime):
        return runtime
    runtime = DummyOSPlanSafetyRuntime(coordinator, get_do_plan_scheduler_runtime(coordinator))
    setattr(coordinator, _SAFETY_RUNTIME_ATTR, runtime)
    return runtime


class _SafetyEntityMixin:
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, runtime: DummyOSPlanSafetyRuntime) -> None:
        self.runtime = runtime
        self.coordinator = runtime.coordinator
        self._remove_store_listener = None
        self._remove_coordinator_listener = None
        self._remove_source_listener = None
        self._remove_mode_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Energy Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.runtime.store_runtime.async_ensure_loaded()
        await self.runtime.mode_runtime.async_ensure_loaded()
        self._remove_store_listener = self.runtime.store_runtime.add_listener(self._handle_update)
        self._remove_coordinator_listener = self.coordinator.async_add_listener(self._handle_update)
        self._remove_mode_listener = self.runtime.mode_runtime.add_listener(self._handle_update)
        self._remove_source_listener = async_track_state_change_event(
            self.coordinator.hass,
            [RAW_SOC_ENTITY, RESERVE_ENTITY],
            self._handle_source_update,
        )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        for remove in (
            self._remove_store_listener,
            self._remove_coordinator_listener,
            self._remove_source_listener,
            self._remove_mode_listener,
        ):
            if remove is not None:
                remove()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        """Handle event-loop owned coordinator/store/mode updates."""
        self.async_write_ha_state()

    @callback
    def _handle_source_update(self, _event) -> None:
        """Handle HA state-change events on the event loop, never in executor."""
        self.async_write_ha_state()


class DummyOSPlanSafetySensor(_SafetyEntityMixin, SensorEntity):
    _attr_name = "DO Plan Safety"
    _attr_unique_id = "do_plan_safety"
    _attr_suggested_object_id = "do_plan_safety"
    _attr_icon = "mdi:shield-check-outline"

    @property
    def native_value(self) -> str:
        return str(self.runtime.results()[0].get("safety_status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.results()[0]


class DummyOSPlanPrestartSensor(_SafetyEntityMixin, SensorEntity):
    _attr_name = "DO Plan Prestart"
    _attr_unique_id = "do_plan_prestart"
    _attr_suggested_object_id = "do_plan_prestart"
    _attr_icon = "mdi:shield-sync-outline"

    @property
    def native_value(self) -> str:
        return str(self.runtime.results()[1].get("prestart_status", "initializing"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.results()[1]


def build_do_plan_safety_sensors(coordinator: Any) -> list[SensorEntity]:
    runtime = get_do_plan_safety_runtime(coordinator)
    return [DummyOSPlanSafetySensor(runtime), DummyOSPlanPrestartSensor(runtime)]
