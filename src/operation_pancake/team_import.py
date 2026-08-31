"""Team Manager screenshot evidence, structured extraction, conservative matching, and import state."""
from __future__ import annotations
import hashlib, json, re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

IMAGE_TYPES={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/heic":".heic","image/heif":".heif"}
SPECIALIST_SLOTS={"3DRB","PWHB","SLWR","GAD","NT","SUBLB","RRE","RDT","RLE","SLCB","KR","PR","LS","KOS"}
VIEW_SLOTS={
 "OFFENSE":("LT1","LG1","C1","RG1","RT1","TE1","WR1","WR3","HB1","QB1","FB1","WR2"),
 "DEFENSE":("FS1","WILL1","MIKE1","MIKE2","SAM1","SS1","CB1","CB3","REDG1","DT1","DT2","LEDG1","CB2"),
 "SPECIAL TEAMS":("P1","K1","KR1","PR1","LS1","KOS1"),
 "SPECIALISTS":("3DRB1","PWHB1","SLWR1","GAD1","NT1","SUBLB1","RRE1","RDT1","RLE1","SLCB1"),
}
SLOT_POSITION={
 "LT1":"LT","LG1":"LG","C1":"C","RG1":"RG","RT1":"RT","TE1":"TE","WR1":"WR","WR2":"WR","WR3":"WR","HB1":"HB","QB1":"QB","FB1":"FB",
 "FS1":"FS","WILL1":"WILL","MIKE1":"MIKE","MIKE2":"MIKE","SAM1":"SAM","SS1":"SS","CB1":"CB","CB2":"CB","CB3":"CB","REDG1":"REDG","LEDG1":"LEDG","DT1":"DT","DT2":"DT",
 "P1":"P","K1":"K","KR1":"KR","PR1":"PR","LS1":"LS","KOS1":"KOS","3DRB1":"3DRB","PWHB1":"PWHB","SLWR1":"SLWR","GAD1":"GAD","NT1":"NT","SUBLB1":"SUBLB","RRE1":"RRE","RDT1":"RDT","RLE1":"RLE","SLCB1":"SLCB",
}
NOISE_WORDS={"OVR","TEAM","CHEM","CHEMISTRY","BONUS","OFFENSE","DEFENSE","SPECIAL","TEAMS","SPECIALISTS","IMPROVEMENTS","LINEUP","MANAGE","ITEM","ITEMS","PLAYER","PLAYERS"}

def normalize_name(value:str)->str: return re.sub(r"[^a-z0-9]","",value.casefold())

@dataclass(frozen=True)
class OCRObservation:
    text:str; box:tuple[float,float,float,float]; confidence:float|None=None
@dataclass(frozen=True)
class SlotRegion:
    slot:str; box:tuple[float,float,float,float]
@dataclass
class ObservedLineupCandidate:
    source_screenshot:str; view:str; slot:str; slot_index:int
    raw_player_name:str|None=None; normalized_player_name:str|None=None; displayed_ovr:int|None=None; visible_position:str|None=None
    other_observed_text:list[str]=field(default_factory=list); observed_ratings:dict[str,int]=field(default_factory=dict)
    bounding_region:tuple[float,float,float,float]|None=None; extraction_confidence:float|None=None; provenance:list[str]=field(default_factory=list); backups:list[dict[str,Any]]=field(default_factory=list)
@dataclass
class Candidate:
    id:str; group:str; slot:str; player_name:str|None=None; displayed_ovr:int|None=None; position:str|None=None; program:str|None=None; canonical_card_id:str|None=None
    match_status:str="UNMATCHED"; confidence:float|None=None; observed_ratings:dict[str,int]=field(default_factory=dict); provenance:list[str]=field(default_factory=list)
    slot_index:int|None=None; bounding_region:tuple[float,float,float,float]|None=None; backups:list[dict[str,Any]]=field(default_factory=list)
@dataclass
class TeamImportState:
    version:int=3; screenshots:list[dict[str,Any]]=field(default_factory=list); candidates:list[Candidate]=field(default_factory=list); team_observations:dict[str,Any]=field(default_factory=dict)

class TeamImportStore:
    def __init__(self,path:Path,upload_dir:Path|None=None): self.path=path; self.upload_dir=upload_dir or path.parent/'team_uploads'
    def load(self)->TeamImportState:
        if not self.path.exists(): return TeamImportState()
        d=json.loads(self.path.read_text(encoding='utf-8')); candidates=[]
        for x in d.get('candidates',[]): candidates.append(Candidate(**{k:v for k,v in x.items() if k in Candidate.__dataclass_fields__}))
        return TeamImportState(int(d.get('version',1)),list(d.get('screenshots',[])),candidates,dict(d.get('team_observations',{})))
    def save(self,state:TeamImportState)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'version':max(3,state.version),'screenshots':state.screenshots,'candidates':[asdict(x) for x in state.candidates],'team_observations':state.team_observations},indent=2)+'\n',encoding='utf-8'); tmp.replace(self.path)
    def stage_bytes(self,files:list[tuple[str,str,bytes]])->list[dict[str,Any]]:
        state=self.load(); self.upload_dir.mkdir(parents=True,exist_ok=True); added=[]
        for filename,ctype,data in files:
            if ctype not in IMAGE_TYPES or not data: raise ValueError('Only non-empty PNG, JPEG, WEBP, HEIC, or HEIF images are accepted')
            digest=hashlib.sha256(data).hexdigest(); target=self.upload_dir/f'{digest[:20]}{IMAGE_TYPES[ctype]}'; target.write_bytes(data)
            row={'id':f'shot-{len(state.screenshots)+1}','filename':Path(filename).name,'content_type':ctype,'sha256':digest,'bytes':len(data),'path':str(target),'extraction_status':'STAGED — EXTRACTION PENDING'}
            state.screenshots.append(row); added.append(row)
        self.save(state); return added
    def set_candidates(self,candidates:list[Candidate],team_observations:dict[str,Any]|None=None)->None:
        state=self.load(); state.version=3; state.candidates=candidates; state.team_observations=team_observations or {}; self.save(state)

