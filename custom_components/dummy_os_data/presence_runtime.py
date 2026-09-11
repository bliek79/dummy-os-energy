"""Persistent Presence/Away runtime for Dummy OS Energy."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .presence import active_window_id, build_presence_state, schedule_validation

PRESENCE_STORAGE_VERSION = 1
PRESENCE_STORAGE_KEY = f"{DOMAIN}.presence"


class DummyOSPresenceContextRuntime:
    """Own Presence configuration, persistence and profile transitions."""

    def __init__(self, hass: HomeAssistant, coordinator: Any) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.store: Store[dict[str, Any]] = Store(hass, PRESENCE_STORAGE_VERSION, PRESENCE_STORAGE_KEY)
        self.schedule_enabled = False
        self.schedule_start: str | None = None
        self.schedule_end: str | None = None
        self.pre_schedule_profile: str | None = None
        self.schedule_applied_window_id: str | None = None
        self.manual_override_window_id: str | None = None
        self.restart_restored = False
        self.change_reason = "initial_default"
        self.storage_valid = True
        self.runtime_ready = False
        self._transition_in_progress = False
        self._listeners: list[Callable[[], None]] = []
        self._remove_profile_listener: Callable[[], None] | None = None
        self._remove_timer: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        try:
            stored = await self.store.async_load()
            if stored is not None and not isinstance(stored, dict):
                raise ValueError("presence store is not a mapping")
        except Exception:  # Home Assistant storage failures must fail closed.
            stored = None
            self.storage_valid = False
        if self.storage_valid and stored:
            self.schedule_enabled = bool(stored.get("schedule_enabled", False))
            self.schedule_start = stored.get("schedule_start")
            self.schedule_end = stored.get("schedule_end")
            self.pre_schedule_profile = stored.get("pre_schedule_profile")
            self.schedule_applied_window_id = stored.get("schedule_applied_window_id")
            self.manual_override_window_id = stored.get("manual_override_window_id")
            self.restart_restored = True
        if not self.storage_valid:
            self.schedule_enabled = False
        self.runtime_ready = True
        self._remove_profile_listener = self.coordinator.async_add_listener(self._profile_changed)
        await self._async_reconcile("startup_restore")

    async def async_shutdown(self) -> None:
        if self._remove_timer is not None:
            self._remove_timer(); self._remove_timer = None
        if self._remove_profile_listener is not None:
            self._remove_profile_listener(); self._remove_profile_listener = None
        await self._async_save()

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        result = build_presence_state(
            now=now or dt_util.utcnow(),
            schedule_enabled=self.schedule_enabled,
            schedule_start=self.schedule_start,
            schedule_end=self.schedule_end,
            current_profile=self.coordinator.profile,
            pre_schedule_profile=self.pre_schedule_profile,
            schedule_applied_window_id=self.schedule_applied_window_id,
            manual_override_window_id=self.manual_override_window_id,
            storage_valid=self.storage_valid,
            runtime_ready=self.runtime_ready,
        )
        result.update({
            "profile_source": self.coordinator.profile_change_source,
            "manual_profile": self.coordinator.profile if result["presence_context"] in {"manual", "manual_override"} else None,
            "schedule_enabled": self.schedule_enabled,
            "schedule_start": self.schedule_start,
            "schedule_end": self.schedule_end,
            "previous_profile": self.coordinator.previous_profile,
            "profile_changed_at": self.coordinator.profile_changed_at,
            "change_reason": self.change_reason,
            "restart_restored": self.restart_restored,
        })
        return result

    async def async_set_enabled(self, enabled: bool) -> None:
        self.schedule_enabled = bool(enabled)
        await self._async_reconcile("schedule_enabled_changed")

    async def async_set_start(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("Presence start must be timezone-aware")
        self.schedule_start = dt_util.as_utc(value).isoformat()
        self._reset_window_claims_if_identity_changed()
        await self._async_reconcile("schedule_start_changed")

    async def async_set_end(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("Presence end must be timezone-aware")
        self.schedule_end = dt_util.as_utc(value).isoformat()
        self._reset_window_claims_if_identity_changed()
        await self._async_reconcile("schedule_end_changed")

    def _configured_window_id(self) -> str | None:
        valid = schedule_validation(self.schedule_start, self.schedule_end)
        if not valid["valid"]:
            return None
        return active_window_id(valid["start"], valid["end"])

    def _reset_window_claims_if_identity_changed(self) -> None:
        configured = self._configured_window_id()
        if configured != self.schedule_applied_window_id:
            self.schedule_applied_window_id = None
        if configured != self.manual_override_window_id:
            self.manual_override_window_id = None

    @callback
    def _profile_changed(self) -> None:
        if self._transition_in_progress or not self.runtime_ready:
            return
        snap = self.snapshot()
        if snap["schedule_active"] and self.schedule_applied_window_id == snap["active_window_id"]:
            self.manual_override_window_id = snap["active_window_id"]
            self.change_reason = "manual_override"
            self.hass.async_create_task(self._async_save_and_refresh())

    async def _async_save_and_refresh(self) -> None:
        await self._async_save()
        self._schedule_next_transition()
        self._notify()

    async def _async_set_profile(self, profile: str, source: str) -> None:
        if self.coordinator.profile == profile:
            return
        self._transition_in_progress = True
        try:
            await self.coordinator.async_set_profile(profile, source=source)
        finally:
            self._transition_in_progress = False

    async def _async_reconcile(self, reason: str) -> None:
        now = dt_util.utcnow()
        snap = self.snapshot(now)
        self.change_reason = reason
        configured_window = snap.get("active_window_id")

        if snap["status"] == "blocked":
            await self._async_save(); self._schedule_next_transition(); self._notify(); return

        if snap["schedule_active"] and not snap["manual_override_active"]:
            if self.schedule_applied_window_id != configured_window:
                self.pre_schedule_profile = self.coordinator.profile
                await self._async_set_profile("away", "presence_schedule_start")
                self.schedule_applied_window_id = configured_window
                self.change_reason = "presence_schedule_start"
        elif not snap["schedule_active"] and self.schedule_applied_window_id is not None:
            if self.manual_override_window_id != self.schedule_applied_window_id and self.pre_schedule_profile is not None:
                await self._async_set_profile(self.pre_schedule_profile, "presence_schedule_end")
                self.change_reason = "presence_schedule_end"
            self.schedule_applied_window_id = None
            self.manual_override_window_id = None
            self.pre_schedule_profile = None

        await self._async_save()
        self._schedule_next_transition()
        self._notify()

    def _schedule_next_transition(self) -> None:
        if self._remove_timer is not None:
            self._remove_timer(); self._remove_timer = None
        snap = self.snapshot()
        next_at = snap.get("next_transition_at")
        if not next_at:
            return
        target = datetime.fromisoformat(next_at)
        self._remove_timer = async_track_point_in_utc_time(self.hass, self._async_timer, target)

    async def _async_timer(self, _now: datetime) -> None:
        self._remove_timer = None
        await self._async_reconcile("schedule_boundary")

    async def _async_save(self) -> None:
        if not self.storage_valid:
            return
        await self.store.async_save({
            "schedule_enabled": self.schedule_enabled,
            "schedule_start": self.schedule_start,
            "schedule_end": self.schedule_end,
            "pre_schedule_profile": self.pre_schedule_profile,
            "schedule_applied_window_id": self.schedule_applied_window_id,
            "manual_override_window_id": self.manual_override_window_id,
        })


def get_presence_runtime(coordinator: Any) -> DummyOSPresenceContextRuntime:
    runtime = getattr(coordinator, "presence", None)
    if runtime is None:
        raise RuntimeError("Presence runtime is not initialized")
    return runtime
