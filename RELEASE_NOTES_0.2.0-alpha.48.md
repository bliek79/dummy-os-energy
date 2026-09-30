## Dummy OS Energy 0.2.0-alpha.48 - Solar F3 Horizon Candidate

**Tag:** `0.2.0-alpha.48`

### Doel
Deze prerelease bouwt uitsluitend Fase 3 van het bindende Solar Forecast-optimalisatiecontract: een parallelle fysieke horizon/direct-diffuse candidate bovenop de reeds live bewezen F1-temperatuurcorrectie. Raw Solar en de temperature candidate blijven ongewijzigd beschikbaar en er vindt geen modelpromotie plaats.

### Nieuw
- Open-Meteo Solar vraagt naast `temperature_2m` en `global_tilted_irradiance` ook `direct_radiation` en `diffuse_radiation` op dezelfde native 15-minutentijdas.
- Configureerbare fysieke horizonprofielen voor Noord en Zuid in de Options Flow als JSON `[[azimut,elevatie], ...]`.
- Strikt profielcontract: kompasazimut 0..360 graden, 0/360 verplicht met gelijke elevatie, strikt oplopende punten en lineaire interpolatie.
- Deterministische zonne-azimut en zonne-elevatie per slot, geëvalueerd op de Open-Meteo backward-average bronstempel aan het einde van het kwartier.
- Eenvoudige F3-horizonregel:
  - zon boven/op lokale horizon -> GTI blijft effectief;
  - zon onder lokale horizon -> diffuse_radiation wordt effectieve instraling.
- De F1 Ross-celtemperatuurcorrectie wordt daarna ongewijzigd toegepast.
- Nieuwe canonical candidate-entiteiten:
  - `sensor.do_solar_horizon_candidate_timeline`
  - `sensor.do_solar_horizon_candidate_next_quarter`
  - `sensor.do_solar_horizon_candidate_evaluation_last_completed_quarter`
- Modelidentiteit: `open_meteo_gti_horizon_temperature_candidate_v0.1`.
- F3-candidate krijgt dezelfde pre-actual kwartierlock en actual/coverage-evaluatiebasis als raw/F1, zodat F4 later zonder hindsight kan vergelijken.

### Fail-safe
- Een leeg of ongeldig horizonprofiel maakt uitsluitend de F3-candidate `not_ready`.
- Ontbrekende, niet-finite of niet-uitgelijnde direct/diffuse-data maakt uitsluitend de F3-candidate `not_ready`.
- Raw Solar en F1 temperature candidate blijven onafhankelijk beschikbaar.
- De integratie verzint geen lokale obstakelhoeken; de feitelijke Noord/Zuid-profielpunten moeten fysiek worden vastgesteld en ingevoerd.

### Bewust ongewijzigd
- native 15 minuten / 72 uur / 288 slots;
- raw model `open_meteo_gti_physical_v0.1`;
- F1 temperature model `open_meteo_gti_temperature_candidate_v0.1`;
- performancefactoren en hun semantiek;
- de huidige Energy per-array `ac_limit_kw`-cap voor raw/F1/F3, zodat F3 A/B-isolatie behouden blijft;
- geen partial shading; direct/diffuse-ratio en empirische hard-shadowlogica blijven F5;
- geen residual learning;
- geen automatische kalibratie;
- geen modelpromotie;
- geen planner/EMS- of DOEMS-wijziging.

### Validatie voor publicatie
- volledige testsuite groen;
- F1/F2-regressies groen;
- F3-profiel-, geometrie-, irradiance-, lock-, identity- en fail-safe-tests groen;
- canonical entity-ID-routes aanwezig;
- raw/F1 regressievrij;
- F3 levert 288 slots zodra beide geldige fysieke horizonprofielen zijn ingevoerd.

### Live gate na installatie
1. Voer geldige Noord- en Zuid-horizonprofielen in via Options.
2. Bevestig `sensor.do_solar_horizon_candidate_timeline` met `candidate_status=ready` en 288 punten.
3. Controleer hetzelfde next-quarter slot voor raw, temperature en horizon candidate.
4. Laat een volledig kwartier doorlopen en bevestig de F3-evaluation op dezelfde lock/actual/coveragebasis.
5. Geen promotie; F2 blijft parallel langer bewijs verzamelen.
