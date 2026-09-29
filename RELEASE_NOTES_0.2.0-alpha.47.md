## Dummy OS Energy 0.2.0-alpha.47

**Tag:** `0.2.0-alpha.47`

### Solar Forecast F2 - persistent temperature A/B validation

Deze prerelease bouwt uitsluitend Fase 2 van het bindende Solar Forecast-optimalisatieplan af: de bestaande raw Solar Forecast en de in F1 gebouwde temperature candidate worden op exact dezelfde vooraf gelockte kwartieren persistent met elkaar vergeleken.

#### F2-validatiecontract
- raw en temperature candidate moeten dezelfde `slot_id` hebben;
- raw en candidate moeten exact dezelfde `forecast_captured_at` hebben;
- beide modellen worden tegen exact dezelfde actual en coverage beoordeeld;
- alleen geldige kwartieren met status `ok` worden in de F2-aggregatie opgenomen;
- restart-partials en onvoldoende coverage blijven buiten modelkwaliteit;
- validatie wordt per Noord, Zuid en totaal opgebouwd.

#### Persistente A/B-evidence
De integratie bewaart compacte dagaggregaten voor geldige F2-samples en herstelt deze na een Home Assistant-herstart. De aggregatie bevat:
- sample- en dagtelling;
- som actual en forecast per model;
- signed error / bias;
- absolute error;
- WAPE;
- bereik van celtemperatuur en temperatuurfactor voor de gelockte temperature candidate.

Nieuwe diagnostische entiteit:
- `sensor.do_solar_temperature_ab_validation`

Deze entiteit is uitsluitend diagnostisch en heeft geen promotion authority.

#### Bewust ongewijzigd
- raw Solar Forecast-formule;
- temperature candidate-formule en Ross-referentieparameters;
- Open-Meteo input blijft `temperature_2m,global_tilted_irradiance`;
- native 15 minuten / 72 uur / 288 slots;
- performancefactoren;
- bestaande Energy AC-caproute;
- forecast-lock en actual-integratie;
- geen direct/diffuus;
- geen horizonprofiel of fysieke shadingcorrectie;
- geen partial shading;
- geen residual learning;
- geen automatische modelpromotie;
- geen planner/EMS-wijziging;
- geen DOEMS-wijziging;
- geen Google Sheets-structuurwijziging.

### Doel na installatie
Alpha47 moet zelfstandig meerdere representatieve dagen F2-evidence kunnen opbouwen. Pas na beoordeling van die evidence op absolute fout, signed error/bias en WAPE kan F2 formeel groen of niet-groen worden verklaard. F3 blijft tot dat expliciete besluit gesloten.
