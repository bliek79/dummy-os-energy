"""Home Assistant sensor adapter for observer-only DO Plan Preview."""

from __future__ import annotations

from typing import Any

from .do_plan_preview import build_do_plan_preview


def build_do_plan_preview_sensors(coordinator: Any) -> list[Any]:
    """Build Step-4 sensors after sensor.py has finished importing.

    The lazy import avoids a module cycle while reusing the already validated
    Step-1/2/3 sensor chain and its update listeners.
    """
    from .sensor import (
        DummyOSPlanReserveSOCSensor,
        _build_plan_input_from_snapshot,
        _build_reserve_from_snapshot,
    )

    class DummyOSPlanPreviewSensor(DummyOSPlanReserveSOCSensor):
        """Observer-only safety, solar-headroom and trade preview."""

        _attr_name = "DO Plan Preview"
        _attr_unique_id = "do_plan_preview"
        _attr_suggested_object_id = "do_plan_preview"
        _attr_icon = "mdi:clipboard-text-clock-outline"
        _unrecorded_attributes = frozenset(
            {"safety_charge_hours", "best_import_avoidance", "best_export_trade"}
        )

        CHARGE_EFFICIENCY_PERCENT = 92.0
        DISCHARGE_EFFICIENCY_PERCENT = 92.0
        MINIMUM_TRADE_MARGIN = 0.10
        MAX_CHARGE_POWER_W = 3200
        MAX_DISCHARGE_POWER_W = 3200

        def _calculate_result(self, snapshot: dict[str, Any]) -> dict[str, Any]:
            input_result = _build_plan_input_from_snapshot(snapshot)
            reserve_result = _build_reserve_from_snapshot(snapshot)
            result = build_do_plan_preview(
                input_result=input_result,
                reserve_result=reserve_result,
                now=snapshot["now"],
                charge_efficiency_percent=self.CHARGE_EFFICIENCY_PERCENT,
                discharge_efficiency_percent=self.DISCHARGE_EFFICIENCY_PERCENT,
                minimum_trade_margin=self.MINIMUM_TRADE_MARGIN,
                max_charge_power_w=self.MAX_CHARGE_POWER_W,
                max_discharge_power_w=self.MAX_DISCHARGE_POWER_W,
            )
            result["input_entity"] = "sensor.do_plan_input_72h"
            result["reserve_entity"] = "sensor.do_plan_reserve_soc"
            result["soc_source_entity"] = reserve_result.get("soc_source_entity")
            result["source_layer_status"] = reserve_result.get("source_layer_status")
            return result

    return [DummyOSPlanPreviewSensor(coordinator)]
