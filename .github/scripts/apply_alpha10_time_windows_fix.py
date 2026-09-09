from pathlib import Path
import json

VERSION = "0.2.0-alpha.10"
PREVIOUS = "0.2.0-alpha.9"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing expected block: {label}")
    return text.replace(old, new, 1)


sensor_path = Path("custom_components/dummy_os_data/sensor.py")
sensor = sensor_path.read_text()
start = sensor.index("class DummyOSEnergyTimeWindowsSensor(DummyOSBaseSensor):")
end = sensor.index("\n\nclass DummyOSEnergyRecencyWeightingSensor", start)

new_block = '''class DummyOSEnergyTimeWindowsSensor(DummyOSBaseSensor):
    """Observer-only Step 7 Energy Time Windows diagnostics."""

    _attr_name = "DO Energy Time Windows"
    _attr_unique_id = "do_energy_time_windows"
    _attr_suggested_object_id = "do_energy_time_windows"
    _attr_icon = "mdi:timeline-clock-outline"

    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        super().__init__(coordinator)
        self._cached_result: dict[str, Any] | None = None
        self._refresh_task = None
        self._refresh_pending = False

    @property
    def name(self) -> str:
        """Return the canonical runtime name used for friendly_name."""
        return "DO Energy Time Windows"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_refresh()

    async def async_will_remove_from_hass(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self._schedule_refresh()

    @callback
    def _schedule_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_pending = True
            return
        self._refresh_task = self.hass.async_create_task(self._async_refresh_result())

    async def _async_refresh_result(self) -> None:
        while True:
            self._refresh_pending = False
            evaluations = list(self.coordinator.evaluations)
            profile = self.coordinator.profile
            result = await self.hass.async_add_executor_job(
                self._calculate_result, evaluations, profile
            )
            self._cached_result = result
            self.async_write_ha_state()
            if not self._refresh_pending:
                return

    @staticmethod
    def _empty_result(profile: str, *, status: str, blocker: str) -> dict[str, Any]:
        classification_source = "profile_unclassified" if blocker == "profile_unclassified" else "calculation_pending"
        return {
            "schema_version": "7b.1",
            "algorithm_version": "time_windows_observer_v1",
            "profile": profile,
            "context_key": f"{profile}|{classification_source}",
            "classification_source": classification_source,
            "observer_only": True,
            "forecast_influence_enabled": False,
            "ready_for_live_observation": False,
            "ready_for_forecast_influence": False,
            "event_count": 0,
            "event_days": 0,
            "rejected_event_count": 0,
            "reject_reasons": {},
            "window_start": None,
            "window_end": None,
            "window_width_minutes": None,
            "window_quarter_count": None,
            "p10_start_minute": None,
            "p90_end_minute": None,
            "median_center_minute": None,
            "center_mad_minutes": None,
            "contained_day_count": None,
            "contained_day_ratio": None,
            "median_event_duration_minutes": None,
            "median_daily_energy_kwh": None,
            "energy_iqr_kwh": None,
            "lodo_max_start_shift_minutes": None,
            "lodo_max_end_shift_minutes": None,
            "early_late_start_shift_minutes": None,
            "early_late_end_shift_minutes": None,
            "protected_window_overlap": False,
            "native_resolution_minutes": 15,
            "calibration_method": "daily_representative_p10_start_p90_end",
            "minimum_event_days_collecting_exit": 8,
            "minimum_event_days_calibrated": 12,
            "minimum_event_days_stable": 16,
            "maximum_boundary_shift_minutes": 15,
            "source_basis": {},
            "calibration_fingerprint": None,
            "blockers": [blocker],
            "status": status,
        }

    def _calculate_result(
        self, evaluations: list[dict[str, Any]], profile: str
    ) -> dict[str, Any]:
        if profile not in PROFILE_LEARNING_OPTIONS:
            return self._empty_result(
                profile, status="blocked", blocker="profile_unclassified"
            )
        peak_result = calculate_peak_learning(evaluations, profile, dt_util.as_local)
        return calculate_time_windows(peak_result, profile, dt_util.as_local)

    def _result(self) -> dict[str, Any]:
        return self._cached_result or self._empty_result(
            self.coordinator.profile,
            status="initializing",
            blocker="observer_calculation_pending",
        )

    @property
    def native_value(self) -> str:
        return str(self._result()["status"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._result()
        return {
            "schema_version": result["schema_version"],
            "algorithm_version": result["algorithm_version"],
            "profile": result["profile"],
            "context_key": result["context_key"],
            "classification_source": result["classification_source"],
            "observer_only": result["observer_only"],
            "forecast_influence_enabled": result["forecast_influence_enabled"],
            "ready_for_live_observation": result["ready_for_live_observation"],
            "ready_for_forecast_influence": result["ready_for_forecast_influence"],
            "event_count": result["event_count"],
            "event_days": result["event_days"],
            "rejected_event_count": result["rejected_event_count"],
            "reject_reasons": result["reject_reasons"],
            "window_start": result["window_start"],
            "window_end": result["window_end"],
            "window_width_minutes": result["window_width_minutes"],
            "window_quarter_count": result["window_quarter_count"],
            "p10_start_minute": result["p10_start_minute"],
            "p90_end_minute": result["p90_end_minute"],
            "median_center_minute": result["median_center_minute"],
            "center_mad_minutes": result["center_mad_minutes"],
            "contained_day_count": result["contained_day_count"],
            "contained_day_ratio": result["contained_day_ratio"],
            "median_event_duration_minutes": result["median_event_duration_minutes"],
            "median_daily_energy_kwh": result["median_daily_energy_kwh"],
            "energy_iqr_kwh": result["energy_iqr_kwh"],
            "lodo_max_start_shift_minutes": result["lodo_max_start_shift_minutes"],
            "lodo_max_end_shift_minutes": result["lodo_max_end_shift_minutes"],
            "early_late_start_shift_minutes": result["early_late_start_shift_minutes"],
            "early_late_end_shift_minutes": result["early_late_end_shift_minutes"],
            "protected_window_overlap": result["protected_window_overlap"],
            "native_resolution_minutes": result["native_resolution_minutes"],
            "calibration_method": result["calibration_method"],
            "minimum_event_days_collecting_exit": result["minimum_event_days_collecting_exit"],
            "minimum_event_days_calibrated": result["minimum_event_days_calibrated"],
            "minimum_event_days_stable": result["minimum_event_days_stable"],
            "maximum_boundary_shift_minutes": result["maximum_boundary_shift_minutes"],
            "source_basis": result["source_basis"],
            "calibration_fingerprint": result["calibration_fingerprint"],
            "blockers": result["blockers"],
        }
'''

