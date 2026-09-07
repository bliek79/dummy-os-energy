from pathlib import Path
import json

version = "0.1.0-alpha.12.23"

const = Path("custom_components/dummy_os_data/const.py")
text = const.read_text()
assert 'VERSION = "0.1.0-alpha.12.22"' in text
const.write_text(text.replace('VERSION = "0.1.0-alpha.12.22"', f'VERSION = "{version}"', 1))

manifest = Path("custom_components/dummy_os_data/manifest.json")
data = json.loads(manifest.read_text())
assert data["version"] == "0.1.0-alpha.12.22"
data["version"] = version
manifest.write_text(json.dumps(data, indent=2) + "\n")

consistency = Path("tests/test_release_consistency.py")
text = consistency.read_text()
assert 'VERSION = "0.1.0-alpha.12.22"' in text
consistency.write_text(text.replace('VERSION = "0.1.0-alpha.12.22"', f'VERSION = "{version}"', 1))

notes = Path("RELEASE_NOTES.md")
old = notes.read_text()
head = """# GitHub Release

**Tag:** `0.1.0-alpha.12.23`  
**Release title:** Dummy OS Forecast 0.1.0-alpha.12.23 - Step 12 Forecast Quality by Horizon Observer

## Dummy OS Forecast 0.1.0-alpha.12.23

Deze pre-release implementeert Stap 12 als strikt observer-only kwaliteitsmeting per forecastafstand. De productieforecast zelf blijft ongewijzigd.

### Nieuw
- Nieuwe observer `sensor.do_energy_forecast_quality_by_horizon` met algoritme `forecast_horizon_quality_observer_v1`.
- Vaste native horizonset: 0h-control, 1h, 3h, 6h, 12h, 24h, 48h en de 72h-rand.
- De 72h-rand is exact het laatste van de 288 native kwartieren: start op +71u45 en einde exact op +72u; er wordt geen 289e slot gemaakt.
- Per kwartier worden alleen acht compacte probes uit de bestaande productieforecast vastgelegd.
- Afgeronde evidence wordt compact per profiel, lokale dag en horizon geaggregeerd; pending probes worden na evaluatie verwijderd.
- Per horizon worden sample count, distinct local days, MAE, bias, WAPE-achtige accuracy, gemiddelde captured confidence, source-distributie en uitsluitingen gevolgd.
- Normal en Away blijven strikt gescheiden. Profile mismatch, mixed/unclassified, onvoldoende coverage, invalid actual, malformed snapshot en late capture leveren geen nulwaarden en geen positief bewijs.

### Bewijs- en veiligheidscontract
- `observer_only = true`.
- `forecast_influence_enabled = false`.
- Observing per horizon vanaf minimaal 32 geldige evaluaties over minimaal 8 lokale dagen.
- Sufficient basis per horizon vanaf minimaal 64 geldige evaluaties over minimaal 14 lokale dagen.
- De hoofdstatus wordt pas `sufficient_basis` wanneer alle acht horizons voldoende basis hebben.
- Geen historische backfill met toekomstige informatie; elke horizonprobe is daadwerkelijk vóór het targetkwartier vastgelegd.
- Een grotere of niet-monotone fout op langere horizon is een meetresultaat en veroorzaakt geen automatische modelwijziging.

### Ongewijzigd
- Native architectuur: exact 15 minuten / 72 uur / 288 slots.
- Productiemodel: `historical_baseline` modelversie `0.4`.
- Productie-recency: 28 dagen half-life.
- `forecast.py` is niet gewijzigd.
- Energy Store normalizer en schema 2 zijn niet gewijzigd.
- Productieconfidence, Meaningful Confidence observer, Fallback Hierarchy, Peak Learning, Time Windows en Recency Weighting veranderen niet.
- Model Health, Weather, Solar, Prices, Degree Days, Package 41, Dummy OS EMS en fysieke batterijbesturing zijn niet gewijzigd.
- De brede friendly-name-opschoning blijft bewust geparkeerd tot na de inhoudelijke forecaststappen.

### Live validatie na installatie
- Bevestigen dat de horizonobserver actief publiceert met `observer_only=true` en `forecast_influence_enabled=false`.
- Bevestigen dat exact de acht vastgelegde horizons aanwezig zijn, inclusief de 72h-rand op 4305 minuten.
- Bevestigen dat de productieforecast exact 288 slots op 15 minuten / 72 uur blijft leveren met model 0.4 en 28-daagse recency.
- Verwachten dat 0h/1h-evidence eerder begint op te bouwen dan lange horizons; voor de 72h-rand kan pas na minimaal 72 uur natuurlijke live evidence ontstaan.
- Geen productiepromotie of horizoncorrectie uitvoeren vanuit deze release.

---

"""
notes.write_text(head + old)
