"""Supported Team Setup runtime with executable-verified OCR and real Team Manager layouts."""
from __future__ import annotations
import csv,io,re,subprocess
from collections import Counter
from pathlib import Path
from operation_pancake import team_app
from operation_pancake.ocr_runtime import discover_tesseract
from operation_pancake.slot_crop_ocr import ocr_slot_crops
from operation_pancake.team_import import OCRObservation,SlotRegion,VIEW_SLOTS,classify_view,extract_structured,match_candidate,to_candidate
TEAM_SETUP_BUILD="OCR-LAYOUT-PATCH-5";_ORIGINAL_UPLOAD_SURFACE=team_app._upload_surface
def _r(slot,cx,y1,y2,width=.095,backup_depth=.105):return SlotRegion(slot,(cx-width/2,y1,cx+width/2,min(.965,y2+backup_depth)))
REAL_TEAM_MANAGER_REGIONS={
"OFFENSE":[_r("LT1",.320,.405,.449),_r("LG1",.431,.405,.449),_r("C1",.544,.405,.449),_r("RG1",.656,.405,.449),_r("RT1",.768,.405,.449),_r("TE1",.880,.405,.449),_r("WR1",.320,.704,.752),_r("WR3",.431,.704,.752),_r("HB1",.544,.704,.752),_r("QB1",.656,.704,.752),_r("FB1",.768,.704,.752),_r("WR2",.880,.704,.752)],
"DEFENSE":[_r("FS1",.315,.426,.466),_r("WILL1",.418,.426,.466),_r("MIKE1",.522,.426,.466),_r("MIKE2",.625,.426,.466),_r("SAM1",.728,.426,.466),_r("SS1",.832,.426,.466),_r("CB1",.270,.690,.735),_r("CB3",.371,.690,.735),_r("REDG1",.472,.690,.735),_r("DT1",.573,.690,.735),_r("DT2",.674,.690,.735),_r("LEDG1",.775,.690,.735),_r("CB2",.876,.690,.735)],
"SPECIAL TEAMS":[_r("P1",.378,.435,.476),_r("K1",.468,.435,.476),_r("KR1",.700,.435,.476),_r("PR1",.802,.435,.476),_r("LS1",.378,.675,.716),_r("KOS1",.468,.675,.716)],
"SPECIALISTS":[_r("3DRB1",.365,.455,.505),_r("PWHB1",.468,.455,.505),_r("SLWR1",.570,.455,.505),_r("GAD1",.673,.455,.505),_r("NT1",.776,.455,.505),_r("SUBLB1",.365,.704,.755),_r("RRE1",.468,.704,.755),_r("RDT1",.570,.704,.755),_r("RLE1",.673,.704,.755),_r("SLCB1",.776,.704,.755)]}
def _ocr(path):
 runtime=discover_tesseract()
 if not runtime.ready or not runtime.executable:return None
 try:
  p=subprocess.run([runtime.executable,str(path),"stdout","--psm","11","tsv"],capture_output=True,text=True,timeout=45,check=False)
  if p.returncode:return None
  rows=list(csv.DictReader(io.StringIO(p.stdout),delimiter='\t'));pw=max([int(r.get('width') or 0) for r in rows if r.get('level')=='1'] or [1]);ph=max([int(r.get('height') or 0) for r in rows if r.get('level')=='1'] or [1]);out=[]
  for r in rows:
   text=(r.get('text') or '').strip()
   if not text:continue
   x,y,w,h=(int(r.get(k) or 0) for k in ('left','top','width','height'));conf=float(r.get('conf') or -1);out.append(OCRObservation(text,(x/pw,y/ph,(x+w)/pw,(y+h)/ph),None if conf<0 else conf/100))
  return out
 except (OSError,subprocess.TimeoutExpired,ValueError):return None

