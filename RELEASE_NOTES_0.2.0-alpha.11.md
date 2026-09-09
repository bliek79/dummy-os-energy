# GitHub Release

**Tag:** `0.2.0-alpha.11`  
**Release title:** Dummy OS Energy 0.2.0-alpha.11 - Evaluation Metrics Main-Thread Fix

## Dummy OS Energy 0.2.0-alpha.11

Deze prerelease lost uitsluitend de resterende gedeelde evaluation-metrics main-threadbelasting op die onder alpha.10 zichtbaar werd via `sensor.do_energy_forecast_accuracy` (0,469 s).

### Opgelost
- De gedeelde `DummyOSEvaluationBaseSensor` berekent evaluation metrics niet langer synchronisch tijdens entity state updates.
- Accuracy, MAE, Bias en Evaluation Samples gebruiken nu dezelfde executor-backed cachelaag.
- Overlappende refreshes worden samengevoegd; state/attributen lezen uitsluitend het laatst voltooide resultaat.

### Bewust ongewijzigd
- forecastformules en evaluationformules;
- entity-ID's/namen van Accuracy, MAE, Bias en Evaluation Samples;
- native 15 minuten / 72 uur / exact 288 slots;
- Planner Stap 1 t/m 4;
- reserve-/SOC-, prijs- en solarcontracten;
- `shadow_only=true`, `active_use_permitted=false`, `physical_execution_authority=false`;
- geen Planner Stap 5-functionaliteit.

### Live-validatie
Na installatie en volledige Home Assistant-herstart de volledige startup/update-log controleren op alle `dummy_os_data` main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze gate schoon is.
