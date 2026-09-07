from pathlib import Path

path = Path("custom_components/dummy_os_data/sensor.py")
text = path.read_text()

needle = "from .forecast import HomeBaselineForecast\n"
replacement = (
    "from .forecast import HomeBaselineForecast\n"
    "from .horizon_quality import calculate_horizon_quality\n"
    "from .model_health import calculate_model_health_readiness\n"
)
if needle not in text:
    raise SystemExit("forecast import anchor missing")
text = text.replace(needle, replacement, 1)

start = text.index("class DummyOSHomeForecastModelHealthSensor(DummyOSBaseSensor):")
end = text.index("\n\nclass DummyOSEvaluationBaseSensor", start)
new_block = '''class DummyOSHomeForecastModelHealthSensor(DummyOSBaseSensor):
    _attr_name = "DO Energy Forecast Model Health"
    _attr_unique_id = "do_energy_forecast_model_health"
    _attr_suggested_object_id = "do_energy_forecast_model_health"
    _attr_icon = "mdi:heart-pulse"

    def _readiness(self) -> dict[str, Any]:
        slots = self._forecast()
        supported = sum(1 for slot in slots if slot.source in SUPPORTED_SOURCES)
        coverage = round(supported / len(slots) * 100, 1) if slots else None
        confidence = HomeBaselineForecast.average_confidence(slots)
        metrics = self.coordinator.evaluation_metrics(self.coordinator.profile)
        horizon_quality = calculate_horizon_quality(
            self.coordinator.horizon_daily_stats,
            self.coordinator.profile,
        )
        day_type_daypart_quality = calculate_day_type_daypart_quality(
            self.coordinator.evaluations,
            self.coordinator.records,
            self.coordinator.profile,
            dt_util.as_local,
        )
        hour_quality = calculate_hour_quality(
            self.coordinator.evaluations,
            self.coordinator.records,
            self.coordinator.profile,
            dt_util.as_local,
        )
        return calculate_model_health_readiness(
            records=self.coordinator.records,
            profile=self.coordinator.profile,
            source_available=self.coordinator.source_available,
            forecast_coverage_percent=coverage,
            average_confidence_percent=confidence,
            evaluation_metrics=metrics,
            horizon_quality=horizon_quality,
            day_type_daypart_quality=day_type_daypart_quality,
            hour_quality=hour_quality,
            localize=dt_util.as_local,
        )

    @property
    def native_value(self) -> str:
        if not self._profile_learnable:
            return "profile_unclassified"
        return str(self._readiness()["readiness_status"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._readiness())
'''
text = text[:start] + new_block + text[end:]
path.write_text(text)
