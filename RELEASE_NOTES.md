# GitHub Release

**Tag:** `0.2.0-alpha.15`  
**Release title:** Dummy OS Energy 0.2.0-alpha.15 - Step 6B Performance and Version Hotfix

## Dummy OS Energy 0.2.0-alpha.15

Deze prerelease is een gerichte hotfix na de live alpha.14-validatie. Hij corrigeert de versiebronfout van alpha.14 en vermindert de extra Step-6B Plan Store Bridge-belasting zonder de plannerarchitectuur of safetygrenzen te wijzigen.

### Opgelost
- De repositoryversie staat vóór tagging consequent op `0.2.0-alpha.15` in `const.py`, `manifest.json` en de release-consistency gate.
- De Plan Store Bridge gebruikt een deterministische material-input fingerprint.
- Binnen hetzelfde native kwartier wordt de zware input -> reserve -> preview -> plan72 -> grid-support keten niet opnieuw berekend wanneer plannerrelevante input inhoudelijk gelijk blijft.
- Echte wijzigingen in profiel, SOC, historie/evaluaties, solar of prijzen invalidëren de cache direct.
- Een nieuw native 15-minutenkwartier forceert opnieuw een geldige plannerberekening.
- De bestaande Plan Store, candidate-identiteit, reconciliation en persistente shadow-store blijven inhoudelijk ongewijzigd.

### Architectuur en safety ongewijzigd
- native resolutie: 15 minuten;
- horizon: 72 uur;
- exact 288 slots;
- Plan Store: exact 3 slots;
- `shadow_only=true`;
- `shadow_store_write=true`;
- `operational_plan_store_write=false`;
- `active_use_permitted=false`;
- `physical_execution_authority=false`;
- `scheduler_invoked=false`;
- `safety_chain_invoked=false`;
- `service_calls_performed=false`.

### Bewust niet gewijzigd
- Grid Support shadow-testgrens blijft 0,25 kWh;
- geen Planner Stap 7 Scheduler;
- geen Safety/Prestart;
- geen Execution;
- geen fysieke Home Assistant-servicecalls;
- geen dashboardmigratie.

### Live-validatie na installatie
- Home Assistant moet de integratie als `0.2.0-alpha.15` tonen.
- Controleer de startup/update-log specifiek op nieuwe `dummy_os_data` main-threadwaarschuwingen.
- `sensor.dummy_os_energy_do_plan_store_bridge` moet `ready` blijven en `skipped_refreshes` moet bij ongewijzigde refreshes kunnen oplopen.
- Een echte plannerinputwijziging of nieuwe kwartiergrens moet de bridge opnieuw laten rekenen.
- Alle shadow/safetyvlaggen moeten gesloten blijven.

---
# GitHub Release

**Tag:** `0.2.0-alpha.13`  
**Release title:** Dummy OS Energy 0.2.0-alpha.13 - Planner Step 5 Grid Support Shadow

## Dummy OS Energy 0.2.0-alpha.13

Deze prerelease voegt uitsluitend observer-only netondersteuningsdiagnostiek toe bovenop Planner Stap 5.

### Toegevoegd
- `DO Plan Grid Support` met shadow-testgrens X = 0,25 kWh op Step-2 `additional_grid_charge_kwh`.
- Splitsing in laadbaar batterijtekort en onvermijdbaar resttekort; nooit laden boven 100% SOC.
- Native 15-minuten economische laadvensterselectie binnen exact 72 uur / 288 slots.
- Echte all-in importprijs, 92% laadefficiëntie, solar-first gedeelde 3200 W laadheadroom en kritieke deadline.
- Baseline/candidate 72h-resimulatie met kostendelta en solar displacement.
- Exacte native home-quarterwaarden worden additief door de bestaande Forecast->Planner-keten meegenomen.

### Safetyrechten onveranderd
- `shadow_only=true`
- `active_use_permitted=false`
- `physical_execution_authority=false`
- `plan_store_write=false`
- `scheduler_invoked=false`
- `safety_chain_invoked=false`
- `service_calls_performed=false`

Geen fysieke batterijactie, scheduler of Plan Store. X=0,25 kWh is uitsluitend de eerste shadow-testwaarde en nog geen definitieve operationele instelling.

---
# GitHub Release

**Tag:** `0.2.0-alpha.12`  
**Release title:** Dummy OS Energy 0.2.0-alpha.12 - Planner Step 5 72h Sequential Simulation

## Dummy OS Energy 0.2.0-alpha.12

Deze prerelease implementeert Planner Stap 5 als observer-only `DO Plan 72h` sequentiële simulatie bovenop de bestaande gevalideerde Planner Stap 1-4 keten.

### Toegevoegd
- Exact 72 volledige planneruren als sequentiële batterijsimulatie.
- Twee simulatiepasses: baseline zonder trade en candidate met uitsluitend de Stap-4 tradecandidate.
- Solar-first energiestroom en gedeelde 3200 W laadlimiet voor solar + grid.
- 7,2 kWh batterij, 5% minimum-SOC, 7% software-reserve, 2% diagnostische execution-buffer en 92%/92% efficiency.
- Uurdiagnostiek voor SOC en energieflows; baseline/candidate samenvatting en `solar_displacement_kwh`.
- Strikte upstream signature/72h-validatie; missing/NaN wordt niet als nul behandeld.

### Safetyrechten onveranderd
- `shadow_only=true`
- `active_use_permitted=false`
- `physical_execution_authority=false`
- `plan_store_write=false`
- `scheduler_invoked=false`
- `safety_chain_invoked=false`
- `service_calls_performed=false`

Er wordt geen plan opgeslagen, geen scheduler aangeroepen en geen fysieke batterijactie uitgevoerd.

