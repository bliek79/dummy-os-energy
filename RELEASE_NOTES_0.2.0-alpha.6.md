# GitHub Release

**Tag:** `0.2.0-alpha.6`  
**Release title:** Dummy OS Energy 0.2.0-alpha.6 - Pre-Step-5 Health Fix

## Dummy OS Energy 0.2.0-alpha.6

Deze pre-release publiceert de reeds gemergede pre-Step-5 health-fix. Er wordt geen nieuwe plannerfunctionaliteit toegevoegd.

### Opgelost
- Herstelt de startupfout waarbij `sensor.do_energy_history_status` en `sensor.do_energy_forecast_model` konden falen met `NameError: name 'slot_count' is not defined`.
- Verplaatst de `slot_count`-validatie naar `HomeBaselineForecast.build(...)`, waar `slot_count` daadwerkelijk beschikbaar is.
- Verplaatst de zware observerberekeningen voor Fallback Hierarchy, Meaningful Confidence en Recency Weighting van de Home Assistant main thread naar executor-backed achtergrondberekening.
- Cachet de voltooide observerresultaten zodat `native_value` en `extra_state_attributes` de zware analyse niet telkens synchroon opnieuw uitvoeren.
- Maakt snapshots van records, evaluations en profiel voor executorwerk en voegt overlappende refreshes samen.
- Tijdens de eerste achtergrondberekening kan tijdelijk `initializing` met blocker `observer_calculation_pending` worden gepubliceerd.

### Bewust ongewijzigd
- native forecastarchitectuur blijft 15 minuten / 72 uur / 288 slots;
- plannerprojectie en Planner Stap 1 t/m 4 blijven functioneel ongewijzigd;
- geen nieuwe plannerbeslislogica;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false` blijven leidend;
- de planner entity-ID cleanup blijft uitgesteld tot het einde van de plannerbouw;
- de dubbele Home Assistant Solar-validatieautomatie-ID `1788072577846` valt buiten deze release.

### Live-validatie na installatie
Na installatie en volledige Home Assistant-herstart moet worden bevestigd dat:
- `sensor.do_energy_history_status` en `sensor.do_energy_forecast_model` zonder `NameError` laden;
- de eerdere main-threadwaarschuwingen voor Fallback Hierarchy (~15 s), Meaningful Confidence (~9 s) en Recency Weighting (~6 s) niet terugkomen;
- de bestaande plannerketen tot en met `do_plan_preview` correct blijft functioneren;
- er geen fysieke uitvoeringsautoriteit is ontstaan.

Planner Stap 5 blijft geparkeerd totdat deze health-fix live is gevalideerd.
