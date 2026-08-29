"""Team Setup recovery layer over the accepted product application."""
from __future__ import annotations
import argparse, html, json, shutil, subprocess, tempfile
from dataclasses import asdict
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from operation_pancake import product_app
from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterAssignment, RosterStore
from operation_pancake.team_import import Candidate, SPECIALIST_SLOTS, TeamImportStore, match_candidate

GROUP_SLOTS={
 'OFFENSE':['QB','HB','FB','WR','TE','LT','LG','C','RG','RT'],
 'DEFENSE':['FS','SS','CB','WILL','MIKE','SAM','LEDG','REDG','DT'],
 'SPECIAL TEAMS':['K','P','KR','PR','LS','KOS'],
 'SPECIALISTS':['3DRB','PWHB','SLWR','GAD','NT','SUBLB','RRE','RDT','RLE','SLCB']}

def _multipart(headers,body):
    raw=(f'Content-Type: {headers.get("Content-Type","")}\r\nMIME-Version: 1.0\r\n\r\n').encode()+body
    msg=BytesParser(policy=default).parsebytes(raw); out=[]
    if not msg.is_multipart(): raise ValueError('multipart/form-data required')
    for part in msg.iter_parts():
        if part.get_content_disposition()!='form-data': continue
        name=part.get_param('name',header='content-disposition'); filename=part.get_filename()
        if filename: out.append((name,filename,part.get_content_type(),part.get_payload(decode=True) or b''))
    return out

def _ocr(path:Path)->str|None:
    exe=shutil.which('tesseract')
    if not exe:return None
    try:
        p=subprocess.run([exe,str(path),'stdout','--psm','11'],capture_output=True,text=True,timeout=45,check=False)
        return p.stdout if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): return None

def _extract(state_store:TeamImportStore,gm:GMProduct):
    state=state_store.load(); candidates=[]
    for shot in state.screenshots:
        text=_ocr(Path(shot['path']))
        if text is None: shot['extraction_status']='OCR ENGINE UNAVAILABLE'; continue
        shot['extraction_status']='OCR READ'; folded=' '.join(text.casefold().split())
        hits=[]
        for card in gm.population:
            name=(card.get('player_name') or '').strip()
            if len(name)>=5 and name.casefold() in folded: hits.append(card)
        seen=set()
        for card in hits:
            key=card.get('player_name','').casefold()
            if key in seen: continue
            seen.add(key); versions=[x for x in hits if (x.get('player_name') or '').casefold()==key]
            c=Candidate(f'cand-{len(candidates)+1}','UNASSIGNED','UNKNOWN',card.get('player_name'),position=card.get('position'),provenance=[shot['id']])
            c=match_candidate(c,versions); candidates.append(c)
    state.candidates=candidates; state_store.save(state); return state