### Live-validatie
Controleer na installatie `sensor.do_plan_72h`: status, `hour_count=72`, signatures, safetyflags, baseline/candidate, SOC-verloop en afwezigheid van nieuwe `dummy_os_data` main-threadwaarschuwingen.

---
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

---
# GitHub Release

**Tag:** `0.2.0-alpha.10`  
**Release title:** Dummy OS Energy 0.2.0-alpha.10 - Time Windows Main-Thread Fix

## Dummy OS Energy 0.2.0-alpha.10

Deze prerelease lost uitsluitend de laatste Dummy OS Energy main-threadwaarschuwing uit de live alpha.9-startup op. Planner Stap 5 wordt niet toegevoegd.

### Opgelost
- `DO Energy Time Windows` voert Peak Learning + Time Windows observerberekening niet langer synchronisch uit tijdens entity state updates.
- De bestaande observerberekening draait via executor-backed caching met coalescing van overlappende refreshes.
- `native_value` en `extra_state_attributes` lezen alleen het laatst voltooide cache-resultaat.
- Tijdens de eerste achtergrondberekening wordt fail-safe `initializing` gepubliceerd met `observer_calculation_pending`.

### Bewust ongewijzigd
- forecastformules;
- Time Windows-algoritme en drempels;
- entity-ID `sensor.do_energy_time_windows`, unique_id en friendly name;
- native 15 minuten / 72 uur / exact 288 slots;
- Planner Stap 1 t/m 4;
- reserve-/SOC-, prijs- en solarcontracten;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false`;
- unknown/unavailable wordt niet stilzwijgend als nul behandeld;
- geen Planner Stap 5-functionaliteit.

### Live-validatie na installatie
Na installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat `sensor.do_energy_time_windows`, die in alpha.9 nog 0,637 s main-threadtijd veroorzaakte, niet meer als main-threadwaarschuwing terugkomt. Daarnaast moet de volledige startup-log worden gecontroleerd op andere nieuwe `dummy_os_data` main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze live gate schoon is.

---
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

---
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

---
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

---
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

---
# GitHub Release

**Tag:** `0.2.0-alpha.5`  
**Release title:** Dummy OS Energy 0.2.0-alpha.5 - DO Plan Preview

## Dummy OS Energy 0.2.0-alpha.5

Deze pre-release publiceert Planner Stap 4: de observer-only `do_plan_preview`-laag bovenop de live-gevalideerde plannerstappen 1 t/m 3.

### Nieuw
- Nieuwe plannerdiagnose `do_plan_preview`.
- Veiligheidslading wordt afgeleid uit het Stap-3 reserve-tekort; Stap 3 blijft de enige autoritatieve reserve-SOC-bron.
- Laadefficiëntie wordt meegenomen in de benodigde netinput voor veiligheidsladen.
- Goedkoopste beschikbare laaduren vóór `first_usable_solar` worden observer-only geselecteerd.
- Eventueel niet inpasbaar reserve-tekort blijft expliciet zichtbaar als `safety_unallocated_battery_kwh`.
- Vrije batterij-energie boven de beschermde reserve wordt apart omgerekend naar maximaal leverbare energie na ontlaadverlies.
- Importvermijding en exporthandel worden als twee afzonderlijke financiële routes beoordeeld; import- en exportprijs worden niet aan elkaar gelijkgesteld.
- Publiceert onder andere `preview_decision`, `required_grid_input_kwh`, `max_deliverable_from_free_kwh`, `price_min_import`, `price_max_import`, `price_spread_import`, aparte self-use/export kandidaten en marges, plus `solar_capacity_protection`.
- Een conservatieve zonne-capaciteitsbescherming voorkomt dat theoretische handelslading beschikbare batterijruimte vóór verwachte bruikbare zon wegdrukt.

### Vaste uitgangspunten
- native forecastarchitectuur blijft 15 minuten / 72 uur / 288 slots;
- plannerprojectie blijft exact 72 volledige uren;
- charge efficiency: 92%;
- discharge efficiency: 92%;
- roundtrip efficiency volgt uit beide rendementen;
- minimum handelsmarge: 0,10 per kWh;
- maximum observer-only laad- en ontlaadvermogen: 3200 W;
- echte `0.0` blijft geldig;
- missing/unknown/NaN/inf wordt nooit stilzwijgend nul;
- ontbrekende exportprijs wordt nooit vervangen door importprijs.

### Architectuurgrenzen
- `do_plan_preview` maakt nog geen fysiek plan aan.
- Geen Plan Store, Scheduler, Bridge, Safety of Execution wordt aangeroepen.
- `reserve_recalculated=false`: Stap 4 berekent de beschermde reserve niet opnieuw.
- De planner entity-ID cleanup blijft bewust uitgesteld tot het einde van de plannerbouw.
- Dummy OS EMS blijft tijdens de overgang beschikbaar als referentie en rollback.

### Veiligheid
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- `calculation_scope=planner_preview_only`.

### Live-validatie na installatie
Controleer na installatie en herstart minimaal de nieuwe `DO Plan Preview`-entiteit:
- `status`, `valid`, `reason`, `blockers`;
- `preview_decision`;
- `input_status`, `input_rows_signature`, `reserve_status`;
- `reserve_deficit_battery_kwh` en `required_grid_input_kwh`;
- `safety_charge_needed`, `safety_schedule_sufficient`, `safety_unallocated_battery_kwh` en geselecteerde laaduren;
- `free_above_reserve_battery_kwh` en `max_deliverable_from_free_kwh`;
- importprijs min/max/spread;
- aparte self-use- en exportkandidaten/marges;
- `solar_capacity_protection`;
- opnieuw alle drie observer-only veiligheidsvlaggen.

Planner Stap 5 wordt pas inhoudelijk vrijgegeven nadat Stap 4 live is geaccepteerd.

---
# GitHub Release

**Tag:** `0.2.0-alpha.4`  
**Release title:** Dummy OS Energy 0.2.0-alpha.4 - DO Plan Reserve SOC

## Dummy OS Energy 0.2.0-alpha.4

Deze pre-release publiceert Planner Stap 3: de observer-only reserve- en SOC-beschermingslaag bovenop de live-gevalideerde `do_plan_energy_need`-uitkomst.

### Nieuw
- Nieuwe plannerdiagnose `do_plan_reserve_soc`.
- Vertaalt de Stap-2 energiebehoefte naar een expliciete beschermde reserve-SOC-positie.
- Publiceert onder andere `reserve_soc_raw_percent`, `reserve_soc_target_percent`, `reserve_deficit_kwh`, `reserve_deficit_percent`, `free_above_reserve_kwh`, `free_above_reserve_percent` en `unmet_reserve_at_full_soc_kwh`.
- Neemt `input_status`, `input_rows_signature`, `first_usable_solar` en `available_battery_kwh` mee voor traceerbaarheid naar Stap 2 en Stap 1.
- Onderscheidt `blocked`, `infeasible`, `ready/reserve_deficit`, `ready/reserve_covered` en `ready/reserve_surplus`.
- Echte `0.0`-waarden blijven geldig; missing/unknown/NaN/inf wordt niet als nul behandeld.

### Formule
- Beschikbare batterij-energie boven minimum-SOC: `C * max(SOC - SOC_min, 0) / 100`.
- Benodigde beschermde energie: `energy_need_until_solar_kwh + safety_reserve_kwh`.
- Ruwe reserve-SOC: `SOC_min + 100 * required_including_reserve_kwh / C`.
- Doel-SOC wordt begrensd op 100%.
- Als de benodigde energie zelfs bij 100% SOC niet boven minimum-SOC beschikbaar kan zijn, wordt de toestand expliciet `infeasible`.

### Bewuste architectuurgrens
- Laad- en ontlaadefficiëntie wordt in Stap 3 nog niet toegepast; deze laag bepaalt uitsluitend de beschermde batterij-energiepositie.
- Er worden geen laad- of ontlaadacties gepland.
- Geen Plan Store, Scheduler, Bridge, Safety of Execution wordt aangeroepen.
- De tijdelijke directe SOC-bron uit Stap 2 blijft alleen read-only input totdat een planner source contract wordt ingevoerd.
- De centrale planner entity-ID cleanup blijft uitgesteld tot het einde van de plannerbouw.

### Veiligheid
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- Dummy OS EMS blijft actief als referentie en rollback tijdens de overgang.

### Live-validatie na installatie
- Controleer de nieuwe `DO Plan Reserve SOC`-entiteit.
- Bevestig `status`, `valid`, `reason` en `blockers`.
- Vergelijk `reserve_soc_target_percent`, `reserve_deficit_kwh` en `free_above_reserve_kwh` met een onafhankelijke handberekening op hetzelfde moment.
- Controleer dat `input_rows_signature` overeenkomt met de actuele upstream plannerketen.
- Bevestig opnieuw dat alle drie observer-only veiligheidsvlaggen ongewijzigd blijven.
- Planner Stap 4 start pas na live acceptatie van deze release.

---
# GitHub Release

**Tag:** `0.2.0-alpha.3`  
**Release title:** Dummy OS Energy 0.2.0-alpha.3 - DO Plan Energy Need

## Dummy OS Energy 0.2.0-alpha.3

Deze pre-release bouwt Planner Stap 2: de eerste observer-only energiebalans bovenop de live-gevalideerde `do_plan_input_72h`-matrix.

### Nieuw
- Nieuwe plannerdiagnose `do_plan_energy_need`.
- Berekent netto energiebehoefte tot de eerste van twee opeenvolgende uren waarin solar minimaal het woningverbruik dekt.
- Berekent beschikbare batterij-energie boven 5% minimum-SOC bij 7.2 kWh capaciteit.
- Berekent een softwarematige veiligheidsreserve van 7%.
- Leidt diagnostisch `additional_grid_charge_kwh` en `tradable_battery_kwh` af.
- Neemt de `rows_signature` van Planner Stap 1 mee voor herleidbaarheid.

### Verbeterd ten opzichte van huidige EMS
- Missing solar wordt nooit als 0.0 behandeld.
- NaN/inf/negatieve ongeldige forecastwaarden blokkeren in plaats van door te rekenen.
- Geen bruikbare solargrens binnen 72 uur wordt expliciet `waiting_for_usable_solar`; de horizon wordt niet stilzwijgend als volledige nacht behandeld.
- De rekenlaag gebruikt uitsluitend de gevalideerde `do_plan_input_72h`-architectuur.

### Veiligheid
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- Geen Plan Store, Scheduler, Bridge, Safety of Execution wordt aangeroepen.
- Dummy OS EMS blijft actief als referentie en rollback.
- De planner entity-ID cleanup blijft bewust uitgesteld tot het einde van de plannerbouw.

### Live-validatie
- Controleer status/valid/reason, SOC-bron, energy_need_until_solar_kwh en first_usable_solar.
- Vergelijk dezelfde timestamp met de huidige EMS Energy Need en verklaar eventuele verschillen.
- Controleer dat alle drie veiligheidsvlaggen observer-only blijven.
- Planner Stap 3 start pas na live acceptatie van deze stap.

---
# GitHub Release

**Tag:** `0.2.0-alpha.2`  
**Release title:** Dummy OS Energy 0.2.0-alpha.2 - DO Plan Input 72h

## Dummy OS Energy 0.2.0-alpha.2

Deze pre-release bouwt Planner Stap 1: één observer-only, exact tijdgematchte 72-uurs invoermatrix voor de nieuwe interne Dummy OS Energy-planner.

### Nieuw
- Nieuwe diagnose-entiteit `sensor.do_plan_input_72h`.
- Exact 72 contracturen als leidende tijdas.
- Woningverbruik rechtstreeks uit het Forecast→Planner-contract.
- Solar en import-/exportprijzen uitsluitend via exact gematchte kwartierstimestamps.
- Vier echte kwartieren per planneruur vereist; geen nearest-match, interpolatie of padding.
- `0.0` blijft een geldige echte waarde; missing/NaN/inf wordt nooit stilzwijgend nul.
- Interne read-only bronbuffers voor Solar en Prices zodat de 72 volledige contracturen kunnen worden afgedekt zonder de publieke 288-slot timelines te verlengen.
- Compacte SHA-256 `rows_signature` voor parallelvalidatie.

### Veiligheid
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- Geen plan store, Scheduler, safety-chain of batterijservice wordt aangeroepen.
- Dummy OS EMS blijft actief en ongewijzigd als referentie en rollback.

### Live-validatie
- `sensor.do_plan_input_72h` moet 72 uurankers hebben die exact overeenkomen met het Forecast→Planner-contract.
- `valid_home_hours`, `valid_solar_hours` en `valid_price_hours` worden afzonderlijk gecontroleerd.
- Bij volledige brondekking moet `fully_valid_hours=72` zijn.
- Een runtime bronstoring mag structurele geldigheid niet maskeren en resulteert in `runtime_blocked`.
- Planner Stap 2 (`do_plan_energy_need`) start pas na expliciete live-validatie van deze inputlaag.

---
# GitHub Release

**Tag:** `0.2.0-alpha.1`  
**Release title:** Dummy OS Energy 0.2.0-alpha.1 - Product Migration Foundation

## Dummy OS Energy 0.2.0-alpha.1

Deze pre-release start de nieuwe Dummy OS Energy-ontwikkellijn. De bestaande Forecast-integratie wordt voortaan rechtstreeks uitgebouwd tot de definitieve energie-integratie; er komt geen latere samenvoeging met Dummy OS EMS.

### Gewijzigd
- Productnaam gewijzigd naar **Dummy OS Energy**.
- GitHub-repository is `bliek79/dummy-os-energy`.
- HACS-weergavenaam is **Dummy OS Energy**.
- Manifest-documentatie verwijst naar de nieuwe repository.
- Runtime `NAME` is **Dummy OS Energy**.
- Versielijn start op `0.2.0-alpha.1`.
- Config-flow en vertalingen tonen voortaan **Dummy OS Energy**.
- Architectuurdocumentatie legt vast dat de nieuwe planner in deze integratie wordt gebouwd.
- Nieuwe planner-entiteiten krijgen de vaste namespace `do_plan_*`.

### Bewust ongewijzigd
- Home Assistant-domain blijft `dummy_os_data`.
- Integratiemap blijft `custom_components/dummy_os_data`.
- Bestaande `do_*` entity_id's en unique_id's worden niet hernoemd.
- Native forecastarchitectuur blijft 15 minuten / 72 uur / 288 publieke slots.
- Er is geen nieuwe planner-, safety- of executionlogica toegevoegd in deze release.
- Dummy OS EMS blijft voorlopig apart actief als referentie en rollback tijdens de stapsgewijze vervanging.

### Live-validatie na installatie
- Controleer dat HACS/Home Assistant de integratie als **Dummy OS Energy** toont.
- Controleer dat de bestaande config entry en opties behouden zijn.
- Controleer dat bestaande `do_*`-entiteiten dezelfde entity_id/unique_id behouden en geen duplicaten ontstaan.
- Controleer dat de Forecast-timeline nog exact 288 slots op 15 minuten / 72 uur levert.
- Start pas na deze validatie met de eerste `do_plan_*`-plannerlaag.

---
# GitHub Release

**Tag:** `0.1.0-alpha.12.26`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.26 - Step 15 Stable Forecast to Planner Contract

## Dummy OS Forecast 0.1.0-alpha.12.26

Deze pre-release implementeert Stap 15, de laatste inhoudelijke forecaststap: één stabiel, versioneerbaar Forecast→Planner-contract bovenop de live-gevalideerde Step-13-readiness en Step-14 planneruren.

### Nieuw
- Nieuwe canonical interface `sensor.do_energy_forecast_planner_contract`.
- Contractnaam `dummy_os_forecast_to_planner`, `contract_version=1`, `schema_version=1` en `profile_contract_version=1`.
- De planner ontvangt exact dezelfde 72 uurrecords uit Step 14 plus expliciete profiel-, tijd-, quality/readiness- en runtime-metadata.
- `ready_for_planner=true` vereist een leerbaar profiel, exact 288 native slots, 72 planneruren, 4 echte kwartieren per uur, exact 72 echte uren, geen padding, geen tweede forecastarchitectuur en Model Health `usable` of `strong`.
- Runtimebronbeschikbaarheid blijft afzonderlijk zichtbaar via `runtime_input_status`, `forecast_operational_input_ok` en `runtime_blockers`; een tijdelijke bronstoring overschrijft opgebouwde model-readiness niet.
- Step 13 Model Health en Step 14 Planner Hours gebruiken nu gedeelde helpers; het contract consumeert exact dezelfde berekeningen en bevat geen duplicaatlogica.
- `hours` is recorder-excluded.
- Canonical entity-ID alias en registry-migratieroute zijn vanaf de eerste release aanwezig.

### Contractveiligheid
- `physical_execution_authority=false`: dit forecastcontract geeft geen fysieke batterijopdracht.
- `unknown`/`unavailable`/missing wordt nooit nul.
- Een onvolledig uur, fout tijdvenster, padding, tweede architectuur, profile mismatch of onvoldoende Model Health blokkeert het contract deterministisch.
- Normal en Away blijven strikt gescheiden; mixed/unclassified is niet planner-ready.
- Interne fallback- en recencyformules maken bewust geen deel uit van het publieke contract.

### Ongewijzigd
- Native productiearchitectuur: 15 minuten / 72 uur / exact 288 publieke slots.
- Productiemodel: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- Step-14 uurlaag: exact 72 volledige planneruren uit echte kwartieren, maximaal 0-3 interne extra kwartieren, geen padding.
- Package 41, Dummy OS EMS en fysieke batterijbesturing zijn in deze forecastrelease niet inhoudelijk herschreven.
- Friendly-name-opschoning blijft geparkeerd tot na afronding van deze forecaststap.

### Live-validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_planner_contract` exact canonical bestaat.
- Bevestigen: state `ready`, `ready_for_planner=true`, `contract_version=1`, `schema_version=1`, `profile=normal`.
- Bevestigen: `native_slot_count=288`, `planner_hour_count=72`, `quarters_per_hour=4`, `padding_used=false`, `second_forecast_architecture=false`.
- Bevestigen dat `planner_start` tot `planner_end` exact 72 echte uren omvat en `hours` exact 72 aansluitende uurrecords bevat.
- Bevestigen dat Model Health minimaal `usable` is en runtimebronstatus apart blijft staan.
- Tegelijk bevestigen dat `sensor.do_energy_forecast_timeline` exact 288 punten / 15 minuten / 72 uur / model 0.4 blijft.

