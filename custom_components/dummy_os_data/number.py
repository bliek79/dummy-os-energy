"""Number controls for the three manual Dummy OS Energy plan slots."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, NAME, VERSION
from .do_plan_manual_interface_sensor import get_do_plan_manual_interface_runtime
from .do_plan_store import SLOT_COUNT


@dataclass(frozen=True)
class ManualNumberDefinition:
    field: str
    label: str
    minimum: float
    maximum: float
    step: float
    unit: str | None


DEFINITIONS = (
    ManualNumberDefinition("power_w", "Power", 100.0, 3200.0, 100.0, UnitOfPower.WATT),
    ManualNumberDefinition("target_soc_percent", "Target SOC", 5.0, 100.0, 1.0, PERCENTAGE),
    ManualNumberDefinition("max_start_delay_minutes", "Maximum Start Delay", 0.0, 60.0, 1.0, UnitOfTime.MINUTES),
    ManualNumberDefinition("max_runtime_minutes", "Maximum Runtime", 15.0, 1440.0, 15.0, UnitOfTime.MINUTES),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    runtime = get_do_plan_manual_interface_runtime(coordinator)
    async_add_entities(
        DummyOSManualPlanNumber(runtime, slot_id, definition)
        for slot_id in range(1, SLOT_COUNT + 1)
        for definition in DEFINITIONS
    )


class DummyOSManualPlanNumber(NumberEntity):
    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime, slot_id: int, definition: ManualNumberDefinition) -> None:
        self.runtime = runtime
        self.slot_id = slot_id
        self.definition = definition
        self._remove_listener = None
        suffix = definition.field
        self._attr_name = f"DO Plan {slot_id} {definition.label}"
        self._attr_unique_id = f"do_plan_{slot_id}_{suffix}"
        self._attr_suggested_object_id = f"do_plan_{slot_id}_{suffix}"
        self._attr_native_min_value = definition.minimum
        self._attr_native_max_value = definition.maximum
        self._attr_native_step = definition.step
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "main")},
            name=NAME,
            manufacturer="Dummy OS",
            model="Energy Platform",
            sw_version=VERSION,
        )

    @property
    def native_value(self) -> float:
        value = self.runtime.control_value(self.slot_id, self.definition.field)
        return float(value if value is not None else self.native_min_value)

    async def async_set_native_value(self, value: float) -> None:
        value = max(self.native_min_value, min(self.native_max_value, float(value)))
        steps = round((value - self.native_min_value) / self.native_step)
        value = self.native_min_value + steps * self.native_step
        await self.runtime.async_set_control(self.slot_id, self.definition.field, value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.runtime.add_listener(self._handle_update)
        await self.runtime.async_ensure_controls_loaded()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
