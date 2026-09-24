## Dummy OS Energy 0.2.0-alpha.44

**Tag:** `0.2.0-alpha.44`

### Live startup hotfix after alpha.43

Deze prerelease volgt direct op de live Home Assistant-reboot met alpha.43. De forecast-only productgrens blijft ongewijzigd; alpha.44 repareert uitsluitend twee live gevonden startup-/forecastproblemen.

#### Opgelost
- `sensor.do_energy_forecast` en `sensor.do_energy_forecast_timeline` gebruiken opnieuw een geldige kwartieruitlijning. De alpha.43-regressie `NameError: build_time_contract is not defined` is verwijderd zonder Forecast-to-Planner entities terug te brengen.
- De publieke forecastcache gebruikt rechtstreeks de bestaande 15-minuten `ceil_quarter`-tijdhelper en behoudt exact dezelfde rolling 72h / 288-slot semantiek.
- Zware Energy Forecast/quality-berekeningen starten niet meer tijdens de kritieke Home Assistant bootstrapfase.
- Executor-backed Forecast, Evaluation Metrics, Time Windows, Recency Weighting, Fallback Hierarchy en Meaningful Confidence wachten nu tot Home Assistant de state `running` heeft bereikt.
- Die refreshes draaien daarna als config-entry background tasks en blokkeren Home Assistant startup of `async_block_till_done` niet.
- De Weather/Prices/Solar cloud-source wave is eveneens omgezet van een gewone tracked HA-task naar een config-entry background task.

#### Bewust ongewijzigd
- native architectuur: 15 minuten / 72 uur / 288 slots;
- historical_baseline model 0.4;
- normal / away / unclassified profielcontract;
- forecast learning, kwaliteit, confidence en validatie-inhoud;
- Weather, Solar, Prices en Degree Days-functionaliteit;
- geen `do_plan_*`, Plan Store, Scheduler, Safety, Presence/Away-scheduler of Operating Mode in Dummy OS Data;
- DOEMS blijft de enige Dummy OS planner/EMS-route;
- anker_ems blijft fysieke batterijauthority.

### Live aanleiding
De alpha.43 reboot liet drie relevante feiten zien:
1. de twee publieke Energy Forecast-entiteiten faalden tijdens registratie door een ontbrekende tijdhelper;
2. Fallback Hierarchy en Meaningful Confidence stonden nog als pending Dummy OS Data executor-taken in de Home Assistant stage-2 timeout;
3. ZHA werd opnieuw door dezelfde globale stage-2 timeout geannuleerd tijdens zijn SQLite attribute-load, terwijl de database eerder offline gezond was bevonden.

Alpha.44 verwijdert daarom de resterende Dummy OS Data-berekeningen uit het kritieke bootstrapvenster.

### Acceptatie na installatie
- volledige Home Assistant-reboot, zonder handmatige ZHA-reload;
- `sensor.do_energy_forecast` en `sensor.do_energy_forecast_timeline` moeten foutloos registreren;
- geen `NameError: build_time_contract`;
- geen Dummy OS Data Fallback/Meaningful/Forecast refresh als stage-2 pending taak;
- ZHA moet normaal tijdens dezelfde reboot laden;
- minimaal één kwartiergrens observeren en bevestigen dat de forecast foutloos blijft verversen;
- de forecast-only scope blijft gesloten voor planner/EMS-functionaliteit.

### Buiten deze release
De live log bevatte daarnaast een afzonderlijke pending `Dummy OS EMS execution max-runtime stop` taak in `anker_ems` en Recorder-waarschuwingen voor zeer grote `sensor.dummy_os_ems_bridge_*` attributen. Die horen niet bij Dummy OS Data en worden in alpha.44 niet gewijzigd.