def _filename_view(filename):
 """Use an explicit user filename only as a conservative fallback when OCR cannot read the view tab."""
 stem=re.sub(r'[^a-z0-9]+',' ',Path(filename).stem.casefold()).strip();tokens=stem.split()
 if 'special' in tokens and 'teams' in tokens:return 'SPECIAL TEAMS'
 if 'specialists' in tokens or 'specialist' in tokens or ('special' in tokens and 'teams' not in tokens):return 'SPECIALISTS'
 if 'offense' in tokens or tokens[-1:] == ['o']:return 'OFFENSE'
 if 'defense' in tokens or tokens[-1:] == ['d']:return 'DEFENSE'
 return 'UNKNOWN'
def _propose_view(shot,obs):
 if obs is None:return 'UNKNOWN','ocr-unavailable'
 view=classify_view(obs)[0]
 if view in VIEW_SLOTS:return view,'ocr'
 fallback=_filename_view(shot.get('filename',''))
 return fallback,('filename-fallback' if fallback in VIEW_SLOTS else 'unresolved')
def _extract_unique(state_store,gm):
 """Classify every uploaded screenshot once; duplicate/missing views fail closed."""
 state=state_store.load();read=[];classified=[];sources=[]
 for shot in state.screenshots:
  obs=_ocr(Path(shot['path']));read.append((shot,obs));view,source=_propose_view(shot,obs);classified.append(view);sources.append(source)
 counts=Counter(v for v in classified if v in VIEW_SLOTS);complete=len(state.screenshots)==4 and set(counts)==set(VIEW_SLOTS) and all(n==1 for n in counts.values());candidates=[];meta={}
 for (shot,obs),proposed,source in zip(read,classified,sources):
  if obs is None:shot['extraction_status']='OCR ENGINE UNAVAILABLE';continue
  view=proposed if complete else ('UNKNOWN' if proposed not in VIEW_SLOTS or counts.get(proposed,0)!=1 else proposed)
  if view=='UNKNOWN':shot['extraction_status']='OCR READ — VIEW UNRESOLVED';shot['view']='UNKNOWN';meta[shot['id']]={'view':'UNKNOWN','provenance':['four-view-set:not-unique']};continue
  runtime=discover_tesseract();slot_obs=obs;crop_diagnostics={}
  if runtime.ready and runtime.executable:
   try:slot_obs,crop_diagnostics=ocr_slot_crops(Path(shot['path']),REAL_TEAM_MANAGER_REGIONS[view],runtime.executable)
   except (OSError,ValueError,subprocess.TimeoutExpired):crop_diagnostics={'error':'slot-crop-ocr-failed'}
  _,found,m=extract_structured(shot['id'],slot_obs,REAL_TEAM_MANAGER_REGIONS,view=view);m['classification_source']=source;m['slot_crop_ocr']=crop_diagnostics;shot['extraction_status']=f'OCR READ — {view}';shot['view']=view;shot['view_confidence']=m.get('view_confidence');meta[shot['id']]=m
  for observed in found:
   c=to_candidate(observed,f'cand-{len(candidates)+1}');candidates.append(match_candidate(c,gm.population))
 state.version=3;state.candidates=candidates;state.team_observations={'screenshots':meta,'four_view_set_complete':complete};state_store.save(state);return state

