#!/usr/bin/env python3
"""Acquire, normalize, and blind-validate historical CFB.FAN TE populations for E.15."""
from __future__ import annotations
import argparse, itertools, json, re, time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
BASE='https://cfb.fan'; OUT=Path('data/research/cfb27_e15/historical_validation')
TITLE_RE=re.compile(r'(?P<name>.+?)\s+(?P<ovr>\d{2})\s+OVR',re.I)
ARCHETYPES=('Gritty Possession','Vertical Threat','Physical Route Runner','Pure Blocker')
WEIGHTS={
'blocking':{'SPD':0,'ACC':0,'AGI':0,'STR':6,'JMP':0,'AWR':9,'BCV':0,'BTK':2,'ELU':0,'TRK':1,'SFA':2,'CTH':3,'CIT':3,'SPC':0,'RLS':0,'SRR':5,'MRR':4,'DRR':0,'IBL':9,'LBK':8,'PBK':8,'PBF':6,'PBP':6,'RBK':10,'RBF':9,'RBP':9},
'possession':{'SPD':3,'ACC':4,'AGI':3,'STR':4,'JMP':0,'AWR':9,'BCV':1,'BTK':2,'ELU':0,'TRK':1,'SFA':2,'CTH':10,'CIT':14,'SPC':1,'RLS':2,'SRR':12,'MRR':6,'DRR':0,'IBL':4,'LBK':2,'PBK':3,'PBF':2,'PBP':2,'RBK':5,'RBF':4,'RBP':4},
'vertical':{'SPD':7,'ACC':7,'AGI':4,'STR':0,'JMP':3,'AWR':9,'BCV':2,'BTK':3,'ELU':2,'TRK':1,'SFA':2,'CTH':11,'CIT':8,'SPC':4,'RLS':3,'SRR':7,'MRR':9,'DRR':5,'IBL':0,'LBK':0,'PBK':2,'PBF':1,'PBP':1,'RBK':3,'RBF':3,'RBP':3}}
MODEL_SPEC={'Gritty Possession':{'model':'TE-MODEL-001 v1.1','base':'possession'},'Physical Route Runner':{'model':'TE-MODEL-003 v1.1','blend':{'vertical_v13':0.71,'possession':0.29}},'Pure Blocker':{'model':'TE-MODEL-004 v1.1','base':'blocking'},'Vertical Threat':{'model':'TE-MODEL-006 v1.3','base':'vertical_v13'}}
def atomic_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n'); tmp.replace(path)
def get(session,url,pause):
 last=None
 for attempt in range(7):
  try:
   r=session.get(url,timeout=30,headers={'User-Agent':'Operation-Pancake-research/1.0'}); last=r.status_code
   if r.status_code==200: time.sleep(pause); return r.text
   if r.status_code not in {429,500,502,503,504}: r.raise_for_status()
  except requests.RequestException:
   if attempt==6: raise
  time.sleep(min(60,2**attempt))
 raise RuntimeError(f'failed after retries status={last}: {url}')
def enumerate_te_links(session,season,pause):
 cached=OUT/f'cfb{season}_te_urls.json'
 if cached.exists():
  try:
   links=json.loads(cached.read_text()); man=OUT/f'cfb{season}_page_manifest.json'
   if links and man.exists() and json.loads(man.read_text()).get('complete'): return sorted(set(links))
  except (OSError,json.JSONDecodeError): pass
 links=set(); page=1; pages=[]
 while True:
  url=f'{BASE}/{season}/players/?page={page}'
  try: html=get(session,url,pause)
  except requests.HTTPError as exc:
   if exc.response is not None and exc.response.status_code==404 and page>1:
    atomic_json(OUT/f'cfb{season}_page_manifest.json',{'season':season,'pages':pages,'unique_te_links':len(links),'complete':True,'terminal_page':page,'terminal_status':404}); break
   raise
  soup=BeautifulSoup(html,'html.parser'); cards=[]
  for a in soup.find_all('a',href=True):
   text,href=' '.join(a.stripped_strings),a['href']
   if '/players/' in href and re.search(r'\bTE\s+-\s+',text): cards.append(urljoin(BASE,href))
  all_cards=[a for a in soup.find_all('a',href=True) if re.search(r'\bOVR\b',' '.join(a.stripped_strings)) and '/players/' in a['href']]
  before=len(links); links.update(cards); pages.append({'page':page,'url':url,'player_cards':len(all_cards),'te_links':len(cards),'new_te_links':len(links)-before})
  atomic_json(OUT/f'cfb{season}_page_manifest.json',{'season':season,'pages':pages,'unique_te_links':len(links),'complete':not bool(all_cards)})
  if not all_cards: break
  page+=1
  if page>1000: raise RuntimeError('pagination safety limit reached')
 atomic_json(cached,sorted(links)); return sorted(links)
