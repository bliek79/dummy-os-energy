"""Home Assistant adapters for Step 5 grid support and Step 6B shadow store bridge."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from typing import Any
from .do_plan_grid_support import build_do_plan_grid_support
from .do_plan_store_bridge import build_do_plan_store_bridge
from .do_plan_store_sensor import build_do_plan_store_sensors, get_do_plan_store_runtime


def _stable_material(value: Any) -> str:
    """Return a compact stable representation for planner-refresh fingerprinting."""
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{_stable_material(value[k])}" for k in sorted(value)) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_stable_material(item) for item in value) + "]"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return repr(value)


def build_plan_store_bridge_refresh_key(snapshot: dict[str, Any]) -> str:
    """Fingerprint only material planner inputs plus the native 15-minute bucket."""
    now = snapshot.get("now")
    if isinstance(now, datetime):
        now_utc = now.astimezone(timezone.utc)
        quarter = now_utc.replace(minute=(now_utc.minute // 15) * 15, second=0, microsecond=0).isoformat()
    else:
        quarter = repr(now)
    material = {
        "quarter": quarter,
        "profile": snapshot.get("profile"),
        "source_available": snapshot.get("source_available"),
        "soc_percent": snapshot.get("soc_percent"),
        "solar_status": snapshot.get("solar_status"),
        "prices_status": snapshot.get("prices_status"),
        "prices_freshness": snapshot.get("prices_freshness"),
        "records": snapshot.get("records"),
        "evaluations": snapshot.get("evaluations"),
        "horizon_daily_stats": snapshot.get("horizon_daily_stats"),
        "solar_points": snapshot.get("solar_points"),
        "price_points": snapshot.get("price_points"),
    }
    return hashlib.sha256(_stable_material(material).encode("utf-8")).hexdigest()


def build_do_plan_grid_support_sensors(coordinator: Any) -> list[Any]:
    from .do_plan_72h import build_do_plan_72h
    from .do_plan_preview import build_do_plan_preview
    from .sensor import DummyOSPlanReserveSOCSensor, _build_plan_input_from_snapshot, _build_energy_need_from_snapshot, _build_reserve_from_snapshot

    class DummyOSPlanGridSupportSensor(DummyOSPlanReserveSOCSensor):
        _attr_name = "DO Plan Grid Support"
        _attr_unique_id = "do_plan_grid_support"
        _attr_suggested_object_id = "do_plan_grid_support"
        _attr_icon = "mdi:transmission-tower-import"
        _unrecorded_attributes = frozenset({"selected_charge_slots"})
        GRID_CHARGE_TRIGGER_KWH = 0.25
        def _calculate_result(self, snapshot: dict[str, Any]) -> dict[str, Any]:
            input_result = _build_plan_input_from_snapshot(snapshot)
            need = _build_energy_need_from_snapshot(snapshot)
            result = build_do_plan_grid_support(input_result=input_result, energy_need_result=need, trigger_kwh=self.GRID_CHARGE_TRIGGER_KWH)
            result["input_entity"] = "sensor.do_plan_input_72h"
            result["energy_need_entity"] = "sensor.do_plan_energy_need"
            result["soc_source_entity"] = need.get("soc_source_entity")
            result["source_layer_status"] = need.get("source_layer_status")
            return result
        def _initial_result(self) -> dict[str, Any]:
            return {"status":"initializing","valid":False,"selected_charge_slots":[],"shadow_only":True,"active_use_permitted":False,"physical_execution_authority":False,"plan_store_write":False,"scheduler_invoked":False,"safety_chain_invoked":False,"service_calls_performed":False,"blockers":["planner_calculation_pending"]}
        @property
        def native_value(self) -> str:
            return str(self._result().get("status","initializing"))
        @property
        def extra_state_attributes(self) -> dict[str, Any]:
            return dict(self._result())

    runtime = get_do_plan_store_runtime(coordinator)

    class DummyOSPlanStoreBridgeSensor(DummyOSPlanReserveSOCSensor):
        _attr_name = "DO Plan Store Bridge"
        _attr_unique_id = "do_plan_store_bridge"
        _attr_suggested_object_id = "do_plan_store_bridge"
        _attr_icon = "mdi:database-arrow-down-outline"
        _unrecorded_attributes = frozenset({"candidates", "suppressed_candidates"})

        def __init__(self, coordinator: Any) -> None:
            super().__init__(coordinator)
            self._last_material_key: str | None = None
            self._skipped_refreshes = 0

        def _calculate_result(self, snapshot: dict[str, Any]) -> dict[str, Any]:
            input_result = _build_plan_input_from_snapshot(snapshot)
            reserve_result = _build_reserve_from_snapshot(snapshot)
            need = _build_energy_need_from_snapshot(snapshot)
            preview_result = build_do_plan_preview(input_result=input_result,reserve_result=reserve_result,now=snapshot["now"],charge_efficiency_percent=92.0,discharge_efficiency_percent=92.0,minimum_trade_margin=0.10,max_charge_power_w=3200,max_discharge_power_w=3200)
            plan72_result = build_do_plan_72h(input_result=input_result,reserve_result=reserve_result,preview_result=preview_result)
            grid_support_result = build_do_plan_grid_support(input_result=input_result,energy_need_result=need,trigger_kwh=0.25)
            result = build_do_plan_store_bridge(plan72_result=plan72_result,grid_support_result=grid_support_result,now=snapshot["now"])
            result["plan72_entity"] = "sensor.do_plan_72h"
            result["grid_support_entity"] = "sensor.do_plan_grid_support"
            return result

        async def _async_refresh_result(self) -> None:
            while True:
                self._refresh_pending = False
                snapshot = self._snapshot()
                material_key = build_plan_store_bridge_refresh_key(snapshot)
                if self._cached_result is not None and material_key == self._last_material_key:
                    self._skipped_refreshes += 1
                    if not self._refresh_pending:
                        return
                    continue
                result = await self.hass.async_add_executor_job(self._calculate_result, snapshot)
                await runtime.async_ensure_loaded()
                candidates = result.get("candidates") if result.get("status") == "ready" else []
                if not isinstance(candidates, list): candidates = []
                apply_result = await runtime.async_apply_bridge_candidates(candidates, snapshot["now"])
                result["store_apply_status"] = apply_result.get("status")
                result["store_changed"] = apply_result.get("changed")
                result["store_persistence_saved"] = apply_result.get("persistence_saved")
                result["store_sync"] = apply_result.get("sync")
                result["refresh_key"] = material_key
                result["skipped_refreshes"] = self._skipped_refreshes
                if apply_result.get("status") != "ready":
                    result["status"] = "blocked"; result["valid"] = False
                    result["blockers"] = sorted(set([*(result.get("blockers") or []), *(apply_result.get("blockers") or [])]))
                self._last_material_key = material_key
                self._cached_result = result
                self.async_write_ha_state()
                if not self._refresh_pending: return

        def _initial_result(self) -> dict[str, Any]:
            return {"status":"initializing","valid":False,"candidate_count":0,"candidates":[],"suppressed_candidates":[],"shadow_only":True,"shadow_store_write":True,"operational_plan_store_write":False,"active_use_permitted":False,"physical_execution_authority":False,"scheduler_invoked":False,"safety_chain_invoked":False,"service_calls_performed":False,"skipped_refreshes":0,"blockers":["planner_calculation_pending"]}
        @property
        def native_value(self) -> str:
            return str(self._result().get("status", "initializing"))
        @property
        def extra_state_attributes(self) -> dict[str, Any]:
            result = dict(self._result())
            result["skipped_refreshes"] = self._skipped_refreshes
            return result

    return [DummyOSPlanGridSupportSensor(coordinator),DummyOSPlanStoreBridgeSensor(coordinator),*build_do_plan_store_sensors(coordinator,runtime)]
