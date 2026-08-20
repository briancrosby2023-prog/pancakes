#!/usr/bin/env python3
"""OP-X-016: execute frozen TE models against canonical CFB25/26 databases."""
from __future__ import annotations
import itertools,json,math
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'data/research/op_x_013'; OUT=ROOT/'data/research/op_x_016'; SPEC=OUT/'frozen_te_scoring_spec.json'

def load_jsonl(path):
 rows=[]
 with path.open() as f:
  for line in f:
   if line.strip(): rows.append(json.loads(line))
 return rows

def weighted(attrs,w):
 used={k:v for k,v in w.items() if k in attrs}; den=sum(used.values())
 return (sum(attrs[k]*v for k,v in used.items())/den if den else None,den,sorted(set(w)-set(used)))

def score(row,spec):
 aliases=spec['archetype_aliases']; arch=aliases.get(row.get('archetype'),row.get('archetype','UNKNOWN')); a=row.get('attributes') or {}; w=spec['madden19_weights']
 if arch=='Gritty Possession': val,den,miss=weighted(a,w['Possession']); model='TE-MODEL-001 v1.1'
 elif arch=='Pure Blocker': val,den,miss=weighted(a,w['Blocking']); model='TE-MODEL-004 v1.1'
 elif arch=='Vertical Threat':
  vw=dict(w['Vertical Threat']); vw.pop('ELU',None); vw.update({'LBK':2,'IBL':3}); val,den,miss=weighted(a,vw); model='TE-MODEL-006 v1.3'
 elif arch=='Physical Route Runner':
  vw=dict(w['Vertical Threat']); vw.pop('ELU',None); v,vd,vm=weighted(a,vw); p,pd,pm=weighted(a,w['Possession']); val=0.71*v+0.29*p if v is not None and p is not None else None; den=None; miss=sorted(set(vm+pm)); model='TE-MODEL-003 v1.1'
 else: val=den=None; miss=[]; model=None
 return {**row,'canonical_archetype':arch,'frozen_model':model,'frozen_score':val,'weight_denominator':den,'missing_weighted_attributes':miss,'scoring_eligible':val is not None}

def metrics(rows):
 x=[r for r in rows if r['scoring_eligible']]; residual=[r['frozen_score']-r['ovr'] for r in x]; correct=inv=tie=0
 for a,b in itertools.combinations(x,2):
  if a['ovr']==b['ovr']: continue
  hi,lo=(a,b) if a['ovr']>b['ovr'] else (b,a); d=hi['frozen_score']-lo['frozen_score']
  if math.isclose(d,0,abs_tol=1e-12): tie+=1
  elif d>0: correct+=1
  else: inv+=1
 n=len(x); mean=sum(residual)/n if n else None; mae=sum(abs(v) for v in residual)/n if n else None
 return {'n':n,'mean_residual':mean,'raw_score_ovr_mae':mae,'distinct_ovr_pairs':correct+inv+tie,'correct_rankings':correct,'inversions':inv,'ties':tie,'ranking_accuracy_excluding_ties':correct/(correct+inv) if correct+inv else None}

def dump(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 spec=json.loads(SPEC.read_text()); expected={25:542,26:657}; report={'operation':'OP-X-016','control':'frozen models; no refit','seasons':{}}
 all_scored=[]
 for season in (25,26):
  rows=load_jsonl(SRC/f'cfb{season}_records.jsonl'); te=[r for r in rows if r.get('position')=='TE']
  if len(te)!=expected[season]: raise SystemExit(f'CFB{season} TE control mismatch: {len(te)} != {expected[season]}')
  scored=[score(r,spec) for r in te]; all_scored.extend(scored); arches=Counter(r['canonical_archetype'] for r in scored)
  sr={'population_n':len(te),'scored_n':sum(r['scoring_eligible'] for r in scored),'archetype_counts':dict(sorted(arches.items())),'models':{}}
  for arch in spec['models']:
   m=metrics([r for r in scored if r['canonical_archetype']==arch]); m['production_model']=spec['models'][arch]['production']; sr['models'][arch]=m
  report['seasons'][str(season)]=sr; dump(OUT/f'cfb{season}_te_scored.json',scored)
 report['combined']={'population_n':len(all_scored),'scored_n':sum(r['scoring_eligible'] for r in all_scored),'models':{}}
 for arch in spec['models']:
  report['combined']['models'][arch]=metrics([r for r in all_scored if r['canonical_archetype']==arch])
 dump(OUT/'validation_results.json',report)
 lines=['# OP-X-016 Historical TE Validation','',f"CFB25 TE: {report['seasons']['25']['population_n']}",f"CFB26 TE: {report['seasons']['26']['population_n']}",f"Combined TE: {report['combined']['population_n']}",'','Frozen coefficients only; no refit. TE-MODEL-004 is reported diagnostically and excluded from primary production scoring.','']
 for s in ('25','26'):
  lines += [f'## CFB{s}']+[f"- {a}: n={m['n']}, rank accuracy={m['ranking_accuracy_excluding_ties']}, MAE={m['raw_score_ovr_mae']}" for a,m in report['seasons'][s]['models'].items()]
 (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
