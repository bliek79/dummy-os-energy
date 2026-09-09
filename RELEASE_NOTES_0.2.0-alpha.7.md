# GitHub Release

**Tag:** `0.2.0-alpha.7`  
**Release title:** Dummy OS Energy 0.2.0-alpha.7 - Planner Main-Thread Performance Fix

## Dummy OS Energy 0.2.0-alpha.7

Deze pre-release publiceert uitsluitend de reeds gemergede vervolgfix na de live-validatie van 0.2.0-alpha.6. Planner Stap 5 wordt niet toegevoegd.

### Opgelost
- Verplaatst de resterende zware berekeningen van de planner-, contract- en model-healthketen van de Home Assistant main thread naar executor-backed achtergrondberekening.
- Past dit cachepatroon toe op Forecast Planner Hours, Forecast Planner Contract, DO Plan Input 72h, DO Plan Energy Need, DO Plan Reserve SOC, DO Plan Preview en Forecast Model Health.
- `native_value` en `extra_state_attributes` lezen alleen het laatst voltooide cache-resultaat in plaats van de volledige geneste plannerketen synchroon opnieuw op te bouwen.
- Invoer wordt op de Home Assistant main thread als snapshot vastgelegd; de pure rekenstap draait via `hass.async_add_executor_job(...)`.
- Overlappende refreshes worden samengevoegd met een pending-flag om onnodige parallelle herberekeningen te voorkomen.
- Tijdens de eerste berekening kan tijdelijk fail-safe `initializing` zichtbaar zijn met blocker `planner_calculation_pending` of `model_health_calculation_pending`.

### Bewust ongewijzigd
- native forecastarchitectuur blijft 15 minuten / 72 uur / exact 288 slots;
- Planner Stap 1 t/m 4 blijven inhoudelijk en functioneel ongewijzigd;
- plannerformules, reserve-/SOC-logica, prijs-/solarcontracten en entity-identiteiten zijn niet gewijzigd;
- geen Planner Stap 5-functionaliteit;
- geen Plan Store, Scheduler, Bridge, Safety of fysieke execution-takeover;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false` blijven leidend;
- cross-sensor hergebruik wordt nog niet centraal gedeeld; eerst live meten of deze gerichte fix voldoende is.

### Live-validatie na installatie
Na installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat:
- de eerdere startup-main-threadwaarschuwingen voor Forecast Planner Hours (~0,475 s), Forecast Planner Contract (~1,368 s), DO Plan Input 72h (~1,193 s), DO Plan Energy Need (~1,524 s), DO Plan Reserve SOC (~1,765 s), DO Plan Preview (~3,573 s) en Forecast Model Health (~0,707 s) niet terugkomen als blokkerende/synchrone waarschuwingen;
- Planner Stap 1 t/m 4 dezelfde observer-only uitkomsten blijven geven;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false` behouden blijven;
- geen nieuwe regressies in de startup-log zichtbaar zijn.

Planner Stap 5 blijft geparkeerd totdat deze performance-gate live is geslaagd.
