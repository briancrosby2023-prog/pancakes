"""Campaign-based longitudinal market recorder with strict evidence semantics."""
from __future__ import annotations
import csv, hashlib, io, json, statistics
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any
from .market import CORE_TRAINING_QUICKSELL, parse_timestamp
from .market_campaign import history_statistics
from .monitor import canonical_cards, load_json, monitor_run, save_json
from .transition import WINDOW_LABELS, checkpoint_time
RECORDER_HISTORY="data/production/market/longitudinal_observations.json"
CAMPAIGN_STATE="data/production/market/campaigns.json"
RECORDER_STATE="data/production/market/recorder_state.json"
SEMANTICS={"LIVE_LISTING":{"unit":"CUT_COINS","class":"LISTING"},"LOWEST_VISIBLE_LISTING":{"unit":"CUT_COINS","class":"LISTING"},"DISPLAYED_MARKET_PRICE":{"unit":"CUT_COINS","class":"DISPLAY"},"COMPLETED_SALE":{"unit":"CUT_COINS","class":"SALE"},"MEDIAN_COMPLETED_SALE":{"unit":"CUT_COINS","class":"SALE_STATISTIC"},"PRICE_TRACKER_VALUE":{"unit":"CUT_COINS","class":"TRACKER"},"SUPPLY_COUNT":{"unit":"COUNT","class":"SUPPLY"},"SALE_VOLUME":{"unit":"COUNT","class":"VOLUME"},"TRAINING_BASKET":{"unit":"CUT_COINS","class":"TRAINING"},"COLLECTION_COMPONENT":{"unit":"CUT_COINS","class":"COLLECTION"},"CURRENT_PLAYER_RESALE":{"unit":"CUT_COINS","class":"RESALE"}}
PRICE_TYPES={k for k,v in SEMANTICS.items() if v["unit"]=="CUT_COINS"}
CAMPAIGN_TYPES={"PERSONAL HIT LIST","PANCAKE TOP 10","PANCAKE TOP 25","ROSTER UPGRADES","NEAR-EQUIVALENT ALTERNATIVES","SCHEME / COLLECTION","TRAINING BASKET","EVENT WINDOW","SEASON TRANSITION"}
def stable_id(parts:list[Any])->str:return "recorder:"+hashlib.sha256(json.dumps(parts,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]
def default_campaign(root:Path,now:str)->dict[str,Any]:
 u=load_json(root/"data/research/op_x_036/monitored_universe.json",{"cards":[]});t=[]
 for r in u["cards"]:
  s=r["sources"];p,ti=(1,"TIER 1") if ("PERSONAL HIT LIST" in s or "TOP 10" in s or "ROSTER BUY TARGET" in s) else ((2,"TIER 2") if ("TOP 25" in s or "NEAR-EQUIVALENT ALTERNATIVE" in s) else (3,"TIER 3"));t.append({"card_id":r["card_id"],"priority":p,"tier":ti,"reasons":r["reasons"],"sources":s})
 return {"campaign_id":"pancake-default-monitored-universe-v1","campaign_type":"PANCAKE TOP 25","schema_version":2,"platform":"PS5","cards":sorted(t,key=lambda r:(r["priority"],r["card_id"])),"reason":"deduplicated OP-X-036 monitored universe; PS5 longitudinal market history","start_time":now,"end_time":None,"desired_cadence_minutes":{"1":60,"2":240,"3":720},"observation_types_requested":["LOWEST_VISIBLE_LISTING","LIVE_LISTING","COMPLETED_SALE","SUPPLY_COUNT","SALE_VOLUME"],"event_id":None,"priority":1,"active":True,"last_successful_observation":None,"next_due_observation":now,"sample_sufficiency":"NO DATA"}
def deduplicated_targets(campaigns):
 m={}
 for c in campaigns:
  if not c.get("active",True):continue
  for t in c.get("cards",[]):
   r=m.setdefault(t["card_id"],{"card_id":t["card_id"],"campaign_ids":[],"reasons":[],"sources":[],"priority":99});r["campaign_ids"].append(c["campaign_id"]);r["priority"]=min(r["priority"],t.get("priority",c.get("priority",99)))
   for k in ("reasons","sources"):
    for v in t.get(k,[]):
     if v not in r[k]:r[k].append(v)
 return sorted(m.values(),key=lambda r:(r["priority"],r["card_id"]))
def normalize_record(raw,cards,campaigns,*,ingested_at,fixture=False):
 cid=raw.get("card_id");typ=raw.get("observation_type");val=raw.get("value")
 if cid not in cards:raise ValueError("ambiguous or unresolved canonical card identity")
 if typ not in SEMANTICS:raise ValueError("unsupported observation semantics")
 if isinstance(val,bool) or not isinstance(val,int) or val<=0:raise ValueError("observation value must be a positive integer")
 at=raw.get("observed_at")
 if not at:raise ValueError("observed_at is required")
 obs,ing=parse_timestamp(at),parse_timestamp(ingested_at);avail_at=raw.get("available_at",at);avail=parse_timestamp(avail_at)
 if obs>ing or avail>ing:raise ValueError("future timestamp rejected")
 if avail<obs:raise ValueError("timestamp reversal rejected")
 camp=raw.get("campaign_id")
 if camp not in campaigns:raise ValueError("unknown campaign")
 if cid not in {r["card_id"] for r in campaigns[camp].get("cards",[])}:raise ValueError("campaign/card mismatch")
 platform=raw.get("platform","UNKNOWN");expected=campaigns[camp].get("platform")
 if expected and expected!=platform:raise ValueError("platform mismatch")
 card=cards[cid];identity={"card_id":cid,"player_name":card.get("player_name"),"position":card.get("position"),"overall":card.get("native_overall"),"program":card.get("program"),"archetype":card.get("archetype")}
 rid=stable_id([cid,val,typ,at,avail_at,raw.get("source"),platform,camp])
 return {"observation_id":rid,**identity,"value":val,"observed_price":val if typ in PRICE_TYPES else None,"observation_type":typ,"source_semantics":SEMANTICS[typ],"source":raw.get("source","USER_BROWSER_ASSISTED"),"observed_at":at,"user_observed_at":at,"ingested_at":ingested_at,"available_at":avail_at,"platform":platform,"provenance":raw.get("provenance","USER_EXPORT"),"confidence":raw.get("confidence","USER_ATTESTED"),"identity_confidence":"EXACT","campaign_id":camp,"event_id":campaigns[camp].get("event_id"),"evidence_scope":"FIXTURE" if fixture else "REAL","sequence":raw.get("sequence"),"listing_age_minutes":raw.get("listing_age_minutes"),"second_lowest_listing":raw.get("second_lowest_listing")}
def parse_browser_export(text,format_name):
 if format_name=="json":
  p=json.loads(text)
  if not isinstance(p,list):raise ValueError("JSON export must be a list")
  return p
 if format_name=="csv":return list(csv.DictReader(io.StringIO(text)))
 raise ValueError("supported import formats are json and csv")
def append_records(path,rows,*,production):
 if production and any(r.get("evidence_scope")!="REAL" for r in rows):raise ValueError("fixture observations cannot enter production history")
 old=load_json(path,[]);m={r["observation_id"]:r for r in old};before=len(m)
 for r in rows:m.setdefault(r["observation_id"],r)
 result=sorted(m.values(),key=lambda r:(r["observed_at"],r["observation_id"]));save_json(path,result);return {"existing":before,"appended":len(result)-before,"total":len(result),"records":result}
def completed_sale_statistics(rows):
 s=sorted((r for r in rows if r["observation_type"] in {"COMPLETED_SALE","MEDIAN_COMPLETED_SALE"}),key=lambda r:r["observed_at"]);v=[r["value"] for r in s]
 if not v:return {"count":0,"status":"NO DATA"}
 ts=[parse_timestamp(r["observed_at"]) for r in s];ints=[(b-a).total_seconds()/3600 for a,b in zip(ts,ts[1:])]
 return {"count":len(v),"median":statistics.median(v),"mean":round(statistics.mean(v),6),"minimum":min(v),"maximum":max(v),"range":max(v)-min(v),"dispersion":0.0 if len(v)<2 else round(statistics.pstdev(v)/statistics.mean(v),6),"trend":None if len(v)<2 else round((v[-1]-v[0])/v[0],6),"mean_hours_between_sales":None if not ints else round(statistics.mean(ints),6),"sale_velocity_per_day":None if not ints or sum(ints)==0 else round((len(v)-1)*24/sum(ints),6)}
def listing_statistics(rows):
 ls=[r for r in rows if SEMANTICS[r["observation_type"]]["class"]=="LISTING"];sup=[r["value"] for r in rows if r["observation_type"]=="SUPPLY_COUNT"];p=[r["value"] for r in ls]
 return {"listing_samples":len(ls),"supply_samples":len(sup),"lowest_listing":min(p) if p else None,"second_lowest_listing":next((r.get("second_lowest_listing") for r in reversed(ls) if r.get("second_lowest_listing") is not None),None),"latest_supply_count":sup[-1] if sup else None}
def sample_sufficiency(rows,as_of,event=None):
 pr=[r for r in rows if r["observation_type"] in PRICE_TYPES];comp=[{**r,"observed_price":r["value"],"user_observed_at":r["observed_at"]} for r in pr];st=history_statistics(comp,as_of);types=Counter(r["observation_type"] for r in rows);cov=event_checkpoint_coverage(event,rows) if event else None
 return {"state":"NO DATA" if not rows else st.get("quality","INSUFFICIENT"),"observations":len(rows),"distinct_times":len({r["observed_at"] for r in rows}),"timespan_hours":st.get("time_span_hours",0),"freshness_hours":st.get("latest_age_hours"),"sale_samples":types["COMPLETED_SALE"]+types["MEDIAN_COMPLETED_SALE"],"listing_samples":types["LIVE_LISTING"]+types["LOWEST_VISIBLE_LISTING"],"supply_samples":types["SUPPLY_COUNT"],"volume_samples":types["SALE_VOLUME"],"event_checkpoint_coverage":cov}
def register_event(raw):
 if not raw.get("release_time"):raise ValueError("verified release_time is required")
 parse_timestamp(raw["release_time"])
 if not raw.get("source") or not raw.get("confidence"):raise ValueError("event source and confidence are required")
 return {**raw,"checkpoints":{l:checkpoint_time(raw["release_time"],l).isoformat() for l in WINDOW_LABELS},"unknown_fields":raw.get("unknown_fields",[])}
def event_checkpoint_coverage(event,rows):
 if not event:return None
 obs={r.get("checkpoint") for r in rows if r.get("checkpoint")};return {"observed":[l for l in event["checkpoints"] if l in obs],"missing":[l for l in event["checkpoints"] if l not in obs]}
def training_basket(card_rows,version):
 unsupported=[r["card_id"] for r in card_rows if r["overall"] not in CORE_TRAINING_QUICKSELL]
 if unsupported:raise ValueError(f"unsupported training quicksell tiers: {unsupported}")
 return {"basket_version":version,"composition_frozen":True,"cards":[{**r,"training":CORE_TRAINING_QUICKSELL[r["overall"]]} for r in card_rows]}
def longitudinal_export(rows,events):
 return [{"observation_id":r["observation_id"],"card_id":r["card_id"],"observation_type":r["observation_type"],"value":r["value"],"observed_at":r["observed_at"],"available_at":r["available_at"],"event_time":events.get(r.get("event_id"),{}).get("release_time"),"platform":r["platform"]} for r in rows]
def scheduler_state(campaign,now,*,success,failure_reason=None):
 cadence=campaign.get("desired_cadence_minutes",60);cadence=min(cadence.values()) if isinstance(cadence,dict) else cadence;state=dict(campaign)
 if success:state.update({"last_success":now,"consecutive_failures":0,"last_failure":None})
 else:state.update({"consecutive_failures":state.get("consecutive_failures",0)+1,"last_failure":{"at":now,"reason":failure_reason}})
 state["next_due"]=(parse_timestamp(now)+timedelta(minutes=cadence)).isoformat();return state
def run_snapshot(root,raw_rows,campaigns,events,*,ingested_at,fixture=False,persist=False):
 cards=canonical_cards(root);cm={c["campaign_id"]:c for c in campaigns};accepted=[];failures=[]
 for raw in raw_rows:
  try:accepted.append(normalize_record(raw,cards,cm,ingested_at=ingested_at,fixture=fixture))
  except (ValueError,TypeError,KeyError) as e:failures.append({"raw":raw,"error":str(e)})
 key=stable_id([[r["observation_id"] for r in accepted],failures])
 if persist:append_records(root/RECORDER_HISTORY,accepted,production=not fixture)
 return {"accepted":len(accepted),"partial_success":bool(accepted and failures),"failures":failures,"records":accepted,"deterministic_key":key}