---

# GitHub Release

**Tag:** `0.1.0-alpha.12.25`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.25 - Step 14 Exact 72 Complete Planner Hours

## Dummy OS Forecast 0.1.0-alpha.12.25

Deze pre-release implementeert Stap 14: exact 72 volledige planneruren, afgeleid uit dezelfde native kwartierforecast zonder padding en zonder tweede forecastarchitectuur.

### Nieuw
- Nieuwe canonical interface `sensor.do_energy_forecast_planner_hours`.
- Exact 72 planneruurrecords van elk precies vier opeenvolgende echte 15-minutenkwartieren.
- Plannerstart wordt uitgelijnd op het eerstvolgende volledige lokale klokuur.
- Bij native start op HH:15 / HH:30 / HH:45 worden respectievelijk 3 / 2 / 1 voorloopkwartieren uitsluitend voor de uurlaag overgeslagen.
- Hetzelfde `historical_baseline`-model mag intern exact evenveel extra kwartieren aan de staart berekenen; maximaal 291 interne kwartieren.
- De publieke productieforecast blijft exact 288 slots.
- DST-overgangen blijven 72 chronologische echte 60-minutenblokken met ISO-offsets; geen kunstmatige lokale uren.
- Een ontbrekend kwartier maakt het betreffende planneruur `energy_kwh=None`; partiële sommen en nulvulling zijn verboden.

