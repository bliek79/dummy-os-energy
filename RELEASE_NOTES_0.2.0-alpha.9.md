# GitHub Release

**Tag:** `0.2.0-alpha.9`  
**Release title:** Dummy OS Energy 0.2.0-alpha.9 - Final Pre-Step5 Main-Thread Fix

## Dummy OS Energy 0.2.0-alpha.9

Deze prerelease lost uitsluitend de twee resterende Dummy OS Energy main-threadwaarschuwingen op die na de live alpha.8-validatie overbleven. Planner Stap 5 wordt niet toegevoegd.

### Opgelost
- `DO Energy Forecast Coverage` bouwt de 72-uurs forecast niet langer synchronisch vanuit de entity state-property; de berekening draait via executor-backed caching.
- `DO Energy Peak Learning` voert `calculate_peak_learning(...)` niet langer synchronisch uit tijdens entity state updates; de observerberekening draait via dezelfde executor-backed cachelaag.

### Bewust ongewijzigd
- native 15 minuten / 72 uur / exact 288 slots;
- forecastformules en historical_baseline model 0.4;
- Peak Learning-inhoud, drempels en observer-only betekenis;
- entity-identiteiten;
- Planner Stap 1 t/m 4;
- reserve-/SOC-, prijs- en solarcontracten;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false`;
- unknown/unavailable wordt niet als nul behandeld;
- geen Planner Stap 5-functionaliteit.

### Live-validatie na installatie
Na installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat de twee in alpha.8 gemeten waarschuwingen niet terugkomen voor:
- `sensor.do_energy_forecast_coverage` (0,520 s in alpha.8);
- `sensor.do_energy_peak_learning` (0,451 s in alpha.8).

Daarnaast controleren op nieuwe Dummy OS Energy main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze live gate geslaagd is.