def _clean_name(name): return re.sub(r'^([A-Z])\s+([a-z])',r'\1\2',name.strip())
def parse_player(html,url,season):
 soup=BeautifulSoup(html,'html.parser'); text=' '.join(soup.stripped_strings); h1=soup.find('h1'); title=' '.join(h1.stripped_strings) if h1 else ''
 mt=TITLE_RE.search(title)
 if not mt or ' TE ' not in f' {text} ': return None
 m=re.search(r'Archetype\s+(.+?)\s*-\s*TE\b',text,re.I); arch=m.group(1).strip() if m else None
 if arch not in ARCHETYPES: arch=next((a for a in ARCHETYPES if re.search(re.escape(a)+r'\s*-\s*TE\b',text,re.I)),None)
 attrs={}
 for m in re.finditer(r'\b([A-Z]{2,4})\s+(\d{1,2})\b',text): attrs[m.group(1)]=int(m.group(2))
 return {'season':season,'url':url,'name':_clean_name(mt.group('name')),'ovr':int(mt.group('ovr')),'position':'TE','archetype':arch or 'UNKNOWN','attributes':attrs}
def acquire_population(session,season,links,pause):
 path=OUT/f'cfb{season}_te_population.json'; existing=[]
 if path.exists():
  try: existing=json.loads(path.read_text())
  except (json.JSONDecodeError,OSError): pass
 by_url={r['url']:r for r in existing if isinstance(r,dict) and r.get('url')}; failures=[]
 for i,url in enumerate(links,1):
  current=by_url.get(url)
  if current and current.get('archetype') in ARCHETYPES: continue
  try:
   record=parse_player(get(session,url,pause),url,season)
   if record is None: failures.append({'url':url,'kind':'parse_failure'})
   else: by_url[url]=record
  except Exception as exc: failures.append({'url':url,'kind':'fetch_failure','error':repr(exc)})
  if i%10==0 or i==len(links): atomic_json(path,list(by_url.values())); atomic_json(OUT/f'cfb{season}_failures.json',failures)
 atomic_json(path,list(by_url.values())); atomic_json(OUT/f'cfb{season}_failures.json',failures); return list(by_url.values())
def weighted(attrs,weights,omit=frozenset()):
 used={k:w for k,w in weights.items() if w and k in attrs and k not in omit}; missing=[k for k,w in weights.items() if w and k not in attrs and k not in omit]; den=sum(used.values()); return (sum(attrs[k]*w for k,w in used.items())/den if den else None,sorted(used),missing,den)
def score_record(r):
 a=r.get('attributes',{}); arch=r.get('archetype'); spec=MODEL_SPEC.get(arch)
 if not spec: return {**r,'scoring_eligible':False,'scoring_reason':'unknown_archetype'}
 p=weighted(a,WEIGHTS['possession']); b=weighted(a,WEIGHTS['blocking']); vweights=dict(WEIGHTS['vertical']); vweights['LBK']=2; vweights['IBL']=3; v=weighted(a,vweights,{'ELU'})
 if arch=='Gritty Possession': x=p
 elif arch=='Pure Blocker': x=b
 elif arch=='Vertical Threat': x=v
 else: x=(.71*v[0]+.29*p[0],sorted(set(v[1]+p[1])),sorted(set(v[2]+p[2])),None) if p[0] is not None and v[0] is not None else (None,[],[],0)
 return {**r,'model':spec['model'],'weighted_score':x[0],'attributes_used':x[1],'attributes_unavailable':x[2],'scoring_eligible':x[0] is not None,'scoring_reason':'ok' if x[0] is not None else 'missing_required_attributes'}
