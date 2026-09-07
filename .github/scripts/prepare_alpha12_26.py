from pathlib import Path

VERSION_OLD = "0.1.0-alpha.12.25"
VERSION_NEW = "0.1.0-alpha.12.26"


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing release anchor in {path}: {old!r}")
    p.write_text(text.replace(old, new, 1))

replace_once(
    "custom_components/dummy_os_data/const.py",
    f'VERSION = "{VERSION_OLD}"',
    f'VERSION = "{VERSION_NEW}"',
)
replace_once(
    "custom_components/dummy_os_data/manifest.json",
    f'"version": "{VERSION_OLD}"',
    f'"version": "{VERSION_NEW}"',
)
replace_once(
    "tests/test_release_consistency.py",
    f'VERSION = "{VERSION_OLD}"',
    f'VERSION = "{VERSION_NEW}"',
)

notes = Path("RELEASE_NOTES.md")
current = notes.read_text()
header = '''# GitHub Release

**Tag:** `0.1.0-alpha.12.26`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.26 - Step 15 Stable Forecast to Planner Contract

## Dummy OS Forecast 0.1.0-alpha.12.26

Deze pre-release implementeert Stap 15, de laatste inhoudelijke forecaststap: één stabiel, versioneerbaar Forecast→Planner-contract bovenop de live-gevalideerde Step-13-readiness en Step-14 planneruren.

### Nieuw
- Nieuwe canonical interface `sensor.do_energy_forecast_planner_contract`.
- Contractnaam `dummy_os_forecast_to_planner`, `contract_version=1`, `schema_version=1` en `profile_contract_version=1`.
- De planner ontvangt exact dezelfde 72 uurrecords uit Step 14 plus expliciete profiel-, tijd-, quality/readiness- en runtime-metadata.
- `ready_for_planner=true` vereist een leerbaar profiel, exact 288 native slots, 72 planneruren, 4 echte kwartieren per uur, exact 72 echte uren, geen padding, geen tweede forecastarchitectuur en Model Health `usable` of `strong`.
- Runtimebronbeschikbaarheid blijft afzonderlijk zichtbaar via `runtime_input_status`, `forecast_operational_input_ok` en `runtime_blockers`; een tijdelijke bronstoring overschrijft opgebouwde model-readiness niet.
- Step 13 Model Health en Step 14 Planner Hours gebruiken nu gedeelde helpers; het contract consumeert exact dezelfde berekeningen en bevat geen duplicaatlogica.
- `hours` is recorder-excluded.
- Canonical entity-ID alias en registry-migratieroute zijn vanaf de eerste release aanwezig.

### Contractveiligheid
- `physical_execution_authority=false`: dit forecastcontract geeft geen fysieke batterijopdracht.
- `unknown`/`unavailable`/missing wordt nooit nul.
- Een onvolledig uur, fout tijdvenster, padding, tweede architectuur, profile mismatch of onvoldoende Model Health blokkeert het contract deterministisch.
- Normal en Away blijven strikt gescheiden; mixed/unclassified is niet planner-ready.
- Interne fallback- en recencyformules maken bewust geen deel uit van het publieke contract.

### Ongewijzigd
- Native productiearchitectuur: 15 minuten / 72 uur / exact 288 publieke slots.
- Productiemodel: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- Step-14 uurlaag: exact 72 volledige planneruren uit echte kwartieren, maximaal 0-3 interne extra kwartieren, geen padding.
- Package 41, Dummy OS EMS en fysieke batterijbesturing zijn in deze forecastrelease niet inhoudelijk herschreven.
- Friendly-name-opschoning blijft geparkeerd tot na afronding van deze forecaststap.

### Live-validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_planner_contract` exact canonical bestaat.
- Bevestigen: state `ready`, `ready_for_planner=true`, `contract_version=1`, `schema_version=1`, `profile=normal`.
- Bevestigen: `native_slot_count=288`, `planner_hour_count=72`, `quarters_per_hour=4`, `padding_used=false`, `second_forecast_architecture=false`.
- Bevestigen dat `planner_start` tot `planner_end` exact 72 echte uren omvat en `hours` exact 72 aansluitende uurrecords bevat.
- Bevestigen dat Model Health minimaal `usable` is en runtimebronstatus apart blijft staan.
- Tegelijk bevestigen dat `sensor.do_energy_forecast_timeline` exact 288 punten / 15 minuten / 72 uur / model 0.4 blijft.

---

'''
notes.write_text(header + current)
