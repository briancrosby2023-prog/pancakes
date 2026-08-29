"""Team Setup recovery layer over the accepted product application."""
from __future__ import annotations
import argparse, csv, html, io, json, shutil, subprocess
from dataclasses import asdict
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from operation_pancake import product_app
from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterAssignment, RosterStore
from operation_pancake.team_import import (Candidate, OCRObservation, SlotRegion, SPECIALIST_SLOTS,
    TeamImportStore, VIEW_SLOTS, extract_structured, match_candidate, to_candidate)

# Conservative normalized regions. These encode stable Team Manager card ordering, not user players.
def _grid(slots):
    cols=5; rows=(len(slots)+cols-1)//cols; out=[]
    for i,slot in enumerate(slots):
        c=i%cols; r=i//cols; x=.02+c*.196; y=.18+r*(.78/max(1,rows))
        out.append(SlotRegion(slot,(x,y,min(.99,x+.185),min(.98,y+.78/max(1,rows)-.015))))
    return out
DEFAULT_REGIONS={view:_grid(slots) for view,slots in VIEW_SLOTS.items()}

def _multipart(headers,body):
    raw=(f'Content-Type: {headers.get("Content-Type","")}\r\nMIME-Version: 1.0\r\n\r\n').encode()+body
    msg=BytesParser(policy=default).parsebytes(raw); out=[]
    if not msg.is_multipart(): raise ValueError('multipart/form-data required')
    for part in msg.iter_parts():
        if part.get_content_disposition()!='form-data': continue
        name=part.get_param('name',header='content-disposition'); filename=part.get_filename()
        if filename: out.append((name,filename,part.get_content_type(),part.get_payload(decode=True) or b''))
    return out

def _ocr(path:Path)->list[OCRObservation]|None:
    """Return normalized word boxes; OCR quality is separate from layout extraction."""
    exe=shutil.which('tesseract')
    if not exe:return None
    try:
        p=subprocess.run([exe,str(path),'stdout','--psm','11','tsv'],capture_output=True,text=True,timeout=45,check=False)
        if p.returncode!=0:return None
        rows=list(csv.DictReader(io.StringIO(p.stdout),delimiter='\t')); words=[]
        page_w=max([int(r.get('width') or 0) for r in rows if r.get('level')=='1'] or [1]); page_h=max([int(r.get('height') or 0) for r in rows if r.get('level')=='1'] or [1])
        for r in rows:
            text=(r.get('text') or '').strip()
            if not text: continue
            x,y,w,h=(int(r.get(k) or 0) for k in ('left','top','width','height')); conf=float(r.get('conf') or -1)
            words.append(OCRObservation(text,(x/page_w,y/page_h,(x+w)/page_w,(y+h)/page_h),None if conf<0 else conf/100))
        return words
    except (OSError,subprocess.TimeoutExpired,ValueError): return None

def _extract(state_store:TeamImportStore,gm:GMProduct):
    state=state_store.load(); candidates=[]; observations={}
    for shot in state.screenshots:
        obs=_ocr(Path(shot['path']))
        if obs is None: shot['extraction_status']='OCR ENGINE UNAVAILABLE'; continue
        view,found,meta=extract_structured(shot['id'],obs,DEFAULT_REGIONS)
        shot['extraction_status']=f'OCR READ — {view}'; shot['view']=view; shot['view_confidence']=meta.get('view_confidence')
        observations[shot['id']]=meta
        for observed in found:
            c=to_candidate(observed,f'cand-{len(candidates)+1}')
            c=match_candidate(c,gm.population); candidates.append(c)
    state.version=2; state.candidates=candidates; state.team_observations={'screenshots':observations}; state_store.save(state); return state

