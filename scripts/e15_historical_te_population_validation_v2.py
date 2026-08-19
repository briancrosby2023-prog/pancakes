#!/usr/bin/env python3
"""Resumable CFB25/26 TE acquisition for E.15; delegates scoring to frozen scorer."""
from __future__ import annotations
import argparse,json,re,subprocess,sys,time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
BASE="https://cfb.fan"; OUT=Path("data/research/cfb27_e15/historical_validation")
TITLE_RE=re.compile(r"(?P<name>.+?)\s+(?P<ovr>\d{2})\s+OVR",re.I)
ALIASES={"Possession":"Gritty Possession","Blocking":"Pure Blocker","Gritty Possession":"Gritty Possession","Pure Blocker":"Pure Blocker","Vertical Threat":"Vertical Threat","Physical Route Runner":"Physical Route Runner"}
def atomic(path,v):
 path.parent.mkdir(parents=True,exist_ok=True); t=path.with_suffix(path.suffix+".tmp"); t.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n"); t.replace(path)
def get(s,url,pause):
 for attempt in range(7):
  try:
   r=s.get(url,timeout=30,headers={"User-Agent":"Operation-Pancake-research/1.0"})
   if r.status_code==200: time.sleep(pause); return r.text
   if r.status_code not in {429,500,502,503,504}: r.raise_for_status()
  except requests.RequestException:
   if attempt==6: raise
  time.sleep(min(60,2**attempt))
 raise RuntimeError(url)
def enumerate_links(s,season,pause):
 up=OUT/f"cfb{season}_te_urls.json"; mp=OUT/f"cfb{season}_page_manifest.json"
 if up.exists() and mp.exists():
  try:
   u=json.loads(up.read_text()); m=json.loads(mp.read_text())
   if u and m.get("complete"): return sorted(set(u))
  except Exception: pass
 links=set(); pages=[]; page=1
 while True:
  url=f"{BASE}/{season}/players/?page={page}"
  try: html=get(s,url,pause)
  except requests.HTTPError as e:
   if e.response is not None and e.response.status_code==404 and page>1:
    atomic(mp,{"season":season,"pages":pages,"unique_te_links":len(links),"complete":True,"terminal_page":page,"terminal_status":404}); break
   raise
  soup=BeautifulSoup(html,"html.parser"); all_cards=[]; te=[]
  for a in soup.find_all("a",href=True):
   text=" ".join(a.stripped_strings); href=a["href"]
   if "/players/" in href and "OVR" in text: all_cards.append(a)
   if "/players/" in href and re.search(r"\bTE\s*-\s*",text): te.append(urljoin(BASE,href))
  before=len(links); links.update(te); pages.append({"page":page,"url":url,"player_cards":len(all_cards),"te_links":len(te),"new_te_links":len(links)-before})
  atomic(mp,{"season":season,"pages":pages,"unique_te_links":len(links),"complete":not bool(all_cards)})
  if not all_cards: break
  page+=1
  if page>1000: raise RuntimeError("pagination safety limit")
 atomic(up,sorted(links)); return sorted(links)
def clean_name(n): return re.sub(r"^([A-Z])\s+([a-z])",r"\1\2",n.strip())
def parse(html,url,season):
 soup=BeautifulSoup(html,"html.parser"); text=" ".join(soup.stripped_strings); h1=soup.find("h1"); title=" ".join(h1.stripped_strings) if h1 else ""; mt=TITLE_RE.search(title)
 if not mt or " TE " not in f" {text} ": return None
 m=re.search(r"Archetype\s+(.+?)\s*-\s*TE\b",text,re.I); raw=m.group(1).strip() if m else None
 if raw not in ALIASES: raw=next((a for a in ALIASES if re.search(re.escape(a)+r"\s*-\s*TE\b",text,re.I)),raw)
 attrs={m.group(1):int(m.group(2)) for m in re.finditer(r"\b([A-Z]{2,4})\s+(\d{1,2})\b",text)}
 return {"season":season,"url":url,"name":clean_name(mt.group("name")),"ovr":int(mt.group("ovr")),"position":"TE","archetype":ALIASES.get(raw,raw or "UNKNOWN"),"source_archetype":raw or "UNKNOWN","attributes":attrs}
def acquire(s,season,links,pause):
 pp=OUT/f"cfb{season}_te_population.json"; fp=OUT/f"cfb{season}_failures.json"; existing=[]
 if pp.exists():
  try: existing=json.loads(pp.read_text())
  except Exception: pass
 by={r["url"]:r for r in existing if isinstance(r,dict) and r.get("url")}; failures=[]
 for i,url in enumerate(links,1):
  cur=by.get(url)
  if cur and cur.get("archetype") in set(ALIASES.values()): continue
  try:
   row=parse(get(s,url,pause),url,season)
   if row is None: failures.append({"url":url,"kind":"parse_failure"})
   else: by[url]=row
  except Exception as e: failures.append({"url":url,"kind":"fetch_failure","error":repr(e)})
  if i%10==0 or i==len(links): atomic(pp,list(by.values())); atomic(fp,failures)
 atomic(pp,list(by.values())); atomic(fp,failures); return list(by.values()),failures
def summarize(season,links,pop,fail):
 man=json.loads((OUT/f"cfb{season}_page_manifest.json").read_text()); urls=[r.get("url") for r in pop]; arches=Counter(r.get("archetype","UNKNOWN") for r in pop); ovrs=Counter(str(r.get("ovr")) for r in pop); coverage=Counter(k for r in pop for k in r.get("attributes",{}))
 return {"season":season,"listing_pages_enumerated":len(man.get("pages",[])),"terminal_page":man.get("terminal_page"),"terminal_status":man.get("terminal_status"),"enumerated_urls":len(links),"persisted_population":len(pop),"unique_source_urls":len(set(urls)),"missing_urls":sorted(set(links)-set(urls)),"duplicate_urls":len(urls)-len(set(urls)),"fetch_failures":sum(x.get("kind")=="fetch_failure" for x in fail),"parse_failures":sum(x.get("kind")=="parse_failure" for x in fail),"position_counts":{"TE":len(pop)},"archetype_counts":dict(sorted(arches.items())),"ovr_distribution":dict(sorted(ovrs.items(),key=lambda x:int(x[0]))),"attribute_coverage":dict(sorted(coverage.items())),"complete":len(links)==len(pop)==len(set(urls)) and not fail and arches.get("UNKNOWN",0)==0}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--seasons",nargs="+",type=int,default=[25,26]); ap.add_argument("--pause",type=float,default=.2); args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True); s=requests.Session(); sums=[]
 for season in args.seasons:
  links=enumerate_links(s,season,args.pause); pop,fail=acquire(s,season,links,args.pause); sm=summarize(season,links,pop,fail); atomic(OUT/f"cfb{season}_summary.json",sm); sums.append(sm)
 atomic(OUT/"summary.json",{"seasons":sums,"total_records":sum(x["persisted_population"] for x in sums)})
 subprocess.run([sys.executable,"scripts/e15_historical_te_score.py","--seasons",*[str(x) for x in args.seasons]],check=True)
 subprocess.run([sys.executable,"scripts/e15_historical_te_closure.py"],check=True)
 print(json.dumps({"seasons":sums},indent=2))
if __name__=="__main__": main()
