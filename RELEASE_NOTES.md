# GitHub Release

**Tag:** `0.1.0-alpha.12.19`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.19 - Energy Profile Contract v1

## Dummy OS Forecast 0.1.0-alpha.12.19

Deze pre-release implementeert Stap 9 van de Energy Forecast-route: een expliciet en veilig profielcontract voor `normal`, `away` en `unclassified`, zonder het productieforecastmodel of de native 15-minuten / 72-uur / 288-slot architectuur te wijzigen.

### Nieuw
- `select.do_energy_profile` ondersteunt nu `normal`, `away` en `unclassified` als expliciete publieke toestanden.
- `mixed` is een interne kwartiertoestand wanneer binnen één kwartier van profiel is gewisseld; deze toestand is niet selecteerbaar.
- Profielmetadata wordt persistent bijgehouden met `profile_contract_version`, `previous_profile`, `profile_changed_at` en `profile_change_source`.
- Een ontbrekend of ongeldig opgeslagen profiel wordt veilig `unclassified`; er wordt niet stilzwijgend naar `normal` teruggevallen.

### Kwartier- en leercontract
- Werkelijke kwartiermeting en modelleerbaarheid zijn van elkaar gescheiden via `measurement_valid` en `learning_valid`.
- Het bestaande veld `valid` blijft backward-compatible en volgt `learning_valid`.
- Een betrouwbaar gemeten `mixed`- of `unclassified`-kwartier behoudt zijn gemeten kWh, maar wordt niet gebruikt voor leren of forward evaluation.
- Mogelijke blockers worden expliciet gepubliceerd, waaronder `insufficient_coverage`, `profile_changed` en `profile_unclassified`.

### Forecastgedrag
- `normal` en `away` blijven volledig van elkaar geïsoleerd en mogen nooit elkaars historie gebruiken.
- `unclassified` behoudt het vaste tijdcontract van exact 288 kwartierslots, maar publiceert geen ingevulde forecastwaarden en leent geen historie van `normal` of `away`.
- `historical_baseline` blijft modelversie `0.4`.
- De productie-recency blijft een half-life van 28 dagen.
- Peak Learning, Time Windows en Recency Weighting blijven observer-only; onder `unclassified` worden zij expliciet geblokkeerd in plaats van nieuwe leerbasis op te bouwen.

### Kwartiergrens-hardening
- Profielwisselingen verwerken eerst reeds verstreken kwartiergrenzen en passen daarna het nieuwe profiel toe.
- Een wijziging exact op een kwartiergrens houdt het afgesloten kwartier schoon en gebruikt het nieuwe profiel voor het nieuwe kwartier.
- Opnieuw kiezen van hetzelfde profiel veroorzaakt geen kunstmatige profielwisseling.

### Stabiliteit behouden
- De alpha.12.18 runtimegate blijft intact: snelle wijzigingen van `sensor.do_source_home_power` integreren energie, maar veroorzaken geen volledige Forecast-/observer `_notify()`-fan-out.
- Kwartiergrenzen en echte profielwijzigingen blijven relevante refreshmomenten.

### Ongewijzigd
- Native architectuur: exact 15 minuten / 72 uur / 288 slots.
- Bestaande Normal-historie, forecast-snapshots en evaluaties worden niet gewist.
- Weather, Solar, Prices en Degree Days zijn functioneel niet gewijzigd.
- Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- EMS blijft voorlopig zijn bestaande externe Home Forecast gebruiken; migratie naar Dummy OS Forecast is geen onderdeel van deze release.

### Technische validatie
Releasekandidaat vereist vóór publicatie:
- volledige Python compilecontrole;
- volledige regressietestset groen;
- manifest JSON geldig;
- Step 9 profielcontractgate groen;
- alpha.12.18 snelle source-runtimegate groen;
- installatie-ZIP en SHA256-checksum gebouwd uit exact dezelfde releasecommit.

### Live validatie na installatie
- Bevestigen dat bestaande `normal`-historie en evaluaties behouden blijven na upgrade vanaf alpha.12.18.
- Minimaal één volledig Normal-kwartier controleren op `measurement_valid: true`, `learning_valid: true` en normale forward evaluation.
- Een gecontroleerde profielwisseling testen en bevestigen dat het overgangskwartier `mixed` wordt, gemeten energie behoudt en niet wordt geleerd.
- `unclassified` kort testen: 288 slots blijven aanwezig, maar zonder ingevulde forecastwaarden en zonder nieuwe observer-leerdata.
- `normal` herstellen en bevestigen dat de bestaande 72-uursforecast opnieuw 288 gevulde kwartierslots levert.
- Home Assistant-responsiviteit blijven controleren om te bevestigen dat de alpha.12.18 stabiliteitswinst behouden blijft.
