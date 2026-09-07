from pathlib import Path
import textwrap

# Store defaults
p = Path('custom_components/dummy_os_data/energy_store.py')
t = p.read_text()
old = '    payload.setdefault("evaluations", [])\n    return payload\n'
new = '    payload.setdefault("evaluations", [])\n    payload.setdefault("horizon_pending_probes", {})\n    payload.setdefault("horizon_daily_stats", {})\n    return payload\n'
assert old in t
p.write_text(t.replace(old, new, 1))

# Coordinator persistence/capture/evaluation
p = Path('custom_components/dummy_os_data/coordinator.py')
t = p.read_text()
old = 'from .forecast import ForecastSlot, HomeBaselineForecast\n'
new = old + 'from .horizon_quality import HORIZON_PROBES\n'
assert old in t and 'from .horizon_quality import HORIZON_PROBES' not in t
t = t.replace(old, new, 1)

old = '        self.evaluations: list[dict[str, Any]] = []\n        self.last_quarter: QuarterResult | None = None\n'
new = '        self.evaluations: list[dict[str, Any]] = []\n        self.horizon_pending_probes: dict[str, dict[str, Any]] = {}\n        self.horizon_daily_stats: dict[str, dict[str, Any]] = {}\n        self.last_quarter: QuarterResult | None = None\n'
assert old in t
t = t.replace(old, new, 1)

old = '        self.evaluations = stored.get("evaluations", [])\n        self._prune_records()\n'
new = '        self.evaluations = stored.get("evaluations", [])\n        self.horizon_pending_probes = stored.get("horizon_pending_probes", {})\n        self.horizon_daily_stats = stored.get("horizon_daily_stats", {})\n        self._prune_records()\n'
assert old in t
t = t.replace(old, new, 1)
old = '        self._prune_snapshots()\n        self._prune_evaluations()\n\n        now = dt_util.utcnow()\n'
new = '        self._prune_snapshots()\n        self._prune_evaluations()\n        self._prune_horizon_data()\n\n        now = dt_util.utcnow()\n'
assert old in t
t = t.replace(old, new, 1)

old = '                self._capture_forecast_for_slot_start(\n                    self._quarter_start,\n                    captured_at=boundary_utc,\n                )\n'
new = old + '                self._capture_horizon_probes(\n                    self._quarter_start,\n                    captured_at=boundary_utc,\n                )\n'
assert old in t
t = t.replace(old, new, 1)

old = '        self._evaluate_completed_quarter(result)\n        self._prune_records()\n        self._prune_evaluations()\n'
new = '        self._evaluate_completed_quarter(result)\n        self._evaluate_horizon_completed_quarter(result)\n        self._prune_records()\n        self._prune_evaluations()\n        self._prune_horizon_data()\n'
assert old in t
t = t.replace(old, new, 1)

