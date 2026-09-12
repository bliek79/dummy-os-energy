"""Pure Operating Mode contract and shadow gates for Dummy OS Energy."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

MODE_SELF_CONSUMPTION = "self_consumption"
MODE_MANUAL = "manual"
MODE_AUTOMATIC = "automatic"
MODE_DISABLED = "disabled"
OPERATING_MODE_OPTIONS = [MODE_SELF_CONSUMPTION, MODE_MANUAL, MODE_AUTOMATIC, MODE_DISABLED]
VALID_ORIGINS = {"manual", "automatic_72h_planner"}


def operating_mode_signature(mode: str, changed_at: str | None) -> str:
    raw = json.dumps({"mode": mode, "changed_at": changed_at}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_operating_mode_status(*, mode: Any, previous_mode: Any, changed_at: Any, mode_source: Any, runtime_ready: bool) -> dict[str, Any]:
    blockers: list[str] = []
    valid = isinstance(mode, str) and mode in OPERATING_MODE_OPTIONS
    if not runtime_ready:
        blockers.append("operating_mode_not_ready")
    if not valid:
        blockers.append("operating_mode_invalid")
    effective = mode if valid else None
    scheduler_allowed = valid and runtime_ready and effective in {MODE_MANUAL, MODE_AUTOMATIC}
    manual_allowed = scheduler_allowed and effective in {MODE_MANUAL, MODE_AUTOMATIC}
    automatic_allowed = scheduler_allowed and effective == MODE_AUTOMATIC
    if not runtime_ready:
        status = "initializing"
    elif not valid:
        status = "blocked"
    else:
        status = "ready"
    return {
        "status": status,
        "configured_mode": mode,
        "effective_mode": effective,
        "mode_valid": valid,
        "mode_source": mode_source,
        "previous_mode": previous_mode,
        "changed_at": changed_at,
        "automatic_planning_allowed": automatic_allowed,
        "manual_planning_allowed": manual_allowed,
        "scheduler_selection_allowed": scheduler_allowed,
        "automatic_selection_allowed": automatic_allowed,
        "manual_selection_allowed": manual_allowed,
        "physical_control_required": False,
        "required_physical_mode": "self_consumption" if effective in {MODE_SELF_CONSUMPTION, MODE_DISABLED} else None,
        "physical_control_mode": None,
        "physical_control_source_entity": None,
        "physical_control_ready": False,
        "blockers": blockers,
        "operating_mode_signature": operating_mode_signature(str(mode), changed_at if isinstance(changed_at, str) else None),
        "shadow_only": True,
        "active_use_permitted": False,
        "physical_execution_authority": False,
        "operational_plan_store_write": False,
        "service_calls_performed": False,
        "mode_switch_performed": False,
    }


def gate_store_for_scheduler(store_snapshot: Any, mode_result: Any) -> tuple[Any, list[str]]:
    """Return a copy whose disallowed pending origins cannot be selected by Scheduler."""
    if not isinstance(mode_result, dict) or mode_result.get("status") != "ready" or mode_result.get("mode_valid") is not True:
        return deepcopy(store_snapshot), ["operating_mode_not_ready"]
    mode = mode_result.get("effective_mode")
    gated = deepcopy(store_snapshot)
    if not isinstance(gated, dict) or not isinstance(gated.get("slots"), list):
        return gated, []
    blockers: list[str] = []
    if mode == MODE_DISABLED:
        blockers.append("operating_mode_disabled")
    elif mode == MODE_SELF_CONSUMPTION:
        blockers.append("operating_mode_self_consumption")
    for slot in gated["slots"]:
        if not isinstance(slot, dict) or slot.get("status") != "pending":
            continue
        origin = slot.get("origin")
        allowed = (mode == MODE_MANUAL and origin == "manual") or (mode == MODE_AUTOMATIC and origin in VALID_ORIGINS)
        if not allowed:
            slot["status"] = "blocked"
            slot["operating_mode_original_status"] = "pending"
            slot["operating_mode_blocker"] = "plan_origin_not_allowed"
    return gated, blockers


def apply_scheduler_mode_metadata(result: dict[str, Any], mode_result: dict[str, Any], mode_blockers: list[str]) -> dict[str, Any]:
    out = deepcopy(result)
    out["operating_mode_status"] = mode_result.get("status")
    out["configured_mode"] = mode_result.get("configured_mode")
    out["effective_mode"] = mode_result.get("effective_mode")
    out["manual_selection_allowed"] = mode_result.get("manual_selection_allowed") is True
    out["automatic_selection_allowed"] = mode_result.get("automatic_selection_allowed") is True
    out["scheduler_selection_allowed"] = mode_result.get("scheduler_selection_allowed") is True
    out["operating_mode_signature"] = mode_result.get("operating_mode_signature")
    if mode_blockers and out.get("scheduler_ready") is not True:
        existing = list(out.get("blockers") or [])
        out["blockers"] = sorted(set(existing + mode_blockers))
        if out.get("scheduler_status") in {"idle", "waiting", "attention"}:
            out["status"] = "waiting"
            out["scheduler_status"] = "waiting"
    return out


def apply_safety_mode_gate(safety: dict[str, Any], mode_result: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(safety)
    blockers = list(out.get("blockers") or [])
    mode = mode_result.get("effective_mode") if isinstance(mode_result, dict) else None
    if not isinstance(mode_result, dict) or mode_result.get("status") != "ready" or mode_result.get("mode_valid") is not True:
        blockers.append("operating_mode_not_ready")
    elif mode in {MODE_SELF_CONSUMPTION, MODE_DISABLED}:
        blockers.append("operating_mode_execution_not_allowed")
    else:
        origin = out.get("selected_origin")
        if origin is not None:
            allowed = (mode == MODE_MANUAL and origin == "manual") or (mode == MODE_AUTOMATIC and origin in VALID_ORIGINS)
            if not allowed:
                blockers.append("selected_origin_not_allowed_by_mode")
    blockers = sorted(set(blockers))
    out["operating_mode_status"] = mode_result.get("status") if isinstance(mode_result, dict) else None
    out["configured_mode"] = mode_result.get("configured_mode") if isinstance(mode_result, dict) else None
    out["effective_mode"] = mode
    out["operating_mode_signature"] = mode_result.get("operating_mode_signature") if isinstance(mode_result, dict) else None
    out["blockers"] = blockers
    out["safety_ready"] = not blockers
    out["status"] = "ready" if not blockers else "blocked"
    out["safety_status"] = out["status"]
    return out


def apply_prestart_mode_gate(prestart: dict[str, Any], scheduler: dict[str, Any], safety: dict[str, Any], mode_result: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(prestart)
    blockers = list(out.get("blockers") or [])
    current = mode_result.get("operating_mode_signature") if isinstance(mode_result, dict) else None
    if not current or scheduler.get("operating_mode_signature") != current or safety.get("operating_mode_signature") != current:
        blockers.append("operating_mode_changed")
    blockers = sorted(set(blockers))
    out["operating_mode_status"] = mode_result.get("status") if isinstance(mode_result, dict) else None
    out["effective_mode"] = mode_result.get("effective_mode") if isinstance(mode_result, dict) else None
    out["operating_mode_signature"] = current
    out["blockers"] = blockers
    if blockers:
        out["prestart_ready"] = False
        if out.get("prestart_status") == "ready":
            out["status"] = "blocked"
            out["prestart_status"] = "blocked"
    return out
