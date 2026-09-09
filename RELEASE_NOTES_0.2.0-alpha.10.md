# GitHub Release

**Tag:** `0.2.0-alpha.10`  
**Release title:** Dummy OS Energy 0.2.0-alpha.10 - Time Windows Main-Thread Fix

## Dummy OS Energy 0.2.0-alpha.10

Deze prerelease lost uitsluitend de laatste Dummy OS Energy main-threadwaarschuwing uit de live alpha.9-startup op. Planner Stap 5 wordt niet toegevoegd.

### Opgelost
- `DO Energy Time Windows` voert Peak Learning + Time Windows observerberekening niet langer synchronisch uit tijdens entity state updates.
- De bestaande observerberekening draait via executor-backed caching met coalescing van overlappende refreshes.
- `native_value` en `extra_state_attributes` lezen alleen het laatst voltooide cache-resultaat.
- Tijdens de eerste achtergrondberekening wordt fail-safe `initializing` gepubliceerd met `observer_calculation_pending`.

### Bewust ongewijzigd
- forecastformules;
- Time Windows-algoritme en drempels;
- entity-ID `sensor.do_energy_time_windows`, unique_id en friendly name;
- native 15 minuten / 72 uur / exact 288 slots;
- Planner Stap 1 t/m 4;
- reserve-/SOC-, prijs- en solarcontracten;
- `shadow_only=true`, `active_use_permitted=false` en `physical_execution_authority=false`;
- unknown/unavailable wordt niet stilzwijgend als nul behandeld;
- geen Planner Stap 5-functionaliteit.

### Live-validatie na installatie
Na installatie via HACS en een volledige Home Assistant-herstart moet worden gecontroleerd dat `sensor.do_energy_time_windows`, die in alpha.9 nog 0,637 s main-threadtijd veroorzaakte, niet meer als main-threadwaarschuwing terugkomt. Daarnaast moet de volledige startup-log worden gecontroleerd op andere nieuwe `dummy_os_data` main-threadwaarschuwingen. Planner Stap 5 blijft geparkeerd totdat deze live gate schoon is.
