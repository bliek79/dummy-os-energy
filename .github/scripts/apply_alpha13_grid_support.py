from pathlib import Path
import json

VERSION='0.2.0-alpha.13'
PREVIOUS='0.2.0-alpha.12'

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing expected block: {label}')
    return text.replace(old,new,1)

# 1. Preserve exact native home quarters inside planner-hour output.
p=Path('custom_components/dummy_os_data/planner_hours.py')
t=p.read_text()
old='''        hours.append(\n            {\n                "index": hour_index,\n                "start": quarter_group[0].start.isoformat(),\n                "end": quarter_group[-1].end.isoformat(),\n                "energy_kwh": energy,\n                "quarter_count": QUARTERS_PER_HOUR,\n                "populated_quarters": len(populated),\n                "supported_quarters": len(supported),\n                "minimum_confidence": round(min(confidences), 3) if confidences else None,\n                "average_confidence": (\n                    round(sum(confidences) / len(confidences), 3) if confidences else None\n                ),\n                "source_distribution": dict(sorted(sources.items())),\n                "profile": profile,\n            }\n        )\n'''
new='''        quarter_payload = [\n            {\n                "index": quarter_index,\n                "start": slot.start.isoformat(),\n                "end": slot.end.isoformat(),\n                "energy_kwh": round(float(slot.energy_kwh), 6) if slot.energy_kwh is not None else None,\n                "source": str(slot.source),\n                "confidence": round(float(slot.confidence), 3),\n            }\n            for quarter_index, slot in enumerate(quarter_group)\n        ]\n        hours.append(\n            {\n                "index": hour_index,\n                "start": quarter_group[0].start.isoformat(),\n                "end": quarter_group[-1].end.isoformat(),\n                "energy_kwh": energy,\n                "quarter_count": QUARTERS_PER_HOUR,\n                "populated_quarters": len(populated),\n                "supported_quarters": len(supported),\n                "minimum_confidence": round(min(confidences), 3) if confidences else None,\n                "average_confidence": (\n                    round(sum(confidences) / len(confidences), 3) if confidences else None\n                ),\n                "source_distribution": dict(sorted(sources.items())),\n                "profile": profile,\n                "quarters": quarter_payload,\n            }\n        )\n'''
t=replace_once(t,old,new,'planner quarter payload')
p.write_text(t)

# 2. Carry exact home quarters into Step-1 rows without changing old hourly validity semantics.
p=Path('custom_components/dummy_os_data/do_plan_input.py')
t=p.read_text()
old='''        quarter_starts = [\n            start + timedelta(minutes=index * NATIVE_RESOLUTION_MINUTES)\n            for index in range(QUARTERS_PER_HOUR)\n        ]\n\n        solar_values: list[float] = []\n'''
new='''        quarter_starts = [\n            start + timedelta(minutes=index * NATIVE_RESOLUTION_MINUTES)\n            for index in range(QUARTERS_PER_HOUR)\n        ]\n\n        home_quarters: list[dict[str, Any]] = []\n        raw_home_quarters = hour.get("quarters")\n        home_quarters_valid = isinstance(raw_home_quarters, list) and len(raw_home_quarters) == QUARTERS_PER_HOUR\n        if home_quarters_valid:\n            for quarter_index, quarter_start in enumerate(quarter_starts):\n                quarter = raw_home_quarters[quarter_index]\n                q_start = _aware_utc(quarter.get("start")) if isinstance(quarter, dict) else None\n                q_end = _aware_utc(quarter.get("end")) if isinstance(quarter, dict) else None\n                q_energy = _finite(quarter.get("energy_kwh"), non_negative=True) if isinstance(quarter, dict) else None\n                valid = q_start == quarter_start and q_end == quarter_start + timedelta(minutes=NATIVE_RESOLUTION_MINUTES) and q_energy is not None\n                if not valid:\n                    home_quarters_valid = False\n                home_quarters.append({\n                    "start": quarter_start.isoformat(),\n                    "end": (quarter_start + timedelta(minutes=NATIVE_RESOLUTION_MINUTES)).isoformat(),\n                    "kwh": q_energy if valid else None,\n                })\n        else:\n            home_quarters = [\n                {\n                    "start": quarter_start.isoformat(),\n                    "end": (quarter_start + timedelta(minutes=NATIVE_RESOLUTION_MINUTES)).isoformat(),\n                    "kwh": None,\n                }\n                for quarter_start in quarter_starts\n            ]\n\n        solar_values: list[float] = []\n'''
t=replace_once(t,old,new,'input home quarter extraction')
old='''                "home_valid": home_valid,\n                "solar_valid": solar_valid,\n'''
new='''                "home_valid": home_valid,\n                "home_quarters_valid": home_quarters_valid,\n                "home_quarters": home_quarters,\n                "solar_valid": solar_valid,\n'''
t=replace_once(t,old,new,'input row home quarters')
p.write_text(t)

