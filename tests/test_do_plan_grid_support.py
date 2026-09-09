from __future__ import annotations
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('do_plan_grid_support',ROOT/'custom_components/dummy_os_data/do_plan_grid_support.py'); MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
BASE=datetime(2026,9,9,18,0,tzinfo=timezone.utc)

def make_input(prices=None, solar=None, home=0.10):
    rows=[]; prices=prices or {}; solar=solar or {}
    for h in range(72):
        hs=BASE+timedelta(hours=h); homes=[]; sols=[]; ps=[]
        for q in range(4):
            s=hs+timedelta(minutes=15*q); key=h*4+q
            homes.append({'start':s.isoformat(),'end':(s+timedelta(minutes=15)).isoformat(),'kwh':home})
            sols.append({'start':s.isoformat(),'kwh':solar.get(key,0.0)})
            ps.append({'start':s.isoformat(),'import_price':prices.get(key,0.30),'export_price':0.08,'kind':'known_pt15m','source_resolution_minutes':15})
        rows.append({'index':h,'start':hs.isoformat(),'end':(hs+timedelta(hours=1)).isoformat(),'home_kwh':home*4,'solar_kwh':sum(x['kwh'] for x in sols),'import_price':sum(x['import_price'] for x in ps)/4,'export_price':0.08,'fully_valid':True,'home_quarters_valid':True,'home_quarters':homes,'solar_quarters':sols,'price_quarters':ps})
    return {'status':'ready','fully_valid_hours':72,'rows_signature':'sig','rows':rows}

def need(shortfall=0.96,soc=88.0,first_solar_hours=12):
    return {'status':'ready','valid':True,'input_rows_signature':'sig','additional_grid_charge_kwh':shortfall,'soc_percent':soc,'first_usable_solar':(BASE+timedelta(hours=first_solar_hours)).isoformat()}

def test_below_and_equal_trigger_do_not_charge():
    for value in (0.0,0.25):
        r=MOD.build_do_plan_grid_support(input_result=make_input(),energy_need_result=need(value))
        assert r['grid_charge_triggered'] is False and r['selected_charge_slots']==[] and r['trigger_reason']=='below_trigger'

def test_example_88_percent_capacity_split():
    r=MOD.build_do_plan_grid_support(input_result=make_input(),energy_need_result=need(0.96,88.0))
    assert r['grid_charge_triggered'] is True
    assert r['chargeable_deficit_battery_kwh']==0.864
    assert r['unavoidable_shortfall_battery_kwh']==0.096
    assert r['required_grid_charge_input_kwh']==0.939
    assert r['target_soc_after_safety_charge_percent']==100.0
    assert r['physical_execution_authority'] is False and r['service_calls_performed'] is False

def test_cheapest_safe_slots_before_deadline_are_selected_and_multislot():
    prices={0:0.40,1:0.05,2:0.06,3:0.50,40:-0.20}
    r=MOD.build_do_plan_grid_support(input_result=make_input(prices=prices),energy_need_result=need(1.2,60.0,12))
    assert r['grid_charge_triggered'] is True
    assert r['selected_charge_slot_count']>=2
    starts=[x['start'] for x in r['selected_charge_slots']]
    assert (BASE+timedelta(minutes=15)).isoformat() in starts
    assert (BASE+timedelta(hours=10)).isoformat() not in starts or datetime.fromisoformat((BASE+timedelta(hours=10)).isoformat()) < datetime.fromisoformat(r['grid_charge_deadline'])

def test_solar_uses_shared_charge_headroom_first():
    solar={1:0.70}; prices={1:0.01,2:0.10,3:0.11}
    r=MOD.build_do_plan_grid_support(input_result=make_input(prices=prices,solar=solar),energy_need_result=need(0.8,70.0,10))
    chosen={x['start']:x for x in r['selected_charge_slots']}
    key=(BASE+timedelta(minutes=15)).isoformat()
    if key in chosen:
        assert chosen[key]['available_charge_input_kwh'] <= 0.2 + 1e-6

def test_missing_native_home_quarter_fails_closed():
    inp=make_input(); inp['rows'][0]['home_quarters_valid']=False
    r=MOD.build_do_plan_grid_support(input_result=inp,energy_need_result=need())
    assert r['status']=='blocked' and 'row_0_home_quarters_invalid' in r['blockers']

def test_safety_invariants_are_hard_false():
    r=MOD.build_do_plan_grid_support(input_result=make_input(),energy_need_result=need())
    assert r['shadow_only'] is True and r['active_use_permitted'] is False and r['physical_execution_authority'] is False
    assert r['plan_store_write'] is False and r['scheduler_invoked'] is False and r['safety_chain_invoked'] is False and r['service_calls_performed'] is False
