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