_VISUAL_LINEUP=r'''
<style>.pancake-lineup{margin:14px 0}.lineup-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.lineup-tab{padding:8px 12px;border:1px solid #475569;border-radius:999px;background:transparent;font-weight:800}.lineup-tab[aria-selected="true"]{background:#1e293b}.lineup-view{display:none}.lineup-view.active{display:block}.lineup-grid{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px}.lineup-slot{border:1px solid #475569;border-radius:10px;padding:9px;min-height:78px;background:rgba(15,23,42,.20)}.lineup-slot strong{font-size:13px}.lineup-player{font-weight:800;margin-top:5px}.lineup-backup{font-size:12px;margin-top:3px;opacity:.82}.lineup-review{font-size:11px;font-weight:900;margin-top:5px;padding:2px 6px;border:1px solid #b45309;border-radius:999px}.lineup-detail{display:none}.lineup-detail.open{display:block;margin-top:7px;font-size:11px}.lineup-detail select{max-width:100%}@media(max-width:900px){.lineup-grid{grid-template-columns:repeat(2,minmax(130px,1fr))}}</style>
<script>(()=>{async function build(){const heading=Array.from(document.querySelectorAll('h2')).find(x=>x.textContent.trim()==='Review Team');if(!heading)return;const table=heading.parentElement.querySelector('table');if(!table||table.dataset.visualized==='1')return;table.dataset.visualized='1';let state={candidates:[]};try{state=(await(await fetch('/api/team-import',{cache:'no-store'})).json()).state||state}catch(e){}const bySlot=new Map((state.candidates||[]).map(c=>[c.group+'|'+c.slot,c]));const order=['OFFENSE','DEFENSE','SPECIAL TEAMS','SPECIALISTS'],groups=new Map(order.map(x=>[x,[]]));Array.from(table.querySelectorAll('tr')).slice(1).forEach(row=>{const td=Array.from(row.querySelectorAll('td'));if(td.length<6)return;const view=td[0].textContent.trim(),slot=td[1].textContent.trim(),name=td[2].textContent.trim(),ovr=td[3].textContent.trim(),status=td[5].textContent.trim(),select=td[4].querySelector('select'),data=bySlot.get(view+'|'+slot)||{},review=!name||name==='UNKNOWN'||status!=='MATCHED';const card=document.createElement('div');card.className='lineup-slot';card.innerHTML=`<strong>${slot}</strong><div class="lineup-player">${name&&name!=='UNKNOWN'?name:'Unresolved'}${ovr&&ovr!=='UNKNOWN'?' — '+ovr:''}</div>`;(data.backups||[]).forEach(b=>{const d=document.createElement('div');d.className='lineup-backup';d.textContent=(b.player_name||'Unresolved')+(b.displayed_ovr?' — '+b.displayed_ovr:'');card.append(d)});if(review){const b=document.createElement('button');b.type='button';b.className='lineup-review';b.textContent='REVIEW';card.append(b);const detail=document.createElement('div');detail.className='lineup-detail';if(select)detail.append(select);b.addEventListener('click',()=>detail.classList.toggle('open'));card.append(detail)}(groups.get(view)||groups.get('SPECIALISTS')).push(card)});const shell=document.createElement('div');shell.className='pancake-lineup';const tabs=document.createElement('div');tabs.className='lineup-tabs';shell.append(tabs);order.forEach((view,i)=>{const b=document.createElement('button');b.type='button';b.className='lineup-tab';b.textContent=view;b.setAttribute('aria-selected',i?'false':'true');const s=document.createElement('section');s.className='lineup-view'+(i?'':' active');const g=document.createElement('div');g.className='lineup-grid';(groups.get(view)||[]).forEach(x=>g.append(x));s.append(g);b.addEventListener('click',()=>{shell.querySelectorAll('.lineup-tab').forEach(x=>x.setAttribute('aria-selected','false'));shell.querySelectorAll('.lineup-view').forEach(x=>x.classList.remove('active'));b.setAttribute('aria-selected','true');s.classList.add('active')});tabs.append(b);shell.append(s)});heading.textContent='Lineup';table.replaceWith(shell)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build()})();</script>'''
def _upload_surface():
 runtime=discover_tesseract();original=_ORIGINAL_UPLOAD_SURFACE();marker='<span id="team-drop-status"';ready=f'<br><span id="team-ocr-status" role="status">{runtime.message}</span>\n';return original.replace(marker,ready+marker,1).replace('TEAM SETUP BUILD: DROP-ZONE-PATCH-3',f'TEAM SETUP BUILD: {TEAM_SETUP_BUILD}',1)+_VISUAL_LINEUP
def install_runtime():
 team_app.TEAM_SETUP_BUILD=TEAM_SETUP_BUILD;team_app.DEFAULT_REGIONS=REAL_TEAM_MANAGER_REGIONS;team_app._ocr=_ocr;team_app._extract=_extract_unique;team_app._upload_surface=_upload_surface
def main():install_runtime();print(discover_tesseract().message);team_app.main()