# 3. Replace grid support implementation with native-quarter baseline/candidate resimulation.
Path('custom_components/dummy_os_data/do_plan_grid_support.py').write_text(r'''"""Observer-only Planner Step 5 grid-support trigger and economic charge window."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import math
from typing import Any

BATTERY_CAPACITY_KWH=7.2
MIN_SOC_PERCENT=5.0
SAFETY_RESERVE_PERCENT=7.0
EXECUTION_BUFFER_PERCENT=2.0
CHARGE_EFFICIENCY_PERCENT=92.0
DISCHARGE_EFFICIENCY_PERCENT=92.0
MAX_CHARGE_POWER_W=3200
MAX_DISCHARGE_POWER_W=3200
DEFAULT_GRID_CHARGE_TRIGGER_KWH=0.25
NATIVE_RESOLUTION_MINUTES=15
NATIVE_SLOT_COUNT=288
PLANNER_HOUR_COUNT=72
EPS=0.01
PRICE_TIE_EUR_PER_KWH=0.001


def _finite(value:Any,*,non_negative:bool=False)->float|None:
    try: n=float(value)
    except (TypeError,ValueError): return None
    if not math.isfinite(n) or (non_negative and n<0): return None
    return n


def _utc(value:Any)->datetime|None:
    if isinstance(value,datetime): p=value
    elif isinstance(value,str):
        try: p=datetime.fromisoformat(value)
        except ValueError: return None
    else: return None
    if p.tzinfo is None: return None
    return p.astimezone(timezone.utc)


def _base(input_result:dict[str,Any],trigger:float)->dict[str,Any]:
    return {
        'input_rows_signature':input_result.get('rows_signature'),
        'native_resolution_minutes':15,'native_slot_count':288,'planner_hour_count':72,
        'battery_capacity_kwh':BATTERY_CAPACITY_KWH,'grid_charge_trigger_kwh':round(trigger,3),
        'trigger_rule':'additional_grid_charge_kwh > grid_charge_trigger_kwh',
        'charge_efficiency_percent':CHARGE_EFFICIENCY_PERCENT,'discharge_efficiency_percent':DISCHARGE_EFFICIENCY_PERCENT,
        'max_charge_power_w':MAX_CHARGE_POWER_W,'max_discharge_power_w':MAX_DISCHARGE_POWER_W,
        'shadow_only':True,'active_use_permitted':False,'physical_execution_authority':False,
        'plan_store_write':False,'scheduler_invoked':False,'safety_chain_invoked':False,'service_calls_performed':False,
        'missing_as_zero_used':False,'prices_fallback_used':False,'price_direction':'import_only','safety_priority_over_trade':True,
    }


def _blocked(base, blockers):
    return {**base,'status':'blocked','valid':False,'reason':blockers[0],'blockers':sorted(set(blockers)),'grid_charge_triggered':False,'selected_charge_slots':[],'selected_charge_slot_count':0}


def _native_slots(rows:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[str]]:
    slots=[]; blockers=[]
    expected_index=0
    for row in rows:
        homes=row.get('home_quarters'); solars=row.get('solar_quarters'); prices=row.get('price_quarters')
        if row.get('home_quarters_valid') is not True or not isinstance(homes,list) or len(homes)!=4:
            blockers.append(f'row_{row.get("index")}_home_quarters_invalid'); continue
        if not isinstance(solars,list) or len(solars)!=4 or not isinstance(prices,list) or len(prices)!=4:
            blockers.append(f'row_{row.get("index")}_native_quarters_invalid'); continue
        for q in range(4):
            h=homes[q]; s=solars[q]; p=prices[q]
            start=_utc(h.get('start') if isinstance(h,dict) else None)
            end=_utc(h.get('end') if isinstance(h,dict) else None)
            solar_start=_utc(s.get('start') if isinstance(s,dict) else None)
            price_start=_utc(p.get('start') if isinstance(p,dict) else None)
            home=_finite(h.get('kwh') if isinstance(h,dict) else None,non_negative=True)
            solar=_finite(s.get('kwh') if isinstance(s,dict) else None,non_negative=True)
            imp=_finite(p.get('import_price') if isinstance(p,dict) else None)
            exp=_finite(p.get('export_price') if isinstance(p,dict) else None)
            if None in (start,end,solar_start,price_start,home,solar,imp,exp) or start!=solar_start or start!=price_start or end-start!=timedelta(minutes=15):
                blockers.append(f'native_slot_{expected_index}_invalid'); expected_index+=1; continue
            slots.append({'index':expected_index,'start':start.isoformat(),'end':end.isoformat(),'home_kwh':home,'solar_kwh':solar,'import_price':imp,'export_price':exp,'source_resolution_minutes':p.get('source_resolution_minutes'),'kind':p.get('kind')})
            expected_index+=1
    if len(slots)!=NATIVE_SLOT_COUNT: blockers.append('native_slot_count_not_288')
    return slots,sorted(set(blockers))


def _simulate(slots:list[dict[str,Any]], *, start_soc:float, charge_plan:dict[str,float]|None=None)->dict[str,Any]:
    stored=BATTERY_CAPACITY_KWH*start_soc/100.0
    floor=BATTERY_CAPACITY_KWH*(MIN_SOC_PERCENT+SAFETY_RESERVE_PERCENT+EXECUTION_BUFFER_PERCENT)/100.0
    ce=CHARGE_EFFICIENCY_PERCENT/100.0; de=DISCHARGE_EFFICIENCY_PERCENT/100.0
    max_in=MAX_CHARGE_POWER_W/1000.0*0.25; max_out=MAX_DISCHARGE_POWER_W/1000.0*0.25
    net_cost=0.0; import_cost=0.0; export_revenue=0.0; solar_to_batt_total=0.0; grid_to_batt_total=0.0; grid_to_home_total=0.0
    first_floor_need=None; timeline=[]
    for slot in slots:
        start_stored=stored; home=slot['home_kwh']; solar=slot['solar_kwh']; imp=slot['import_price']; exp=slot['export_price']
        solar_to_home=min(home,solar); rem_home=home-solar_to_home; surplus=solar-solar_to_home
        solar_input=min(surplus,max_in,max(0.0,(BATTERY_CAPACITY_KWH-stored)/ce)); solar_stored=solar_input*ce; stored+=solar_stored
        solar_to_batt_total+=solar_stored
        solar_to_grid=max(0.0,surplus-solar_input); export_revenue+=solar_to_grid*exp
        grid_headroom=max(0.0,max_in-solar_input)
        requested=(charge_plan or {}).get(slot['start'],0.0)
        grid_batt=min(requested,grid_headroom,max(0.0,(BATTERY_CAPACITY_KWH-stored)/ce)); stored+=grid_batt*ce; grid_to_batt_total+=grid_batt; import_cost+=grid_batt*imp
        available=max(0.0,(stored-floor)*de); batt_home=min(rem_home,max_out,available); stored-=batt_home/de
        grid_home=rem_home-batt_home; grid_to_home_total+=grid_home; import_cost+=grid_home*imp
        if grid_home>EPS and first_floor_need is None: first_floor_need=slot['end']
        stored=min(BATTERY_CAPACITY_KWH,max(0.0,stored)); net_cost=import_cost-export_revenue
        timeline.append({'start':slot['start'],'end':slot['end'],'start_soc_percent':round(start_stored/BATTERY_CAPACITY_KWH*100,3),'end_soc_percent':round(stored/BATTERY_CAPACITY_KWH*100,3),'grid_to_battery_kwh':round(grid_batt,6),'grid_to_home_kwh':round(grid_home,6),'solar_to_battery_stored_kwh':round(solar_stored,6),'solar_to_grid_kwh':round(solar_to_grid,6)})
    return {'end_soc_percent':round(stored/BATTERY_CAPACITY_KWH*100,3),'first_grid_support_need':first_floor_need,'import_cost_eur':round(import_cost,6),'export_revenue_eur':round(export_revenue,6),'net_grid_cost_eur':round(net_cost,6),'solar_to_battery_stored_kwh':round(solar_to_batt_total,6),'grid_to_battery_input_kwh':round(grid_to_batt_total,6),'grid_to_home_kwh':round(grid_to_home_total,6),'timeline':timeline}


def build_do_plan_grid_support(*,input_result:dict[str,Any],energy_need_result:dict[str,Any],trigger_kwh:float=DEFAULT_GRID_CHARGE_TRIGGER_KWH)->dict[str,Any]:
    trigger=_finite(trigger_kwh,non_negative=True); base=_base(input_result,trigger if trigger is not None else DEFAULT_GRID_CHARGE_TRIGGER_KWH); blockers=[]
    if trigger is None: blockers.append('grid_charge_trigger_invalid')
    if input_result.get('status')!='ready' or input_result.get('fully_valid_hours')!=72: blockers.append('planner_input_not_ready')
    if energy_need_result.get('status')!='ready' or energy_need_result.get('valid') is not True: blockers.append('energy_need_not_ready')
    if energy_need_result.get('input_rows_signature')!=input_result.get('rows_signature'): blockers.append('input_signature_mismatch')
    rows=input_result.get('rows'); raw=_finite(energy_need_result.get('additional_grid_charge_kwh'),non_negative=True); soc=_finite(energy_need_result.get('soc_percent'),non_negative=True); first_solar=_utc(energy_need_result.get('first_usable_solar'))
    if not isinstance(rows,list) or len(rows)!=72: blockers.append('rows_not_exactly_72')
    if raw is None: blockers.append('additional_grid_charge_invalid')
    if soc is None or soc>100: blockers.append('soc_invalid')
    if first_solar is None: blockers.append('first_usable_solar_invalid')
    if blockers: return _blocked(base,blockers)
    assert trigger is not None and raw is not None and soc is not None and first_solar is not None and isinstance(rows,list)
    slots,native_blockers=_native_slots(rows)
    if native_blockers: return _blocked(base,native_blockers)
    free_capacity=BATTERY_CAPACITY_KWH*max(100.0-soc,0.0)/100.0
    chargeable=min(raw,free_capacity); unavoidable=max(raw-chargeable,0.0); required_input=chargeable/(CHARGE_EFFICIENCY_PERCENT/100.0) if chargeable>EPS else 0.0
    target_soc=min(100.0,soc+(chargeable/BATTERY_CAPACITY_KWH*100.0))
    triggered=raw>trigger
    common={**base,'additional_grid_charge_kwh':round(raw,3),'grid_charge_triggered':triggered,'chargeable_deficit_battery_kwh':round(chargeable,3),'unavoidable_shortfall_battery_kwh':round(unavoidable,3),'required_grid_charge_input_kwh':round(required_input,3),'target_soc_after_safety_charge_percent':round(target_soc,3),'capacity_limited_shortfall':unavoidable>EPS,'first_usable_solar':first_solar.isoformat(),'soc_percent':round(soc,3)}
    if not triggered:
        return {**common,'status':'ready','valid':True,'reason':'below_trigger','trigger_reason':'below_trigger','blockers':[],'grid_charge_deadline':None,'eligible_charge_slot_count':0,'selected_charge_slots':[],'selected_charge_slot_count':0,'selected_charge_input_kwh_total':0.0,'selected_charge_stored_kwh_total':0.0,'weighted_average_import_price':None,'effective_stored_cost_per_kwh':None,'candidate_charge_cost_eur':0.0,'baseline_grid_support_cost_eur':0.0,'candidate_72h_net_cost_eur':None,'economic_delta_eur':0.0,'solar_displacement_kwh':0.0,'safety_charge_fully_allocated':True,'unallocated_chargeable_deficit_battery_kwh':0.0}
    baseline=_simulate(slots,start_soc=soc)
    deadline=_utc(baseline['first_grid_support_need']) or first_solar
    eligible=[slot for slot in slots if _utc(slot['start']) is not None and _utc(slot['start'])<deadline]
    # initial economic ordering by true all-in import price; same constant efficiency => same effective order.
    # near-equal prices prefer less same-slot solar surplus, then later safe slot.
    def key(slot):
        surplus=max(slot['solar_kwh']-slot['home_kwh'],0.0)
        return (round(slot['import_price']/PRICE_TIE_EUR_PER_KWH),surplus,-_utc(slot['start']).timestamp())
    eligible.sort(key=key)
    max_slot_input=MAX_CHARGE_POWER_W/1000.0*0.25
    plan={}; remaining=required_input; selected=[]; projected_soc=soc
    for slot in eligible:
        if remaining<=EPS: break
        solar_surplus=max(slot['solar_kwh']-slot['home_kwh'],0.0)
        available=max(0.0,max_slot_input-solar_surplus)
        alloc=min(available,remaining)
        if alloc<=EPS: continue
        plan[slot['start']]=alloc; remaining-=alloc; stored=alloc*(CHARGE_EFFICIENCY_PERCENT/100.0); projected_soc=min(100.0,projected_soc+stored/BATTERY_CAPACITY_KWH*100.0)
        selected.append({'start':slot['start'],'end':slot['end'],'import_price_all_in':round(slot['import_price'],6),'available_charge_input_kwh':round(available,6),'allocated_charge_input_kwh':round(alloc,6),'stored_battery_kwh':round(stored,6),'projected_soc_after_percent':round(projected_soc,3),'solar_charge_headroom_used_kwh':round(solar_surplus,6),'estimated_solar_displacement_kwh':0.0,'selection_reason':'lowest_true_import_price_then_low_solar_then_later_safe'})
    candidate=_simulate(slots,start_soc=soc,charge_plan=plan)
    actual_input=candidate['grid_to_battery_input_kwh']; actual_stored=actual_input*(CHARGE_EFFICIENCY_PERCENT/100.0)
    unallocated=max(chargeable-actual_stored,0.0); fully=unallocated<=EPS
    solar_displacement=max(0.0,baseline['solar_to_battery_stored_kwh']-candidate['solar_to_battery_stored_kwh'])
    # distribute observed aggregate displacement across selected slots for diagnostics only.
    if selected and solar_displacement>0:
        each=solar_displacement/len(selected)
        for item in selected: item['estimated_solar_displacement_kwh']=round(each,6)
    charge_cost=sum(item['allocated_charge_input_kwh']*item['import_price_all_in'] for item in selected)
    weighted=(charge_cost/sum(item['allocated_charge_input_kwh'] for item in selected)) if selected and sum(item['allocated_charge_input_kwh'] for item in selected)>EPS else None
    effective=(weighted/(CHARGE_EFFICIENCY_PERCENT/100.0)) if weighted is not None else None
    status='ready' if fully else 'infeasible'; reason='meaningful_shortfall' if fully and unavoidable<=EPS else ('capacity_limited_shortfall' if fully else 'safe_charge_window_capacity_insufficient')
    return {**common,'status':status,'valid':fully,'reason':reason,'trigger_reason':'capacity_limited_shortfall' if unavoidable>EPS else 'meaningful_shortfall','blockers':[] if fully else ['safe_charge_window_capacity_insufficient'],'grid_charge_deadline':deadline.isoformat(),'eligible_charge_slot_count':len(eligible),'selected_charge_slots':selected,'selected_charge_slot_count':len(selected),'selected_charge_input_kwh_total':round(actual_input,3),'selected_charge_stored_kwh_total':round(actual_stored,3),'weighted_average_import_price':round(weighted,6) if weighted is not None else None,'effective_stored_cost_per_kwh':round(effective,6) if effective is not None else None,'candidate_charge_cost_eur':round(charge_cost,4),'baseline_grid_support_cost_eur':round(baseline['net_grid_cost_eur'],4),'candidate_72h_net_cost_eur':round(candidate['net_grid_cost_eur'],4),'economic_delta_eur':round(candidate['net_grid_cost_eur']-baseline['net_grid_cost_eur'],4),'solar_displacement_kwh':round(solar_displacement,3),'safety_charge_fully_allocated':fully,'unallocated_chargeable_deficit_battery_kwh':round(unallocated,3),'baseline_end_soc_percent':baseline['end_soc_percent'],'candidate_end_soc_percent':candidate['end_soc_percent'],'source_resolution_minutes_seen':sorted({slot['source_resolution_minutes'] for slot in selected if slot['source_resolution_minutes'] is not None}),'candidate_resimulation_performed':True}
''')