sensor = sensor[:start] + new_block + sensor[end:]
sensor_path.write_text(sensor)

const_path = Path("custom_components/dummy_os_data/const.py")
const_text = const_path.read_text()
const_text = replace_once(
    const_text,
    f'VERSION = "{PREVIOUS}"',
    f'VERSION = "{VERSION}"',
    "const version",
)
const_path.write_text(const_text)

manifest_path = Path("custom_components/dummy_os_data/manifest.json")
manifest = json.loads(manifest_path.read_text())
if manifest.get("version") != PREVIOUS:
    raise SystemExit(f'unexpected manifest version: {manifest.get("version")}')
manifest["version"] = VERSION
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

release_test_path = Path("tests/test_release_consistency.py")
release_test = release_test_path.read_text()
release_test = replace_once(
    release_test,
    f'VERSION = "{PREVIOUS}"',
    f'VERSION = "{VERSION}"',
    "release consistency version",
)
release_test_path.write_text(release_test)

Path("tests/test_pre_step5_time_windows_main_thread_fix.py").write_text('''from pathlib import Path\n\nROOT = Path(__file__).parents[1]\n\n\ndef test_time_windows_is_executor_backed_without_identity_change():\n    sensor = (ROOT / "custom_components/dummy_os_data/sensor.py").read_text()\n    start = sensor.index("class DummyOSEnergyTimeWindowsSensor(DummyOSBaseSensor):")\n    end = sensor.index("\\n\\nclass DummyOSEnergyRecencyWeightingSensor", start)\n    block = sensor[start:end]\n    assert '_attr_unique_id = "do_energy_time_windows"' in block\n    assert '_attr_suggested_object_id = "do_energy_time_windows"' in block\n    assert 'return "DO Energy Time Windows"' in block\n    assert "async_add_executor_job" in block\n    assert "self._cached_result" in block\n    assert "self._refresh_pending" in block\n    assert "calculate_peak_learning(evaluations, profile, dt_util.as_local)" in block\n    assert "calculate_time_windows(peak_result, profile, dt_util.as_local)" in block\n    assert "calculate_peak_learning(self.coordinator.evaluations" not in block\n\n\ndef test_time_windows_fix_preserves_safety_invariants():\n    preview = (ROOT / "custom_components/dummy_os_data/do_plan_preview.py").read_text()\n    assert '\"shadow_only\": True' in preview\n    assert '\"active_use_permitted\": False' in preview\n    assert '\"physical_execution_authority\": False' in preview\n''')

notes = '''# GitHub Release\n\n**Tag:** `0.2.0-alpha.10`  \n**Release title:** Dummy OS Energy 0.2.0-alpha.10 - Time Windows Main-Thread Fix\n\n## Dummy OS Energy 0.2.0-alpha.10\n\nDeze prerelease lost uitsluitend de laatste Dummy OS Energy main-threadwaarschuwing uit de live alpha.9-startup op. Planner Stap 5 wordt niet toegevoegd.\n\n### Opgelost\n- `DO Energy Time Windows` voert Peak Learning + Time Windows observerberekening niet langer synchronisch uit tijdens entity state updates.\n- De bestaande observerberekening draait via executor-backed caching met coalescing van overlappende refreshes.\n- `native_value` en `extra_state_attributes` lezen alleen het laatst voltooide cache-resultaat.\n- Tijdens de eerste achtergrondberekening wordt fail-safe `initializing` gepubliceerd met `observer_calculation_pending`.\n\n### Bewust ongewijzigd\n- forecastformules;\n- Time Windows-algoritme en drempels;\n- entity-ID `sensor.do_energy_time_windows`, unique_id en friendly name;\n- native 15 minuten / 72 uur / exact 288 slots;\n- Planner Stap 1 t/m 4;\n- reserve-/SOC-, prijs- en solarcontracten;\n- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false`;\n- unknown/unavailable wordt niet stilzwijgend als nul behandeld;\n- geen Planner Stap 5-functionaliteit.\n\n### Live-validatie na installatie\nNa installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat `sensor.do_energy_time_windows`, die in alpha.9 nog 0,637 s main-threadtijd veroorzaakte, niet meer als main-threadwaarschuwing terugkomt. Daarnaast moet de volledige startup-log worden gecontroleerd op andere nieuwe `dummy_os_data` main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze live gate schoon is.\n'''
Path(f"RELEASE_NOTES_{VERSION}.md").write_text(notes)
history_path = Path("RELEASE_NOTES.md")
history = history_path.read_text()
if f"**Tag:** `{VERSION}`" in history:
    raise SystemExit("alpha.10 release notes already present")
history_path.write_text(notes + "\n---\n" + history)