### Veiligheidscontract
- `padding_used=false`.
- `second_forecast_architecture=false`.
- `native_public_slots=288`.
- `planner_hour_count=72`.
- `quarters_per_hour=4`.
- `extra_quarters_generated` is uitsluitend 0..3 en gelijk aan de uitlijnings-offset.
- Normal/Away blijven strikt gescheiden; unclassified leent geen historie.
- Package 41, Dummy OS EMS en fysieke batterijbesturing zijn in Stap 14 niet gewijzigd. Daadwerkelijke Forecast→Planner-consumptie blijft Stap 15.

### Ongewijzigd
- Productieforecast: `historical_baseline` modelversie `0.4`.
- Native resolutie/horizon: 15 minuten / 72 uur / 288 publieke slots.
- Productie-recency: 28 dagen half-life.
- Productieconfidence, Model Health/readiness, fallback, Peak Learning, Time Windows, Recency Weighting, Meaningful Confidence en Horizon Quality blijven inhoudelijk ongewijzigd.
- Friendly-name-opschoning blijft geparkeerd.

### Live validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_planner_hours` exact onder de canonical entity-id bestaat.
- Bevestigen dat `planner_hour_count=72`, `quarters_per_hour=4`, `padding_used=false` en `second_forecast_architecture=false` live worden gepubliceerd.
- Bevestigen dat `leading_quarter_offset` en `extra_quarters_generated` exact bij de actuele native startuitlijning passen.
- Bevestigen dat planner_start/planner_end exact 72 echte uren omvatten en alle 72 uurrecords chronologisch aansluiten.
- Tegelijk bevestigen dat `sensor.do_energy_forecast_timeline` exact 288 publieke punten / 15 minuten / 72 uur / model 0.4 / 28-daagse recency blijft.