# 4. New HA sensor adapter; inherit SOC-aware executor/caching path.
Path('custom_components/dummy_os_data/do_plan_grid_support_sensor.py').write_text('''"""Home Assistant sensor adapter for observer-only Step 5 grid support."""\nfrom __future__ import annotations\nfrom typing import Any\nfrom .do_plan_grid_support import build_do_plan_grid_support\n\ndef build_do_plan_grid_support_sensors(coordinator: Any) -> list[Any]:\n    from .sensor import DummyOSPlanReserveSOCSensor, _build_plan_input_from_snapshot, _build_energy_need_from_snapshot\n    class DummyOSPlanGridSupportSensor(DummyOSPlanReserveSOCSensor):\n        _attr_name = "DO Plan Grid Support"\n        _attr_unique_id = "do_plan_grid_support"\n        _attr_suggested_object_id = "do_plan_grid_support"\n        _attr_icon = "mdi:transmission-tower-import"\n        _unrecorded_attributes = frozenset({"selected_charge_slots"})\n        GRID_CHARGE_TRIGGER_KWH = 0.25\n        def _calculate_result(self, snapshot: dict[str, Any]) -> dict[str, Any]:\n            input_result = _build_plan_input_from_snapshot(snapshot)\n            need = _build_energy_need_from_snapshot(snapshot)\n            result = build_do_plan_grid_support(input_result=input_result, energy_need_result=need, trigger_kwh=self.GRID_CHARGE_TRIGGER_KWH)\n            result["input_entity"] = "sensor.do_plan_input_72h"\n            result["energy_need_entity"] = "sensor.do_plan_energy_need"\n            result["soc_source_entity"] = need.get("soc_source_entity")\n            result["source_layer_status"] = need.get("source_layer_status")\n            return result\n        def _initial_result(self) -> dict[str, Any]:\n            return {"status":"initializing","valid":False,"selected_charge_slots":[],"shadow_only":True,"active_use_permitted":False,"physical_execution_authority":False,"plan_store_write":False,"scheduler_invoked":False,"safety_chain_invoked":False,"service_calls_performed":False,"blockers":["planner_calculation_pending"]}\n        @property\n        def native_value(self) -> str:\n            return str(self._result().get("status","initializing"))\n        @property\n        def extra_state_attributes(self) -> dict[str, Any]:\n            return dict(self._result())\n    return [DummyOSPlanGridSupportSensor(coordinator)]\n''')

