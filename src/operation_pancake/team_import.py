"""Team Manager screenshot evidence, structured extraction, conservative matching, and import state."""
from __future__ import annotations
import hashlib,json,re
from dataclasses import asdict,dataclass,field
from pathlib import Path
from typing import Any,Iterable
IMAGE_TYPES={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/heic":".heic","image/heif":".heif"}
SPECIALIST_SLOTS={"3DRB","PWHB","SLWR","GAD","NT","SUBLB","RRE","RDT","RLE","SLCB","KR","PR","LS","KOS"}
VIEW_SLOTS={"OFFENSE":("LT1","LG1","C1","RG1","RT1","TE1","WR1","WR3","HB1","QB1","FB1","WR2"),"DEFENSE":("FS1","WILL1","MIKE1","MIKE2","SAM1","SS1","CB1","CB3","REDG1","DT1","DT2","LEDG1","CB2"),"SPECIAL TEAMS":("P1","K1","KR1","PR1","LS1","KOS1"),"SPECIALISTS":("3DRB1","PWHB1","SLWR1","GAD1","NT1","SUBLB1","RRE1","RDT1","RLE1","SLCB1")}
SLOT_POSITION={"LT1":"LT","LG1":"LG","C1":"C","RG1":"RG","RT1":"RT","TE1":"TE","WR1":"WR","WR2":"WR","WR3":"WR","HB1":"HB","QB1":"QB","FB1":"FB","FS1":"FS","WILL1":"WILL","MIKE1":"MIKE","MIKE2":"MIKE","SAM1":"SAM","SS1":"SS","CB1":"CB","CB2":"CB","CB3":"CB","REDG1":"REDG","LEDG1":"LEDG","DT1":"DT","DT2":"DT","P1":"P","K1":"K","KR1":"KR","PR1":"PR","LS1":"LS","KOS1":"KOS","3DRB1":"3DRB","PWHB1":"PWHB","SLWR1":"SLWR","GAD1":"GAD","NT1":"NT","SUBLB1":"SUBLB","RRE1":"RRE","RDT1":"RDT","RLE1":"RLE","SLCB1":"SLCB"}
NOISE_WORDS={"OVR","TEAM","CHEM","CHEMISTRY","BONUS","OFFENSE","DEFENSE","SPECIAL","TEAMS","SPECIALISTS","IMPROVEMENTS","LINEUP","MANAGE","ITEM","ITEMS","PLAYER","PLAYERS"}
def normalize_name(value:str)->str:return re.sub(r"[^a-z0-9]","",value.casefold())
@dataclass(frozen=True)
class OCRObservation:text:str;box:tuple[float,float,float,float];confidence:float|None=None
@dataclass(frozen=True)
class SlotRegion:
 slot:str;box:tuple[float,float,float,float];starter_name_box:tuple[float,float,float,float]|None=None;starter_ovr_box:tuple[float,float,float,float]|None=None;backup_boxes:tuple[tuple[float,float,float,float],...] = ()
@dataclass
class ObservedLineupCandidate:
 source_screenshot:str;view:str;slot:str;slot_index:int;raw_player_name:str|None=None;normalized_player_name:str|None=None;displayed_ovr:int|None=None;visible_position:str|None=None;other_observed_text:list[str]=field(default_factory=list);observed_ratings:dict[str,int]=field(default_factory=dict);bounding_region:tuple[float,float,float,float]|None=None;extraction_confidence:float|None=None;provenance:list[str]=field(default_factory=list);backups:list[dict[str,Any]]=field(default_factory=list)
@dataclass
class Candidate:
 id:str;group:str;slot:str;player_name:str|None=None;displayed_ovr:int|None=None;position:str|None=None;program:str|None=None;canonical_card_id:str|None=None;match_status:str="UNMATCHED";confidence:float|None=None;observed_ratings:dict[str,int]=field(default_factory=dict);provenance:list[str]=field(default_factory=list);slot_index:int|None=None;bounding_region:tuple[float,float,float,float]|None=None;backups:list[dict[str,Any]]=field(default_factory=list)
@dataclass
class TeamImportState:version:int=3;screenshots:list[dict[str,Any]]=field(default_factory=list);candidates:list[Candidate]=field(default_factory=list);team_observations:dict[str,Any]=field(default_factory=dict)
class TeamImportStore:
 def __init__(self,path:Path,upload_dir:Path|None=None):self.path=path;self.upload_dir=upload_dir or path.parent/'team_uploads'
 def load(self)->TeamImportState:
  if not self.path.exists():return TeamImportState()
  d=json.loads(self.path.read_text(encoding='utf-8'));cs=[Candidate(**{k:v for k,v in x.items() if k in Candidate.__dataclass_fields__}) for x in d.get('candidates',[])];return TeamImportState(int(d.get('version',1)),list(d.get('screenshots',[])),cs,dict(d.get('team_observations',{})))
 def save(self,state:TeamImportState)->None:
  self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'version':max(3,state.version),'screenshots':state.screenshots,'candidates':[asdict(x) for x in state.candidates],'team_observations':state.team_observations},indent=2)+'\n',encoding='utf-8');tmp.replace(self.path)
 def stage_bytes(self,files:list[tuple[str,str,bytes]])->list[dict[str,Any]]:
  state=self.load();self.upload_dir.mkdir(parents=True,exist_ok=True);added=[]
  for filename,ctype,data in files:
   if ctype not in IMAGE_TYPES or not data:raise ValueError('Only non-empty PNG, JPEG, WEBP, HEIC, or HEIF images are accepted')
   digest=hashlib.sha256(data).hexdigest();target=self.upload_dir/f'{digest[:20]}{IMAGE_TYPES[ctype]}';target.write_bytes(data);row={'id':f'shot-{len(state.screenshots)+1}','filename':Path(filename).name,'content_type':ctype,'sha256':digest,'bytes':len(data),'path':str(target),'extraction_status':'STAGED — EXTRACTION PENDING'};state.screenshots.append(row);added.append(row)
  self.save(state);return added
 def set_candidates(self,candidates:list[Candidate],team_observations:dict[str,Any]|None=None)->None:
  state=self.load();state.version=3;state.candidates=candidates;state.team_observations=team_observations or {};self.save(state)
