#!/usr/bin/env python3
"""Deterministic frozen-model scorer for E.15 historical TE populations."""
from __future__ import annotations
import argparse, itertools, json
from collections import Counter
from pathlib import Path

OUT=Path('data/research/cfb27_e15/historical_validation')
ALIASES={'Possession':'Gritty Possession','Blocking':'Pure Blocker','Gritty Possession':'Gritty Possession','Pure Blocker':'Pure Blocker','Vertical Threat':'Vertical Threat','Physical Route Runner':'Physical Route Runner'}
WEIGHTS={
'blocking':{'STR':6,'AWR':9,'BTK':2,'TRK':1,'SFA':2,'CTH':3,'CIT':3,'SRR':5,'MRR':4,'IBL':9,'LBK':8,'PBK':8,'PBF':6,'PBP':6,'RBK':10,'RBF':9,'RBP':9},
'possession':{'SPD':3,'ACC':4,'AGI':3,'STR':4,'AWR':9,'BCV':1,'BTK':2,'TRK':1,'SFA':2,'CTH':10,'CIT':14,'SPC':1,'RLS':2,'SRR':12,'MRR':6,'IBL':4,'LBK':2,'PBK':3,'PBF':2,'PBP':2,'RBK':5,'RBF':4,'RBP':4},
'vertical':{'SPD':7,'ACC':7,'AGI':4,'JMP':3,'AWR':9,'BCV':2,'BTK':3,'ELU':2,'TRK':1,'SFA':2,'CTH':11,'CIT':8,'SPC':4,'RLS':3,'SRR':7,'MRR':9,'DRR':5,'PBK':2,'PBF':1,'PBP':1,'RBK':3,'RBF':3,'RBP':3}}
MODELS={'Gritty Possession':'TE-MODEL-001 v1.1','Vertical Threat':'TE-MODEL-006 v1.3','Physical Route Runner':'TE-MODEL-003 v1.1','Pure Blocker':'TE-MODEL-004 v1.1'}

def dump(path,value): path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def weighted(attrs,weights,omit=()):
 used={k:w for k,w in weights.items() if k not in omit and k in attrs}; missing=sorted(k for k in weights if k not in omit and k not in attrs); den=sum(used.values())
 return (sum(attrs[k]*w for k,w in used.items())/den if den else None,sorted(used),missing,den)
def score(row):
 raw=row.get('archetype','UNKNOWN'); arch=ALIASES.get(raw,raw); attrs=row.get('attributes',{})
 p=weighted(attrs,WEIGHTS['possession']); b=weighted(attrs,WEIGHTS['blocking']); base_v=weighted(attrs,WEIGHTS['vertical'],('ELU',)); v13w=dict(WEIGHTS['vertical']); v13w['LBK']=2; v13w['IBL']=3; v13=weighted(attrs,v13w,('ELU',))
 if arch=='Gritty Possession': x=p
 elif arch=='Pure Blocker': x=b
 elif arch=='Vertical Threat': x=v13
 elif arch=='Physical Route Runner':
  x=(0.71*base_v[0]+0.29*p[0],sorted(set(base_v[1]+p[1])),sorted(set(base_v[2]+p[2])),None) if base_v[0] is not None and p[0] is not None else (None,[],[],0)
 else: return {**row,'canonical_archetype':arch,'scoring_eligible':False,'scoring_reason':'unknown_archetype'}
 return {**row,'canonical_archetype':arch,'model':MODELS[arch],'weighted_score':x[0],'attributes_used':x[1],'attributes_unavailable':x[2],'scoring_eligible':x[0] is not None,'scoring_reason':'ok' if x[0] is not None else 'no_weighted_attributes'}
def metrics(rows):
 rows=[r for r in rows if r.get('scoring_eligible')]; correct=inv=ties=0; inversions=[]
 for a,b in itertools.combinations(rows,2):
  if a['ovr']==b['ovr']: continue
  hi,lo=(a,b) if a['ovr']>b['ovr'] else (b,a); d=hi['weighted_score']-lo['weighted_score']
  if abs(d)<1e-12: ties+=1
  elif d>0: correct+=1
  else: inv+=1; inversions.append({'higher_name':hi['name'],'higher_ovr':hi['ovr'],'higher_score':hi['weighted_score'],'higher_url':hi['url'],'lower_name':lo['name'],'lower_ovr':lo['ovr'],'lower_score':lo['weighted_score'],'lower_url':lo['url'],'score_delta':d,'ovr_gap':hi['ovr']-lo['ovr']})
 residual=[r['weighted_score']-r['ovr'] for r in rows]; bands={}
 for ovr in sorted(set(r['ovr'] for r in rows)):
  group=[r for r in rows if r['ovr']==ovr]; rr=[r['weighted_score']-ovr for r in group]; bands[str(ovr)]={'n':len(group),'mean_score':sum(r['weighted_score'] for r in group)/len(group),'mean_residual':sum(rr)/len(rr),'mae':sum(abs(x) for x in rr)/len(rr)}
 return {'n':len(rows),'comparable_distinct_ovr_pairs':correct+inv+ties,'correct_rankings':correct,'inversions':inv,'ties':ties,'ranking_accuracy_excluding_ties':correct/(correct+inv) if correct+inv else None,'ranking_accuracy_ties_as_incorrect':correct/(correct+inv+ties) if correct+inv+ties else None,'raw_score_ovr_mae':sum(abs(x) for x in residual)/len(residual) if residual else None,'mean_residual':sum(residual)/len(residual) if residual else None,'ovr_bands':bands,'inversion_records':sorted(inversions,key=lambda x:(x['score_delta'],-x['ovr_gap']))}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--seasons',nargs='+',type=int,default=[25,26]); args=ap.parse_args(); all_rows=[]; result={}
 dump(OUT/'frozen_te_scoring_spec.json',{'models':MODELS,'historical_archetype_aliases':ALIASES,'madden19_weights':WEIGHTS,'TE-MODEL-006 v1.3':'M19 Vertical Threat +2 LBK +3 IBL; ELU unavailable omitted/renormalized','TE-MODEL-003 v1.1':'71% M19 Vertical Threat candidate (ELU unavailable omitted/renormalized) + 29% M19 Possession; no v1.3 blocking modification','control':'CFB25/26 validation does not refit frozen models'})
 for season in args.seasons:
  pop=json.loads((OUT/f'cfb{season}_te_population.json').read_text()); scored=[score(r) for r in pop]; dump(OUT/f'cfb{season}_te_scored.json',scored); all_rows.extend(scored); result[str(season)]={}
  for arch in MODELS:
   m=metrics([r for r in scored if r.get('canonical_archetype')==arch]); result[str(season)][arch]=m; dump(OUT/f'cfb{season}_{arch.lower().replace(" ","_")}_validation.json',m)
  result[str(season)]['coverage']={'population_n':len(scored),'scored_n':sum(r['scoring_eligible'] for r in scored),'unknown_archetypes':dict(Counter(r.get('archetype','UNKNOWN') for r in scored if not r['scoring_eligible']))}
 dump(OUT/'historical_te_database.json',all_rows); dump(OUT/'validation_metrics.json',result); print(json.dumps({s:{a:{k:v for k,v in m.items() if k not in {'inversion_records','ovr_bands'}} if isinstance(m,dict) else m for a,m in d.items()} for s,d in result.items()},indent=2))
if __name__=='__main__': main()
