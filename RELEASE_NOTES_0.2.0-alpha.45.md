## Dummy OS Energy 0.2.0-alpha.45

**Tag:** `0.2.0-alpha.45`

### Solar Forecast F1 - parallel temperature candidate

Deze prerelease bouwt Fase 1 van de Solar Forecast-optimalisatie uitsluitend in Dummy OS Energy als proving ground. De bestaande actieve Solar Forecast blijft de raw baseline en wordt niet vervangen. DOEMS alpha25 wordt niet gewijzigd.

#### Nieuw
- Open-Meteo Solar vraagt naast `global_tilted_irradiance` nu ook `temperature_2m` op binnen dezelfde native 15-minutenbron.
- Een afzonderlijke temperature candidate berekent per array:
  - intervalgemiddelde buitentemperatuur uit de twee temperatuurgrenzen van het kwartier;
  - geschatte celtemperatuur met het Ross-referentiemodel;
  - een transparante temperatuurcorrectiefactor;
  - kandidaatvermogen en -energie met dezelfde bestaande Energy performancefactor en AC-caproute als raw.
- Nieuwe diagnostische entiteiten:
  - `sensor.do_solar_temperature_candidate_timeline`
  - `sensor.do_solar_temperature_candidate_next_quarter`
  - `sensor.do_solar_temperature_candidate_evaluation_last_completed_quarter`
- Raw en candidate worden voor hetzelfde kwartier en op hetzelfde lockmoment vastgelegd. De candidate-evaluatie gebruikt exact dezelfde actual- en coveragegegevens als raw.
- De actieve candidate-snapshot en laatste candidate-evaluatie worden persistent opgeslagen.

#### F1 referentieparameters
- Ross-coefficient `k = 0.0342 °C·m²/W`
- temperatuurcoëfficiënt `alpha = -0.004 /°C`
- `T_STC = 25 °C`
- `G_STC = 1000 W/m²`

Deze waarden zijn expliciete kandidaatparameters voor A/B-validatie en zijn geen definitief gekalibreerde DOEMS-defaults.

#### Fail-safe
- De raw GTI-timeline wordt eerst opgebouwd en blijft leidend.
- Ontbrekende, niet-finite of niet-uitgelijnde temperatuurdata maakt uitsluitend de temperature candidate `not_ready`.
- Bij candidate-fout worden geen stale candidate-punten als actuele voorspelling aangeboden.
- De bestaande raw Solar Forecast, kwartierlock, actual-integratie, coverage-eisen en horizon-evaluaties blijven intact.

#### Bewust ongewijzigd
- native architectuur: 15 minuten / 72 uur / exact 288 slots;
- raw model `open_meteo_gti_physical_v0.1`;
- bestaande per-array DC-kWp, tilt, azimut en performancefactor;
- bestaande Energy AC-begrenzingsroute;
- huidige actieve Solar Forecast-entiteiten;
- geen direct/diffuus-model;
- geen horizon/shading;
- geen partial shading;
- geen residual/self-learning;
- geen automatische performancefactor-herkalibratie;
- geen planner/EMS/execution-wijzigingen;
- geen DOEMS-wijzigingen.

#### Architectuurnotitie
De actuele Energy raw-implementatie begrenst momenteel per array met de geconfigureerde `ac_limit_kw`. Het Solar-optimalisatiewerkdocument beschrijft voor de uiteindelijke doelarchitectuur een invertergroep-cap met proportionele member scaling. Alpha.45 wijzigt de caproute bewust niet, zodat temperatuur de enige nieuwe A/B-variabele blijft. Dit consistentiepunt moet vóór een latere model-freeze/DOEMS-parity afzonderlijk worden opgelost of formeel verklaard.

#### Technische validatie
Voor publicatie moeten minimaal groen zijn:
- Python compile;
- volledige pytest-suite;
- bestaande Solar raw regressietests;
- nieuwe temperatuurformule- en fail-safe-tests;
- F1 source-/lock-/identitycontract;
- forecast-only scope.

#### Na installatie
Alpha.45 is uitsluitend een observation candidate. De volgende stap is F2: meerdere representatieve dagen raw versus temperature candidate vergelijken op vooraf gelockte kwartieren, met absolute fout, signed error/bias en geaggregeerde WAPE. Er vindt in alpha.45 geen modelpromotie plaats.

#### Bronreferentie
De fysieke rekenprincipes zijn zelfstandig binnen Dummy OS Energy geïmplementeerd met `rany2/open-meteo-solar-forecast` (MIT) als technische referentie voor Ross/celtemperatuur en de 15-minutensemantiek. Er is geen volledige upstream-integratie overgenomen.
