"""Team Manager screenshot evidence, conservative matching, and import state."""
from __future__ import annotations
import hashlib, json, re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

IMAGE_TYPES={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/heic":".heic","image/heif":".heif"}
SPECIALIST_SLOTS={"3DRB","PWHB","SLWR","GAD","NT","SUBLB","RRE","RDT","RLE","SLCB","KR","PR","LS","KOS"}

def normalize_name(value:str)->str: return re.sub(r"[^a-z0-9]","",value.casefold())

@dataclass
class Candidate:
    id:str; group:str; slot:str; player_name:str|None=None; displayed_ovr:int|None=None
    position:str|None=None; program:str|None=None; canonical_card_id:str|None=None
    match_status:str="UNMATCHED"; confidence:float|None=None
    observed_ratings:dict[str,int]=field(default_factory=dict); provenance:list[str]=field(default_factory=list)

@dataclass
class TeamImportState:
    version:int=1; screenshots:list[dict[str,Any]]=field(default_factory=list)
    candidates:list[Candidate]=field(default_factory=list); team_observations:dict[str,Any]=field(default_factory=dict)

class TeamImportStore:
    def __init__(self,path:Path,upload_dir:Path|None=None): self.path=path; self.upload_dir=upload_dir or path.parent/'team_uploads'
    def load(self)->TeamImportState:
        if not self.path.exists(): return TeamImportState()
        d=json.loads(self.path.read_text(encoding='utf-8'))
        return TeamImportState(int(d.get('version',1)),list(d.get('screenshots',[])),[Candidate(**x) for x in d.get('candidates',[])],dict(d.get('team_observations',{})))
    def save(self,state:TeamImportState)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'version':state.version,'screenshots':state.screenshots,'candidates':[asdict(x) for x in state.candidates],'team_observations':state.team_observations},indent=2)+'\n',encoding='utf-8'); tmp.replace(self.path)
    def stage_bytes(self,files:list[tuple[str,str,bytes]])->list[dict[str,Any]]:
        state=self.load(); self.upload_dir.mkdir(parents=True,exist_ok=True); added=[]
        for filename,ctype,data in files:
            if ctype not in IMAGE_TYPES or not data: raise ValueError('Only non-empty PNG, JPEG, WEBP, HEIC, or HEIF images are accepted')
            digest=hashlib.sha256(data).hexdigest(); ext=IMAGE_TYPES[ctype]; target=self.upload_dir/f'{digest[:20]}{ext}'
            target.write_bytes(data); row={'id':f'shot-{len(state.screenshots)+1}','filename':Path(filename).name,'content_type':ctype,'sha256':digest,'bytes':len(data),'path':str(target),'extraction_status':'STAGED — EXTRACTION PENDING'}
            state.screenshots.append(row); added.append(row)
        self.save(state); return added
    def set_candidates(self,candidates:list[Candidate],team_observations:dict[str,Any]|None=None)->None:
        state=self.load(); state.candidates=candidates; state.team_observations=team_observations or {}; self.save(state)

def match_candidate(candidate:Candidate,cards:list[dict[str,Any]])->Candidate:
    if not candidate.player_name: return candidate
    name=normalize_name(candidate.player_name); pool=[c for c in cards if normalize_name(c.get('player_name') or '')==name]
    if candidate.position: pool=[c for c in pool if (c.get('position') or '').upper()==candidate.position.upper()]
    if candidate.program: pool=[c for c in pool if (c.get('program') or '').casefold()==candidate.program.casefold()]
    if candidate.displayed_ovr is not None:
        exact=[c for c in pool if c.get('native_overall')==candidate.displayed_ovr]
        if exact: pool=exact
    if len(pool)==1:
        candidate.canonical_card_id=pool[0]['card_id']; candidate.match_status='MATCHED'; candidate.confidence=1.0
    elif len(pool)>1:
        candidate.match_status='AMBIGUOUS'; candidate.confidence=None
    return candidate
