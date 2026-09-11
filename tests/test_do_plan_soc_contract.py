from datetime import datetime,timezone
from custom_components.dummy_os_data.do_plan_soc_contract import build_do_plan_soc_contract
NOW=datetime(2026,9,11,12,0,tzinfo=timezone.utc)
def test_valid():
 r=build_do_plan_soc_contract(source_entity="sensor.raw",raw_state="64.5",now=NOW); assert r["status"]=="ready" and r["soc_percent"]==64.5 and r["blockers"]==[]
def test_unknown_lkg_not_used():
 r=build_do_plan_soc_contract(source_entity="sensor.raw",raw_state="unknown",now=NOW,last_known_good_soc_percent=63); assert r["status"]=="blocked" and r["soc_percent"] is None and r["last_known_good_soc_percent"]==63 and r["last_known_good_used_for_current"] is False
def test_invalids():
 assert build_do_plan_soc_contract(source_entity="sensor.raw",raw_state="abc",now=NOW)["reason"]=="soc_source_non_numeric"; assert build_do_plan_soc_contract(source_entity="sensor.raw",raw_state="101",now=NOW)["reason"]=="soc_out_of_range"
def test_missing_not_zero():
 r=build_do_plan_soc_contract(source_entity="sensor.raw",raw_state=None,now=NOW); assert r["soc_percent"] is None and r["reason"]=="soc_source_missing"
