from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import sys
import types

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "custom_components/dummy_os_data/do_plan_grid_support_sensor.py"


def _load_refresh_key():
    package = types.ModuleType("custom_components.dummy_os_data")
    package.__path__ = [str(MODULE_PATH.parent)]
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    sys.modules["custom_components.dummy_os_data"] = package

    # The CI unit environment intentionally does not install Home Assistant.
    # This test imports only the pure refresh-key helper, so provide the minimal
    # adapter stubs required by module import without exercising HA runtime APIs.
    homeassistant = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda *args, **kwargs: None
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.utcnow = lambda: datetime.now(timezone.utc)
    homeassistant.helpers = helpers
    homeassistant.util = util
    helpers.entity_registry = entity_registry
    util.dt = dt
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
    sys.modules["homeassistant.util"] = util
    sys.modules["homeassistant.util.dt"] = dt

    const = types.ModuleType("custom_components.dummy_os_data.const")
    const.DOMAIN = "dummy_os_data"
    sys.modules[const.__name__] = const

    for name in (
        "do_plan_grid_support",
        "do_plan_store_bridge",
        "do_plan_store_sensor",
        "do_plan_scheduler_sensor",
        "do_plan_safety_sensor",
    ):
        module = types.ModuleType(f"custom_components.dummy_os_data.{name}")
        if name == "do_plan_grid_support":
            module.build_do_plan_grid_support = lambda **kwargs: {}
        elif name == "do_plan_store_bridge":
            module.build_do_plan_store_bridge = lambda **kwargs: {}
        elif name == "do_plan_scheduler_sensor":
            module.build_do_plan_scheduler_sensors = lambda *args, **kwargs: []
        elif name == "do_plan_safety_sensor":
            module.build_do_plan_safety_sensors = lambda *args, **kwargs: []
        else:
            module.DummyOSShadowPlanStoreRuntime = object
            module.build_do_plan_store_sensors = lambda *args, **kwargs: []
            module.get_do_plan_store_runtime = lambda *args, **kwargs: object()
        sys.modules[module.__name__] = module
    spec = importlib.util.spec_from_file_location(
        "custom_components.dummy_os_data.do_plan_grid_support_sensor", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.build_plan_store_bridge_refresh_key


def _snapshot(now):
    return {
        "now": now,
        "profile": "normal",
        "source_available": True,
        "soc_percent": 64.0,
        "solar_status": "ready",
        "prices_status": "ready",
        "prices_freshness": "fresh",
        "records": [{"start": "2026-09-10T08:00:00+00:00", "energy_kwh": 0.2}],
        "evaluations": [],
        "horizon_daily_stats": {},
        "solar_points": [[1, 0.1]],
        "price_points": [[1, 0.2]],
    }


def test_bridge_refresh_key_ignores_time_noise_inside_native_quarter():
    key = _load_refresh_key()
    start = datetime(2026, 9, 10, 8, 1, tzinfo=timezone.utc)
    assert key(_snapshot(start)) == key(_snapshot(start + timedelta(minutes=12)))


def test_bridge_refresh_key_changes_on_next_native_quarter():
    key = _load_refresh_key()
    assert key(_snapshot(datetime(2026, 9, 10, 8, 14, tzinfo=timezone.utc))) != key(
        _snapshot(datetime(2026, 9, 10, 8, 15, tzinfo=timezone.utc))
    )


def test_bridge_refresh_key_changes_immediately_on_material_input_change():
    key = _load_refresh_key()
    snapshot = _snapshot(datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc))
    changed = _snapshot(datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc))
    changed["soc_percent"] = 63.0
    assert key(snapshot) != key(changed)


def test_bridge_refresh_key_changes_on_price_or_solar_data_change():
    key = _load_refresh_key()
    snapshot = _snapshot(datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc))
    price_changed = _snapshot(datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc))
    price_changed["price_points"] = [[1, 0.25]]
    solar_changed = _snapshot(datetime(2026, 9, 10, 8, 5, tzinfo=timezone.utc))
    solar_changed["solar_points"] = [[1, 0.15]]
    assert key(snapshot) != key(price_changed)
    assert key(snapshot) != key(solar_changed)
