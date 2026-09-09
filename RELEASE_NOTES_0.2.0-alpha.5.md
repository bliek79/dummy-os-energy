# GitHub Release

**Tag:** `0.2.0-alpha.5`  
**Release title:** Dummy OS Energy 0.2.0-alpha.5 - DO Plan Preview

## Dummy OS Energy 0.2.0-alpha.5

Deze pre-release publiceert Planner Stap 4: de observer-only `do_plan_preview`-laag bovenop de live-gevalideerde plannerstappen 1 t/m 3.

### Nieuw
- Nieuwe plannerdiagnose `do_plan_preview`.
- Veiligheidslading wordt afgeleid uit het Stap-3 reserve-tekort; Stap 3 blijft de enige autoritatieve reserve-SOC-bron.
- Laadefficiëntie wordt meegenomen in de benodigde netinput voor veiligheidsladen.
- Goedkoopste beschikbare laaduren vóór `first_usable_solar` worden observer-only geselecteerd.
- Eventueel niet inpasbaar reserve-tekort blijft expliciet zichtbaar als `safety_unallocated_battery_kwh`.
- Vrije batterij-energie boven de beschermde reserve wordt apart omgerekend naar maximaal leverbare energie na ontlaadverlies.
- Importvermijding en exporthandel worden als twee afzonderlijke financiële routes beoordeeld; import- en exportprijs worden niet aan elkaar gelijkgesteld.
- Publiceert onder andere `preview_decision`, `required_grid_input_kwh`, `max_deliverable_from_free_kwh`, `price_min_import`, `price_max_import`, `price_spread_import`, aparte self-use/export kandidaten en marges, plus `solar_capacity_protection`.
- Een conservatieve zonne-capaciteitsbescherming voorkomt dat theoretische handelslading beschikbare batterijruimte vóór verwachte bruikbare zon wegdrukt.

### Vaste uitgangspunten
- native forecastarchitectuur blijft 15 minuten / 72 uur / 288 slots;
- plannerprojectie blijft exact 72 volledige uren;
- charge efficiency: 92%;
- discharge efficiency: 92%;
- roundtrip efficiency volgt uit beide rendementen;
- minimum handelsmarge: 0,10 per kWh;
- maximum observer-only laad- en ontlaadvermogen: 3200 W;
- echte `0.0` blijft geldig;
- missing/unknown/NaN/inf wordt nooit stilzwijgend nul;
- ontbrekende exportprijs wordt nooit vervangen door importprijs.

### Architectuurgrenzen
- `do_plan_preview` maakt nog geen fysiek plan aan.
- Geen Plan Store, Scheduler, Bridge, Safety of Execution wordt aangeroepen.
- `reserve_recalculated=false`: Stap 4 berekent de beschermde reserve niet opnieuw.
- De planner entity-ID cleanup blijft bewust uitgesteld tot het einde van de plannerbouw.
- Dummy OS EMS blijft tijdens de overgang beschikbaar als referentie en rollback.

### Veiligheid
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- `calculation_scope=planner_preview_only`.

### Live-validatie na installatie
Controleer na installatie en herstart minimaal de nieuwe `DO Plan Preview`-entiteit:
- `status`, `valid`, `reason`, `blockers`;
- `preview_decision`;
- `input_status`, `input_rows_signature`, `reserve_status`;
- `reserve_deficit_battery_kwh` en `required_grid_input_kwh`;
- `safety_charge_needed`, `safety_schedule_sufficient`, `safety_unallocated_battery_kwh` en geselecteerde laaduren;
- `free_above_reserve_battery_kwh` en `max_deliverable_from_free_kwh`;
- importprijs min/max/spread;
- aparte self-use- en exportkandidaten/marges;
- `solar_capacity_protection`;
- opnieuw alle drie observer-only veiligheidsvlaggen.

Planner Stap 5 wordt pas inhoudelijk vrijgegeven nadat Stap 4 live is geaccepteerd.