def _center(box): return ((box[0]+box[2])/2,(box[1]+box[3])/2)
def _inside(point,box): return box[0]<=point[0]<=box[2] and box[1]<=point[1]<=box[3]
def _slot_base(slot:str)->str: return re.sub(r"\d+$","",slot.upper())

def classify_view(observations:Iterable[OCRObservation])->tuple[str,float,list[str]]:
    """Classify from stable view/tab labels first; ambiguous evidence fails closed."""
    obs=list(observations)
    labels={"OFFENSE":"OFFENSE","DEFENSE":"DEFENSE","SPECIAL TEAMS":"SPECIAL TEAMS","SPECIALISTS":"SPECIALISTS"}
    upper=' '.join(o.text.upper() for o in obs)
    explicit=[view for view,label in labels.items() if re.search(rf'(?<![A-Z0-9]){re.escape(label)}(?![A-Z0-9])',upper)]
    if len(explicit)==1: return explicit[0],1.0,[f'view-label:{explicit[0]}']
    anchors={
      'OFFENSE':('QB','HB','WR','LT','LG','RG','RT'), 'DEFENSE':('FS','SS','CB','MIKE','WILL','SAM','LEDG','REDG'),
      'SPECIAL TEAMS':('KICK RETURN','PUNT RETURN','KOS'), 'SPECIALISTS':('SUBLB','RRE','RDT','RLE','SLCB','3DRB','PWHB'),
    }
    scored=[]
    for view,terms in anchors.items():
        hits=[t for t in terms if re.search(rf'(?<![A-Z0-9]){re.escape(t)}(?![A-Z0-9])',upper)]; scored.append((len(hits),view,hits))
    scored.sort(reverse=True); best=scored[0]
    if explicit or best[0]<2 or best[0]==scored[1][0]: return 'UNKNOWN',0.0,['view:ambiguous-or-insufficient']
    return best[1],min(.9,best[0]/6),[f'view-anchor:{x}' for x in best[2]]

def associate_observations(observations:Iterable[OCRObservation],regions:Iterable[SlotRegion])->dict[str,list[OCRObservation]]:
    out={r.slot:[] for r in regions}
    for obs in observations:
        matches=[r for r in regions if _inside(_center(obs.box),r.box)]
        if matches:
            r=min(matches,key=lambda x:(x.box[2]-x.box[0])*(x.box[3]-x.box[1])); out[r.slot].append(obs)
    return out

def _clean_tokens(observations:list[OCRObservation], expected_position:str)->tuple[list[OCRObservation],int|None,list[str]]:
    ordered=sorted(observations,key=lambda o:(_center(o.box)[1],o.box[0])); ovr=None; names=[]; other=[]
    for o in ordered:
        text=o.text.strip(); upper=text.upper().strip(); compact=re.sub(r'[^A-Z0-9]','',upper)
        m=re.fullmatch(r'(?:OVR)?(\d{2})',compact)
        if m and 40<=int(m.group(1))<=99 and ovr is None: ovr=int(m.group(1)); continue
        if compact in NOISE_WORDS or compact in {expected_position,_slot_base(expected_position)} or re.fullmatch(r'OVR\d*',compact): other.append(text); continue
        if any(word in upper.split() for word in NOISE_WORDS): other.append(text); continue
        if re.fullmatch(r'[A-Za-z][A-Za-z.\-\']*',text) and len(re.sub(r'[^A-Za-z]','',text))>=2: names.append(o)
        else: other.append(text)
    return names,ovr,other

