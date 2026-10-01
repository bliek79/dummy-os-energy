## Dummy OS Energy 0.2.0-alpha.50 - Solar F5 Partial Shading Observer

**Tag:** `0.2.0-alpha.50`

### Doel
Deze prerelease bouwt uitsluitend Fase 5 van het bindende Solar Forecast-optimalisatiecontract: een experimentele partial-shading observer bovenop de bewezen F3 horizon/direct-diffuse candidate.

F5 is observer-only en heeft geen promotie-autoriteit.

### Bindende formule
- F3 blijft de horizontrigger bepalen per array.
- Niet geblokkeerd: `effective_partial = GTI`.
- Geblokkeerd en `diffuse + direct > 0`:
  - `partial_factor = clamp(diffuse / (diffuse + direct), 0..1)`
  - `effective_partial = diffuse * partial_factor`
- Geblokkeerd en `diffuse + direct <= 0`: `partial_factor = 1`, effectieve instraling blijft diffuse.
- Daarna exact dezelfde F1 temperatuurcorrectie, statische performancefactor en bestaande Energy per-array AC-cap.

### Nieuw
- Pure helper `partial_shading_effective_irradiance_wm2`.
- Nieuwe F5 15-min / 72h / 288-slot candidate.
- Zelfde F3 zonnestand, horizonprofielen en direct/diffuse inputs; geen extra providerinput.
- Eigen pre-slot snapshot en completed-quarter evaluation.
- Persistente exact-lock F3 horizon-simple versus F5 partial-validatie.
- Aparte blocked-effect metrics per Noord/Zuid/totaal zodat niet-geblokkeerde identieke slots het daadwerkelijke partial-shadingeffect niet maskeren.

### Nieuwe canonical entiteiten
- `sensor.do_solar_partial_shading_candidate_timeline`
- `sensor.do_solar_partial_shading_candidate_next_quarter`
- `sensor.do_solar_partial_shading_candidate_evaluation_last_completed_quarter`
- `sensor.do_solar_partial_shading_validation`

### Fail-safe
- F5 wordt alleen ready wanneer F3 ready is.
- F5-fouten wijzigen raw, F1, F2, F3 of F4 niet.
- Slot-, lock-, actual- en coverage-mismatch worden geweigerd in F5-validatie.
- Duplicate/out-of-order slots worden niet opnieuw persistent geteld.

### Bewust ongewijzigd
- raw Solar;
- F1 temperature candidate;
- F2 temperature A/B;
- F3 horizon-simple candidate;
- F4 multi-modelvalidation;
- native 15 minuten / 72 uur / 288 slots;
- Open-Meteo providerinputs;
- horizonprofielen;
- performancefactoren;
- bestaande Energy per-array `ac_limit_kw`;
- geen residual learning;
- geen automatische kalibratie;
- geen modelpromotie;
- geen planner/EMS-wijziging;
- geen DOEMS-port.

### Huidige fysieke beperking
Noord en Zuid gebruiken momenteel beide de neutrale horizon `[[0,0],[360,0]]`. Daardoor zal F5 tijdens normale daglichtslots vrijwel gelijk zijn aan F3. Dat is geldig voor technische pipeline/regressievalidatie, maar inhoudelijke partial-shadingkwaliteit vereist later echte fysiek gemeten horizonpunten of een bekende geblokkeerde dagsituatie.

### Live gate na installatie
1. `sensor.do_solar_partial_shading_candidate_timeline`: `candidate_status=ready`, `point_count=288`, `last_error=null`.
2. Eerste geldige pre-slot completed-quarter evaluation: `status=ok`, `valid=true`, `candidate_status=locked`.
3. `sensor.do_solar_partial_shading_validation`: `status=collecting`, `last_pair_status=ok`, `sample_count>=1`.
4. Bij niet-geblokkeerde slots moeten F3 en F5 exact gelijk blijven.
5. Echte F5-effectbeoordeling pas op blocked-effect samples; geen promotie.
