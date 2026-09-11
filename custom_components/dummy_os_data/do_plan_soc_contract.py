"""Central fail-closed SOC Contract v1 for Dummy OS Energy."""
from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Any
SOC_CONTRACT_VERSION=1

def build_do_plan_soc_contract(*,source_entity:str,raw_state:Any,now:datetime,last_known_good_soc_percent:float|None=None,last_known_good_observed_at:str|None=None)->dict[str,Any]:
    now_utc=now.astimezone(timezone.utc) if now.tzinfo is not None else None
    raw_text=None if raw_state is None else str(raw_state); blockers=[]; reason="ready"; soc=None
    if not source_entity: blockers.append("soc_source_entity_missing"); reason="soc_source_entity_missing"
    elif raw_state is None: blockers.append("soc_source_missing"); reason="soc_source_missing"
    elif raw_text in {"unknown","unavailable","none","None",""}: blockers.append("soc_source_unavailable"); reason="soc_source_unavailable"
    else:
        try: candidate=float(raw_state)
        except (TypeError,ValueError): blockers.append("soc_source_non_numeric"); reason="soc_source_non_numeric"
        else:
            if not math.isfinite(candidate): blockers.append("soc_source_non_finite"); reason="soc_source_non_finite"
            elif candidate<0.0 or candidate>100.0: blockers.append("soc_out_of_range"); reason="soc_out_of_range"
            else: soc=round(candidate,3)
    if now_utc is None: blockers.append("soc_observation_time_invalid"); reason=reason if reason!="ready" else "soc_observation_time_invalid"
    valid=not blockers
    return {"status":"ready" if valid else "blocked","validation_status":"valid" if valid else "invalid","valid":valid,"contract_version":SOC_CONTRACT_VERSION,"source_entity":source_entity,"raw_source_status":raw_text,"soc_percent":soc if valid else None,"reason":reason,"blockers":sorted(set(blockers)),"observed_at":now_utc.isoformat() if now_utc else None,"last_known_good_soc_percent":last_known_good_soc_percent,"last_known_good_observed_at":last_known_good_observed_at,"last_known_good_used_for_current":False,"fallback_used":False,"fallback_source_entity":None,"shadow_only":True,"active_use_permitted":False,"physical_execution_authority":False}
