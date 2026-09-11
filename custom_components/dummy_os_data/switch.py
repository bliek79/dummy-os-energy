"""Switch entities for Dummy OS Energy."""
from __future__ import annotations
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .const import DOMAIN, NAME, VERSION
from .presence_runtime import async_get_presence_runtime

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime=await async_get_presence_runtime(entry.runtime_data)
    async_add_entities([DummyOSPresenceAwayScheduleEnabled(runtime)])

class DummyOSPresenceAwayScheduleEnabled(SwitchEntity):
    _attr_name="DO Presence Away Schedule Enabled"; _attr_unique_id="do_presence_away_schedule_enabled"; _attr_suggested_object_id="do_presence_away_schedule_enabled"; _attr_icon="mdi:calendar-account"; _attr_should_poll=False; _attr_has_entity_name=False
    def __init__(self,runtime)->None: self.runtime=runtime; self._remove_listener=None
    @property
    def is_on(self)->bool: return self.runtime.schedule_enabled
    @property
    def device_info(self)->DeviceInfo: return DeviceInfo(identifiers={(DOMAIN,"main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    async def async_turn_on(self,**kwargs)->None: await self.runtime.async_set_enabled(True)
    async def async_turn_off(self,**kwargs)->None: await self.runtime.async_set_enabled(False)
    async def async_added_to_hass(self)->None:
        await super().async_added_to_hass(); self.runtime.canonicalize_control_entity("switch",self._attr_unique_id,self.entity_id); self._remove_listener=self.runtime.add_listener(self._handle_update)
    async def async_will_remove_from_hass(self)->None:
        if self._remove_listener is not None: self._remove_listener()
        await self.runtime.async_shutdown(); await super().async_will_remove_from_hass()
    @callback
    def _handle_update(self)->None: self.async_write_ha_state()