marker = '    def _store_forecast_snapshot(\n'
assert marker in t
methods = '''    def _capture_horizon_probes(self, slot_start_utc: datetime, captured_at: datetime) -> None:
        """Freeze compact Step 12 probes from the existing 288-slot production forecast."""
        if self.profile not in PROFILE_LEARNING_OPTIONS:
            return
        target_start = dt_util.as_utc(slot_start_utc)
        just_before = target_start - timedelta(microseconds=1)
        slots = HomeBaselineForecast(self.records).build(self.profile, now=just_before)
        if len(slots) != 288 or slots[0].start != target_start:
            _LOGGER.warning("Skipping Step 12 horizon capture: invalid native forecast shape")
            return
        captured_iso = dt_util.as_utc(captured_at).isoformat()
        for _key, offset, horizon_minutes, semantics in HORIZON_PROBES:
            slot = slots[offset]
            if slot.energy_kwh is None:
                continue
            probe_key = f"{slot.start.isoformat()}|{horizon_minutes}|{self.profile}"
            self.horizon_pending_probes[probe_key] = {
                "target_start": slot.start.isoformat(),
                "target_end": slot.end.isoformat(),
                "captured_at": captured_iso,
                "profile": self.profile,
                "horizon_minutes": horizon_minutes,
                "target_semantics": semantics,
                "forecast_kwh": slot.energy_kwh,
                "source": slot.source,
                "sample_count": slot.sample_count,
                "confidence": slot.confidence,
                "model": "historical_baseline",
                "model_version": "0.4",
            }

    def _horizon_bucket(self, probe: dict[str, Any], result: QuarterResult) -> dict[str, Any]:
        local_date = dt_util.as_local(result.start).date().isoformat()
        horizon_minutes = int(probe["horizon_minutes"])
        profile = str(probe["profile"])
        key = f"{profile}|{local_date}|{horizon_minutes}"
        return self.horizon_daily_stats.setdefault(
            key,
            {
                "profile": profile,
                "local_date": local_date,
                "horizon_minutes": horizon_minutes,
                "sample_count": 0,
                "sum_abs_error_kwh": 0.0,
                "sum_error_kwh": 0.0,
                "sum_actual_kwh": 0.0,
                "sum_forecast_kwh": 0.0,
                "sum_confidence": 0.0,
                "source_counts": {},
                "excluded_record_counts": {},
            },
        )

    @staticmethod
    def _increment_horizon_exclusion(bucket: dict[str, Any], reason: str) -> None:
        excluded = bucket.setdefault("excluded_record_counts", {})
        excluded[reason] = int(excluded.get(reason, 0) or 0) + 1

    def _evaluate_horizon_completed_quarter(self, result: QuarterResult) -> None:
        """Evaluate all Step 12 probes whose target is this completed quarter."""
        target = result.start.isoformat()
        matches = [key for key, probe in self.horizon_pending_probes.items() if probe.get("target_start") == target]
        for key in matches:
            probe = self.horizon_pending_probes.pop(key)
            try:
                bucket = self._horizon_bucket(probe, result)
            except (KeyError, TypeError, ValueError):
                continue
            if result.profile in {PROFILE_UNCLASSIFIED, PROFILE_MIXED}:
                self._increment_horizon_exclusion(bucket, "unclassified_or_mixed")
                continue
            if result.profile != probe.get("profile"):
                self._increment_horizon_exclusion(bucket, "profile_mismatch")
                continue
            if not result.measurement_valid:
                self._increment_horizon_exclusion(bucket, "insufficient_coverage")
                continue
            if not result.learning_valid or result.energy_kwh is None:
                self._increment_horizon_exclusion(bucket, "invalid_actual")
                continue
            try:
                forecast_kwh = float(probe["forecast_kwh"])
                confidence = float(probe.get("confidence", 0.0))
                captured_at = datetime.fromisoformat(str(probe["captured_at"]))
            except (KeyError, TypeError, ValueError):
                self._increment_horizon_exclusion(bucket, "malformed_snapshot")
                continue
            if captured_at.tzinfo is None:
                self._increment_horizon_exclusion(bucket, "malformed_snapshot")
                continue
            if dt_util.as_utc(captured_at) > dt_util.as_utc(result.start):
                self._increment_horizon_exclusion(bucket, "late_capture")
                continue
            error = forecast_kwh - result.energy_kwh
            bucket["sample_count"] = int(bucket.get("sample_count", 0) or 0) + 1
            bucket["sum_abs_error_kwh"] = float(bucket.get("sum_abs_error_kwh", 0.0) or 0.0) + abs(error)
            bucket["sum_error_kwh"] = float(bucket.get("sum_error_kwh", 0.0) or 0.0) + error
            bucket["sum_actual_kwh"] = float(bucket.get("sum_actual_kwh", 0.0) or 0.0) + result.energy_kwh
            bucket["sum_forecast_kwh"] = float(bucket.get("sum_forecast_kwh", 0.0) or 0.0) + forecast_kwh
            bucket["sum_confidence"] = float(bucket.get("sum_confidence", 0.0) or 0.0) + confidence
            source = str(probe.get("source") or "unknown")
            sources = bucket.setdefault("source_counts", {})
            sources[source] = int(sources.get(source, 0) or 0) + 1

    def _prune_horizon_data(self) -> None:
        """Keep pending probes briefly and daily evidence for the normal 400-day window."""
        now = dt_util.utcnow()
        pending_cutoff = now - timedelta(days=4)
        kept_pending: dict[str, dict[str, Any]] = {}
        for key, probe in self.horizon_pending_probes.items():
            try:
                target_end = datetime.fromisoformat(str(probe["target_end"]))
            except (KeyError, TypeError, ValueError):
                continue
            if target_end.tzinfo is None:
                continue
            if dt_util.as_utc(target_end) >= pending_cutoff:
                kept_pending[key] = probe
        self.horizon_pending_probes = kept_pending

        date_cutoff = dt_util.as_local(now - timedelta(days=MAX_HISTORY_DAYS)).date()
        kept_stats: dict[str, dict[str, Any]] = {}
        for key, bucket in self.horizon_daily_stats.items():
            try:
                local_date = datetime.fromisoformat(str(bucket["local_date"])).date()
            except (KeyError, TypeError, ValueError):
                continue
            if local_date >= date_cutoff:
                kept_stats[key] = bucket
        self.horizon_daily_stats = kept_stats

'''
t = t.replace(marker, methods + marker, 1)

