"""Datetime entities for Dummy OS Energy."""
from __future__ import annotations
from datetime import datetime
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from .const import DOMAIN, NAME, VERSION
from .do_plan_manual_interface_sensor import get_do_plan_manual_interface_runtime
from .do_plan_store import SLOT_COUNT
from .presence import parse_aware_datetime
from .presence_runtime import async_get_presence_runtime

async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry,async_add_entities:AddConfigEntryEntitiesCallback)->None:
    coordinator=entry.runtime_data
    presence_runtime=await async_get_presence_runtime(coordinator)
    manual_runtime=get_do_plan_manual_interface_runtime(coordinator)
    async_add_entities([
        DummyOSPresenceAwayStart(presence_runtime),
        DummyOSPresenceAwayEnd(presence_runtime),
        *[DummyOSManualPlanStart(manual_runtime, slot_id) for slot_id in range(1, SLOT_COUNT + 1)],
    ])

class _PresenceDateTime(DateTimeEntity):
    _attr_should_poll=False; _attr_has_entity_name=False
    def __init__(self,runtime)->None: self.runtime=runtime; self._remove_listener=None
    @property
    def device_info(self)->DeviceInfo: return DeviceInfo(identifiers={(DOMAIN,"main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    async def async_added_to_hass(self)->None:
        await super().async_added_to_hass(); self.runtime.canonicalize_control_entity("datetime",self._attr_unique_id,self.entity_id); self._remove_listener=self.runtime.add_listener(self._handle_update)
    async def async_will_remove_from_hass(self)->None:
        if self._remove_listener is not None: self._remove_listener()
        await super().async_will_remove_from_hass()
    @callback
    def _handle_update(self)->None: self.async_write_ha_state()

class DummyOSPresenceAwayStart(_PresenceDateTime):
    _attr_name="DO Presence Away Start"; _attr_unique_id="do_presence_away_start"; _attr_suggested_object_id="do_presence_away_start"; _attr_icon="mdi:calendar-start"
    @property
    def native_value(self)->datetime|None:
        value=parse_aware_datetime(self.runtime.schedule_start); return dt_util.as_local(value) if value is not None else None
    async def async_set_value(self,value:datetime)->None: await self.runtime.async_set_start(value)

class DummyOSPresenceAwayEnd(_PresenceDateTime):
    _attr_name="DO Presence Away End"; _attr_unique_id="do_presence_away_end"; _attr_suggested_object_id="do_presence_away_end"; _attr_icon="mdi:calendar-end"
    @property
    def native_value(self)->datetime|None:
        value=parse_aware_datetime(self.runtime.schedule_end); return dt_util.as_local(value) if value is not None else None
    async def async_set_value(self,value:datetime)->None: await self.runtime.async_set_end(value)

class DummyOSManualPlanStart(DateTimeEntity):
    """Native start-time control for one manual plan slot."""
    _attr_should_poll=False; _attr_has_entity_name=False; _attr_icon="mdi:calendar-clock"
    def __init__(self,runtime,slot_id:int)->None:
        self.runtime=runtime; self.slot_id=slot_id; self._remove_listener=None
        self._attr_name=f"DO Plan {slot_id} Start"
        self._attr_unique_id=f"do_plan_{slot_id}_start_time"
        self._attr_suggested_object_id=f"do_plan_{slot_id}_start_time"
        self._attr_device_info=DeviceInfo(identifiers={(DOMAIN,"main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    @property
    def native_value(self)->datetime|None:
        raw=self.runtime.control_value(self.slot_id,"start_time")
        if not raw: return None
        parsed=dt_util.parse_datetime(str(raw))
        if parsed is None: return None
        if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return dt_util.as_local(parsed)
    async def async_set_value(self,value:datetime)->None:
        if value.tzinfo is None: value=value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        await self.runtime.async_set_control(self.slot_id,"start_time",value.astimezone(dt_util.UTC).isoformat())
    async def async_added_to_hass(self)->None:
        await super().async_added_to_hass(); self._remove_listener=self.runtime.add_listener(self._handle_update); await self.runtime.async_ensure_controls_loaded(); self.async_write_ha_state()
    async def async_will_remove_from_hass(self)->None:
        if self._remove_listener is not None: self._remove_listener()
        await super().async_will_remove_from_hass()
    @callback
    def _handle_update(self)->None: self.async_write_ha_state()