---

# GitHub Release

**Tag:** `0.1.0-alpha.12.24`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.24 - Step 13 Objective Model Health Readiness

## Dummy OS Forecast 0.1.0-alpha.12.24

Deze pre-release implementeert Stap 13A: de bestaande Energy Forecast Model Health wordt een objectieve evidence-readinessstatus, zonder een tweede publieke healthsensor en zonder wijziging van de productieforecast.

### Gewijzigd
- De bestaande `sensor.do_energy_forecast_model_health` blijft dezelfde publieke entiteit met hetzelfde unique_id en dezelfde naam.
- De state is voor leerbare profielen uitsluitend `collecting`, `learning`, `usable` of `strong`.
- Tijdelijke bronbeschikbaarheid overschrijft de opgebouwde model-readiness niet meer; deze wordt apart gepubliceerd via `runtime_input_status`, `forecast_operational_input_ok` en `runtime_blockers`.
- Readiness gebruikt historie, forward-looking evaluaties, forecastcoverage, productieconfidence, accuracy, MAE, absolute bias, Step-12-horizonbewijs en voldoende-basis segmentkwaliteit.
- De gates zijn hiërarchisch; een zwakke foutmetric kan niet door veel samples of hoge coverage worden weggemiddeld.
- Missing/non-numeric evidence wordt nooit nul.
- Normal en Away blijven strikt gescheiden; `unclassified` behoudt expliciet `profile_unclassified`.