# 5. Register sensor.
p=Path('custom_components/dummy_os_data/sensor.py'); t=p.read_text()
t=replace_once(t,'from .do_plan_72h_sensor import build_do_plan_72h_sensors\n','from .do_plan_72h_sensor import build_do_plan_72h_sensors\nfrom .do_plan_grid_support_sensor import build_do_plan_grid_support_sensors\n','sensor import grid support')
t=replace_once(t,'            *build_do_plan_72h_sensors(coordinator),\n','            *build_do_plan_72h_sensors(coordinator),\n            *build_do_plan_grid_support_sensors(coordinator),\n','sensor setup grid support')
p.write_text(t)

# 6. Tests.
Path('tests/test_do_plan_grid_support.py').write_text(r'''from __future__ import annotations
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
''')

# strengthen planner hour test and input contract test additively.
p=Path('tests/test_planner_hours.py'); t=p.read_text(); t=replace_once(t,'        assert all(hour["quarter_count"] == 4 for hour in result["hours"])\n','        assert all(hour["quarter_count"] == 4 for hour in result["hours"])\n        assert all(len(hour["quarters"]) == 4 for hour in result["hours"])\n        assert result["hours"][0]["quarters"][0]["energy_kwh"] == 0.1\n','planner test quarters'); p.write_text(t)

