## Dummy OS Energy 0.2.0-alpha.51 - Solar F6 Residual Learning Candidate

**Tag:** `0.2.0-alpha.51`

### Doel
Deze prerelease bouwt Fase 6 van het bindende Solar Forecast-optimalisatiecontract volledig uit als parallelle residual-learningcandidate bovenop één expliciet vastgezet fysiek parentmodel.

F6 is observer/candidate-only en heeft geen promotie-autoriteit. F7/F8/F9 en de DOEMS-port blijven gesloten.

### Expliciete physical parent
- Parent: F5 partial shading candidate `open_meteo_gti_horizon_partial_temperature_candidate_v0.1`.
- Geen automatische winnaarselectie tussen F3 en F5.
- Raw physical, F1, F3, F4 en F5 blijven parallel beschikbaar.
- De parentconfiguratie krijgt een deterministische signature. Een gewijzigde physical parent maakt bestaande qualification ongeldig en herstart veilig met factor 1,0.

### Residual-learningcontract
Per array wordt alleen geleerd op vooraf gelockte, geldige completed quarters:
- coverage minimaal 90%;
- daylight-only: solar elevation >= 0 en weather regime niet `dark`;
- parent forecast minimaal 0,02 kWh;
- slots op de bestaande per-array AC-cap worden niet voor factortraining gebruikt;
- geen duplicate/out-of-order/hindsight/backfill;
- residual ratio = actual / parent.

Condition key per array:
`solar_elevation_band x solar_azimuth_sector x weather_regime`.

### Robuuste estimator en qualification
- maximaal 120 recente ratios per bin;
- plausibilityfilter 0,25..4,0;
- vanaf 20 bruikbare samples median + MAD, met 3xMAD-filter;
- qualified vanaf minimaal 40 bruikbare samples uit minimaal 7 lokale dagen;
- factor = clamp(median residual ratio, 0,75..1,25);
- insufficient, unstable, saturated of invalid => toegepaste factor exact 1,0;
- saturatie opent de clamp niet.

### Leakage- en exact-lockveiligheid
- maximaal één deterministic modelrevision per afgesloten lokale kalenderdag;
- revision gebruikt alleen samples van vóór de lokale training cutoff;
- targetdag/future actuals komen niet in de revision;
- ieder targetslot lockt `model_revision`, parent signature, condition bins en applied factors vóór actuals;
- restart herstelt persisted learner state en de actieve pre-slot snapshot;
- corrupte/ontbrekende state valt veilig terug op parent/factor 1,0.

### AC-capveiligheid
Na een factor >1 wordt de bestaande per-array slotcap opnieuw toegepast:
`ac_limit_kw x 0,25 h`.
F6 kan de elektrische cap niet verhogen. Total blijft uitsluitend `north + south`; er bestaat geen total-factor.

### Nieuwe canonical entiteiten
- `sensor.do_solar_residual_learning_status`
- `sensor.do_solar_residual_learning_candidate_timeline`
- `sensor.do_solar_residual_learning_candidate_next_quarter`
- `sensor.do_solar_residual_learning_candidate_evaluation_last_completed_quarter`
- `sensor.do_solar_residual_learning_validation`

### Validatie
De F6-validation vergelijkt exact-lock F5 parent versus F6 learned op dezelfde actual/coverage en rapporteert Noord/Zuid/totaal plus condition-bin metrics. De 14 complete live observatiedagen en 300 daylight A/B-samples per array blijven uitsluitend exitbewijs voor een latere F6-groen/F7-beoordeling; zij blokkeren deze technische build niet.

### Bewust ongewijzigd
- native 15 minuten / 72 uur / 288 slots;
- raw Solar en F1-F5;
- Open-Meteo provider/inputsemantiek;
- fysieke Noord/Zuid-horizonprofielen;
- temperatuurformule;
- statische performancefactor;
- DC-capaciteit en bestaande per-array AC-cap;
- geen neural network, black-box of cloudtraining;
- geen automatische fysieke parameterkalibratie;
- geen planner/EMS authority;
- geen modelpromotie;
- geen DOEMS-port;
- geen Google Sheets-write.

### Live gate na installatie
1. `sensor.do_solar_residual_learning_candidate_timeline`: `candidate_status=ready`, `point_count=288`, `last_error=null`.
2. Statussensor toont F5 als parent en een persistente `model_revision`.
3. Zolang bins niet qualified zijn: applied factor exact 1,0 en learned candidate gelijk aan parent, behoudens dezelfde AC-cap.
4. Eerste completed quarter: F6 evaluation `status=ok`, `valid=true`, met vooraf gelockte revision/factors.
5. `sensor.do_solar_residual_learning_validation`: exact-lock pair collecting; geen promotie.
