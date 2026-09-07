from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
PATH = ROOT / "custom_components/dummy_os_data/horizon_quality.py"
SPEC = spec_from_file_location("horizon_quality", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

def test_fixed_native_horizon_set_and_72h_edge_semantics():
    assert [probe[2] for probe in MODULE.HORIZON_PROBES] == [0, 60, 180, 360, 720, 1440, 2880, 4305]
    assert MODULE.HORIZON_PROBES[-1][1] == 287
    assert MODULE.HORIZON_PROBES[-1][3] == "last_native_slot_ends_plus_72h"

def test_daily_stats_aggregate_without_reconstructing_missing_as_zero():
    stats = {"normal|2026-09-01|60": {"profile": "normal", "local_date": "2026-09-01", "horizon_minutes": 60, "sample_count": 2, "sum_abs_error_kwh": 0.10, "sum_error_kwh": 0.02, "sum_actual_kwh": 0.40, "sum_forecast_kwh": 0.42, "sum_confidence": 1.4, "source_counts": {"weekday_quarter": 2}, "excluded_record_counts": {"profile_mismatch": 1}}}
    h1 = MODULE.calculate_horizon_quality(stats, "normal")["horizons"]["h01"]
    assert h1["sample_count"] == 2
    assert h1["mae_kwh"] == 0.05
    assert h1["bias_kwh"] == 0.01
    assert h1["mean_captured_confidence"] == 0.7
    assert h1["excluded_record_counts"]["profile_mismatch"] == 1

def test_unclassified_is_inactive_and_never_borrows_normal():
    result = MODULE.calculate_horizon_quality({}, "unclassified")
    assert result["status"] == "inactive_profile"
    assert result["observer_only"] is True
    assert result["forecast_influence_enabled"] is False
