"""Team Manager screenshot evidence, structured extraction, conservative matching, and import state."""
from __future__ import annotations
import hashlib, json, re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

IMAGE_TYPES={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/heic":".heic","image/heif":".heif"}
SPECIALIST_SLOTS={"3DRB","PWHB","SLWR","GAD","NT","SUBLB","RRE","RDT","RLE","SLCB","KR","PR","LS","KOS"}
VIEW_SLOTS={
 "OFFENSE":("QB1","HB1","FB1","WR1","WR2","WR3","TE1","TE2","LT1","LG1","C1","RG1","RT1"),
 "DEFENSE":("FS1","SS1","SS2","CB1","CB2","CB3","WILL1","MIKE1","MIKE2","SAM1","LEDG1","REDG1","DT1","DT2"),
 "SPECIAL TEAMS":("K1","P1","KR1","KR2","PR1","PR2","LS1","KOS1"),
 "SPECIALISTS":("3DRB1","PWHB1","SLWR1","GAD1","NT1","SUBLB1","SUBLB2","RRE1","RDT1","RDT2","RLE1","SLCB1"),
}

def normalize_name(value:str)->str:
    """Conservative OCR normalization: case, whitespace and punctuation only."""
    return re.sub(r"[^a-z0-9]","",value.casefold())

@dataclass(frozen=True)
class OCRObservation:
    text:str
    box:tuple[float,float,float,float] # normalized x1,y1,x2,y2
    confidence:float|None=None

@dataclass(frozen=True)
class SlotRegion:
    slot:str
    box:tuple[float,float,float,float]

@dataclass
class ObservedLineupCandidate:
    source_screenshot:str; view:str; slot:str; slot_index:int
    raw_player_name:str|None=None; normalized_player_name:str|None=None
    displayed_ovr:int|None=None; visible_position:str|None=None
    other_observed_text:list[str]=field(default_factory=list)
    observed_ratings:dict[str,int]=field(default_factory=dict)
    bounding_region:tuple[float,float,float,float]|None=None
    extraction_confidence:float|None=None; provenance:list[str]=field(default_factory=list)

@dataclass
class Candidate:
    id:str; group:str; slot:str; player_name:str|None=None; displayed_ovr:int|None=None
    position:str|None=None; program:str|None=None; canonical_card_id:str|None=None
    match_status:str="UNMATCHED"; confidence:float|None=None
    observed_ratings:dict[str,int]=field(default_factory=dict); provenance:list[str]=field(default_factory=list)
    slot_index:int|None=None; bounding_region:tuple[float,float,float,float]|None=None

@dataclass
class TeamImportState:
    version:int=2; screenshots:list[dict[str,Any]]=field(default_factory=list)
    candidates:list[Candidate]=field(default_factory=list); team_observations:dict[str,Any]=field(default_factory=dict)

class TeamImportStore:
    def __init__(self,path:Path,upload_dir:Path|None=None): self.path=path; self.upload_dir=upload_dir or path.parent/'team_uploads'
    def load(self)->TeamImportState:
        if not self.path.exists(): return TeamImportState()
        d=json.loads(self.path.read_text(encoding='utf-8'))
        # v1/v2 are deliberately forward-readable; absent structured fields use dataclass defaults.
        candidates=[]
        for x in d.get('candidates',[]):
            allowed={k:v for k,v in x.items() if k in Candidate.__dataclass_fields__}
            candidates.append(Candidate(**allowed))
        return TeamImportState(int(d.get('version',1)),list(d.get('screenshots',[])),candidates,dict(d.get('team_observations',{})))
    def save(self,state:TeamImportState)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'version':max(2,state.version),'screenshots':state.screenshots,'candidates':[asdict(x) for x in state.candidates],'team_observations':state.team_observations},indent=2)+'\n',encoding='utf-8'); tmp.replace(self.path)
    def stage_bytes(self,files:list[tuple[str,str,bytes]])->list[dict[str,Any]]:
        state=self.load(); self.upload_dir.mkdir(parents=True,exist_ok=True); added=[]
        for filename,ctype,data in files:
            if ctype not in IMAGE_TYPES or not data: raise ValueError('Only non-empty PNG, JPEG, WEBP, HEIC, or HEIF images are accepted')
            digest=hashlib.sha256(data).hexdigest(); ext=IMAGE_TYPES[ctype]; target=self.upload_dir/f'{digest[:20]}{ext}'
            target.write_bytes(data); row={'id':f'shot-{len(state.screenshots)+1}','filename':Path(filename).name,'content_type':ctype,'sha256':digest,'bytes':len(data),'path':str(target),'extraction_status':'STAGED — EXTRACTION PENDING'}
            state.screenshots.append(row); added.append(row)
        self.save(state); return added
    def set_candidates(self,candidates:list[Candidate],team_observations:dict[str,Any]|None=None)->None:
        state=self.load(); state.version=2; state.candidates=candidates; state.team_observations=team_observations or {}; self.save(state)