old = '                "evaluations": self.evaluations,\n            }\n'
new = '                "evaluations": self.evaluations,\n                "horizon_pending_probes": self.horizon_pending_probes,\n                "horizon_daily_stats": self.horizon_daily_stats,\n            }\n'
assert old in t
t = t.replace(old, new, 1)
p.write_text(t)

# Sensor
p = Path('custom_components/dummy_os_data/home_input_sensor.py')
t = p.read_text()
old = 'from .meaningful_confidence import calculate_meaningful_confidence\n'
new = old + 'from .horizon_quality import calculate_horizon_quality\n'
assert old in t and 'calculate_horizon_quality' not in t
t = t.replace(old, new, 1)
marker = '\n\ndef build_home_input_sensors(\n'
assert marker in t
cls = '''

class DummyOSEnergyForecastQualityByHorizonSensor(SensorEntity):
    """Observer-only Step 12 quality by forecast horizon."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_name = "DO Energy Forecast Quality by Horizon"
    _attr_unique_id = "do_energy_forecast_quality_by_horizon"
    _attr_suggested_object_id = "do_energy_forecast_quality_by_horizon"
    _attr_icon = "mdi:timeline-clock-outline"
    _unrecorded_attributes = frozenset({"horizons"})

    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        self.coordinator = coordinator
        self._remove_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, "main")}, name=NAME, manufacturer="Dummy OS", model="Forecast Platform", sw_version=VERSION)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self.coordinator.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    def _result(self) -> dict[str, Any]:
        return calculate_horizon_quality(self.coordinator.horizon_daily_stats, self.coordinator.profile)

    @property
    def native_value(self) -> str:
        return str(self._result()["status"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._result())
'''
t = t.replace(marker, cls + marker, 1)
old = '    entities.append(DummyOSEnergyMeaningfulConfidenceSensor(coordinator))\n    return entities\n'
new = '    entities.append(DummyOSEnergyMeaningfulConfidenceSensor(coordinator))\n    entities.append(DummyOSEnergyForecastQualityByHorizonSensor(coordinator))\n    return entities\n'
assert old in t
p.write_text(t.replace(old, new, 1))

# Migration aliases
p = Path('custom_components/dummy_os_data/entity_migrations.py')
t = p.read_text()
old = '    "do_energy_meaningful_confidence": "sensor.dummy_os_forecast_do_energy_meaningful_confidence",\n'
new = old + '    "do_energy_forecast_quality_by_horizon": "sensor.dummy_os_forecast_do_energy_forecast_quality_by_horizon",\n'
assert old in t and 'do_energy_forecast_quality_by_horizon' not in t
p.write_text(t.replace(old, new, 1))

p = Path('custom_components/dummy_os_data/__init__.py')
t = p.read_text()
old = '    ("sensor", "do_energy_meaningful_confidence", "sensor.do_energy_meaningful_confidence"),\n'
new = old + '    ("sensor", "do_energy_forecast_quality_by_horizon", "sensor.do_energy_forecast_quality_by_horizon"),\n'
assert old in t and 'do_energy_forecast_quality_by_horizon' not in t
p.write_text(t.replace(old, new, 1))

