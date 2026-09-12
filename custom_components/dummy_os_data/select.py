"""Select entities for Dummy OS Forecast."""
from __future__ import annotations
from typing import Any
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .const import DOMAIN, NAME, PROFILE_CONTRACT_VERSION, PROFILE_LEARNING_OPTIONS, PROFILE_OPTIONS, VERSION
from .coordinator import DummyOSHomeDataCoordinator
from .do_plan_manual_interface import VALID_SLOT_OPTIONS
from .do_plan_manual_interface_sensor import get_do_plan_manual_interface_runtime
from .do_plan_operating_mode import OPERATING_MODE_OPTIONS
from .do_plan_operating_mode_sensor import get_do_plan_operating_mode_runtime

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator: DummyOSHomeDataCoordinator = entry.runtime_data
    async_add_entities([DummyOSEnergyProfileSelect(coordinator), DummyOSManualPlanSlotSelect(coordinator), DummyOSPlanOperatingModeSelect(coordinator)])

class DummyOSEnergyProfileSelect(SelectEntity):
    """Select the active Energy Forecast historical profile."""
    _attr_name = "DO Energy Profile"; _attr_unique_id = "do_energy_profile"; _attr_suggested_object_id = "do_energy_profile"
    _attr_options = PROFILE_OPTIONS; _attr_icon = "mdi:home-account"; _attr_should_poll = False; _attr_has_entity_name = False
    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        self.coordinator = coordinator; self._remove_listener = None
    @property
    def current_option(self) -> str: return self.coordinator.profile
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        learning_enabled = self.coordinator.profile in PROFILE_LEARNING_OPTIONS
        return {"profile_contract_version": PROFILE_CONTRACT_VERSION,"profile_resolved": learning_enabled,"learning_enabled": learning_enabled,"forecast_enabled": learning_enabled,"previous_profile": self.coordinator.previous_profile,"profile_changed_at": self.coordinator.profile_changed_at,"profile_change_source": self.coordinator.profile_change_source}
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")},name=NAME,manufacturer="Dummy OS",model="Forecast Platform",sw_version=VERSION)
    async def async_select_option(self, option: str) -> None:
        if option not in PROFILE_OPTIONS: raise ValueError(f"Unsupported profile: {option}")
        await self.coordinator.async_set_profile(option, source="manual_select")
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass(); self._remove_listener = self.coordinator.async_add_listener(self._handle_update)
    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None: self._remove_listener()
        await super().async_will_remove_from_hass()
    @callback
    def _handle_update(self) -> None: self.async_write_ha_state()

class DummyOSManualPlanSlotSelect(SelectEntity):
    """Select which persistent Plan Store slot the shadow manual interface reads."""
    _attr_name = "DO Plan Manual Slot"; _attr_unique_id = "do_plan_manual_slot"; _attr_suggested_object_id = "do_plan_manual_slot"
    _attr_options = list(VALID_SLOT_OPTIONS); _attr_icon = "mdi:format-list-numbered"; _attr_should_poll = False; _attr_has_entity_name = False
    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        self.coordinator = coordinator; self.runtime = get_do_plan_manual_interface_runtime(coordinator); self._remove_listener = None
    @property
    def current_option(self) -> str: return self.runtime.selected_slot
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"shadow_only": True,"manual_interface_write": False,"shadow_store_write": False,"operational_plan_store_write": False,"plan_store_mutated": False,"service_calls_performed": False,"physical_execution_authority": False}
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    async def async_select_option(self, option: str) -> None: self.runtime.select(option)
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass(); self._remove_listener = self.runtime.add_listener(self.async_write_ha_state)
    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None: self._remove_listener()
        await super().async_will_remove_from_hass()

class DummyOSPlanOperatingModeSelect(SelectEntity):
    """Select the persistent logical Dummy OS Energy operating mode."""
    _attr_name = "DO Plan Operating Mode"; _attr_unique_id = "do_plan_operating_mode"; _attr_suggested_object_id = "do_plan_operating_mode"
    _attr_options = list(OPERATING_MODE_OPTIONS); _attr_icon = "mdi:cog-transfer-outline"; _attr_should_poll = False; _attr_has_entity_name = False
    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        self.coordinator = coordinator; self.runtime = get_do_plan_operating_mode_runtime(coordinator); self._remove_listener = None
    @property
    def current_option(self) -> str: return self.runtime.mode
    @property
    def extra_state_attributes(self) -> dict[str, Any]: return self.runtime.result()
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    async def async_select_option(self, option: str) -> None: await self.runtime.async_set_mode(option, source="manual_select")
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass(); self._remove_listener = self.runtime.add_listener(self.async_write_ha_state); await self.runtime.async_ensure_loaded(); self.async_write_ha_state()
    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None: self._remove_listener()
        await super().async_will_remove_from_hass()
