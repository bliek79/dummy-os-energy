# GitHub Release

**Tag:** `0.2.0-alpha.18`  
**Release title:** Dummy OS Energy 0.2.0-alpha.18 - Plan Store Sensor Setup Hotfix

## Dummy OS Energy 0.2.0-alpha.18

Gerichte stability-hotfix naar aanleiding van live Home Assistant-validatie van alpha.17.

### Wijziging
- Herstelt de foutieve `build_do_plan_store_sensors(coordinator, runtime)` aanroep naar de actuele `build_do_plan_store_sensors(coordinator)` builder.
- De gedeelde Plan Store runtime voor de Bridge blijft behouden via `get_do_plan_store_runtime(coordinator)`.
- Regressietests bewaken voortaan de builder-signature/call-consistentie en de bestaande shadow-only veiligheidsmarkers.

### Architectuur en veiligheid ongewijzigd
- Native resolutie: 15 minuten.
- Forecast-horizon: 72 uur / 288 slots.
- Geen wijziging aan plannerlogica, Grid Support-drempel, Plan Store-lifecycle, Scheduler, Safety/Prestart, Execution of fysieke batterijbevoegdheid.
- Shadow-only blijft gesloten; geen fysieke batterijservicecalls, modeswitch of command dispatch.

### Validatie hotfix
PR #201: 357 tests geslaagd in 1,29 s. Compile sources, manifestvalidatie, Step 9 profile contract, runtime-gate, validation ZIP en artifact-upload zijn geslaagd.

### Live validatie na installatie
Controleer na installatie en herstart dat Dummy OS Data sensorplatform zonder `build_do_plan_store_sensors() takes 1 positional argument but 2 were given` opstart. De bekende Anker Solix startupvertraging blijft buiten scope als externe integratiebeperking.
