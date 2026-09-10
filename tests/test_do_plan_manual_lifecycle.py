from copy import deepcopy
from datetime import datetime, timedelta, timezone

from custom_components.dummy_os_data.do_plan_manual_lifecycle import (
    clear_manual_slot,
    edit_manual_draft,
    finalize_manual_draft,
    new_manual_draft,
    patch_manual_draft,
    validate_manual_draft,
)
from custom_components.dummy_os_data.do_plan_store import (
    ORIGIN_AUTOMATIC,
    ORIGIN_MANUAL,
    STATUS_PENDING,
    STATUS_RUNNING,
    empty_slot,
    new_store_snapshot,
)

NOW = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)


def valid_new_draft(snapshot, slot_id=1, start=None):
    draft, result = new_manual_draft(snapshot, slot_id, NOW)
    assert result["status"] == "draft"
    return patch_manual_draft(
        draft,
        {
            "action": "charge",
            "start_time": (start or (NOW + timedelta(hours=2))).isoformat(),
            "power_w": 1200,
            "target_soc_percent": 80,
            "max_runtime_minutes": 60,
            "max_start_delay_minutes": 10,
        },
        NOW,
    )


def test_draft_does_not_mutate_store():
    snapshot = new_store_snapshot(NOW)
    before = deepcopy(snapshot)
    draft = valid_new_draft(snapshot)
    assert snapshot == before
    assert draft["status"] == "draft"


def test_validate_normalizes_end_and_energy():
    snapshot = new_store_snapshot(NOW)
    result = validate_manual_draft(valid_new_draft(snapshot), snapshot, NOW)
    assert result["valid"] is True
    assert result["normalized"]["planned_end_time"] == "2026-09-11T11:00:00+00:00"
    assert result["normalized"]["planned_energy_kwh"] == 1.2


def test_quarter_alignment_power_soc_and_runtime_limits():
    snapshot = new_store_snapshot(NOW)
    draft = valid_new_draft(snapshot)
    draft = patch_manual_draft(draft, {"start_time": "2026-09-11T10:07:00+00:00", "power_w": 3201, "target_soc_percent": 4, "max_runtime_minutes": 17}, NOW)
    blockers = validate_manual_draft(draft, snapshot, NOW)["blockers"]
    assert "start_not_quarter_aligned" in blockers
    assert "power_above_limit" in blockers
    assert "target_soc_out_of_range" in blockers
    assert "runtime_not_quarter_aligned" in blockers


def test_manual_manual_overlap_is_blocked_including_delay_reservation():
    snapshot = new_store_snapshot(NOW)
    first, result = finalize_manual_draft(snapshot, valid_new_draft(snapshot, 1, NOW + timedelta(hours=2)), NOW)
    assert result["changed"] is True
    second = valid_new_draft(first, 2, NOW + timedelta(hours=3))
    validation = validate_manual_draft(second, first, NOW)
    # First reserves 10:00 through 11:10 because max start delay is included.
    assert validation["valid"] is False
    assert validation["overlap_slot_ids"] == [1]
    assert "plan_overlap" in validation["blockers"]


def test_manual_automatic_overlap_is_blocked():
    snapshot = new_store_snapshot(NOW)
    auto = empty_slot(2)
    auto.update({
        "status": STATUS_PENDING,
        "origin": ORIGIN_AUTOMATIC,
        "plan_id": "auto-1",
        "candidate_id": "c1",
        "planner_identity": "id1",
        "planner_signature": "sig1",
        "action": "discharge",
        "start_time": "2026-09-11T10:30:00+00:00",
        "planned_end_time": "2026-09-11T11:30:00+00:00",
        "max_runtime_minutes": 60,
        "max_start_delay_minutes": 0,
        "power_w": 1000,
        "planned_energy_kwh": 1,
        "target_soc_percent": 40,
        "manual_priority": False,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    })
    snapshot["slots"][1] = auto
    validation = validate_manual_draft(valid_new_draft(snapshot, 1), snapshot, NOW)
    assert validation["valid"] is False
    assert validation["overlap_slot_ids"] == [2]


def test_touching_windows_do_not_overlap():
    snapshot = new_store_snapshot(NOW)
    first_draft = valid_new_draft(snapshot, 1, NOW + timedelta(hours=2))
    first_draft = patch_manual_draft(first_draft, {"max_start_delay_minutes": 0}, NOW)
    first, _ = finalize_manual_draft(snapshot, first_draft, NOW)
    second = valid_new_draft(first, 2, NOW + timedelta(hours=3))
    second = patch_manual_draft(second, {"max_start_delay_minutes": 0}, NOW)
    assert validate_manual_draft(second, first, NOW)["valid"] is True


