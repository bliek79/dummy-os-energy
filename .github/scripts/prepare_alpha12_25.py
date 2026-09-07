from pathlib import Path
import json

version = "0.1.0-alpha.12.25"
const = Path("custom_components/dummy_os_data/const.py")
text = const.read_text().replace('VERSION = "0.1.0-alpha.12.24"', f'VERSION = "{version}"', 1)
const.write_text(text)

manifest = Path("custom_components/dummy_os_data/manifest.json")
data = json.loads(manifest.read_text())
data["version"] = version
manifest.write_text(json.dumps(data, indent=2) + "\n")

test = Path("tests/test_release_consistency.py")
text = test.read_text().replace('VERSION = "0.1.0-alpha.12.24"', f'VERSION = "{version}"', 1)
test.write_text(text)

notes = Path("RELEASE_NOTES.md")
old = notes.read_text()
head = '''# GitHub Release

**Tag:** `0.1.0-alpha.12.25`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.25 - Step 14 Exact 72 Complete Planner Hours

## Dummy OS Forecast 0.1.0-alpha.12.25

Deze pre-release implementeert Stap 14: exact 72 volledige planneruren, afgeleid uit dezelfde native kwartierforecast zonder padding en zonder tweede forecastarchitectuur.

### Nieuw
- Nieuwe canonical interface `sensor.do_energy_forecast_planner_hours`.
- Exact 72 planneruurrecords van elk precies vier opeenvolgende echte 15-minutenkwartieren.
- Plannerstart wordt uitgelijnd op het eerstvolgende volledige lokale klokuur.
- Bij native start op HH:15 / HH:30 / HH:45 worden respectievelijk 3 / 2 / 1 voorloopkwartieren uitsluitend voor de uurlaag overgeslagen.
- Hetzelfde `historical_baseline`-model mag intern exact evenveel extra kwartieren aan de staart berekenen; maximaal 291 interne kwartieren.
- De publieke productieforecast blijft exact 288 slots.
- DST-overgangen blijven 72 chronologische echte 60-minutenblokken met ISO-offsets; geen kunstmatige lokale uren.
- Een ontbrekend kwartier maakt het betreffende planneruur `energy_kwh=None`; partiële sommen en nulvulling zijn verboden.

### Veiligheidscontract
- `padding_used=false`.
- `second_forecast_architecture=false`.
- `native_public_slots=288`.
- `planner_hour_count=72`.
- `quarters_per_hour=4`.
- `extra_quarters_generated` is uitsluitend 0..3 en gelijk aan de uitlijnings-offset.
- Normal/Away blijven strikt gescheiden; unclassified leent geen historie.
- Package 41, Dummy OS EMS en fysieke batterijbesturing zijn in Stap 14 niet gewijzigd. Daadwerkelijke Forecast→Planner-consumptie blijft Stap 15.

### Ongewijzigd
- Productieforecast: `historical_baseline` modelversie `0.4`.
- Native resolutie/horizon: 15 minuten / 72 uur / 288 publieke slots.
- Productie-recency: 28 dagen half-life.
- Productieconfidence, Model Health/readiness, fallback, Peak Learning, Time Windows, Recency Weighting, Meaningful Confidence en Horizon Quality blijven inhoudelijk ongewijzigd.
- Friendly-name-opschoning blijft geparkeerd.

### Live validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_planner_hours` exact onder de canonical entity-id bestaat.
- Bevestigen dat `planner_hour_count=72`, `quarters_per_hour=4`, `padding_used=false` en `second_forecast_architecture=false` live worden gepubliceerd.
- Bevestigen dat `leading_quarter_offset` en `extra_quarters_generated` exact bij de actuele native startuitlijning passen.
- Bevestigen dat planner_start/planner_end exact 72 echte uren omvatten en alle 72 uurrecords chronologisch aansluiten.
- Tegelijk bevestigen dat `sensor.do_energy_forecast_timeline` exact 288 publieke punten / 15 minuten / 72 uur / model 0.4 / 28-daagse recency blijft.

---

'''
notes.write_text(head + old)