# 7. Version + notes.
p=Path('custom_components/dummy_os_data/const.py'); t=p.read_text(); t=replace_once(t,f'VERSION = "{PREVIOUS}"',f'VERSION = "{VERSION}"','const version'); p.write_text(t)
p=Path('custom_components/dummy_os_data/manifest.json'); data=json.loads(p.read_text());
if data.get('version')!=PREVIOUS: raise SystemExit('unexpected manifest version')
data['version']=VERSION; p.write_text(json.dumps(data,indent=2)+'\n')
p=Path('tests/test_release_consistency.py'); t=p.read_text(); t=replace_once(t,f'VERSION = "{PREVIOUS}"',f'VERSION = "{VERSION}"','release test version'); p.write_text(t)
notes='''# GitHub Release\n\n**Tag:** `0.2.0-alpha.13`  \n**Release title:** Dummy OS Energy 0.2.0-alpha.13 - Planner Step 5 Grid Support Shadow\n\n## Dummy OS Energy 0.2.0-alpha.13\n\nDeze prerelease voegt uitsluitend observer-only netondersteuningsdiagnostiek toe bovenop Planner Stap 5.\n\n### Toegevoegd\n- `DO Plan Grid Support` met shadow-testgrens X = 0,25 kWh op Step-2 `additional_grid_charge_kwh`.\n- Splitsing in laadbaar batterijtekort en onvermijdbaar resttekort; nooit laden boven 100% SOC.\n- Native 15-minuten economische laadvensterselectie binnen exact 72 uur / 288 slots.\n- Echte all-in importprijs, 92% laadefficiëntie, solar-first gedeelde 3200 W laadheadroom en kritieke deadline.\n- Baseline/candidate 72h-resimulatie met kostendelta en solar displacement.\n- Exacte native home-quarterwaarden worden additief door de bestaande Forecast->Planner-keten meegenomen.\n\n### Safetyrechten onveranderd\n- `shadow_only=true`\n- `active_use_permitted=false`\n- `physical_execution_authority=false`\n- `plan_store_write=false`\n- `scheduler_invoked=false`\n- `safety_chain_invoked=false`\n- `service_calls_performed=false`\n\nGeen fysieke batterijactie, scheduler of Plan Store. X=0,25 kWh is uitsluitend de eerste shadow-testwaarde en nog geen definitieve operationele instelling.\n'''
Path(f'RELEASE_NOTES_{VERSION}.md').write_text(notes)
p=Path('RELEASE_NOTES.md'); cur=p.read_text(); p.write_text(notes+'\n---\n'+cur)