def _parse_region(source:str,view:str,region:SlotRegion,observations:list[OCRObservation])->ObservedLineupCandidate:
    """Parse one slot only. Names and backups are row-local; malformed rows stay unresolved."""
    expected=SLOT_POSITION.get(region.slot,_slot_base(region.slot)); names,ovr,other=_clean_tokens(observations,expected)
    rows=[]
    for o in names:
        cy=_center(o.box)[1]; target=next((r for r in rows if abs(r[0]-cy)<.012),None)
        if target: target[1].append(o); target[0]=(target[0]+cy)/2
        else: rows.append([cy,[o]])
    rows.sort(key=lambda r:r[0]); parsed=[]
    for cy,words in rows:
        words.sort(key=lambda o:o.box[0]); text=' '.join(o.text.strip() for o in words).strip()
        alpha=re.sub(r'[^A-Za-z]','',text)
        if len(alpha)>=4 and 1<=len(words)<=4: parsed.append((cy,text))
    name=parsed[0][1] if parsed else None
    backups=[]
    for cy,text in parsed[1:]:
        nearby=[]
        for o in observations:
            if abs(_center(o.box)[1]-cy)<.014:
                m=re.fullmatch(r'(?:OVR\s*)?(\d{2})',o.text.upper().strip())
                if m and 40<=int(m.group(1))<=99: nearby.append(int(m.group(1)))
        backups.append({'player_name':text,'displayed_ovr':nearby[0] if nearby else None})
    confs=[o.confidence for o in observations if o.confidence is not None]
    provenance=[f'view:{view}',f'slot-region:{region.slot}','spatial-association','deterministic-slot-container','name-row-isolation']
    if not name: provenance.append('starter-name:unresolved')
    if ovr is None: provenance.append('starter-ovr:unresolved')
    return ObservedLineupCandidate(source,view,region.slot,int(re.search(r'\d+$',region.slot).group()) if re.search(r'\d+$',region.slot) else 1,name,normalize_name(name) if name else None,ovr,expected,other,{},region.box,sum(confs)/len(confs) if confs else None,provenance,backups)

def extract_structured(source_screenshot:str,observations:list[OCRObservation],regions_by_view:dict[str,list[SlotRegion]],view:str|None=None)->tuple[str,list[ObservedLineupCandidate],dict[str,Any]]:
    classified,confidence,prov=classify_view(observations) if view is None else (view.upper(),1.0,['view:provided'])
    if classified not in VIEW_SLOTS or classified not in regions_by_view: return 'UNKNOWN',[],{'view':'UNKNOWN','view_confidence':0.0,'provenance':prov}
    regions=regions_by_view[classified]; grouped=associate_observations(observations,regions)
    found=[_parse_region(source_screenshot,classified,r,grouped.get(r.slot,[])) for r in regions]
    return classified,found,{'view':classified,'view_confidence':confidence,'provenance':prov,'topology':'deterministic-slot-containers','slot_count':len(found)}

def to_candidate(observed:ObservedLineupCandidate,candidate_id:str|None=None)->Candidate:
    return Candidate(candidate_id or f'{observed.source_screenshot}:{observed.slot}',observed.view,observed.slot,observed.raw_player_name,observed.displayed_ovr,observed.visible_position,match_status='UNMATCHED',observed_ratings=dict(observed.observed_ratings),provenance=list(observed.provenance),slot_index=observed.slot_index,bounding_region=observed.bounding_region,backups=list(observed.backups))

def match_candidate(candidate:Candidate,cards:list[dict[str,Any]])->Candidate:
    candidate.canonical_card_id=None; candidate.match_status='UNRESOLVED' if not candidate.player_name else 'UNMATCHED'; candidate.confidence=None
    if not candidate.player_name: return candidate
    pool=[c for c in cards if normalize_name(c.get('player_name') or '')==normalize_name(candidate.player_name)]
    expected=SLOT_POSITION.get(candidate.slot,candidate.position)
    if expected: pool=[c for c in pool if (c.get('position') or '').upper()==expected.upper()]
    if candidate.program: pool=[c for c in pool if (c.get('program') or '').casefold()==candidate.program.casefold()]
    if candidate.displayed_ovr is not None:
        exact=[c for c in pool if c.get('native_overall')==candidate.displayed_ovr]
        if exact: pool=exact
    if len(pool)==1: candidate.canonical_card_id=pool[0]['card_id']; candidate.match_status='MATCHED'; candidate.confidence=1.0
    elif len(pool)>1: candidate.match_status='AMBIGUOUS'
    return candidate

def ownership_key(candidate:Candidate)->str: return candidate.canonical_card_id or candidate.id