def _center(b):return((b[0]+b[2])/2,(b[1]+b[3])/2)
def _inside(p,b):return b[0]<=p[0]<=b[2] and b[1]<=p[1]<=b[3]
def _slot_base(s):return re.sub(r'\d+$','',s.upper())
def classify_view(observations:Iterable[OCRObservation])->tuple[str,float,list[str]]:
 obs=list(observations);upper=' '.join(o.text.upper() for o in obs);labels={x:x for x in VIEW_SLOTS};explicit=[v for v,l in labels.items() if re.search(rf'(?<![A-Z0-9]){re.escape(l)}(?![A-Z0-9])',upper)]
 if len(explicit)==1:return explicit[0],1.0,[f'view-label:{explicit[0]}']
 anchors={'OFFENSE':('QB','HB','WR','LT','LG','RG','RT'),'DEFENSE':('FS','SS','CB','MIKE','WILL','SAM','LEDG','REDG'),'SPECIAL TEAMS':('KICK RETURN','PUNT RETURN','KOS'),'SPECIALISTS':('SUBLB','RRE','RDT','RLE','SLCB','3DRB','PWHB')};scored=[]
 for v,terms in anchors.items():
  hits=[t for t in terms if re.search(rf'(?<![A-Z0-9]){re.escape(t)}(?![A-Z0-9])',upper)];scored.append((len(hits),v,hits))
 scored.sort(reverse=True);best=scored[0]
 if explicit or best[0]<2 or best[0]==scored[1][0]:return'UNKNOWN',0.0,['view:ambiguous-or-insufficient']
 return best[1],min(.9,best[0]/6),[f'view-anchor:{x}' for x in best[2]]
def associate_observations(observations,regions):
 out={r.slot:[] for r in regions}
 for o in observations:
  matches=[r for r in regions if _inside(_center(o.box),r.box)]
  if matches:
   r=min(matches,key=lambda x:(x.box[2]-x.box[0])*(x.box[3]-x.box[1]));out[r.slot].append(o)
 return out
def _name_tokens(observations,expected):
 good=[];other=[]
 for o in observations:
  text=o.text.strip();upper=text.upper().strip();compact=re.sub(r'[^A-Z0-9]','',upper)
  if compact in NOISE_WORDS or compact in {expected,_slot_base(expected)} or re.fullmatch(r'OVR\d*',compact) or any(w in upper.split() for w in NOISE_WORDS):other.append(text);continue
  parts=text.split();alpha=re.sub(r'[^A-Za-z]','',text)
  if 1<=len(parts)<=4 and len(alpha)>=2 and all(re.fullmatch(r"[A-Za-z][A-Za-z.\-']*",p) for p in parts):good.append(o)
  else:other.append(text)
 return good,other
