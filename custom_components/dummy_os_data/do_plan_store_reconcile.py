"""Bridge membership reconciliation for the isolated Step-6 shadow Plan Store."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from .do_plan_store import ORIGIN_AUTOMATIC, STATUS_PENDING, empty_slot, validate_store_snapshot


def prune_obsolete_automatic_pending(snapshot: dict[str, Any], candidates: list[dict[str, Any]], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Release automatic pending plans no longer represented by the bridge.

    A slot is retained when either its exact planner signature is still present
    or the same planner identity is present with a revised signature. The latter
    allows ``sync_automatic_candidates`` to reconcile that revision in-place and
    preserve plan_id/slot_id. Manual plans and non-pending lifecycle states are
    never changed here.
    """
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "released_slots": [], "blockers": blockers}
    signatures = {
        str(item.get("planner_signature"))
        for item in candidates
        if isinstance(item, dict) and item.get("planner_signature")
    }
    identities = {
        str(item.get("planner_identity"))
        for item in candidates
        if isinstance(item, dict) and item.get("planner_identity")
    }
    result = deepcopy(snapshot)
    released: list[int] = []
    for index, slot in enumerate(result["slots"]):
        if slot.get("origin") != ORIGIN_AUTOMATIC or slot.get("status") != STATUS_PENDING:
            continue
        signature = slot.get("planner_signature")
        identity = slot.get("planner_identity")
        if signature in signatures or identity in identities:
            continue
        released.append(int(slot["slot_id"]))
        result["slots"][index] = empty_slot(int(slot["slot_id"]))
    if released:
        result["updated_at"] = now.astimezone(timezone.utc).isoformat()
    return result, {"changed": bool(released), "released_slots": released, "blockers": []}
