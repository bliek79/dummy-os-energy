"""Bridge membership reconciliation for the isolated Step-6 shadow Plan Store."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from .do_plan_store import ORIGIN_AUTOMATIC, STATUS_PENDING, empty_slot, validate_store_snapshot


def prune_obsolete_automatic_pending(snapshot: dict[str, Any], candidates: list[dict[str, Any]], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Release automatic pending plans no longer present in the current bridge set.

    Manual plans and non-pending lifecycle states are never changed here.
    """
    valid, blockers = validate_store_snapshot(snapshot)
    if not valid:
        return deepcopy(snapshot), {"changed": False, "released_slots": [], "blockers": blockers}
    signatures = {str(item.get("planner_signature")) for item in candidates if isinstance(item, dict) and item.get("planner_signature")}
    result = deepcopy(snapshot); released=[]
    for index, slot in enumerate(result["slots"]):
        if slot.get("origin") != ORIGIN_AUTOMATIC or slot.get("status") != STATUS_PENDING:
            continue
        signature = slot.get("planner_signature")
        if signature not in signatures:
            released.append(int(slot["slot_id"]))
            result["slots"][index] = empty_slot(int(slot["slot_id"]))
    if released:
        result["updated_at"] = now.astimezone(timezone.utc).isoformat()
    return result, {"changed": bool(released), "released_slots": released, "blockers": []}
