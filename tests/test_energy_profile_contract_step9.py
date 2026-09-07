from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text()


def test_profile_contract_constants_are_explicit_and_native_shape_is_unchanged():
    const = _source("custom_components/dummy_os_data/const.py")
    assert 'PROFILE_NORMAL = "normal"' in const
    assert 'PROFILE_AWAY = "away"' in const
    assert 'PROFILE_UNCLASSIFIED = "unclassified"' in const
    assert 'PROFILE_MIXED = "mixed"' in const
    assert "PROFILE_LEARNING_OPTIONS = [PROFILE_NORMAL, PROFILE_AWAY]" in const
    assert "PROFILE_OPTIONS = [PROFILE_NORMAL, PROFILE_AWAY, PROFILE_UNCLASSIFIED]" in const
    assert "PROFILE_CONTRACT_VERSION = 1" in const
    assert "QUARTER_MINUTES = 15" in const
    assert "FORECAST_HORIZON_HOURS = 72" in const
    assert "FORECAST_SLOTS = FORECAST_HORIZON_HOURS * 60 // QUARTER_MINUTES" in const


def test_profile_select_exposes_single_canonical_contract_entity():
    select = _source("custom_components/dummy_os_data/select.py")
    assert '_attr_unique_id = "do_energy_profile"' in select
    assert '_attr_suggested_object_id = "do_energy_profile"' in select
    assert "_attr_options = PROFILE_OPTIONS" in select
    assert '"profile_contract_version": PROFILE_CONTRACT_VERSION' in select
    assert '"profile_resolved": learning_enabled' in select
    assert '"previous_profile": self.coordinator.previous_profile' in select
    assert 'source="manual_select"' in select


def test_store_restore_never_silently_defaults_to_normal():
    coordinator = _source("custom_components/dummy_os_data/coordinator.py")
    store = _source("custom_components/dummy_os_data/energy_store.py")
    assert "default_profile=PROFILE_UNCLASSIFIED" in coordinator
    assert "valid_profiles=PROFILE_OPTIONS" in coordinator
    assert 'profile = payload.get("profile")' in store
    assert "profile = default_profile" in store
    assert "payload[\"profile_contract_version\"] = profile_contract_version" in store


def test_quarter_measurement_and_learning_validity_are_separate():
    coordinator = _source("custom_components/dummy_os_data/coordinator.py")
    assert "measurement_valid = coverage >= MIN_VALID_COVERAGE" in coordinator
    assert "learning_valid = (" in coordinator
    assert "and final_profile in PROFILE_LEARNING_OPTIONS" in coordinator
    assert 'learning_blocker = "profile_changed"' in coordinator
    assert 'learning_blocker = "profile_unclassified"' in coordinator
    assert "energy_kwh = self._energy_ws / 3_600_000 if measurement_valid else None" in coordinator
    assert '"measurement_valid": result.measurement_valid' in coordinator
    assert '"learning_valid": result.learning_valid' in coordinator
    assert '"valid": result.valid' in coordinator


def test_profile_change_catches_up_boundary_before_integrating_current_quarter():
    coordinator = _source("custom_components/dummy_os_data/coordinator.py")
    start = coordinator.index("async def async_set_profile")
    end = coordinator.index("async def _async_save", start)
    block = coordinator[start:end]
    catch_up = block.index("await self._advance_through_elapsed_boundaries(now_utc)")
    integrate = block.index("self._integrate_until(now_utc)")
    assert catch_up < integrate
    assert "at_quarter_start" in block
    assert "self._quarter_profile = profile" in block
    assert "self._profile_changed_in_quarter = True" in block
    assert "if profile == self.profile:\n            return" in block


def test_unclassified_forecast_keeps_288_slots_without_borrowing_history():
    forecast = _source("custom_components/dummy_os_data/forecast.py")
    assert "if profile not in PROFILE_LEARNING_OPTIONS:" in forecast
    assert "return exact, day_type, quarter, all_values" in forecast
    assert 'source = "profile_unclassified" if profile not in PROFILE_LEARNING_OPTIONS else "unavailable"' in forecast
    assert "slot_count: int = FORECAST_SLOTS" in forecast
    assert "for offset in range(slot_count):" in forecast


def test_actual_quarter_keeps_measured_energy_when_learning_is_blocked():
    sensor = _source("custom_components/dummy_os_data/sensor.py")
    start = sensor.index("class DummyOSActualQuarterSensor")
    end = sensor.index("class DummyOSHistoryStatusSensor", start)
    block = sensor[start:end]
    assert "result.energy_kwh if result and result.measurement_valid else None" in block
    assert '"measurement_valid": result.measurement_valid' in block
    assert '"learning_valid": result.learning_valid' in block
    assert '"learning_blocker": result.learning_blocker' in block


def test_observers_are_blocked_for_unclassified_profile():
    sensor = _source("custom_components/dummy_os_data/sensor.py")
    assert sensor.count('"profile_unclassified"') >= 8
    assert 'return "profile_unclassified"' in sensor
    assert '"status": "blocked"' in sensor


def test_alpha1218_fast_source_runtime_gate_is_still_preserved():
    coordinator = _source("custom_components/dummy_os_data/coordinator.py")
    start = coordinator.index("def _async_source_changed")
    end = coordinator.index("@staticmethod", start)
    block = coordinator[start:end]
    assert "self._integrate_until(now)" in block
    assert "self._notify()" not in block
