"""Pure diagnostic contract for the alpha.20 manual lifecycle test.

The diagnostic only transforms shadow Plan Store snapshots. It has no Home
Assistant service calls and no physical control path.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from .do_plan_manual_lifecycle import (
    clear_manual_slot,
    edit_manual_draft,
    finalize_manual_draft,
    new_manual_draft,
    patch_manual_draft,
    validate_manual_draft,
)


def _next_quarter(now: datetime, lead_minutes: int = 120) -> datetime:
    candidate = now.astimezone(timezone.utc) + timedelta(minutes=lead_minutes)
    candidate = candidate.replace(second=0, microsecond=0)
    remainder = candidate.minute % 15
    if remainder:
        candidate += timedelta(minutes=15 - remainder)
    return candidate


def _step(name: str, status: str, blockers: list[str] | None = None, **details: Any) -> dict[str, Any]:
    return {"step": name, "status": status, "blockers": blockers or [], **details}


def run_manual_lifecycle_diagnostic(
    snapshot: dict[str, Any],
    *,
    slot_id: int,
    now: datetime,
    start_time: str | None = None,
    action: str = "charge",
    power_w: float = 500.0,
    edited_power_w: float = 600.0,
    target_soc_percent: float = 70.0,
    max_runtime_minutes: float = 30.0,
    max_start_delay_minutes: float = 10.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run draft->validate->finalize->edit->finalize->clear fail-closed."""
    original = deepcopy(snapshot)
    working = deepcopy(snapshot)
    steps: list[dict[str, Any]] = []
    start = start_time or _next_quarter(now).isoformat()

    draft, result = new_manual_draft(working, slot_id, now)
    steps.append(_step("draft", result.get("status", "blocked"), result.get("blockers", [])))
    if not draft:
        return original, _result("blocked", slot_id, start, steps, result.get("blockers", []))
    draft = patch_manual_draft(draft, {"action": action, "start_time": start, "power_w": power_w, "target_soc_percent": target_soc_percent, "max_runtime_minutes": max_runtime_minutes, "max_start_delay_minutes": max_start_delay_minutes}, now)

    validation = validate_manual_draft(draft, working, now)
    steps.append(_step("validate_new", validation["status"], validation["blockers"]))
    if not validation["valid"]:
        return original, _result("blocked", slot_id, start, steps, validation["blockers"])

    working, finalized = finalize_manual_draft(working, draft, now)
    steps.append(_step("finalize_new", finalized.get("status", "blocked"), finalized.get("blockers", []), changed=finalized.get("changed", False)))
    if not finalized.get("changed"):
        return original, _result("blocked", slot_id, start, steps, finalized.get("blockers", []))
    first = deepcopy(working["slots"][slot_id - 1])
    first_ok = first.get("origin") == "manual" and first.get("manual_priority") is True and first.get("status") == "pending" and first.get("manual_revision") == 1
    steps.append(_step("verify_revision_1", "passed" if first_ok else "failed", [] if first_ok else ["revision_1_contract_failed"], plan_id=first.get("plan_id"), manual_revision=first.get("manual_revision")))
    if not first_ok:
        return original, _result("failed", slot_id, start, steps, ["revision_1_contract_failed"])

    edit, edit_result = edit_manual_draft(working, slot_id, now + timedelta(seconds=1))
    steps.append(_step("edit", edit_result.get("status", "blocked"), edit_result.get("blockers", [])))
    if not edit:
        return original, _result("blocked", slot_id, start, steps, edit_result.get("blockers", []))
    edit = patch_manual_draft(edit, {"power_w": edited_power_w}, now + timedelta(seconds=1))
    edit_validation = validate_manual_draft(edit, working, now + timedelta(seconds=1))
    steps.append(_step("validate_edit", edit_validation["status"], edit_validation["blockers"]))
    if not edit_validation["valid"]:
        return original, _result("blocked", slot_id, start, steps, edit_validation["blockers"])

    working, edited = finalize_manual_draft(working, edit, now + timedelta(seconds=1))
    steps.append(_step("finalize_edit", edited.get("status", "blocked"), edited.get("blockers", []), changed=edited.get("changed", False)))
    if not edited.get("changed"):
        return original, _result("blocked", slot_id, start, steps, edited.get("blockers", []))
    second = deepcopy(working["slots"][slot_id - 1])
    second_ok = second.get("plan_id") == first.get("plan_id") and second.get("manual_revision") == 2 and float(second.get("power_w") or 0) == float(edited_power_w)
    steps.append(_step("verify_revision_2", "passed" if second_ok else "failed", [] if second_ok else ["revision_2_contract_failed"], plan_id=second.get("plan_id"), manual_revision=second.get("manual_revision"), power_w=second.get("power_w")))
    if not second_ok:
        return original, _result("failed", slot_id, start, steps, ["revision_2_contract_failed"])

    working, cleared = clear_manual_slot(working, slot_id, now + timedelta(seconds=2), expected_plan_id=second.get("plan_id"), expected_updated_at=second.get("updated_at"))
    steps.append(_step("clear", cleared.get("status", "blocked"), cleared.get("blockers", []), changed=cleared.get("changed", False)))
    empty_ok = working["slots"][slot_id - 1].get("status") == "empty"
    steps.append(_step("verify_empty", "passed" if empty_ok else "failed", [] if empty_ok else ["slot_not_empty_after_clear"]))
    if not cleared.get("changed") or not empty_ok:
        return original, _result("failed", slot_id, start, steps, cleared.get("blockers", []) or ["slot_not_empty_after_clear"])

    return working, _result("passed", slot_id, start, steps, [], plan_id=first.get("plan_id"))


def _result(status: str, slot_id: int, start_time: str, steps: list[dict[str, Any]], blockers: list[str], plan_id: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "passed": status == "passed",
        "slot_id": slot_id,
        "start_time": start_time,
        "plan_id": plan_id,
        "steps": steps,
        "blockers": blockers,
        "shadow_only": True,
        "operational_plan_store_write": False,
        "scheduler_invoked": False,
        "safety_chain_invoked": False,
        "execution_handoff_performed": False,
        "external_service_calls_performed": False,
        "physical_execution_authority": False,
        "mode_switch_performed": False,
        "command_dispatched": False,
    }