def _center(box): return ((box[0]+box[2])/2,(box[1]+box[3])/2)
def _inside(point,box): return box[0]<=point[0]<=box[2] and box[1]<=point[1]<=box[3]
def _slot_base(slot:str)->str: return re.sub(r"\d+$","",slot.upper())

def classify_view(observations:Iterable[OCRObservation])->tuple[str,float,list[str]]:
    text=' '.join(o.text.upper() for o in observations)
    anchors={
      'OFFENSE':('OFFENSE','QB','HB','WR','LT','LG','RG','RT'),
      'DEFENSE':('DEFENSE','FS','SS','CB','MIKE','WILL','SAM','LEDG','REDG'),
      'SPECIAL TEAMS':('SPECIAL TEAMS','KICK RETURN','PUNT RETURN','KOS'),
      'SPECIALISTS':('SPECIALISTS','SUBLB','RRE','RDT','RLE','SLCB','3DRB','PWHB'),
    }
    scored=[]
    for view,terms in anchors.items():
        hits=[t for t in terms if re.search(rf'(?<![A-Z0-9]){re.escape(t)}(?![A-Z0-9])',text)]
        score=(2 if terms[0] in hits else 0)+len(hits)
        scored.append((score,view,hits))
    scored.sort(reverse=True)
    best=scored[0]
    if best[0]<2 or (len(scored)>1 and best[0]==scored[1][0]): return 'UNKNOWN',0.0,['view:insufficient-or-tied-evidence']
    return best[1],min(1.0,best[0]/5),[f'view-anchor:{x}' for x in best[2]]

def associate_observations(observations:Iterable[OCRObservation],regions:Iterable[SlotRegion])->dict[str,list[OCRObservation]]:
    out={r.slot:[] for r in regions}
    for obs in observations:
        p=_center(obs.box)
        matches=[r for r in regions if _inside(p,r.box)]
        if matches:
            # smallest containing region wins if fixtures/layouts overlap.
            r=min(matches,key=lambda x:(x.box[2]-x.box[0])*(x.box[3]-x.box[1])); out[r.slot].append(obs)
    return out

