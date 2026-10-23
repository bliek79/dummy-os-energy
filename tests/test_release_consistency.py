"""Check release version metadata, retained platform and retired integrations."""
from pathlib import Path
import json

ROOT = Path(__file__).parents[1]
MOD = ROOT / "custom_components/dummy_os_data"
VERSION = "0.2.0-alpha.53"

def source(name):
    return (MOD / name).read_text(encoding="utf-8")

def test_release_metadata():
    assert json.loads(source("manifest.json"))["version"] == VERSION
    assert f'VERSION = "{VERSION}"' in source("const.py")
    assert f"**Tag:** `{VERSION}`" in (ROOT / f"RELEASE_NOTES_{VERSION}.md").read_text()

def test_translation_keys_match():
    strings = json.loads(source("strings.json"))
    en = json.loads(source("translations/en.json"))
    nl = json.loads(source("translations/nl.json"))
    assert set(strings["options"]["step"]["init"]["data"]) == set(en["options"]["step"]["init"]["data"]) == set(nl["options"]["step"]["init"]["data"])

def test_retired_modules_and_sensor_scope():
    assert 'PLATFORMS = ["sensor"]' in source("const.py")
    assert "do_prices_status" not in source("sensor.py")
    assert "DummyOSHomeForecast" not in source("sensor.py")
    assert not (MOD / "prices.py").exists()
    assert not (MOD / "forecast.py").exists()
