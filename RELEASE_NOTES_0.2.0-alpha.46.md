## Dummy OS Energy 0.2.0-alpha.46

**Tag:** `0.2.0-alpha.46`

### Solar Forecast F1 - canonical entity-ID fix

Deze prerelease repareert uitsluitend de Home Assistant entity-ID-registratie van de in alpha.45 live groen bevonden Solar temperature candidate. De rekenlaag, Open-Meteo-input, temperatuurformule, performancefactoren, AC-caproute, forecast-lock en actual-validatie blijven inhoudelijk ongewijzigd.

#### Live bewijs alpha.45
- raw Solar timeline: 288/288;
- temperature candidate timeline: 288/288;
- `candidate_status=ready`;
- `temperature_candidate_last_error=None`;
- raw en candidate next-quarter exact hetzelfde slot;
- raw en candidate completed-quarter exact hetzelfde slot en dezelfde `forecast_captured_at`;
- temperature correction fysisch consistent bij gemeten live sample.

#### Fix
De drie automatisch gegenereerde alpha.45 entity-ID's worden veilig gemigreerd naar de vaste Dummy OS namespace:
- `sensor.do_solar_temperature_candidate_timeline`
- `sensor.do_solar_temperature_candidate_next_quarter`
- `sensor.do_solar_temperature_candidate_evaluation_last_completed_quarter`

Bekende alpha.45 automatisch gegenereerde IDs worden expliciet als veilige migratie-alias herkend, zodat bestaande registry rows in-place worden hernoemd en geen duplicaten worden aangemaakt.

Daarnaast gebruikt de algemene Solar-statusdiagnostiek voor de parallelle kandidaat voortaan `observation_parallel` in plaats van `observation_shadow`. De term shadow blijft daarmee gereserveerd voor echte fysieke shading.

#### Bewust ongewijzigd
- native 15 minuten / 72 uur / 288 slots;
- raw model en raw entiteiten;
- Open-Meteo GTI + temperature_2m contract;
- Ross-referentieparameters;
- performancefactoren;
- bestaande Energy AC-caproute;
- candidate formule en candidate lock;
- geen direct/diffuus;
- geen horizon/shading;
- geen partial shading;
- geen residual learning;
- geen modelpromotie;
- geen DOEMS-wijziging.

#### Na installatie
Eerst bevestigen dat de drie vaste `sensor.do_solar_temperature_candidate_*` IDs bestaan, dat raw en candidate beide 288 slots houden en dat `candidate_status=ready` blijft. Daarna mag F2-dataverzameling starten: representatieve gelockte kwartieren raw versus temperature candidate vergelijken op absolute fout, signed error/bias en geaggregeerde WAPE.
