# GitHub Release

**Tag:** `0.2.0-alpha.21`  
**Release title:** Dummy OS Energy 0.2.0-alpha.21 - Central SOC Contract v1

## Dummy OS Energy 0.2.0-alpha.21

Deze prerelease introduceert de centrale fail-closed SOC Contract v1-laag voor de Dummy OS Energy plannerketen.

### Nieuw
- Nieuwe `sensor.do_plan_soc_contract` als centrale actuele SOC-interface.
- De bestaande Anker-SOC `sensor.anker_solix_solarbank_max_ac_185_soc` blijft de expliciete ruwe bron, maar wordt alleen nog door de SOC-adapter gelezen.
- DO Plan Energy Need en Safety/Prestart consumeren voortaan het centrale SOC-contract in plaats van de ruwe batterij-entiteit rechtstreeks.
- Contractdiagnostiek bevat bronstatus, gevalideerde `soc_percent`, reden/blockers, observatietijd en last-known-good informatie.

### Fail-closed gedrag
- `unknown`, `unavailable`, ontbrekende, niet-numerieke, niet-eindige en buiten 0-100% vallende SOC wordt geblokkeerd.
- Een ongeldige actuele bron levert geen stille nulwaarde.
- Last-known-good blijft uitsluitend diagnostisch en wordt nooit als actuele SOC gebruikt.
- In deze stap is bewust geen tweede/fallback SOC-bron toegevoegd.

### Veiligheidsgrens ongewijzigd
- `shadow_only=true`.
- `active_use_permitted=false`.
- `physical_execution_authority=false`.
- Geen nieuwe Scheduler-, execution-handoff-, mode-switch- of batterijservicebevoegdheid.
- Native architectuur blijft 15 minuten / 72 uur / 288 slots.

### Validatie
- Gerichte SOC Contract v1-tests zijn groen.
- Volledige regressiesuite is groen.
- Bestaande Step 9 Profile Contract CI, compile, manifestvalidatie, alpha.12.18 runtime gate en validation ZIP zijn groen op PR #207.

### Live validatie na installatie
Controleer na installatie en herstart minimaal `sensor.do_plan_soc_contract`, `sensor.do_plan_energy_need` en de Safety/Prestart-entiteiten. Bevestig dat de centrale SOC overeenkomt met de ruwe Anker-SOC, dat `soc_source_entity` naar `sensor.do_plan_soc_contract` verwijst en dat alle fysieke uitvoeringsflags gesloten blijven. Controleer daarna de Home Assistant-log op nieuwe fouten, warnings en MainThread-meldingen.