### Readinesscontract
- `learning`: >=7 historiedagen, >=32 evaluaties, >=80% coverage, >=45% confidence.
- `usable`: >=14 historiedagen, >=256 evaluaties, >=95% coverage, >=60% confidence, >=35% accuracy, MAE <=0,100 kWh/kwartier en absolute bias <=0,020 kWh/kwartier.
- `strong`: >=28 historiedagen, >=1.024 evaluaties, >=98% coverage, >=65% confidence, >=45% accuracy, MAE <=0,075 kWh/kwartier en absolute bias <=0,010 kWh/kwartier.
- Voor `strong` moeten bovendien alle acht Step-12-horizons minimaal `observing` zijn.
- Een horizon met `sufficient_basis` en accuracy <25% of absolute bias >0,030 kWh blokkeert `strong`.
- Een voldoende-basis uur- of day_type x daypart-segment met accuracy <20% blokkeert `strong`.

### Ongewijzigd
- `forecast.py` is niet gewijzigd.
- Native architectuur blijft exact 15 minuten / 72 uur / 288 slots.
- Productiemodel blijft `historical_baseline` modelversie `0.4`.
- Productie-recency blijft 28 dagen half-life.
- Productieconfidence, fallback, Peak Learning, Time Windows, Recency Weighting, Meaningful Confidence en Horizon Quality blijven inhoudelijk ongewijzigd.
- Package 41 / Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- De brede friendly-name-opschoning blijft bewust geparkeerd.

### Live validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_model_health` dezelfde canonical entiteit blijft.
- Bevestigen dat de state een readinessstatus is en niet meer `source_unavailable` wordt door een tijdelijke runtimebronstoring.
- Bevestigen dat `runtime_input_status` en `forecast_operational_input_ok` de runtimebron afzonderlijk weergeven.
- Bevestigen dat de actuele Normal-basis niet als `strong` kan eindigen zolang 28 historiedagen en alle acht observing horizons ontbreken.
- Tegelijk bevestigen dat de productieforecast exact 288 slots / 15 minuten / 72 uur / model 0.4 / 28-daagse recency blijft.

---

# GitHub Release

**Tag:** `0.1.0-alpha.12.23`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.23 - Step 12 Forecast Quality by Horizon Observer

## Dummy OS Forecast 0.1.0-alpha.12.23

Deze pre-release implementeert Stap 12 als strikt observer-only kwaliteitsmeting per forecastafstand. De productieforecast zelf blijft ongewijzigd.

### Nieuw
- Nieuwe observer `sensor.do_energy_forecast_quality_by_horizon` met algoritme `forecast_horizon_quality_observer_v1`.
- Vaste native horizonset: 0h-control, 1h, 3h, 6h, 12h, 24h, 48h en de 72h-rand.
- De 72h-rand is exact het laatste van de 288 native kwartieren: start op +71u45 en einde exact op +72u; er wordt geen 289e slot gemaakt.
- Per kwartier worden alleen acht compacte probes uit de bestaande productieforecast vastgelegd.
- Afgeronde evidence wordt compact per profiel, lokale dag en horizon geaggregeerd; pending probes worden na evaluatie verwijderd.
- Per horizon worden sample count, distinct local days, MAE, bias, WAPE-achtige accuracy, gemiddelde captured confidence, source-distributie en uitsluitingen gevolgd.
- Normal en Away blijven strikt gescheiden. Profile mismatch, mixed/unclassified, onvoldoende coverage, invalid actual, malformed snapshot en late capture leveren geen nulwaarden en geen positief bewijs.

### Bewijs- en veiligheidscontract
- `observer_only = true`.
- `forecast_influence_enabled = false`.
- Observing per horizon vanaf minimaal 32 geldige evaluaties over minimaal 8 lokale dagen.
- Sufficient basis per horizon vanaf minimaal 64 geldige evaluaties over minimaal 14 lokale dagen.
- De hoofdstatus wordt pas `sufficient_basis` wanneer alle acht horizons voldoende basis hebben.
- Geen historische backfill met toekomstige informatie; elke horizonprobe is daadwerkelijk vóór het targetkwartier vastgelegd.
- Een grotere of niet-monotone fout op langere horizon is een meetresultaat en veroorzaakt geen automatische modelwijziging.

### Ongewijzigd
- Native architectuur: exact 15 minuten / 72 uur / 288 slots.
- Productiemodel: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- `forecast.py` is niet gewijzigd.
- Energy Store normalizer en schema 2 zijn niet gewijzigd.
- Productieconfidence, Meaningful Confidence observer, Fallback Hierarchy, Peak Learning, Time Windows en Recency Weighting veranderen niet.
- Model Health, Weather, Solar, Prices, Degree Days, Package 41, Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- De brede friendly-name-opschoning blijft bewust geparkeerd tot na de inhoudelijke forecaststappen.

