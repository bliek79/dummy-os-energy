from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/energy_store.py"
SPEC = importlib.util.spec_from_file_location("energy_store", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

normalize_energy_store_payload = MODULE.normalize_energy_store_payload
UnsupportedEnergyStoreSchema = MODULE.UnsupportedEnergyStoreSchema


def test_legacy_payload_is_upgraded_without_losing_data():
    legacy = {
        "profile": "normal",
        "records": [{"start": "2026-09-01T00:00:00+00:00", "energy_kwh": 0.1}],
        "forecast_snapshots": {"a": {"forecast_kwh": 0.11}},
        "evaluations": [{"forecast_kwh": 0.11, "actual_kwh": 0.1}],
    }

    normalized = normalize_energy_store_payload(
        legacy,
        current_schema_version=2,
        default_profile="unclassified",
        valid_profiles={"normal", "away", "unclassified"},
        profile_contract_version=1,
    )

    assert normalized["energy_store_schema_version"] == 2
    assert normalized["profile_contract_version"] == 1
    assert normalized["profile"] == legacy["profile"]
    assert normalized["records"] == legacy["records"]
    assert normalized["forecast_snapshots"] == legacy["forecast_snapshots"]
    assert normalized["evaluations"] == legacy["evaluations"]
    assert normalized["previous_profile"] is None
    assert normalized["profile_changed_at"] is None
    assert normalized["profile_change_source"] == "legacy_migration"
    assert "energy_store_schema_version" not in legacy


def test_current_payload_roundtrips_profile_metadata_and_unknown_fields():
    current = {
        "energy_store_schema_version": 2,
        "profile_contract_version": 1,
        "profile": "away",
        "previous_profile": "normal",
        "profile_changed_at": "2026-09-07T09:00:00+00:00",
        "profile_change_source": "manual_select",
        "records": [{"valid": True}],
        "forecast_snapshots": {"slot": {"captured_at": "2026-09-04T07:00:00+00:00"}},
        "evaluations": [{"evaluation_schema_version": 1}],
        "future_additive_field": {"kept": True},
    }

    normalized = normalize_energy_store_payload(
        current,
        current_schema_version=2,
        default_profile="unclassified",
        valid_profiles={"normal", "away", "unclassified"},
        profile_contract_version=1,
    )

    assert normalized == current
    assert normalized is not current


def test_missing_profile_defaults_to_unclassified_not_normal():
    normalized = normalize_energy_store_payload(
        {},
        current_schema_version=2,
        default_profile="unclassified",
        valid_profiles={"normal", "away", "unclassified"},
        profile_contract_version=1,
    )

    assert normalized == {
        "energy_store_schema_version": 2,
        "profile_contract_version": 1,
        "profile": "unclassified",
        "previous_profile": None,
        "profile_changed_at": None,
        "profile_change_source": "initial_default",
        "records": [],
        "forecast_snapshots": {},
        "evaluations": [],
    }


def test_invalid_profile_defaults_to_unclassified_not_normal():
    for invalid in ("unknown", "mixed", "vacation", "", None, 123):
        normalized = normalize_energy_store_payload(
            {"profile": invalid},
            current_schema_version=2,
            default_profile="unclassified",
            valid_profiles={"normal", "away", "unclassified"},
            profile_contract_version=1,
        )
        assert normalized["profile"] == "unclassified"


def test_future_schema_is_rejected_instead_of_silently_downgraded():
    try:
        normalize_energy_store_payload(
            {"energy_store_schema_version": 3, "records": [{"keep": True}]},
            current_schema_version=2,
            default_profile="unclassified",
            valid_profiles={"normal", "away", "unclassified"},
        )
    except UnsupportedEnergyStoreSchema as err:
        assert "supported through 2" in str(err)
    else:
        raise AssertionError("future Energy schema must be rejected")


def test_invalid_schema_type_is_rejected():
    for invalid in (True, "1", 1.0, -1):
        try:
            normalize_energy_store_payload(
                {"energy_store_schema_version": invalid},
                current_schema_version=2,
                default_profile="unclassified",
                valid_profiles={"normal", "away", "unclassified"},
            )
        except UnsupportedEnergyStoreSchema:
            pass
        else:
            raise AssertionError(f"invalid schema {invalid!r} must be rejected")


def test_step9_constants_keep_native_storage_and_forecast_contracts():
    const = (ROOT / "custom_components/dummy_os_data/const.py").read_text()
    assert "STORAGE_VERSION = 1" in const
    assert 'STORAGE_KEY = f"{DOMAIN}.home_forecast"' in const
    assert "ENERGY_STORE_SCHEMA_VERSION = 2" in const
    assert "ENERGY_EVALUATION_SCHEMA_VERSION = 1" in const
    assert "PROFILE_CONTRACT_VERSION = 1" in const
    assert 'PROFILE_UNCLASSIFIED = "unclassified"' in const
    assert 'PROFILE_MIXED = "mixed"' in const
    assert "QUARTER_MINUTES = 15" in const
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const
    assert "MIN_VALID_COVERAGE = 0.90" in const


def test_coordinator_uses_versioned_energy_store_and_profile_contract():
    coordinator = (ROOT / "custom_components/dummy_os_data/coordinator.py").read_text()
    assert "ENERGY_STORE_SCHEMA_VERSION" in coordinator
    assert "ENERGY_EVALUATION_SCHEMA_VERSION" in coordinator
    assert "PROFILE_CONTRACT_VERSION" in coordinator
    assert "normalize_energy_store_payload(" in coordinator
    assert 'default_profile=PROFILE_UNCLASSIFIED' in coordinator
    assert '"energy_store_schema_version": ENERGY_STORE_SCHEMA_VERSION' in coordinator
    assert '"profile_contract_version": PROFILE_CONTRACT_VERSION' in coordinator
    assert '"evaluation_schema_version": ENERGY_EVALUATION_SCHEMA_VERSION' in coordinator