def create_handler(root:Path,**kwargs):
    Base=product_app.create_handler(root,**kwargs); gm=GMProduct(root)
    roster_path=kwargs.get('roster_path') or root/'.operation_pancake/roster.json'; roster=RosterStore(roster_path,set(gm.cards)); imports=TeamImportStore(root/'.operation_pancake/team_import.json')
    class H(Base):
        def _team_page(self):
            state=imports.load(); rows=''
            for c in state.candidates:
                options=''.join(f'<option value="{html.escape(x["card_id"])}" {"selected" if x["card_id"]==c.canonical_card_id else ""}>{html.escape(x.get("player_name") or "")} — {html.escape(x.get("position") or "")} {x.get("native_overall") or ""}</option>' for x in gm.population if not c.player_name or (x.get('player_name') or '').casefold()==c.player_name.casefold())
                rows+=f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.slot)}</td><td>{html.escape(c.player_name or "UNKNOWN")}</td><td>{c.displayed_ovr or "UNKNOWN"}</td><td><select name="card__{c.id}"><option value="">UNMATCHED</option>{options}</select></td><td>{html.escape(c.match_status)}</td></tr>'
            shots=''.join(f'<li>{html.escape(x["filename"])} — {html.escape(x["extraction_status"])}</li>' for x in state.screenshots) or '<li>No images uploaded yet.</li>'
            body='<div class="hero"><h1>Team Setup</h1><p>Structure first. Identity second. Upload Team Manager views for spatial slot extraction and conservative canonical matching.</p></div>'
            body+='<div class="card"><form method="post" action="/team/upload" enctype="multipart/form-data"><input name="images" type="file" accept="image/png,image/jpeg,image/webp,image/heic,image/heif" multiple required><button>READ TEAM</button></form></div>'
            body+=f'<div class="card"><h2>Image evidence</h2><ul>{shots}</ul></div>'
            if state.candidates: body+=f'<form method="post" action="/team/confirm"><div class="card"><h2>Review Team</h2><table><tr><th>View</th><th>Slot</th><th>Player</th><th>Observed OVR</th><th>Canonical match</th><th>Status</th></tr>{rows}</table><button>IMPORT TEAM</button></div></form>'
            return product_app.page('Team Setup',body)
        def do_GET(self):
            p=urlparse(self.path).path
            if p=='/setup': self.send(self._team_page()); return
            if p=='/api/team-import': self.js({'state':asdict(imports.load())}); return
            super().do_GET()
        def do_POST(self):
            p=urlparse(self.path).path
            try:
                if p=='/team/upload':
                    body=self.rfile.read(int(self.headers.get('Content-Length','0'))); parts=_multipart(self.headers,body); files=[(fn,ct,data) for name,fn,ct,data in parts if name=='images']
                    if not files: raise ValueError('Choose at least one image')
                    imports.stage_bytes(files); _extract(imports,gm); self.redir('/setup'); return
                if p=='/team/confirm':
                    f=parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()); state=imports.load(); byslot={x.slot:x for x in roster.load()}
                    for c in state.candidates:
                        cid=f.get('card__'+c.id,[''])[0]; sl=c.slot.upper().strip()
                        if not cid or not sl: continue
                        card=gm.cards.get(cid)
                        if not card: continue
                        base=''.join(ch for ch in sl if not ch.isdigit()); kind='SPECIALIST' if base in SPECIALIST_SLOTS else 'ROSTER'
                        byslot[sl]=RosterAssignment(cid,card.get('position') or c.position or base,sl,True,True,observed_overall=c.displayed_ovr,observed_ratings=c.observed_ratings,evidence=c.provenance,assignment_kind=kind)
                    roster.save(list(byslot.values())); self.redir('/roster'); return
            except (ValueError,KeyError,json.JSONDecodeError) as e: self.send(product_app.page('Team Setup error',f'<div class="card warn">{html.escape(str(e))}</div>'),400); return
            super().do_POST()
    return H

def main():
    p=argparse.ArgumentParser(prog='operation-pancake-app'); p.add_argument('--root',type=Path,default=Path.cwd()); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8765); a=p.parse_args(); s=ThreadingHTTPServer((a.host,a.port),create_handler(a.root.resolve())); print(f'Operation Pancake: http://{a.host}:{a.port}'); s.serve_forever()
if __name__=='__main__': main()