### Live validatie na installatie
- Bevestigen dat de horizonobserver actief publiceert met `observer_only=true` en `forecast_influence_enabled=false`.
- Bevestigen dat exact de acht vastgelegde horizons aanwezig zijn, inclusief de 72h-rand op 4305 minuten.
- Bevestigen dat de productieforecast exact 288 slots op 15 minuten / 72 uur blijft leveren met model 0.4 en 28-daagse recency.
- Verwachten dat 0h/1h-evidence eerder begint op te bouwen dan lange horizons; voor de 72h-rand kan pas na minimaal 72 uur natuurlijke live evidence ontstaan.
- Geen productiepromotie of horizoncorrectie uitvoeren vanuit deze release.

---

# GitHub Release

**Tag:** `0.1.0-alpha.12.22`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.22 - Step 11 Meaningful Confidence Observer

## Dummy OS Forecast 0.1.0-alpha.12.22

Deze pre-release implementeert Stap 11 als strikt observer-only meaningful-confidencelaag. De productieconfidence en de productieforecast blijven ongewijzigd.

### Nieuw
- Nieuwe observer `sensor.do_energy_meaningful_confidence` met algoritme `meaningful_confidence_observer_v1`.
- Kandidaatconfidence combineert recency-gewogen effectieve steekproefgrootte, historische stabiliteit/spreiding, historische coverage, fallback-/brondiepte en recente forward-looking forecastfout.
- Productie- en kandidaatconfidence worden naast elkaar geëvalueerd in confidence-buckets en via high-versus-low confidence error-separatie.
- Normal en Away blijven strikt gescheiden; niet-leerbare profielen worden observer-only als `inactive_profile` behandeld.
- Historische records worden alleen gebruikt wanneer het kwartier volledig was afgerond op of vóór `forecast_captured_at`; recente foutinformatie gebruikt alleen eerdere evaluaties.

### Bewijs- en veiligheidscontract
- `observer_only = true`.
- `forecast_influence_enabled = false`.
- `production_confidence_unchanged = true`.
- `promotion_ready = false`.
- `live_shadow_required = true`.
- Observing-basis: minimaal 32 geschikte evaluaties over minimaal 8 lokale dagen.
- Candidate-supported-basis: minimaal 64 geschikte evaluaties over minimaal 14 lokale dagen én aantoonbaar lagere fout bij de hogere candidate-confidencegroep dan bij de lagere groep.
- Een positieve replay of supported-status wijzigt nooit automatisch productieconfidence.

### Ongewijzigd
- Native architectuur: exact 15 minuten / 72 uur / 288 slots.
- Productieforecast: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- De bestaande productieconfidenceformules zijn niet gewijzigd.
- Fallback Hierarchy, Peak Learning, Time Windows en Recency Weighting blijven observer-only.
- Model Health is niet gewijzigd.
- Weather, Solar, Prices en Degree Days zijn functioneel niet gewijzigd.
- Dummy OS EMS, Package 41 en fysieke batterijbesturing zijn niet gewijzigd.
- De eerder geconstateerde bredere friendly-name-afwijkingen zijn bewust uitgesteld tot de gezamenlijke naamopschoningsronde en blokkeren deze inhoudelijke route niet.

### Live validatie na installatie
- Controleren dat de Meaningful Confidence observer actief publiceert en geen productie-invloed heeft.
- Controleren dat `production_confidence_unchanged = true`, `forecast_influence_enabled = false`, `promotion_ready = false` en `live_shadow_required = true` blijven.
- Controleren dat productieforecast nog exact 288 slots op 15 minuten / 72 uur levert en dat bestaande confidence, Model Health en Package-41/EMS-route onaangetast blijven.
- De observer vervolgens forward-looking/live evidence laten opbouwen; productiepromotie blijft een afzonderlijke latere beslissing.

---

## Historische release - Dummy OS Forecast 0.1.0-alpha.12.21

Deze pre-release is een gerichte Step 10E identity-hotfix. De live installatie van alpha.12.20 toonde dat Home Assistant de nieuwe fallback-observer registreerde als `sensor.dummy_os_forecast_do_energy_fallback_hierarchy` in plaats van de vooraf vastgelegde canonical entity-id `sensor.do_energy_fallback_hierarchy`.

### Opgelost
- De exact waargenomen automatisch gegenereerde alias `sensor.dummy_os_forecast_do_energy_fallback_hierarchy` is toegevoegd aan de veilige registry-migratielaag.
- De bestaande registry-entry met unique_id `do_energy_fallback_hierarchy` wordt deterministisch in-place gemigreerd naar `sensor.do_energy_fallback_hierarchy`.
- Er wordt geen tweede observer aangemaakt en een `_2`-variant is niet toegestaan als geaccepteerd resultaat.
- `unique_id` en `suggested_object_id` blijven `do_energy_fallback_hierarchy`.
- De runtime/friendly name blijft exact `DO Energy Fallback Hierarchy`.

### Permanente borging
- De Step 10 sensor-contracttest controleert nu niet alleen naam, unique_id en suggested_object_id, maar ook de exacte generated-prefix alias en de canonical registry-migratieroute.
- De bestaande centrale identity-migratielaag wordt gebruikt, hetzelfde beschermingsprincipe als voor Time Windows en Recency Weighting.
- De volledige regressietestset, manifestcontrole, Step 9 Profile Contract-gate en alpha.12.18 runtimegate moeten groen blijven vóór publicatie.
- Voor nieuwe publieke `do_*`-entiteiten geldt voortaan naast het codecontract ook een expliciete registry-migratiegate en live controle van de exacte entity-id.

### Ongewijzigd
- Het fallback-algoritme `fallback_hierarchy_observer_v1` is niet gewijzigd.
- De observer blijft strikt `observer_only = true` en `forecast_influence_enabled = false`.
- `promotion_ready` blijft `false` en `live_shadow_required` blijft `true`.
- Productieforecast blijft `historical_baseline` modelversie `0.4`.
- Productie-recency blijft 28 dagen half-life.
- Native architectuur blijft exact 15 minuten / 72 uur / 288 slots.
- Forecast confidence, Model Health, Peak Learning, Time Windows en Recency Weighting veranderen niet.
- Weather, Solar, Prices en Degree Days zijn functioneel niet gewijzigd.
- Dummy OS EMS, Package 41 en fysieke batterijbesturing zijn niet gewijzigd.