def test_finalize_new_plan_and_manual_priority():
    snapshot = new_store_snapshot(NOW)
    updated, result = finalize_manual_draft(snapshot, valid_new_draft(snapshot), NOW)
    slot = updated["slots"][0]
    assert result["changed"] is True
    assert slot["origin"] == ORIGIN_MANUAL
    assert slot["manual_priority"] is True
    assert slot["status"] == STATUS_PENDING
    assert slot["manual_revision"] == 1


def test_edit_preserves_plan_id_created_at_and_increments_revision():
    snapshot = new_store_snapshot(NOW)
    updated, _ = finalize_manual_draft(snapshot, valid_new_draft(snapshot), NOW)
    old = deepcopy(updated["slots"][0])
    edit, result = edit_manual_draft(updated, 1, NOW + timedelta(minutes=1))
    assert result["status"] == "draft"
    edit = patch_manual_draft(edit, {"power_w": 1400}, NOW + timedelta(minutes=1))
    edited, result = finalize_manual_draft(updated, edit, NOW + timedelta(minutes=1))
    slot = edited["slots"][0]
    assert result["changed"] is True
    assert slot["plan_id"] == old["plan_id"]
    assert slot["created_at"] == old["created_at"]
    assert slot["manual_revision"] == 2
    assert slot["power_w"] == 1400


def test_stale_edit_is_blocked():
    snapshot = new_store_snapshot(NOW)
    updated, _ = finalize_manual_draft(snapshot, valid_new_draft(snapshot), NOW)
    edit, _ = edit_manual_draft(updated, 1, NOW + timedelta(minutes=1))
    changed = deepcopy(updated)
    changed["slots"][0]["updated_at"] = (NOW + timedelta(seconds=30)).isoformat()
    validation = validate_manual_draft(edit, changed, NOW + timedelta(minutes=1))
    assert "draft_base_stale" in validation["blockers"]


def test_running_manual_plan_cannot_be_edited_or_cleared():
    snapshot = new_store_snapshot(NOW)
    updated, _ = finalize_manual_draft(snapshot, valid_new_draft(snapshot), NOW)
    updated["slots"][0]["status"] = STATUS_RUNNING
    _, edit_result = edit_manual_draft(updated, 1, NOW)
    _, clear_result = clear_manual_slot(updated, 1, NOW)
    assert edit_result["blockers"] == ["running_plan_not_editable"]
    assert clear_result["blockers"] == ["running_plan_not_clearable"]


def test_automatic_slot_cannot_be_edited_or_cleared():
    snapshot = new_store_snapshot(NOW)
    slot = empty_slot(1)
    slot.update({"status": STATUS_PENDING, "origin": ORIGIN_AUTOMATIC, "manual_priority": False})
    snapshot["slots"][0] = slot
    _, edit_result = edit_manual_draft(snapshot, 1, NOW)
    _, clear_result = clear_manual_slot(snapshot, 1, NOW)
    assert edit_result["blockers"] == ["selected_slot_not_manual"]
    assert clear_result["blockers"] == ["automatic_slot_not_clearable"]


def test_clear_uses_optimistic_concurrency_and_is_idempotent_when_empty():
    snapshot = new_store_snapshot(NOW)
    updated, _ = finalize_manual_draft(snapshot, valid_new_draft(snapshot), NOW)
    slot = updated["slots"][0]
    unchanged, stale = clear_manual_slot(updated, 1, NOW, expected_plan_id="wrong")
    assert stale["blockers"] == ["clear_base_stale"]
    assert unchanged == updated
    cleared, result = clear_manual_slot(updated, 1, NOW, expected_plan_id=slot["plan_id"], expected_updated_at=slot["updated_at"])
    assert result["changed"] is True
    assert cleared["slots"][0]["status"] == "empty"
    again, result = clear_manual_slot(cleared, 1, NOW)
    assert result["idempotent"] is True
    assert again == cleared


def test_finalize_revalidates_against_latest_store():
    snapshot = new_store_snapshot(NOW)
    draft = valid_new_draft(snapshot, 1)
    assert validate_manual_draft(draft, snapshot, NOW)["valid"] is True
    occupied = deepcopy(snapshot)
    occupied["slots"][0].update({"status": STATUS_PENDING, "origin": ORIGIN_AUTOMATIC, "manual_priority": False})
    unchanged, result = finalize_manual_draft(occupied, draft, NOW)
    assert result["changed"] is False
    assert "selected_slot_not_empty" in result["blockers"]
    assert unchanged == occupied
