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
