# GitHub Release

**Tag:** `0.2.0-alpha.13`  
**Release title:** Dummy OS Energy 0.2.0-alpha.13 - Planner Step 5 Grid Support Shadow

## Dummy OS Energy 0.2.0-alpha.13

Deze prerelease voegt uitsluitend observer-only netondersteuningsdiagnostiek toe bovenop Planner Stap 5.

### Toegevoegd
- `DO Plan Grid Support` met shadow-testgrens X = 0,25 kWh op Step-2 `additional_grid_charge_kwh`.
- Splitsing in laadbaar batterijtekort en onvermijdbaar resttekort; nooit laden boven 100% SOC.
- Native 15-minuten economische laadvensterselectie binnen exact 72 uur / 288 slots.
- Echte all-in importprijs, 92% laadefficiëntie, solar-first gedeelde 3200 W laadheadroom en kritieke deadline.
- Baseline/candidate 72h-resimulatie met kostendelta en solar displacement.
- Exacte native home-quarterwaarden worden additief door de bestaande Forecast->Planner-keten meegenomen.

### Safetyrechten onveranderd
- `shadow_only=true`
- `active_use_permitted=false`
- `physical_execution_authority=false`
- `plan_store_write=false`
- `scheduler_invoked=false`
- `safety_chain_invoked=false`
- `service_calls_performed=false`

Geen fysieke batterijactie, scheduler of Plan Store. X=0,25 kWh is uitsluitend de eerste shadow-testwaarde en nog geen definitieve operationele instelling.
