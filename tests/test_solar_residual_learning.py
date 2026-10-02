"""Regression contract for F6 Solar residual learning."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNING_PATH = (
    ROOT / "custom_components" / "dummy_os_data" / "solar_residual_learning.py"
)
VALIDATION_PATH = (
    ROOT
    / "custom_components"
    / "dummy_os_data"
    / "solar_residual_learning_validation.py"
)
SOLAR_PATH = ROOT / "custom_components" / "dummy_os_data" / "solar.py"
SENSOR_PATH = ROOT / "custom_components" / "dummy_os_data" / "solar_sensor.py"
INIT_PATH = ROOT / "custom_components" / "dummy_os_data" / "__init__.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEARNING = _load(LEARNING_PATH, "solar_residual_learning")
VALIDATION = _load(
    VALIDATION_PATH, "solar_residual_learning_validation"
)


def _evaluation(
    *,
    parent: float = 0.10,
    actual: float = 0.105,
    coverage: float = 100.0,
    slot: str = "2026-10-02T10:00:00+00:00",
) -> dict:
    result = {
        "status": "ok",
        "valid": True,
        "slot_id": slot,
        "forecast_captured_at": slot,
        "solar_elevation_deg": 20.0,
    }
    for roof in ("north", "south", "total"):
        result[f"valid_{roof}"] = True
        result[f"coverage_{roof}_percent"] = coverage
        result[f"forecast_{roof}_kwh"] = (
            parent if roof != "total" else parent * 2
        )
        result[f"actual_{roof}_kwh"] = (
            actual if roof != "total" else actual * 2
        )
    return result


def test_f6_sources_parse() -> None:
    for path in (
        LEARNING_PATH,
        VALIDATION_PATH,
        SOLAR_PATH,
        SENSOR_PATH,
    ):
        ast.parse(path.read_text(encoding="utf-8"))


def test_f6_bin_contract_matches_f4_conditions() -> None:
    assert (
        LEARNING.condition_key("north", "low", "east", "mixed")
        == "north|low|east|mixed"
    )
    assert LEARNING.condition_key(
        "south", "below_horizon", "east", "mixed"
    ) is None
    assert LEARNING.condition_key(
        "south", "low", "east", "dark"
    ) is None


def test_f6_training_hard_gates() -> None:
    evaluation = _evaluation()
    status, sample = LEARNING.build_training_sample(
        evaluation,
        array="north",
        solar_elevation_band="medium",
        solar_azimuth_sector="south",
        weather_regime="mixed",
        ac_limit_kw=2.45,
        local_date="2026-10-02",
        local_month=10,
        parent_signature="sig",
        expected_parent_signature="sig",
    )
    assert status == "ok"
    assert sample is not None

    low_coverage = dict(evaluation)
    low_coverage["coverage_north_percent"] = 89.9
    assert LEARNING.build_training_sample(
        low_coverage,
        array="north",
        solar_elevation_band="medium",
        solar_azimuth_sector="south",
        weather_regime="mixed",
        ac_limit_kw=2.45,
        local_date="2026-10-02",
        local_month=10,
        parent_signature="sig",
        expected_parent_signature="sig",
    )[0] == "insufficient_coverage"

    assert LEARNING.build_training_sample(
        evaluation,
        array="north",
        solar_elevation_band="medium",
        solar_azimuth_sector="south",
        weather_regime="dark",
        ac_limit_kw=2.45,
        local_date="2026-10-02",
        local_month=10,
        parent_signature="sig",
        expected_parent_signature="sig",
    )[0] == "not_daylight"

    assert LEARNING.build_training_sample(
        evaluation,
        array="north",
        solar_elevation_band="medium",
        solar_azimuth_sector="south",
        weather_regime="mixed",
        ac_limit_kw=2.45,
        local_date="2026-10-02",
        local_month=10,
        parent_signature="old",
        expected_parent_signature="new",
    )[0] == "parent_signature_mismatch"


def test_f6_qualification_40_samples_seven_days() -> None:
    state = LEARNING.new_learning_state(
        LEARNING.F6_PARENT_MODEL, "sig"
    )
    for day in range(1, 8):
        for quarter in range(6):
            evaluation = _evaluation(
                slot=(
                    f"2026-09-{day:02d}T"
                    f"{8 + quarter:02d}:00:00+00:00"
                )
            )
            status, sample = LEARNING.build_training_sample(
                evaluation,
                array="north",
                solar_elevation_band="medium",
                solar_azimuth_sector="south",
                weather_regime="mixed",
                ac_limit_kw=2.45,
                local_date=f"2026-09-{day:02d}",
                local_month=9,
                parent_signature="sig",
                expected_parent_signature="sig",
            )
            assert status == "ok"
            assert sample is not None
            assert LEARNING.add_training_sample(state, sample)

    revision = LEARNING.build_revision(
        state,
        training_cutoff="2026-09-08T00:00:00+02:00",
        cutoff_local_date="2026-09-08",
    )
    fitted = revision["bins"]["north|medium|south|mixed"]
    assert fitted["usable_sample_count"] == 42
    assert fitted["day_count"] == 7
    assert fitted["status"] == "qualified"
    assert fitted["applied_factor"] == 1.05


def test_f6_insufficient_and_saturated_always_apply_one() -> None:
    insufficient = LEARNING.fit_bin(
        [
            {
                "slot_id": str(index),
                "date": "2026-09-01",
                "residual_ratio": 1.1,
                "plausibility_ok": True,
            }
            for index in range(39)
        ]
    )
    assert insufficient["status"] == "insufficient"
    assert insufficient["applied_factor"] == 1.0

    saturated_samples = []
    for day in range(1, 8):
        for quarter in range(6):
            saturated_samples.append(
                {
                    "slot_id": f"{day}-{quarter}",
                    "date": f"2026-09-{day:02d}",
                    "residual_ratio": 2.0,
                    "plausibility_ok": True,
                }
            )
    saturated = LEARNING.fit_bin(saturated_samples)
    assert saturated["status"] == "saturated"
    assert saturated["learned_factor"] == 1.25
    assert saturated["applied_factor"] == 1.0


def test_f6_plausibility_mad_and_120_sample_limit() -> None:
    state = LEARNING.new_learning_state(
        LEARNING.F6_PARENT_MODEL, "sig"
    )
    for index in range(130):
        assert LEARNING.add_training_sample(
            state,
            {
                "slot_id": f"slot-{index:03d}",
                "date": "2026-09-01",
                "bin": "north|medium|south|mixed",
                "residual_ratio": 1.0,
                "plausibility_ok": True,
            },
        )
    assert (
        len(state["bins"]["north|medium|south|mixed"]["samples"])
        == 120
    )

    samples = [
        {
            "slot_id": f"base-{index}",
            "date": f"2026-09-{(index % 7) + 1:02d}",
            "residual_ratio": 1.0,
            "plausibility_ok": True,
        }
        for index in range(42)
    ]
    samples.append(
        {
            "slot_id": "bad",
            "date": "2026-09-07",
            "residual_ratio": 4.5,
            "plausibility_ok": False,
        }
    )
    fitted = LEARNING.fit_bin(samples)
    assert fitted["plausibility_outlier_count"] == 1
    assert fitted["status"] == "qualified"


def test_f6_revision_excludes_target_day_and_is_deterministic() -> None:
    state = LEARNING.new_learning_state(
        LEARNING.F6_PARENT_MODEL, "sig"
    )
    key = "north|medium|south|mixed"
    state["bins"][key] = {
        "samples": [
            {
                "slot_id": "old",
                "date": "2026-10-01",
                "residual_ratio": 1.0,
                "plausibility_ok": True,
            },
            {
                "slot_id": "target-day",
                "date": "2026-10-02",
                "residual_ratio": 1.2,
                "plausibility_ok": True,
            },
        ]
    }
    first = LEARNING.build_revision(
        state,
        training_cutoff="2026-10-02T00:00:00+02:00",
        cutoff_local_date="2026-10-02",
    )
    revision_id = first["model_revision"]
    assert first["bins"][key]["sample_count"] == 1

    second = LEARNING.build_revision(
        state,
        training_cutoff="2026-10-02T00:00:00+02:00",
        cutoff_local_date="2026-10-02",
    )
    assert second["model_revision"] == revision_id


def test_f6_parent_change_resets_state_and_factor() -> None:
    state = LEARNING.new_learning_state(
        LEARNING.F6_PARENT_MODEL, "old"
    )
    changed, reset = LEARNING.reset_for_parent_change(
        state, LEARNING.F6_PARENT_MODEL, "new"
    )
    assert changed is True
    assert reset["parent_signature"] == "new"
    assert reset["bins"] == {}
    assert reset["last_reset_reason"] == "physical_parent_changed"


def test_f6_reapplies_per_array_ac_cap() -> None:
    assert LEARNING.apply_factor_with_ac_cap(
        0.60, 1.25, 2.45
    ) == 0.6125
    assert LEARNING.apply_factor_with_ac_cap(
        0.40, 1.25, 2.45
    ) == 0.50


def test_f6_validation_exact_lock_and_metrics() -> None:
    parent = _evaluation(parent=0.10, actual=0.105)
    learned = _evaluation(parent=0.105, actual=0.105)
    learned.update(
        {
            "model_revision": "r1",
            "parent_model": LEARNING.F6_PARENT_MODEL,
            "parent_signature": "sig",
            "solar_elevation_band": "medium",
            "solar_azimuth_sector": "south",
            "weather_regime": "mixed",
            "north_bin": "north|medium|south|mixed",
            "south_bin": "south|medium|south|mixed",
            "north_bin_status": "qualified",
            "south_bin_status": "qualified",
            "north_applied_factor": 1.05,
            "south_applied_factor": 1.05,
        }
    )
    status, sample = VALIDATION.build_residual_learning_pair(
        parent, learned
    )
    assert status == "ok"
    assert sample is not None
    day = VALIDATION.new_residual_learning_day("2026-10-02")
    VALIDATION.add_residual_learning_sample(day, sample)
    summary = VALIDATION.summarize_residual_learning_history([day])
    assert summary["sample_count"] == 1
    assert summary["components"]["north"][
        "learned_absolute_error_kwh"
    ] == 0.0

    mismatched = dict(learned)
    mismatched["forecast_captured_at"] = "2026-10-02T10:01:00+00:00"
    assert VALIDATION.build_residual_learning_pair(
        parent, mismatched
    )[0] == "lock_mismatch"


def test_f6_canonical_entities_and_scope_are_wired() -> None:
    sensor = SENSOR_PATH.read_text(encoding="utf-8")
    init = INIT_PATH.read_text(encoding="utf-8")
    solar = SOLAR_PATH.read_text(encoding="utf-8")
    for unique_id in (
        "do_solar_residual_learning_status",
        "do_solar_residual_learning_candidate_timeline",
        "do_solar_residual_learning_candidate_next_quarter",
        "do_solar_residual_learning_candidate_evaluation_last_completed_quarter",
        "do_solar_residual_learning_validation",
    ):
        assert unique_id in sensor
        assert unique_id in init

    assert "promotion_authority" in sensor
    assert "SOLAR_RESIDUAL_LEARNING_CANDIDATE_MODEL" in solar
    assert "_residual_learning_candidate_snapshot_for_slot" in solar
    assert "residual_learning_state" in solar
    assert "apply_factor_with_ac_cap" in solar


def test_f6_does_not_change_native_contract_or_authority() -> None:
    solar = SOLAR_PATH.read_text(encoding="utf-8")
    sensor = SENSOR_PATH.read_text(encoding="utf-8")
    assert "SOLAR_RESOLUTION_MINUTES = 15" in solar
    assert "horizon_hours" in sensor
    assert "slot_count" in sensor
    assert '"promotion_authority": False' in sensor
