"""Persistent Presence/Away runtime for Dummy OS Energy."""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any, Callable
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .entity_migrations import is_known_generated_entity_id
from .presence import active_window_id, build_presence_state, schedule_validation

PRESENCE_STORAGE_VERSION = 1
PRESENCE_STORAGE_KEY = f"{DOMAIN}.presence"
_DIAGNOSTIC_ENTITIES = (
    ("sensor", "do_presence_context", "sensor.do_presence_context"),
    ("binary_sensor", "do_presence_away_schedule_valid", "binary_sensor.do_presence_away_schedule_valid"),
    ("binary_sensor", "do_presence_away_active", "binary_sensor.do_presence_away_active"),
)

class DummyOSPresenceContextRuntime:
    def __init__(self, hass: HomeAssistant, coordinator: Any) -> None:
        self.hass=hass; self.coordinator=coordinator
        self.store: Store[dict[str, Any]] = Store(hass, PRESENCE_STORAGE_VERSION, PRESENCE_STORAGE_KEY)
        self.schedule_enabled=False; self.schedule_start=None; self.schedule_end=None
        self.pre_schedule_profile=None; self.schedule_applied_window_id=None; self.manual_override_window_id=None
        self.restart_restored=False; self.change_reason="initial_default"; self.storage_valid=True; self.runtime_ready=False
        self._transition_in_progress=False; self._listeners=[]; self._remove_profile_listener=None; self._remove_timer=None; self._shutdown=False

    async def async_setup(self) -> None:
        try:
            stored=await self.store.async_load()
            if stored is not None and not isinstance(stored, dict): raise ValueError("presence store is not a mapping")
        except Exception:
            stored=None; self.storage_valid=False
        if self.storage_valid and stored:
            self.schedule_enabled=bool(stored.get("schedule_enabled",False)); self.schedule_start=stored.get("schedule_start"); self.schedule_end=stored.get("schedule_end")
            self.pre_schedule_profile=stored.get("pre_schedule_profile"); self.schedule_applied_window_id=stored.get("schedule_applied_window_id"); self.manual_override_window_id=stored.get("manual_override_window_id"); self.restart_restored=True
        if not self.storage_valid: self.schedule_enabled=False
        self.runtime_ready=True
        self._remove_profile_listener=self.coordinator.async_add_listener(self._profile_changed)
        self._register_diagnostic_entities()
        await self._async_reconcile("startup_restore")

    async def async_shutdown(self) -> None:
        if self._shutdown: return
        self._shutdown=True
        if self._remove_timer is not None: self._remove_timer(); self._remove_timer=None
        if self._remove_profile_listener is not None: self._remove_profile_listener(); self._remove_profile_listener=None
        await self._async_save()
        for _,_,entity_id in _DIAGNOSTIC_ENTITIES: self.hass.states.async_remove(entity_id)

    def add_listener(self, listener: Callable[[],None]) -> Callable[[],None]:
        self._listeners.append(listener)
        def remove():
            if listener in self._listeners: self._listeners.remove(listener)
        return remove

    @callback
    def _notify(self) -> None:
        self._publish_diagnostic_states()
        for listener in list(self._listeners): listener()

    def snapshot(self, now: datetime|None=None) -> dict[str,Any]:
        result=build_presence_state(now=now or dt_util.utcnow(),schedule_enabled=self.schedule_enabled,schedule_start=self.schedule_start,schedule_end=self.schedule_end,current_profile=self.coordinator.profile,pre_schedule_profile=self.pre_schedule_profile,schedule_applied_window_id=self.schedule_applied_window_id,manual_override_window_id=self.manual_override_window_id,storage_valid=self.storage_valid,runtime_ready=self.runtime_ready)
        result.update({"profile_source":self.coordinator.profile_change_source,"manual_profile":self.coordinator.profile if result["presence_context"] in {"manual","manual_override"} else None,"schedule_enabled":self.schedule_enabled,"schedule_start":self.schedule_start,"schedule_end":self.schedule_end,"previous_profile":self.coordinator.previous_profile,"profile_changed_at":self.coordinator.profile_changed_at,"change_reason":self.change_reason,"restart_restored":self.restart_restored})
        return result

    def _register_diagnostic_entities(self) -> None:
        registry=er.async_get(self.hass)
        for platform,unique_id,target in _DIAGNOSTIC_ENTITIES:
            entry=registry.async_get_or_create(platform,DOMAIN,unique_id,suggested_object_id=unique_id)
            current=entry.entity_id
            if current != target and is_known_generated_entity_id(platform,unique_id,current) and registry.async_get(target) is None:
                registry.async_update_entity(current,new_entity_id=target); self.hass.states.async_remove(current)
        self._publish_diagnostic_states()

    def canonicalize_control_entity(self, platform: str, unique_id: str, current_entity_id: str) -> None:
        target=f"{platform}.{unique_id}"; registry=er.async_get(self.hass)
        if current_entity_id != target and is_known_generated_entity_id(platform,unique_id,current_entity_id) and registry.async_get(target) is None:
            registry.async_update_entity(current_entity_id,new_entity_id=target); self.hass.states.async_remove(current_entity_id)

    def _publish_diagnostic_states(self) -> None:
        snap=self.snapshot()
        attrs=dict(snap); attrs.update({"profile_contract_version":1,"physical_execution_authority":False})
        self.hass.states.async_set("sensor.do_presence_context",snap["status"],attrs)
        self.hass.states.async_set("binary_sensor.do_presence_away_schedule_valid","on" if snap["schedule_valid"] else "off",{"blockers":snap["blockers"],"schedule_start":self.schedule_start,"schedule_end":self.schedule_end})
        self.hass.states.async_set("binary_sensor.do_presence_away_active","on" if snap["schedule_active"] else "off",{"active_window_id":snap.get("active_window_id"),"manual_override_active":snap.get("manual_override_active",False),"effective_profile":snap.get("effective_profile")})

    async def async_set_enabled(self, enabled: bool) -> None:
        self.schedule_enabled=bool(enabled); await self._async_reconcile("schedule_enabled_changed")
    async def async_set_start(self,value:datetime)->None:
        if value.tzinfo is None: raise ValueError("Presence start must be timezone-aware")
        self.schedule_start=dt_util.as_utc(value).isoformat(); self._reset_window_claims_if_identity_changed(); await self._async_reconcile("schedule_start_changed")
    async def async_set_end(self,value:datetime)->None:
        if value.tzinfo is None: raise ValueError("Presence end must be timezone-aware")
        self.schedule_end=dt_util.as_utc(value).isoformat(); self._reset_window_claims_if_identity_changed(); await self._async_reconcile("schedule_end_changed")

    def _configured_window_id(self):
        valid=schedule_validation(self.schedule_start,self.schedule_end)
        return active_window_id(valid["start"],valid["end"]) if valid["valid"] else None
    def _reset_window_claims_if_identity_changed(self):
        configured=self._configured_window_id()
        if configured != self.schedule_applied_window_id: self.schedule_applied_window_id=None
        if configured != self.manual_override_window_id: self.manual_override_window_id=None

    @callback
    def _profile_changed(self)->None:
        if self._transition_in_progress or not self.runtime_ready: return
        snap=self.snapshot()
        if snap["schedule_active"] and self.schedule_applied_window_id==snap["active_window_id"]:
            self.manual_override_window_id=snap["active_window_id"]; self.change_reason="manual_override"; self.hass.async_create_task(self._async_save_and_refresh())
    async def _async_save_and_refresh(self):
        await self._async_save(); self._schedule_next_transition(); self._notify()
    async def _async_set_profile(self,profile:str,source:str):
        if self.coordinator.profile==profile: return
        self._transition_in_progress=True
        try: await self.coordinator.async_set_profile(profile,source=source)
        finally: self._transition_in_progress=False

    async def _async_reconcile(self,reason:str):
        snap=self.snapshot(); self.change_reason=reason; window=snap.get("active_window_id")
        if snap["status"]=="blocked": await self._async_save(); self._schedule_next_transition(); self._notify(); return
        if snap["schedule_active"] and not snap["manual_override_active"] and self.schedule_applied_window_id != window:
            self.pre_schedule_profile=self.coordinator.profile; await self._async_set_profile("away","presence_schedule_start"); self.schedule_applied_window_id=window; self.change_reason="presence_schedule_start"
        elif not snap["schedule_active"] and self.schedule_applied_window_id is not None:
            if self.manual_override_window_id != self.schedule_applied_window_id and self.pre_schedule_profile is not None: await self._async_set_profile(self.pre_schedule_profile,"presence_schedule_end"); self.change_reason="presence_schedule_end"
            self.schedule_applied_window_id=None; self.manual_override_window_id=None; self.pre_schedule_profile=None
        await self._async_save(); self._schedule_next_transition(); self._notify()

    def _schedule_next_transition(self):
        if self._remove_timer is not None: self._remove_timer(); self._remove_timer=None
        next_at=self.snapshot().get("next_transition_at")
        if next_at: self._remove_timer=async_track_point_in_utc_time(self.hass,self._async_timer,datetime.fromisoformat(next_at))
    async def _async_timer(self,_now): self._remove_timer=None; await self._async_reconcile("schedule_boundary")
    async def _async_save(self):
        if self.storage_valid: await self.store.async_save({"schedule_enabled":self.schedule_enabled,"schedule_start":self.schedule_start,"schedule_end":self.schedule_end,"pre_schedule_profile":self.pre_schedule_profile,"schedule_applied_window_id":self.schedule_applied_window_id,"manual_override_window_id":self.manual_override_window_id})

async def async_get_presence_runtime(coordinator: Any) -> DummyOSPresenceContextRuntime:
    runtime=getattr(coordinator,"presence",None)
    if runtime is not None: return runtime
    lock=getattr(coordinator,"_presence_setup_lock",None)
    if lock is None: lock=asyncio.Lock(); coordinator._presence_setup_lock=lock
    async with lock:
        runtime=getattr(coordinator,"presence",None)
        if runtime is None:
            runtime=DummyOSPresenceContextRuntime(coordinator.hass,coordinator); coordinator.presence=runtime; await runtime.async_setup()
    return runtime

def get_presence_runtime(coordinator: Any) -> DummyOSPresenceContextRuntime:
    runtime=getattr(coordinator,"presence",None)
    if runtime is None: raise RuntimeError("Presence runtime is not initialized")
    return runtime