def _parse_region(source:str,view:str,region:SlotRegion,observations:list[OCRObservation])->ObservedLineupCandidate|None:
    texts=[o.text.strip() for o in observations if o.text.strip()]
    if not texts: return None
    base=_slot_base(region.slot)
    ovr=None; position=None; name_parts=[]; ratings={}; other=[]
    for text in texts:
        upper=text.upper().strip()
        m=re.fullmatch(r'(?:OVR\s*)?(\d{2})',upper)
        if m and 40<=int(m.group(1))<=99 and ovr is None: ovr=int(m.group(1)); continue
        if upper in {'QB','HB','FB','WR','TE','LT','LG','C','RG','RT','FS','SS','CB','WILL','MIKE','SAM','LEDG','REDG','DT','K','P'}:
            position=upper; continue
        rm=re.fullmatch(r'(SPD|ACC|AGI|COD|MCV|ZCV|PRC)\s*(\d{2})',upper)
        if rm: ratings[rm.group(1)]=int(rm.group(2)); continue
        if upper==base or upper==region.slot.upper() or upper in {'OFFENSE','DEFENSE','SPECIAL TEAMS','SPECIALISTS'}: other.append(text); continue
        if re.search(r'[A-Za-z]',text) and not re.search(r'\b(AP|OVR|TEAM|CHEM|BONUS)\b',upper): name_parts.append(text)
        else: other.append(text)
    name=' '.join(name_parts).strip() or None
    if not name and ovr is None and not ratings: return None
    confs=[o.confidence for o in observations if o.confidence is not None]
    return ObservedLineupCandidate(source,view,region.slot,int(re.search(r'\d+$',region.slot).group()) if re.search(r'\d+$',region.slot) else 1,name,normalize_name(name) if name else None,ovr,position,other,ratings,region.box,sum(confs)/len(confs) if confs else None,[f'view:{view}',f'slot-region:{region.slot}','spatial-association'])

def extract_structured(source_screenshot:str,observations:list[OCRObservation],regions_by_view:dict[str,list[SlotRegion]],view:str|None=None)->tuple[str,list[ObservedLineupCandidate],dict[str,Any]]:
    classified,confidence,prov=classify_view(observations) if view is None else (view.upper(),1.0,['view:provided'])
    if classified not in VIEW_SLOTS or classified not in regions_by_view:
        return 'UNKNOWN',[],{'view':'UNKNOWN','view_confidence':0.0,'provenance':prov}
    grouped=associate_observations(observations,regions_by_view[classified]); found=[]
    for region in regions_by_view[classified]:
        candidate=_parse_region(source_screenshot,classified,region,grouped.get(region.slot,[]))
        if candidate: found.append(candidate)
    return classified,found,{'view':classified,'view_confidence':confidence,'provenance':prov}

def to_candidate(observed:ObservedLineupCandidate,candidate_id:str|None=None)->Candidate:
    return Candidate(candidate_id or f'{observed.source_screenshot}:{observed.slot}',observed.view,observed.slot,observed.raw_player_name,observed.displayed_ovr,observed.visible_position,match_status='UNMATCHED',observed_ratings=dict(observed.observed_ratings),provenance=list(observed.provenance),slot_index=observed.slot_index,bounding_region=observed.bounding_region)

def match_candidate(candidate:Candidate,cards:list[dict[str,Any]])->Candidate:
    candidate.canonical_card_id=None; candidate.match_status='UNMATCHED'; candidate.confidence=None
    if not candidate.player_name: return candidate
    name=normalize_name(candidate.player_name); pool=[c for c in cards if normalize_name(c.get('player_name') or '')==name]
    # Native/card position is evidence only when actually observed; lineup slot is not native position.
    if candidate.position: pool=[c for c in pool if (c.get('position') or '').upper()==candidate.position.upper()]
    if candidate.program: pool=[c for c in pool if (c.get('program') or '').casefold()==candidate.program.casefold()]
    if candidate.displayed_ovr is not None:
        exact=[c for c in pool if c.get('native_overall')==candidate.displayed_ovr]
        # Displayed OVR can be chemistry/EVO boosted. Exact OVR narrows only if it yields evidence.
        if exact: pool=exact
    if len(pool)==1:
        candidate.canonical_card_id=pool[0]['card_id']; candidate.match_status='MATCHED'; candidate.confidence=1.0
    elif len(pool)>1: candidate.match_status='AMBIGUOUS'
    return candidate

def ownership_key(candidate:Candidate)->str:
    """Specialist assignments dedupe ownership by canonical card, while retaining each assignment."""
    return candidate.canonical_card_id or candidate.id