### Live validatie na installatie
- Bevestigen dat exact `sensor.do_energy_fallback_hierarchy` bestaat.
- Bevestigen dat `sensor.dummy_os_forecast_do_energy_fallback_hierarchy` niet meer als geregistreerde observer aanwezig is.
- Bevestigen dat geen `sensor.do_energy_fallback_hierarchy_2` of ander duplicaat bestaat.
- Bevestigen dat friendly name `DO Energy Fallback Hierarchy`, unique_id `do_energy_fallback_hierarchy`, `observer_only = true`, `forecast_influence_enabled = false`, `promotion_ready = false` en `live_shadow_required = true` intact zijn.
- Tegelijk bevestigen dat de bestaande productieforecast, confidence, Model Health en Package-41/EMS-route onaangetast blijven.

---

## Historische release - Dummy OS Forecast 0.1.0-alpha.12.20

**Tag:** `0.1.0-alpha.12.20`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.20 - Step 10D Fallback Hierarchy Observer

Deze pre-release implementeert Stap 10D van de Energy Forecast-route als strikt observer-only fallback-hiërarchie. De productieforecast blijft ongewijzigd op `historical_baseline` modelversie `0.4`, met dezelfde 28-daagse recency weighting en dezelfde native architectuur van 15 minuten / 72 uur / 288 slots.

### Nieuw
- Nieuwe observer `sensor.do_energy_fallback_hierarchy` met canonical unique_id en suggested_object_id `do_energy_fallback_hierarchy` en runtime/friendly name `DO Energy Fallback Hierarchy`.
- Observer-algoritme `fallback_hierarchy_observer_v1` voert counterfactual replay uit op bestaande persistente Energy records en forward-looking evaluations.
- De kandidaat-hiërarchie is: `weekday_quarter -> day_type_quarter -> nearby_quarter_day_type -> same_hour_profile -> daypart_profile -> profile_global_median`.
- `nearby_quarter_day_type` gebruikt eerst +/-15 minuten en alleen indien nodig +/-30 minuten, zonder over de lokale daggrens te wrappen.
- `same_hour_profile` gebruikt hetzelfde lokale klokuur binnen exact hetzelfde profiel.
- `daypart_profile` gebruikt de vaste lokale dagdelen night 00:00-06:00, morning 06:00-12:00, afternoon 12:00-18:00 en evening 18:00-24:00.
- `profile_global_median` gebruikt als laatste vangnet een robuuste 28-daags recency-gewogen mediaan binnen exact hetzelfde profiel.

### Bewijs- en veiligheidscontract
- De officiële productiecontrole blijft `weekday_quarter -> day_type_quarter -> quarter_of_day -> profile_mean`.
- Historische replay gebruikt uitsluitend kwartieren die volledig waren afgerond op of vóór `forecast_captured_at`; toekomstige actuals worden niet gebruikt.
- Normal en Away blijven volledig gescheiden. `unclassified` wordt in de publieke observer veilig `inactive_profile` en leent nooit historie van een leerbaar profiel.
- Missing, unknown en unavailable worden nooit naar 0 kWh geconverteerd.
- Control-replay mismatch, te late capture, onvoldoende dekking en ongeldige tijdcontracten worden expliciet uitgesloten.
- De observer publiceert paired control/candidate metrics, fallback-activaties, per-level metrics, day-type x daypart regressiecontrole en early/late stabiliteit.
- `promotion_ready` blijft altijd `false` in deze release en `live_shadow_required` blijft `true`.
- Een positieve counterfactual replay activeert dus nooit automatisch productiegedrag.

### Ongewijzigd
- Native architectuur: exact 15 minuten / 72 uur / 288 slots.
- Productieforecast: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- Forecast confidence en Model Health zijn niet gewijzigd.
- Peak Learning, Time Windows en Recency Weighting blijven observer-only.
- Weather, Solar, Prices en Degree Days zijn functioneel niet gewijzigd.
- Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- Package 41 blijft voorlopig de actieve woningforecast voor Dummy OS EMS totdat een later Forecast -> Planner-contract afzonderlijk is ontworpen en live gevalideerd.

### Technische validatie vóór publicatie
- volledige Python compilecontrole;
- volledige regressietestset groen;
- manifest JSON geldig;
- Step 9 profielcontract- en alpha.12.18 runtimegates blijven groen;
- Step 10D fallbackhiërarchie- en identitytests groen;
- installatie-ZIP en SHA256-checksum gebouwd uit exact dezelfde releasecommit.

### Live validatie na installatie
- Bevestigen dat `sensor.do_energy_fallback_hierarchy` exact onder de canonical entity-id verschijnt, zonder `_2`-variant.
- Bevestigen dat state, profile, observer_only, forecast_influence_enabled, control_hierarchy, candidate_hierarchy, replay_candidate_supported, promotion_ready, live_shadow_required en blockers correct worden gepubliceerd.
- Bevestigen dat de bestaande productieforecast, confidence, Model Health en Package-41/EMS-route door deze observer niet veranderen.
- De observer vervolgens voldoende forward-looking/live shadow data laten opbouwen voor Stap 10E; productiepromotie blijft een afzonderlijk later besluit.

---

## Historische release - Dummy OS Forecast 0.1.0-alpha.12.19

**Tag:** `0.1.0-alpha.12.19`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.19 - Energy Profile Contract v1

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
