# GitHub Release

**Tag:** `0.2.0-alpha.17`  
**Release title:** Dummy OS Energy 0.2.0-alpha.17 - Planner Thread-Safety Hotfix

## Dummy OS Energy 0.2.0-alpha.17

Stability/performance-hotfix naar aanleiding van live Home Assistant-validatie van alpha.16.

### Wijzigingen
- Safety/Prestart state-change callbacks zijn expliciet Home Assistant event-loop callbacks.
- Scheduler, Execution Preview, Manual Interface en Plan Store listenergrenzen zijn op hetzelfde thread-safetycontract gecontroleerd en vastgelegd.
- Directe runtime-listenerregistratie van `async_write_ha_state` is vervangen door expliciete callback-handlers.
- Regressietests bewaken dat deze callbackgrenzen niet opnieuw naar executor/thread-context verschuiven.

### Architectuur en veiligheid ongewijzigd
- Native resolutie: 15 minuten.
- Forecast-horizon: 72 uur / 288 slots.
- Geen wijziging aan plannerlogica, Grid Support-drempel, Safety-grenzen of Plan Store-lifecycle.
- Shadow-only blijft gesloten: geen fysieke batterijservicecalls, modeswitch, command dispatch of physical execution authority.

### Validatie
Hotfix PR #199 CI run #165: 354 tests passed in 1.25s. Compile sources, manifestvalidatie, Step 9 profile contract, alpha.12.18 runtime gate, validation ZIP en artifact upload zijn geslaagd.

### Live validatie na installatie
Controleer na installatie en herstart dat de eerdere `async_write_ha_state from a thread other than the event loop` RuntimeErrors voor `do_plan_safety_sensor.py` verdwenen zijn. Resterende startup- of MainThread-vertragingen worden daarna afzonderlijk beoordeeld.