Path('tests/test_horizon_quality.py').write_text('''from importlib.util import module_from_spec, spec_from_file_location\nfrom pathlib import Path\n\nROOT = Path(__file__).parents[1]\nPATH = ROOT / "custom_components/dummy_os_data/horizon_quality.py"\nSPEC = spec_from_file_location("horizon_quality", PATH)\nassert SPEC is not None and SPEC.loader is not None\nMODULE = module_from_spec(SPEC)\nSPEC.loader.exec_module(MODULE)\n\ndef test_fixed_native_horizon_set_and_72h_edge_semantics():\n    assert [probe[2] for probe in MODULE.HORIZON_PROBES] == [0, 60, 180, 360, 720, 1440, 2880, 4305]\n    assert MODULE.HORIZON_PROBES[-1][1] == 287\n    assert MODULE.HORIZON_PROBES[-1][3] == "last_native_slot_ends_plus_72h"\n\ndef test_daily_stats_aggregate_without_reconstructing_missing_as_zero():\n    stats = {"normal|2026-09-01|60": {"profile": "normal", "local_date": "2026-09-01", "horizon_minutes": 60, "sample_count": 2, "sum_abs_error_kwh": 0.10, "sum_error_kwh": 0.02, "sum_actual_kwh": 0.40, "sum_forecast_kwh": 0.42, "sum_confidence": 1.4, "source_counts": {"weekday_quarter": 2}, "excluded_record_counts": {"profile_mismatch": 1}}}\n    h1 = MODULE.calculate_horizon_quality(stats, "normal")["horizons"]["h01"]\n    assert h1["sample_count"] == 2\n    assert h1["mae_kwh"] == 0.05\n    assert h1["bias_kwh"] == 0.01\n    assert h1["mean_captured_confidence"] == 0.7\n    assert h1["excluded_record_counts"]["profile_mismatch"] == 1\n\ndef test_unclassified_is_inactive_and_never_borrows_normal():\n    result = MODULE.calculate_horizon_quality({}, "unclassified")\n    assert result["status"] == "inactive_profile"\n    assert result["observer_only"] is True\n    assert result["forecast_influence_enabled"] is False\n''')

Path('tests/test_horizon_quality_sensor_contract.py').write_text('''from pathlib import Path\n\nROOT = Path(__file__).parents[1]\nSOURCE = (ROOT / "custom_components/dummy_os_data/home_input_sensor.py").read_text()\nINIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()\nMIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text()\nCOORDINATOR = (ROOT / "custom_components/dummy_os_data/coordinator.py").read_text()\nSTORE = (ROOT / "custom_components/dummy_os_data/energy_store.py").read_text()\nFORECAST = (ROOT / "custom_components/dummy_os_data/forecast.py").read_text()\n\ndef test_step12_sensor_identity_and_registry_route():\n    assert '_attr_unique_id = "do_energy_forecast_quality_by_horizon"' in SOURCE\n    assert '_attr_suggested_object_id = "do_energy_forecast_quality_by_horizon"' in SOURCE\n    assert 'DummyOSEnergyForecastQualityByHorizonSensor(coordinator)' in SOURCE\n    assert '("sensor", "do_energy_forecast_quality_by_horizon", "sensor.do_energy_forecast_quality_by_horizon")' in INIT\n    assert '"do_energy_forecast_quality_by_horizon": "sensor.dummy_os_forecast_do_energy_forecast_quality_by_horizon"' in MIGRATIONS\n\ndef test_step12_store_and_capture_are_observer_only_extensions():\n    assert 'payload.setdefault("horizon_pending_probes", {})' in STORE\n    assert 'payload.setdefault("horizon_daily_stats", {})' in STORE\n    assert 'self._capture_horizon_probes(' in COORDINATOR\n    assert 'self._evaluate_horizon_completed_quarter(result)' in COORDINATOR\n    assert '"horizon_pending_probes": self.horizon_pending_probes' in COORDINATOR\n    assert '"horizon_daily_stats": self.horizon_daily_stats' in COORDINATOR\n\ndef test_production_forecast_contract_remains_native_288():\n    assert 'for offset in range(FORECAST_SLOTS):' in FORECAST\n    assert 'RECENCY_HALF_LIFE_DAYS = 28.0' in FORECAST\n    assert 'horizon_quality' not in FORECAST\n''')