def analyze_group(rows):
 rows=[r for r in rows if r.get('scoring_eligible')]; correct=inv=ties=0; inversions=[]
 for a,b in itertools.combinations(rows,2):
  if a['ovr']==b['ovr']: continue
  hi,lo=(a,b) if a['ovr']>b['ovr'] else (b,a); delta=hi['weighted_score']-lo['weighted_score']
  if abs(delta)<1e-12: ties+=1
  elif delta>0: correct+=1
  else: inv+=1; inversions.append({'higher_ovr':hi['ovr'],'higher_name':hi['name'],'higher_url':hi['url'],'higher_score':hi['weighted_score'],'lower_ovr':lo['ovr'],'lower_name':lo['name'],'lower_url':lo['url'],'lower_score':lo['weighted_score'],'score_delta':delta,'ovr_gap':hi['ovr']-lo['ovr']})
 residuals=[r['weighted_score']-r['ovr'] for r in rows]; bands={}
 for ovr in sorted({r['ovr'] for r in rows}):
  rr=[r for r in rows if r['ovr']==ovr]; res=[r['weighted_score']-r['ovr'] for r in rr]; bands[str(ovr)]={'n':len(rr),'mean_score':sum(r['weighted_score'] for r in rr)/len(rr),'mean_residual':sum(res)/len(res),'mae':sum(abs(x) for x in res)/len(res)}
 return {'n':len(rows),'comparable_distinct_ovr_pairs':correct+inv+ties,'correct_rankings':correct,'inversions':inv,'ties':ties,'ranking_accuracy_excluding_ties':correct/(correct+inv) if correct+inv else None,'ranking_accuracy_ties_as_incorrect':correct/(correct+inv+ties) if correct+inv+ties else None,'raw_score_ovr_mae':sum(abs(x) for x in residuals)/len(residuals) if residuals else None,'mean_residual':sum(residuals)/len(residuals) if residuals else None,'ovr_bands':bands,'inversion_records':sorted(inversions,key=lambda x:(x['score_delta'],-x['ovr_gap']))}
def summarize(season,links,population,failures):
 urls=[r.get('url') for r in population]; arches=Counter(r.get('archetype','UNKNOWN') for r in population); ovrs=Counter(str(r.get('ovr','UNKNOWN')) for r in population); coverage=Counter(k for r in population for k in r.get('attributes',{})); man=json.loads((OUT/f'cfb{season}_page_manifest.json').read_text()) if (OUT/f'cfb{season}_page_manifest.json').exists() else {}
 return {'season':season,'listing_pages_enumerated':len(man.get('pages',[])),'terminal_page':man.get('terminal_page'),'terminal_status':man.get('terminal_status'),'enumerated_urls':len(links),'persisted_population':len(population),'unique_source_urls':len(set(urls)),'missing_urls':sorted(set(links)-set(urls)),'duplicate_urls':len(urls)-len(set(urls)),'fetch_failures':sum(f.get('kind')=='fetch_failure' for f in failures),'parse_failures':sum(f.get('kind')=='parse_failure' for f in failures),'position_counts':{'TE':len(population)},'archetype_counts':dict(sorted(arches.items())),'ovr_distribution':dict(sorted(ovrs.items(),key=lambda x:int(x[0]) if x[0].isdigit() else 999)),'attribute_coverage':dict(sorted(coverage.items())),'complete':len(links)==len(population)==len(set(urls)) and not failures and arches.get('UNKNOWN',0)==0}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--seasons',nargs='+',type=int,default=[25,26]); ap.add_argument('--pause',type=float,default=.20); args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
 atomic_json(OUT/'frozen_te_scoring_spec.json',{'models':MODEL_SPEC,'madden19_weights':WEIGHTS,'vertical_v13_modification':{'+LBK_weight_points':2,'+IBL_weight_points':3,'ELU':'omitted/unavailable and renormalized'},'controls':['frozen; do not refit on CFB25/26','ranking accuracy distinct from exact displayed OVR']})
 session=requests.Session(); summaries=[]; all_scored=[]; validation={}
 for season in args.seasons:
  links=enumerate_te_links(session,season,args.pause); pop=acquire_population(session,season,links,args.pause); failures=json.loads((OUT/f'cfb{season}_failures.json').read_text()) if (OUT/f'cfb{season}_failures.json').exists() else []
  summary=summarize(season,links,pop,failures); atomic_json(OUT/f'cfb{season}_summary.json',summary); summaries.append(summary); scored=[score_record(r) for r in pop]; atomic_json(OUT/f'cfb{season}_te_scored.json',scored); all_scored.extend(scored); validation[str(season)]={}
  for arch in ARCHETYPES:
   validation[str(season)][arch]=analyze_group([r for r in scored if r.get('archetype')==arch]); atomic_json(OUT/f'cfb{season}_{arch.lower().replace(" ","_")}_validation.json',validation[str(season)][arch])
 atomic_json(OUT/'historical_te_database.json',all_scored); atomic_json(OUT/'validation_metrics.json',validation); atomic_json(OUT/'summary.json',{'seasons':summaries,'total_records':len(all_scored),'validation':{s:{a:{k:v for k,v in m.items() if k not in {'inversion_records','ovr_bands'}} for a,m in d.items()} for s,d in validation.items()}}); print(json.dumps({'seasons':summaries,'total_records':len(all_scored)},indent=2))
if __name__=='__main__': main()
