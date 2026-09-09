# GitHub Release

**Tag:** `0.2.0-alpha.12`  
**Release title:** Dummy OS Energy 0.2.0-alpha.12 - Planner Step 5 72h Sequential Simulation

## Dummy OS Energy 0.2.0-alpha.12

Deze prerelease implementeert Planner Stap 5 als observer-only `DO Plan 72h` sequentiële simulatie bovenop de bestaande gevalideerde Planner Stap 1-4 keten.

### Toegevoegd
- Exact 72 volledige planneruren als sequentiële batterijsimulatie.
- Twee simulatiepasses: baseline zonder trade en candidate met uitsluitend de Stap-4 tradecandidate.
- Solar-first energiestroom en gedeelde 3200 W laadlimiet voor solar + grid.
- 7,2 kWh batterij, 5% minimum-SOC, 7% software-reserve, 2% diagnostische execution-buffer en 92%/92% efficiency.
- Uurdiagnostiek voor SOC en energieflows; baseline/candidate samenvatting en `solar_displacement_kwh`.
- Strikte upstream signature/72h-validatie; missing/NaN wordt niet als nul behandeld.

### Safetyrechten onveranderd
- `shadow_only=true`
- `active_use_permitted=false`
- `physical_execution_authority=false`
- `plan_store_write=false`
- `scheduler_invoked=false`
- `safety_chain_invoked=false`
- `service_calls_performed=false`

Er wordt geen plan opgeslagen, geen scheduler aangeroepen en geen fysieke batterijactie uitgevoerd.

### Live-validatie
Controleer na installatie `sensor.do_plan_72h`: status, `hour_count=72`, signatures, safetyflags, baseline/candidate, SOC-verloop en afwezigheid van nieuwe `dummy_os_data` main-threadwaarschuwingen.
