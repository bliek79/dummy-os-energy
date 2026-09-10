# Dummy OS Energy 0.2.0-alpha.16

Performance codepath hotfix voor de observer-only plannerketen.

## Wijzigingen

- `DO Plan Preview` consumeert voortaan de reeds gepubliceerde `DO Plan Input 72h`- en `DO Plan Reserve SOC`-contracten in plaats van Forecast -> Planner -> Model Health opnieuw op te bouwen.
- `DO Plan Grid Support` consumeert voortaan de reeds gepubliceerde `DO Plan Input 72h`- en `DO Plan Energy Need`-contracten in plaats van dezelfde zware upstreamketen opnieuw op te bouwen.
- De alpha.15 material-input cache van de Plan Store Bridge blijft behouden.
- Regressietests bewaken dat Preview en Grid Support op de gepubliceerde upstream-contracten blijven werken.
- Het geisoleerde CI-testharnas is aangevuld voor de Home Assistant adapterimports; Home Assistant is niet als CI-dependency toegevoegd.

## Ongewijzigde architectuur en veiligheid

- Native resolutie: 15 minuten.
- Forecast-horizon: 72 uur / 288 slots.
- Grid Support-trigger: 0,25 kWh.
- Geen wijziging aan plannerlogica, batterijgrenzen, Safety/Prestart, Plan Store-lifecycle of schedulerbeslissingen.
- Shadow-only blijft hard gesloten: geen fysieke batterijservicecalls, geen modeswitch, geen command dispatch en geen physical execution authority.

## Validatie

PR #197 CI run #157:
- 348 tests passed in 1.22s.
- Compile sources: geslaagd.
- Manifestvalidatie: geslaagd.
- Step 9 profile contract: geslaagd.
- alpha.12.18 runtime gate: geslaagd.
- Validation ZIP en artifact upload: geslaagd.

## Live validatie na installatie

Controleer in Home Assistant specifiek of de eerdere MainThread-waarschuwingen voor `DO Plan Preview` en `DO Plan Grid Support` verdwenen zijn. Eventuele resterende waarschuwingen van Energy Forecast / Forecast Model / History worden als afzonderlijk performanceprobleem behandeld.
