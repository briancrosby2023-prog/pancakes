#!/usr/bin/env python3
"""OP-X-013 all-position historical CFB.FAN acquisition, resumable by URL/card id."""
from __future__ import annotations
import argparse,json,re,time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
BASE='https://cfb.fan'; OUT=Path('data/research/op_x_013')
CARD_RE=re.compile(r'/players/(?P<player_id>\d+)-[^/]+/(?P<card_id>\d{2}-\d+)/?')
TITLE_RE=re.compile(r'(?P<name>.+?)\s+(?P<ovr>\d{2})\s+OVR',re.I)
def atomic(p,v):
 p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n'); t.replace(p)
def get(s,url,pause):
 for a in range(7):
  try:
   r=s.get(url,timeout=30,headers={'User-Agent':'Operation-Pancake-research/1.0'})
   if r.status_code==200: time.sleep(pause); return r.text
   if r.status_code==404: r.raise_for_status()
   if r.status_code not in {429,500,502,503,504}: r.raise_for_status()
  except requests.RequestException:
   if a==6: raise
  time.sleep(min(30,2**a))
 raise RuntimeError(url)
def identity(url):
 m=CARD_RE.search(urlparse(url).path)
 return (m.group('card_id'),m.group('player_id')) if m else (None,None)
def enumerate_all(s,season,pause):
 up=OUT/f'cfb{season}_card_urls.json'; mp=OUT/f'cfb{season}_page_manifest.json'
 links={}
 if up.exists():
  try:
   for u in json.loads(up.read_text()):
    cid,_=identity(u)
    if cid: links[cid]=u
  except Exception: pass
 pages=[]; start=1
 if mp.exists():
  try:
   old=json.loads(mp.read_text()); pages=old.get('pages',[])
   if old.get('complete') and links: return sorted(links.values()),old
   if pages: start=max(x['page'] for x in pages)+1
  except Exception: pass
 for page in range(start,1001):
  url=f'{BASE}/{season}/players/?page={page}'
  try: html=get(s,url,pause)
  except requests.HTTPError as e:
   if e.response is not None and e.response.status_code==404 and page>1:
    man={'season':season,'pages':pages,'unique_cards':len(links),'complete':True,'terminal_page':page,'terminal_status':404}; atomic(up,sorted(links.values())); atomic(mp,man); return sorted(links.values()),man
   raise
  soup=BeautifulSoup(html,'html.parser'); found=[]
  for a in soup.find_all('a',href=True):
   href=urljoin(BASE,a['href']); cid,_=identity(href)
   if cid and 'OVR' in ' '.join(a.stripped_strings): found.append((cid,href))
  before=len(links)
  for cid,href in found: links[cid]=href
  pages.append({'page':page,'cards_seen':len(found),'new_unique_cards':len(links)-before,'unique_cards_total':len(links)})
  atomic(up,sorted(links.values())); atomic(mp,{'season':season,'pages':pages,'unique_cards':len(links),'complete':False})
  if not found:
   man={'season':season,'pages':pages,'unique_cards':len(links),'complete':True,'terminal_page':page,'terminal_status':200}; atomic(mp,man); return sorted(links.values()),man
 raise RuntimeError('pagination safety limit')
def parse(html,url,season):
 soup=BeautifulSoup(html,'html.parser'); text=' '.join(soup.stripped_strings); h1=soup.find('h1'); title=' '.join(h1.stripped_strings) if h1 else ''; mt=TITLE_RE.search(title); cid,pid=identity(url)
 if not mt or not cid: return None
 pm=re.search(r'Archetype\s+(.+?)\s*-\s*([A-Z]{1,5})\b',text,re.I)
 archetype=pm.group(1).strip() if pm else None; position=pm.group(2).upper() if pm else None
 attrs={m.group(1):int(m.group(2)) for m in re.finditer(r'\b([A-Z]{2,4})\s+(\d{1,2})\b',text)}
 return {'season':season,'card_id':cid,'player_id':pid,'url':url,'name':mt.group('name').strip(),'ovr':int(mt.group('ovr')),'position':position,'archetype':archetype,'attributes':attrs}
def acquire(s,season,links,pause):
 pp=OUT/f'cfb{season}_records.jsonl'; fp=OUT/f'cfb{season}_failures.json'; existing={}
 if pp.exists():
  for line in pp.read_text().splitlines():
   try:
    r=json.loads(line); existing[r['card_id']]=r
   except Exception: pass
 failures=[]
 if fp.exists():
  try: failures=json.loads(fp.read_text())
  except Exception: pass
 failed={x.get('card_id') for x in failures}; target=[]
 for u in links:
  cid,_=identity(u)
  if cid not in existing: target.append((cid,u))
 for i,(cid,u) in enumerate(target,1):
  try:
   row=parse(get(s,u,pause),u,season)
   if row: existing[cid]=row; failed.discard(cid)
   else: failures.append({'card_id':cid,'url':u,'kind':'parse_failure'}); failed.add(cid)
  except Exception as e: failures.append({'card_id':cid,'url':u,'kind':'fetch_failure','error':repr(e)}); failed.add(cid)
  if i%25==0 or i==len(target):
   pp.write_text(''.join(json.dumps(existing[k],sort_keys=True)+'\n' for k in sorted(existing))); atomic(fp,[x for x in failures if x.get('card_id') in failed]); atomic(OUT/f'cfb{season}_acquisition_checkpoint.json',{'season':season,'enumerated_cards':len(links),'records_acquired':len(existing),'remaining':len(links)-len(existing),'last_batch_index':i,'target_at_start':len(target)})
 return existing,[x for x in failures if x.get('card_id') in failed]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--seasons',nargs='+',type=int,default=[25]); ap.add_argument('--pause',type=float,default=.12); args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True); s=requests.Session(); summaries=[]
 for season in args.seasons:
  links,man=enumerate_all(s,season,args.pause); records,fail=acquire(s,season,links,args.pause); players={r.get('player_id') for r in records.values() if r.get('player_id')}; positions=Counter(r.get('position') or 'UNKNOWN' for r in records.values()); sm={'season':season,'pages_enumerated':len(man.get('pages',[])),'terminal_page':man.get('terminal_page'),'terminal_status':man.get('terminal_status'),'unique_cards_discovered':len(links),'full_records_acquired':len(records),'unique_players':len(players),'failures':len(fail),'position_counts':dict(sorted(positions.items())),'complete_enumeration':bool(man.get('complete')),'complete_records':len(records)==len(links) and not fail}; atomic(OUT/f'cfb{season}_summary.json',sm); summaries.append(sm)
 atomic(OUT/'summary.json',{'seasons':summaries}); print(json.dumps({'seasons':summaries},indent=2))
if __name__=='__main__': main()
