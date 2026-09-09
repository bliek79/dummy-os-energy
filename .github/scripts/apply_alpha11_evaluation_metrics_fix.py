from pathlib import Path
import json

VERSION = "0.2.0-alpha.11"
PREVIOUS = "0.2.0-alpha.10"


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing expected block: {label}")
    return text.replace(old, new, 1)

sensor_path = Path('custom_components/dummy_os_data/sensor.py')
sensor = sensor_path.read_text()
old = '''class DummyOSEvaluationBaseSensor(DummyOSBaseSensor):
    @property
    def _metrics(self) -> dict[str, Any]:
        return self.coordinator.evaluation_metrics(self.coordinator.profile)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        metrics = self._metrics
        return {"profile": self.coordinator.profile, "samples": metrics["samples"], "actual_total_kwh": metrics["actual_total_kwh"], "forecast_total_kwh": metrics["forecast_total_kwh"], "evaluation_scope": "active_profile", "resolution_minutes": 15}
'''
new = '''class DummyOSEvaluationBaseSensor(DummyOSBaseSensor):
    """Executor-backed shared evaluation metrics cache."""

    def __init__(self, coordinator: DummyOSHomeDataCoordinator) -> None:
        super().__init__(coordinator)
        self._cached_metrics: dict[str, Any] | None = None
        self._refresh_task = None
        self._refresh_pending = False

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
        self._refresh_task = self.hass.async_create_task(self._async_refresh_metrics())

    async def _async_refresh_metrics(self) -> None:
        while True:
            self._refresh_pending = False
            evaluations = list(self.coordinator.evaluations)
            profile = self.coordinator.profile
            self._cached_metrics = await self.hass.async_add_executor_job(
                calculate_metrics, evaluations, profile
            )
            self.async_write_ha_state()
            if not self._refresh_pending:
                return

    @property
    def _metrics(self) -> dict[str, Any]:
        return self._cached_metrics or {
            "samples": 0,
            "accuracy_percent": None,
            "mae_kwh": None,
            "bias_kwh": None,
            "actual_total_kwh": 0.0,
            "forecast_total_kwh": 0.0,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        metrics = self._metrics
        return {"profile": self.coordinator.profile, "samples": metrics["samples"], "actual_total_kwh": metrics["actual_total_kwh"], "forecast_total_kwh": metrics["forecast_total_kwh"], "evaluation_scope": "active_profile", "resolution_minutes": 15}
'''
sensor = replace_once(sensor, old, new, 'evaluation base async cache')
sensor_path.write_text(sensor)

for path in ['custom_components/dummy_os_data/const.py', 'tests/test_release_consistency.py']:
    p=Path(path); t=p.read_text(); t=replace_once(t, f'VERSION = "{PREVIOUS}"', f'VERSION = "{VERSION}"', path); p.write_text(t)
p=Path('custom_components/dummy_os_data/manifest.json'); data=json.loads(p.read_text());
if data.get('version') != PREVIOUS: raise SystemExit('unexpected manifest version')
data['version']=VERSION; p.write_text(json.dumps(data, indent=2)+'\n')

Path('tests/test_pre_step5_evaluation_metrics_main_thread_fix.py').write_text('''from pathlib import Path\n\nROOT = Path(__file__).parents[1]\n\ndef test_evaluation_family_uses_executor_backed_shared_base():\n    sensor=(ROOT/"custom_components/dummy_os_data/sensor.py").read_text()\n    start=sensor.index("class DummyOSEvaluationBaseSensor(DummyOSBaseSensor):")\n    end=sensor.index("\\n\\nclass DummyOSWeatherBaseSensor", start)\n    block=sensor[start:end]\n    assert "async_add_executor_job" in block\n    assert "calculate_metrics, evaluations, profile" in block\n    assert "self._cached_metrics" in block\n    assert "self.coordinator.evaluation_metrics" not in block\n    for cls in ("DummyOSHomeForecastAccuracySensor", "DummyOSHomeForecastMaeSensor", "DummyOSHomeForecastBiasSensor", "DummyOSHomeForecastEvaluationSamplesSensor"):\n        assert f"class {cls}(DummyOSEvaluationBaseSensor):" in block\n    for uid in ("do_energy_forecast_accuracy", "do_energy_forecast_mae", "do_energy_forecast_bias", "do_energy_forecast_evaluation_samples"):\n        assert uid in block\n\ndef test_safety_invariants_remain_unchanged():\n    preview=(ROOT/"custom_components/dummy_os_data/do_plan_preview.py").read_text()\n    assert '\"shadow_only\": True' in preview\n    assert '\"active_use_permitted\": False' in preview\n    assert '\"physical_execution_authority\": False' in preview\n''')

notes='''# GitHub Release\n\n**Tag:** `0.2.0-alpha.11`  \n**Release title:** Dummy OS Energy 0.2.0-alpha.11 - Evaluation Metrics Main-Thread Fix\n\n## Dummy OS Energy 0.2.0-alpha.11\n\nDeze prerelease lost uitsluitend de resterende gedeelde evaluation-metrics main-threadbelasting op die onder alpha.10 zichtbaar werd via `sensor.do_energy_forecast_accuracy` (0,469 s).\n\n### Opgelost\n- De gedeelde `DummyOSEvaluationBaseSensor` berekent evaluation metrics niet langer synchronisch tijdens entity state updates.\n- Accuracy, MAE, Bias en Evaluation Samples gebruiken nu dezelfde executor-backed cachelaag.\n- Overlappende refreshes worden samengevoegd; state/attributen lezen uitsluitend het laatst voltooide resultaat.\n\n### Bewust ongewijzigd\n- forecastformules en evaluationformules;\n- entity-ID's/namen van Accuracy, MAE, Bias en Evaluation Samples;\n- native 15 minuten / 72 uur / exact 288 slots;\n- Planner Stap 1 t/m 4;\n- reserve-/SOC-, prijs- en solarcontracten;\n- `shadow_only=true`, `active_use_permitted=false`, `physical_execution_authority=false`;\n- geen Planner Stap 5-functionaliteit.\n\n### Live-validatie\nNa installatie en volledige Home Assistant-herstart de volledige startup/update-log controleren op alle `dummy_os_data` main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze gate schoon is.\n'''
Path(f'RELEASE_NOTES_{VERSION}.md').write_text(notes)
h=Path('RELEASE_NOTES.md'); cur=h.read_text();
if f'**Tag:** `{VERSION}`' in cur: raise SystemExit('release notes already present')
h.write_text(notes+'\n---\n'+cur)
