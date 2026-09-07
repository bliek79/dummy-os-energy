from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "custom_components/dummy_os_data/home_input_sensor.py").read_text(encoding="utf-8")
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text(encoding="utf-8")
MIGRATIONS = (ROOT / "custom_components/dummy_os_data/entity_migrations.py").read_text(encoding="utf-8")


def test_fallback_hierarchy_sensor_identity_contract():
    assert '_attr_name = "DO Energy Fallback Hierarchy"' in SOURCE
    assert '_attr_unique_id = "do_energy_fallback_hierarchy"' in SOURCE
    assert '_attr_suggested_object_id = "do_energy_fallback_hierarchy"' in SOURCE
    assert 'DummyOSEnergyFallbackHierarchySensor(coordinator)' in SOURCE


def test_fallback_hierarchy_registry_migration_is_borged():
    """The live-generated prefix ID must always migrate to the canonical do_* ID."""
    assert (
        '"do_energy_fallback_hierarchy": '
        '"sensor.dummy_os_forecast_do_energy_fallback_hierarchy"'
    ) in MIGRATIONS
    assert (
        '("sensor", "do_energy_fallback_hierarchy", '
        '"sensor.do_energy_fallback_hierarchy")'
    ) in INIT


def test_fallback_hierarchy_is_strictly_observer_only():
    assert '"observer_only": True' in SOURCE
    assert '"forecast_influence_enabled": False' in SOURCE
    assert '"promotion_ready": False' in SOURCE
    assert '"live_shadow_required": True' in SOURCE


def test_unclassified_profile_maps_to_inactive_profile_state():
    assert '"status": "inactive_profile"' in SOURCE
    assert '"profile_unclassified"' in SOURCE
