"""Home Assistant entity for central SOC Contract v1."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN,NAME,VERSION
from .do_plan_soc_contract import build_do_plan_soc_contract
RAW_SOC_ENTITY="sensor.anker_solix_solarbank_max_ac_185_soc"
class DummyOSPlanSOCContractSensor(SensorEntity):
    _attr_name="DO Plan SOC Contract"; _attr_unique_id="do_plan_soc_contract"; _attr_suggested_object_id="do_plan_soc_contract"; _attr_icon="mdi:battery-check-outline"; _attr_should_poll=False; _attr_has_entity_name=False
    def __init__(self,coordinator:Any)->None: self.coordinator=coordinator; self._remove_source_listener=None; self._last_known_good_soc_percent=None; self._last_known_good_observed_at=None
    @property
    def device_info(self)->DeviceInfo: return DeviceInfo(identifiers={(DOMAIN,"main")},name=NAME,manufacturer="Dummy OS",model="Energy Platform",sw_version=VERSION)
    def _result(self)->dict[str,Any]:
        state=self.coordinator.hass.states.get(RAW_SOC_ENTITY); result=build_do_plan_soc_contract(source_entity=RAW_SOC_ENTITY,raw_state=state.state if state else None,now=datetime.now(timezone.utc),last_known_good_soc_percent=self._last_known_good_soc_percent,last_known_good_observed_at=self._last_known_good_observed_at)
        if result["valid"]: self._last_known_good_soc_percent=result["soc_percent"]; self._last_known_good_observed_at=result["observed_at"]; result["last_known_good_soc_percent"]=self._last_known_good_soc_percent; result["last_known_good_observed_at"]=self._last_known_good_observed_at
        result["source_last_changed"]=state.last_changed.isoformat() if state else None; result["source_last_updated"]=state.last_updated.isoformat() if state else None; return result
    @property
    def native_value(self)->str: return str(self._result().get("status","blocked"))
    @property
    def extra_state_attributes(self)->dict[str,Any]: return self._result()
    async def async_added_to_hass(self)->None: await super().async_added_to_hass(); self._remove_source_listener=async_track_state_change_event(self.coordinator.hass,[RAW_SOC_ENTITY],self._handle_source_update); self.async_write_ha_state()
    async def async_will_remove_from_hass(self)->None:
        if self._remove_source_listener: self._remove_source_listener()
        await super().async_will_remove_from_hass()
    @callback
    def _handle_source_update(self,_event)->None: self.async_write_ha_state()
def build_do_plan_soc_contract_sensors(coordinator:Any)->list[SensorEntity]: return [DummyOSPlanSOCContractSensor(coordinator)]
