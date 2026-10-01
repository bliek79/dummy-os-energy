## Dummy OS Energy 0.2.0-alpha.49 - Solar F4 Multi-Model Validation

**Tag:** `0.2.0-alpha.49`

### Doel
Deze prerelease bouwt uitsluitend Fase 4 van het bindende Solar Forecast-optimalisatiecontract: persistente langere-termijn validatie van raw, temperature candidate en horizon candidate op exact dezelfde vooraf gelockte kwartieren.

F4 wijzigt geen forecastformule en heeft geen promotie-autoriteit.

### Nieuw
- Nieuwe pure validatiemodule `solar_multimodel_validation.py`.
- Exact-lock triple-pairing van:
  - raw Solar;
  - F1 temperature candidate;
  - F3 horizon candidate.
- Een F4-sample telt alleen wanneer alle drie:
  - hetzelfde `slot_id` hebben;
  - dezelfde `forecast_captured_at` hebben;
  - `status=ok` en `valid=true` zijn;
  - per Noord/Zuid/totaal exact dezelfde actual en coverage gebruiken.
- Persistente dagaggregatie per lokale kalenderdag, maximaal `MAX_HISTORY_DAYS`.
- Metrics per Noord, Zuid en totaal:
  - actual kWh;
  - forecast kWh per model;
  - signed error per model;
  - absolute error per model;
  - bias per model;
  - WAPE per model.
- Analysebreakdowns op dezelfde geldige samples:
  - zonne-elevatie: `below_horizon`, `low`, `medium`, `high`;
  - zonne-azimut: `north`, `east`, `south`, `west`;
  - validatieweertype uit gelockte direct/diffuse-diagnostiek: `dark`, `diffuse_dominant`, `mixed`, `direct_dominant`.
- Nieuwe canonical entiteit:
  - `sensor.do_solar_multimodel_validation`.

### Sensorcontract
De state is het aantal geldige F4-samples. Attributen tonen onder andere:
- `phase: F4`
- `role: multimodel_validation`
- `status`
- `sample_count` / `day_count`
- `first_date` / `last_date`
- `last_pair_status` / `last_slot_id`
- raw/temperature/horizon modelidentiteiten
- overall metrics per Noord/Zuid/totaal
- breakdown per solar elevation
- breakdown per solar azimuth
- breakdown per weather regime
- recente dagaggregaten
- `promotion_authority: false`

### Fail-safe
- Een ontbrekende of ongeldige raw/F1/F3-evaluation levert geen F4-kwaliteitssample op.
- Slot-, lock-, actual- of coverage-mismatch wordt geweigerd.
- Duplicate en out-of-order slots worden niet opnieuw opgeslagen.
- F4-validatiefouten wijzigen raw, F1, F2 of F3 niet.
- F2 blijft zelfstandig parallel data verzamelen.

### Bewust ongewijzigd
- native 15 minuten / 72 uur / 288 slots;
- Open-Meteo-inputs en providersemantiek;
- raw Solar-formule;
- F1 temperatuurformule;
- F3 horizon/direct-diffuse-formule;
- performancefactoren;
- bestaande Energy per-array `ac_limit_kw`;
- horizonprofielen;
- geen partial shading;
- geen residual learning;
- geen automatische kalibratie;
- geen modelwinner of modelpromotie;
- geen planner/EMS-wijziging;
- geen DOEMS-port.

### Validatie voor publicatie
- volledige testsuite groen;
- F1/F2/F3-regressies groen;
- exact-lock triple-pairtests groen;
- mismatch/fail-safe-tests groen;
- zonnepositie- en validatieweertypeclassificatie groen;
- persistence/dedup-contract groen;
- canonical entity-ID-route aanwezig;
- raw/F1/F2/F3 regressievrij.

### Live gate na installatie
1. Controleer `sensor.do_solar_multimodel_validation`.
2. Wacht op het eerste volledig vooraf gelockte kwartier waarop raw, F1 en F3 alle drie geldig zijn.
3. Bevestig `status=collecting`, `last_pair_status=ok` en `sample_count>=1`.
4. Controleer dat raw/temperature/horizon op dezelfde actual en coverage worden geaggregeerd.
5. Laat F2 en F4 langere tijd parallel bewijs verzamelen; geen promotie op basis van een eerste dag of kwartier.
