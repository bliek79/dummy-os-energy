"""Versioned persistence helpers for Dummy OS Energy Forecast."""

from __future__ import annotations

from typing import Any, Iterable


class UnsupportedEnergyStoreSchema(ValueError):
    """Raised when persisted Energy data uses an unsupported schema."""


def normalize_energy_store_payload(
    stored: dict[str, Any] | None,
    *,
    current_schema_version: int,
    default_profile: str,
    valid_profiles: Iterable[str] | None = None,
    profile_contract_version: int = 1,
) -> dict[str, Any]:
    """Return a normalized Energy store payload without mutating the input.

    Payloads written before explicit schema versioning are treated as legacy
    schema 0 and upgraded in memory. Future schema versions are rejected so an
    older integration can never silently overwrite newer persisted data.

    Step 9 adds an explicit safe profile contract. Missing or invalid persisted
    profile values resolve to ``default_profile`` (the coordinator passes
    ``unclassified``) instead of silently becoming ``normal``.
    """
    payload = dict(stored or {})
    raw_version = payload.get("energy_store_schema_version", 0)
    if isinstance(raw_version, bool) or not isinstance(raw_version, int):
        raise UnsupportedEnergyStoreSchema(
            f"Invalid Energy store schema version: {raw_version!r}"
        )
    if raw_version < 0 or raw_version > current_schema_version:
        raise UnsupportedEnergyStoreSchema(
            "Unsupported Energy store schema version "
            f"{raw_version}; supported through {current_schema_version}"
        )

    allowed_profiles = set(valid_profiles or ())
    profile = payload.get("profile")
    if not isinstance(profile, str) or (allowed_profiles and profile not in allowed_profiles):
        profile = default_profile

    payload["energy_store_schema_version"] = current_schema_version
    payload["profile_contract_version"] = profile_contract_version
    payload["profile"] = profile
    payload.setdefault("previous_profile", None)
    payload.setdefault("profile_changed_at", None)
    payload.setdefault("profile_change_source", "legacy_migration" if stored else "initial_default")
    payload.setdefault("records", [])
    payload.setdefault("forecast_snapshots", {})
    payload.setdefault("evaluations", [])
    return payload
