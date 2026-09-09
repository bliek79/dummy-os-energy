# GitHub Release

**Tag:** `0.2.0-alpha.8`  
**Release title:** Dummy OS Energy 0.2.0-alpha.8 - Remaining Main-Thread Performance Fix

## Dummy OS Energy 0.2.0-alpha.8

Deze prerelease rondt de pre-Step5 main-threadperformancefix af voor de vier resterende startupwaarschuwingen uit de live alpha.7-validatie. Planner Stap 5 wordt niet toegevoegd.

### Opgelost
- `DO Energy Forecast Next Quarter` bouwt de forecast niet langer synchronisch vanuit de entity state-property; de berekening draait via executor-backed caching.
- `DO Energy Forecast Confidence` gebruikt hetzelfde executor-backed cachepatroon.
- De gelijk opgebouwde observer-only qualitysensoren (Daypart, Day Type, Day Type And Daypart en Hour) voeren hun zware kwaliteitsberekeningen buiten de Home Assistant main thread uit en publiceren alleen het laatst voltooide resultaat.
- De Solar Daily-sensoren voor today/tomorrow en north/south/total berekenen hun dagtotalen buiten de main thread en cachen de uitkomst.

### Bewust ongewijzigd
- native 15 minuten / 72 uur / exact 288 slots;
- forecastformules en historical_baseline model 0.4;
- entity-identiteiten;
- Planner Stap 1 t/m 4;
- reserve-/SOC-, prijs- en solarcontracten;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false`;
- unknown/unavailable wordt niet als nul behandeld;
- geen Planner Stap 5-functionaliteit.

### Live-validatie na installatie
Na installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat de vier in alpha.7 gemeten waarschuwingen niet terugkomen voor:
- `sensor.do_energy_forecast_next_quarter` (1,213 s in alpha.7);
- `sensor.do_energy_forecast_confidence` (0,497 s);
- `sensor.do_energy_forecast_quality_by_daypart` (0,413 s);
- `sensor.do_solar_forecast_today_total` (1,123 s).

Daarnaast controleren op nieuwe Dummy OS Energy main-threadwaarschuwingen en bevestigen dat de observer/safetygrenzen ongewijzigd zijn. Planner Stap 5 blijft geparkeerd totdat deze live gate geslaagd is.
