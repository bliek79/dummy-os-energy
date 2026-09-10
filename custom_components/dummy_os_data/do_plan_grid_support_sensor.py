"""Home Assistant sensor adapter for observer-only Step 5 grid support."""
from __future__ import annotations
from typing import Any
from .do_plan_grid_support import build_do_plan_grid_support
from .do_plan_store_sensor import build_do_plan_store_sensors

def build_do_plan_grid_support_sensors(coordinator: Any) -> list[Any]:
    from .sensor import DummyOSPlanReserveSOCSensor, _build_plan_input_from_snapshot, _build_energy_need_from_snapshot
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
    # Step 6B registers its isolated store sensors through the existing planner
    # sensor bundle. This avoids unrelated edits to the large central registry.
    return [DummyOSPlanGridSupportSensor(coordinator), *build_do_plan_store_sensors(coordinator)]