def _name_from_box(observations,box,expected):
 selected=[o for o in observations if _inside(_center(o.box),box)];names,other=_name_tokens(selected,expected);rows=[]
 for o in names:
  cy=_center(o.box)[1];target=next((r for r in rows if abs(r[0]-cy)<.022),None)
  if target:target[1].append(o);target[0]=(target[0]+cy)/2
  else:rows.append([cy,[o]])
 rows.sort(key=lambda r:r[0]);parts=[]
 for _,words in rows:
  words.sort(key=lambda o:o.box[0]);text=' '.join(o.text.strip() for o in words).strip()
  if len(re.sub(r'[^A-Za-z]','',text))>=4:parts.append(text)
 return (' '.join(parts).strip() or None),other
def _ovr_from_box(observations,box):
 for o in sorted((x for x in observations if _inside(_center(x.box),box)),key=lambda x:(x.box[0],_center(x.box)[1])):
  compact=re.sub(r'[^A-Z0-9]','',o.text.upper());m=re.fullmatch(r'(?:OVR)?(\d{2})',compact)
  if m and 40<=int(m.group(1))<=99:return int(m.group(1))
 return None
def _parse_region(source,view,region,observations):
 expected=SLOT_POSITION.get(region.slot,_slot_base(region.slot));name_box=region.starter_name_box or region.box;ovr_box=region.starter_ovr_box or region.box
 name,other=_name_from_box(observations,name_box,expected);ovr=_ovr_from_box(observations,ovr_box);backups=[]
 for box in region.backup_boxes:
  backup_name,_=_name_from_box(observations,box,expected)
  if backup_name:backups.append({'player_name':backup_name,'displayed_ovr':_ovr_from_box(observations,box)})
 used_boxes=(name_box,ovr_box,*region.backup_boxes)
 for o in observations:
  if not any(_inside(_center(o.box),b) for b in used_boxes):other.append(o.text.strip())
 confs=[o.confidence for o in observations if o.confidence is not None];prov=[f'view:{view}',f'slot-region:{region.slot}','spatial-association','deterministic-slot-container','starter-name-subregion','starter-ovr-subregion','backup-subregions']
 if not name:prov.append('starter-name:unresolved')
 if ovr is None:prov.append('starter-ovr:unresolved')
 idx=re.search(r'\d+$',region.slot);return ObservedLineupCandidate(source,view,region.slot,int(idx.group()) if idx else 1,name,normalize_name(name) if name else None,ovr,expected,other,{},region.box,sum(confs)/len(confs) if confs else None,prov,backups)
def extract_structured(source_screenshot,observations,regions_by_view,view=None):
 classified,confidence,prov=classify_view(observations) if view is None else(view.upper(),1.0,['view:provided'])
 if classified not in VIEW_SLOTS or classified not in regions_by_view:return'UNKNOWN',[],{'view':'UNKNOWN','view_confidence':0.0,'provenance':prov}
 regions=regions_by_view[classified];grouped=associate_observations(observations,regions);found=[_parse_region(source_screenshot,classified,r,grouped.get(r.slot,[])) for r in regions];return classified,found,{'view':classified,'view_confidence':confidence,'provenance':prov,'topology':'deterministic-slot-containers','slot_count':len(found)}
def to_candidate(o,candidate_id=None):return Candidate(candidate_id or f'{o.source_screenshot}:{o.slot}',o.view,o.slot,o.raw_player_name,o.displayed_ovr,o.visible_position,match_status='UNMATCHED',observed_ratings=dict(o.observed_ratings),provenance=list(o.provenance),slot_index=o.slot_index,bounding_region=o.bounding_region,backups=list(o.backups))
def match_candidate(c,cards):
 c.canonical_card_id=None;c.match_status='UNRESOLVED' if not c.player_name else'UNMATCHED';c.confidence=None
 if not c.player_name:return c
 pool=[x for x in cards if normalize_name(x.get('player_name') or '')==normalize_name(c.player_name)];expected=SLOT_POSITION.get(c.slot,c.position)
 if expected:pool=[x for x in pool if (x.get('position') or '').upper()==expected.upper()]
 if c.program:pool=[x for x in pool if (x.get('program') or '').casefold()==c.program.casefold()]
 if c.displayed_ovr is not None:
  exact=[x for x in pool if x.get('native_overall')==c.displayed_ovr]
  if exact:pool=exact
 if len(pool)==1:c.canonical_card_id=pool[0]['card_id'];c.match_status='MATCHED';c.confidence=1.0
 elif len(pool)>1:c.match_status='AMBIGUOUS'
 return c
def ownership_key(c):return c.canonical_card_id or c.id