def create_handler(root:Path,**kwargs):
    Base=product_app.create_handler(root,**kwargs); gm=GMProduct(root)
    roster_path=kwargs.get('roster_path') or root/'.operation_pancake/roster.json'; roster=RosterStore(roster_path,set(gm.cards))
    imports=TeamImportStore(root/'.operation_pancake/team_import.json')
    class H(Base):
        def _team_page(self):
            state=imports.load(); rows=''
            for c in state.candidates:
                options=''.join(f'<option value="{html.escape(x["card_id"])}" {"selected" if x["card_id"]==c.canonical_card_id else ""}>{html.escape(x.get("player_name") or "")} — {html.escape(x.get("position") or "")} {x.get("native_overall") or ""} — {html.escape(x.get("program") or "")}</option>' for x in gm.population if not c.player_name or (x.get('player_name') or '').casefold()==c.player_name.casefold())
                rows+=f'<tr><td>{html.escape(c.group)}</td><td><input name="slot__{c.id}" value="{html.escape(c.slot)}"></td><td>{html.escape(c.player_name or "UNKNOWN")}</td><td>{c.displayed_ovr or "UNKNOWN"}</td><td><select name="card__{c.id}"><option value="">UNMATCHED</option>{options}</select></td><td>{html.escape(c.match_status)}</td><td>{html.escape(json.dumps(c.observed_ratings))}</td></tr>'
            shots=''.join(f'<li>{html.escape(x["filename"])} — {html.escape(x["extraction_status"])}</li>' for x in state.screenshots) or '<li>No images uploaded yet.</li>'
            body='''<div class="hero"><h1>Team Setup</h1><p>Drop Team Manager pictures. Pancake preserves the image evidence, reads what the local OCR capability can establish, matches canonical cards conservatively, and leaves uncertainty for review.</p></div>
<div class="card"><form method="post" action="/team/upload" enctype="multipart/form-data" style="display:block"><label for="teamfiles" style="display:block;border:2px dashed #79c8ff;border-radius:18px;padding:54px;text-align:center;font-size:24px;font-weight:800;cursor:pointer">DROP TEAM PICTURES HERE<br><span class="muted" style="font-size:14px">Offense · Defense · Special Teams · Specialists — or click to choose multiple</span></label><input id="teamfiles" name="images" type="file" accept="image/png,image/jpeg,image/webp,image/heic,image/heif" multiple required style="width:100%;margin-top:12px"><button style="margin-top:12px">READ TEAM</button></form></div>'''
            body+=f'<div class="card"><h2>Image evidence</h2><ul>{shots}</ul></div>'
            if state.candidates:
                body+=f'<form method="post" action="/team/confirm"><div class="card"><h2>Review Team</h2><table><tr><th>Group</th><th>Slot</th><th>Player</th><th>Displayed OVR</th><th>Canonical match</th><th>Status</th><th>Observed effective ratings</th></tr>{rows}</table><p class="muted">Canonical ratings remain canonical. Observed/effective ratings are stored separately and are not silently fed into base-rating production scoring.</p><button>IMPORT TEAM</button></div></form>'
            return product_app.page('Team Setup',body)
        def do_GET(self):
            if urlparse(self.path).path=='/setup': self.send(self._team_page()); return
            if urlparse(self.path).path=='/api/team-import': self.js({'state':asdict(imports.load())}); return
            super().do_GET()
        def do_POST(self):
            p=urlparse(self.path)
            try:
                if p.path=='/team/upload':
                    n=int(self.headers.get('Content-Length','0')); body=self.rfile.read(n); parts=_multipart(self.headers,body); files=[(fn,ct,data) for name,fn,ct,data in parts if name=='images']
                    if not files: raise ValueError('Choose at least one image')
                    imports.stage_bytes(files); _extract(imports,gm); self.redir('/setup'); return
                if p.path=='/team/confirm':
                    f=parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()); state=imports.load(); existing=roster.load(); byslot={x.slot:x for x in existing}
                    for c in state.candidates:
                        cid=f.get('card__'+c.id,[''])[0]; sl=f.get('slot__'+c.id,[c.slot])[0].upper().strip()
                        if not cid or not sl: continue
                        card=gm.cards.get(cid)
                        if not card: continue
                        kind='SPECIALIST' if sl in SPECIALIST_SLOTS else 'ROSTER'; row=RosterAssignment(cid,card.get('position') or c.position or sl,sl,True,True,observed_overall=c.displayed_ovr,observed_ratings=c.observed_ratings,evidence=c.provenance,assignment_kind=kind)
                        byslot[sl]=row
                    roster.save(list(byslot.values())); self.redir('/roster'); return
            except (ValueError,KeyError,json.JSONDecodeError) as e: self.send(product_app.page('Team Setup error',f'<div class="card warn">{html.escape(str(e))}</div>'),400); return
            super().do_POST()
    return H

def main():
    p=argparse.ArgumentParser(prog='operation-pancake-app'); p.add_argument('--root',type=Path,default=Path.cwd()); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8765); a=p.parse_args(); s=ThreadingHTTPServer((a.host,a.port),create_handler(a.root.resolve())); print(f'Operation Pancake: http://{a.host}:{a.port}'); s.serve_forever()
if __name__=='__main__': main()
