from pathlib import Path
import json

version = "0.1.0-alpha.12.24"
const = Path("custom_components/dummy_os_data/const.py")
text = const.read_text()
text = text.replace('VERSION = "0.1.0-alpha.12.23"', f'VERSION = "{version}"', 1)
const.write_text(text)

manifest = Path("custom_components/dummy_os_data/manifest.json")
data = json.loads(manifest.read_text())
data["version"] = version
manifest.write_text(json.dumps(data, indent=2) + "\n")

notes = Path("RELEASE_NOTES.md")
old = notes.read_text()
head = '''# GitHub Release

**Tag:** `0.1.0-alpha.12.24`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.24 - Step 13 Objective Model Health Readiness

## Dummy OS Forecast 0.1.0-alpha.12.24

Deze pre-release implementeert Stap 13A: de bestaande Energy Forecast Model Health wordt een objectieve evidence-readinessstatus, zonder een tweede publieke healthsensor en zonder wijziging van de productieforecast.

### Gewijzigd
- De bestaande `sensor.do_energy_forecast_model_health` blijft dezelfde publieke entiteit met hetzelfde unique_id en dezelfde naam.
- De state is voor leerbare profielen uitsluitend `collecting`, `learning`, `usable` of `strong`.
- Tijdelijke bronbeschikbaarheid overschrijft de opgebouwde model-readiness niet meer; deze wordt apart gepubliceerd via `runtime_input_status`, `forecast_operational_input_ok` en `runtime_blockers`.
- Readiness gebruikt historie, forward-looking evaluaties, forecastcoverage, productieconfidence, accuracy, MAE, absolute bias, Step-12-horizonbewijs en voldoende-basis segmentkwaliteit.
- De gates zijn hiërarchisch; een zwakke foutmetric kan niet door veel samples of hoge coverage worden weggemiddeld.
- Missing/non-numeric evidence wordt nooit nul.
- Normal en Away blijven strikt gescheiden; `unclassified` behoudt expliciet `profile_unclassified`.

### Readinesscontract
- `learning`: >=7 historiedagen, >=32 evaluaties, >=80% coverage, >=45% confidence.
- `usable`: >=14 historiedagen, >=256 evaluaties, >=95% coverage, >=60% confidence, >=35% accuracy, MAE <=0,100 kWh/kwartier en absolute bias <=0,020 kWh/kwartier.
- `strong`: >=28 historiedagen, >=1.024 evaluaties, >=98% coverage, >=65% confidence, >=45% accuracy, MAE <=0,075 kWh/kwartier en absolute bias <=0,010 kWh/kwartier.
- Voor `strong` moeten bovendien alle acht Step-12-horizons minimaal `observing` zijn.
- Een horizon met `sufficient_basis` en accuracy <25% of absolute bias >0,030 kWh blokkeert `strong`.
- Een voldoende-basis uur- of day_type x daypart-segment met accuracy <20% blokkeert `strong`.

### Ongewijzigd
- `forecast.py` is niet gewijzigd.
- Native architectuur blijft exact 15 minuten / 72 uur / 288 slots.
- Productiemodel blijft `historical_baseline` modelversie `0.4`.
- Productie-recency blijft 28 dagen half-life.
- Productieconfidence, fallback, Peak Learning, Time Windows, Recency Weighting, Meaningful Confidence en Horizon Quality blijven inhoudelijk ongewijzigd.
- Package 41 / Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- De brede friendly-name-opschoning blijft bewust geparkeerd.

### Live validatie na installatie
- Bevestigen dat `sensor.do_energy_forecast_model_health` dezelfde canonical entiteit blijft.
- Bevestigen dat de state een readinessstatus is en niet meer `source_unavailable` wordt door een tijdelijke runtimebronstoring.
- Bevestigen dat `runtime_input_status` en `forecast_operational_input_ok` de runtimebron afzonderlijk weergeven.
- Bevestigen dat de actuele Normal-basis niet als `strong` kan eindigen zolang 28 historiedagen en alle acht observing horizons ontbreken.
- Tegelijk bevestigen dat de productieforecast exact 288 slots / 15 minuten / 72 uur / model 0.4 / 28-daagse recency blijft.

---

'''
notes.write_text(head + old)
