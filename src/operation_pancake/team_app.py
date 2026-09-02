"""Team Setup recovery layer over the accepted product application."""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import shutil
import subprocess
from dataclasses import asdict
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from operation_pancake import product_app
from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterAssignment, RosterStore
from operation_pancake.team_import import Candidate, IMAGE_TYPES, OCRObservation, SPECIALIST_SLOTS, SlotRegion, TeamImportStore, VIEW_SLOTS, extract_structured, match_candidate, to_candidate

TEAM_SETUP_BUILD = "DROP-ZONE-PATCH-3"


def _grid(slots):
    cols = 5
    rows = (len(slots) + cols - 1) // cols
    out = []
    for i, slot in enumerate(slots):
        c, r = i % cols, i // cols
        x, y = 0.02 + c * 0.196, 0.18 + r * (0.78 / max(1, rows))
        out.append(SlotRegion(slot, (x, y, min(0.99, x + 0.185), min(0.98, y + 0.78 / max(1, rows) - 0.015))))
    return out


DEFAULT_REGIONS = {view: _grid(slots) for view, slots in VIEW_SLOTS.items()}


def _multipart(headers, body):
    raw = (f'Content-Type: {headers.get("Content-Type", "")}\r\nMIME-Version: 1.0\r\n\r\n').encode() + body
    msg = BytesParser(policy=default).parsebytes(raw)
    out = []
    if not msg.is_multipart():
        raise ValueError("multipart/form-data required")
    for part in msg.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name, filename = part.get_param("name", header="content-disposition"), part.get_filename()
        if filename:
            out.append((name, filename, part.get_content_type(), part.get_payload(decode=True) or b""))
    return out


def _upload_surface():
    accept = ",".join(IMAGE_TYPES)
    return f'''<div class="card" id="team-runtime-card" style="padding:10px 16px">
<strong id="team-build">TEAM SETUP BUILD: {TEAM_SETUP_BUILD}</strong><br>
<span id="team-drop-status" role="status" aria-live="polite">DROP HANDLER: NOT READY</span>
</div>
<div class="card" id="team-upload-card">
<form id="team-upload-form" method="post" action="/team/upload" enctype="multipart/form-data" style="display:block">
<input id="teamfiles" name="images" type="file" accept="{accept}" multiple hidden>
<div id="team-dropzone" role="button" tabindex="0" aria-controls="teamfiles" style="display:block;border:2px dashed #79c8ff;border-radius:18px;padding:42px 24px;text-align:center;cursor:pointer">
<strong style="font-size:24px">DROP TEAM PICTURES HERE</strong><br><span class="muted">OFFENSE · DEFENSE · SPECIAL TEAMS · SPECIALISTS</span><br><span>or click to choose all four</span>
</div>
<div id="team-errors" class="error" role="alert" hidden></div>
<div id="team-selection" style="margin-top:16px" hidden><strong id="team-count">0 TEAM SCREENSHOTS READY</strong><ul id="team-file-list"></ul><button id="team-add" type="button">ADD ANOTHER IMAGE</button></div>
<button id="team-analyze" type="submit" disabled style="margin-top:16px;font-weight:800">ANALYZE MY TEAM</button>
<div id="team-processing" role="status" aria-live="polite" style="margin-top:12px;font-weight:700"></div>
</form></div>
<script>
(()=>{{
 function initTeamDrop(){{
  const status=document.getElementById('team-drop-status'); const setStatus=text=>{{if(status)status.textContent=text;}};
  try{{
   setStatus('DROP HANDLER: INITIALIZING');
   const form=document.getElementById('team-upload-form'), input=document.getElementById('teamfiles'), zone=document.getElementById('team-dropzone');
   const selection=document.getElementById('team-selection'), count=document.getElementById('team-count'), list=document.getElementById('team-file-list');
   const add=document.getElementById('team-add'), analyze=document.getElementById('team-analyze'), processing=document.getElementById('team-processing'), errors=document.getElementById('team-errors');
   const required={{form,input,zone,selection,count,list,add,analyze,processing,errors}}; const missing=Object.entries(required).filter(([,value])=>!value).map(([name])=>name);
   if(missing.length){{setStatus(`DROP HANDLER: ERROR — missing ${{missing.join(', ')}}`);return;}} if(zone.dataset.dropReady==='1'){{setStatus('DROP HANDLER: READY');return;}}
   const accepted=new Set({json.dumps(list(IMAGE_TYPES))}); let staged=[]; let dragDepth=0; const key=f=>`${{f.name}}:${{f.size}}:${{f.lastModified}}`; const isFileDrag=e=>!!(e.dataTransfer&&Array.from(e.dataTransfer.types||[]).includes('Files'));
   function syncInput(){{const dt=new DataTransfer(); staged.forEach(f=>dt.items.add(f)); input.files=dt.files;}}
   function render(){{syncInput(); selection.hidden=staged.length===0; analyze.disabled=staged.length===0; count.textContent=`${{staged.length}} TEAM SCREENSHOT${{staged.length===1?'':'S'}} READY`; list.replaceChildren(); staged.forEach((f,i)=>{{const li=document.createElement('li'); li.append(document.createTextNode(f.name+' ')); const b=document.createElement('button'); b.type='button'; b.textContent='REMOVE'; b.dataset.index=String(i); b.addEventListener('click',()=>{{staged.splice(i,1); render();}}); li.append(b); list.append(li);}});}}
   function addFiles(files){{const bad=[]; const seen=new Set(staged.map(key)); Array.from(files||[]).forEach(f=>{{if(!accepted.has(f.type)) bad.push(f.name); else if(!seen.has(key(f))){{staged.push(f); seen.add(key(f));}}}}); if(bad.length){{errors.hidden=false; errors.textContent=`Unsupported image file${{bad.length===1?'':'s'}}: ${{bad.join(', ')}}. Use PNG, JPEG, WEBP, HEIC, or HEIF.`;}} else {{errors.hidden=true; errors.textContent='';}} render();}}
   function pageGuard(e){{if(!isFileDrag(e)) return; e.preventDefault(); if(!zone.contains(e.target)){{e.stopPropagation(); if(e.dataTransfer)e.dataTransfer.dropEffect='none';}}}}
   ['dragenter','dragover','drop'].forEach(type=>window.addEventListener(type,pageGuard,{{capture:true,passive:false}})); ['dragenter','dragover','dragleave','drop'].forEach(type=>zone.addEventListener(type,e=>{{if(!isFileDrag(e))return; e.preventDefault(); e.stopPropagation();}},{{passive:false}}));
   zone.addEventListener('dragenter',e=>{{if(!isFileDrag(e))return; dragDepth++; zone.style.borderStyle='solid'; setStatus('DROP HANDLER: FILE DRAG');}}); zone.addEventListener('dragover',e=>{{if(isFileDrag(e)&&e.dataTransfer)e.dataTransfer.dropEffect='copy';}}); zone.addEventListener('dragleave',e=>{{if(!isFileDrag(e))return; dragDepth=Math.max(0,dragDepth-1); if(!dragDepth){{zone.style.borderStyle='dashed'; setStatus('DROP HANDLER: READY');}}}}); zone.addEventListener('drop',e=>{{if(!isFileDrag(e))return; dragDepth=0; zone.style.borderStyle='dashed'; addFiles(e.dataTransfer.files); setStatus('DROP HANDLER: READY');}});
   zone.addEventListener('click',()=>input.click()); zone.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault(); input.click();}}}}); add.addEventListener('click',()=>input.click()); input.addEventListener('change',()=>addFiles(input.files)); form.addEventListener('submit',e=>{{if(!staged.length){{e.preventDefault(); return;}} analyze.disabled=true; add.disabled=true; zone.setAttribute('aria-disabled','true'); processing.textContent=`ANALYZING ${{staged.length}} TEAM SCREENSHOT${{staged.length===1?'':'S'}}...`;}});
   zone.dataset.dropReady='1'; setStatus('DROP HANDLER: READY');
  }}catch(error){{setStatus(`DROP HANDLER: ERROR — ${{error&&error.message?error.message:'initialization failed'}}`);}}
 }} if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initTeamDrop,{{once:true}}); else initTeamDrop();
}})();
</script>'''


def _ocr(path: Path) -> list[OCRObservation] | None:
    exe = shutil.which("tesseract")
    if not exe:
        return None
    try:
        p = subprocess.run([exe, str(path), "stdout", "--psm", "11", "tsv"], capture_output=True, text=True, timeout=45, check=False)
        if p.returncode != 0:
            return None
        rows = list(csv.DictReader(io.StringIO(p.stdout), delimiter="\t")); words = []
        page_w = max([int(r.get("width") or 0) for r in rows if r.get("level") == "1"] or [1]); page_h = max([int(r.get("height") or 0) for r in rows if r.get("level") == "1"] or [1])
        for r in rows:
            text = (r.get("text") or "").strip()
            if not text: continue
            x, y, w, h = (int(r.get(k) or 0) for k in ("left", "top", "width", "height")); conf = float(r.get("conf") or -1)
            words.append(OCRObservation(text, (x / page_w, y / page_h, (x + w) / page_w, (y + h) / page_h), None if conf < 0 else conf / 100))
        return words
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _extract(state_store: TeamImportStore, gm: GMProduct):
    state = state_store.load(); candidates = []; observations = {}
    for shot in state.screenshots:
        obs = _ocr(Path(shot["path"]))
        if obs is None:
            shot["extraction_status"] = "OCR ENGINE UNAVAILABLE"; continue
        view, found, meta = extract_structured(shot["id"], obs, DEFAULT_REGIONS); shot["extraction_status"] = f"OCR READ — {view}"; shot["view"] = view; shot["view_confidence"] = meta.get("view_confidence"); observations[shot["id"]] = meta
        for observed in found:
            c = to_candidate(observed, f"cand-{len(candidates) + 1}"); candidates.append(match_candidate(c, gm.population))
    state.version = 2; state.candidates = candidates; state.team_observations = {"screenshots": observations}; state_store.save(state); return state


def create_handler(root: Path, **kwargs):
    Base = product_app.create_handler(root, **kwargs); gm = GMProduct(root)
    roster_path = kwargs.get("roster_path") or root / ".operation_pancake/roster.json"; roster = RosterStore(roster_path, set(gm.cards))
    team_import_path = kwargs.get("team_import_path") or root / ".operation_pancake/team_import.json"
    imports = TeamImportStore(team_import_path)

    class H(Base):
        def send(self, data, status=200, ct="text/html; charset=utf-8"):
            self.send_response(status); self.send_header("Content-Type", ct)
            if urlparse(self.path).path == "/setup" and ct.startswith("text/html"):
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"); self.send_header("Pragma", "no-cache"); self.send_header("Expires", "0")
            self.end_headers(); self.wfile.write(data)

        def _team_page(self):
            state = imports.load(); rows = ""
            for c in state.candidates:
                options = "".join(f'<option value="{html.escape(x["card_id"])}" {"selected" if x["card_id"] == c.canonical_card_id else ""}>{html.escape(x.get("player_name") or "")} — {html.escape(x.get("position") or "")} {x.get("native_overall") or ""}</option>' for x in gm.population if not c.player_name or (x.get("player_name") or "").casefold() == c.player_name.casefold())
                rows += f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.slot)}</td><td>{html.escape(c.player_name or "UNKNOWN")}</td><td>{c.displayed_ovr or "UNKNOWN"}</td><td><select name="card__{c.id}"><option value="">UNMATCHED</option>{options}</select></td><td>{html.escape(c.match_status)}</td></tr>'
            shots = "".join(f'<li>{html.escape(x["filename"])} — {html.escape(x["extraction_status"])}</li>' for x in state.screenshots) or "<li>No images uploaded yet.</li>"
            body = '<div class="hero"><h1>Team Setup</h1><p>Give Pancake your Team Manager screenshots. Add all four together, then analyze once.</p></div>' + _upload_surface() + f'<div class="card"><h2>Image evidence</h2><ul>{shots}</ul></div>'
            if state.candidates: body += f'<form method="post" action="/team/confirm"><div class="card"><h2>Review Team</h2><table><tr><th>View</th><th>Slot</th><th>Player</th><th>Observed OVR</th><th>Canonical match</th><th>Status</th></tr>{rows}</table><button>IMPORT TEAM</button></div></form>'
            return product_app.page("Team Setup", body)

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/setup": self.send(self._team_page()); return
            if p == "/api/team-import": self.js({"state": asdict(imports.load())}); return
            super().do_GET()

        def do_POST(self):
            p = urlparse(self.path).path
            try:
                if p == "/team/upload":
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0"))); parts = _multipart(self.headers, body); files = [(fn, ct, data) for name, fn, ct, data in parts if name == "images"]
                    if not files: raise ValueError("Choose at least one image")
                    bad = [fn for fn, ct, data in files if ct not in IMAGE_TYPES or not data]
                    if bad: raise ValueError("Unsupported or empty image file: " + ", ".join(Path(x).name for x in bad) + ". Use PNG, JPEG, WEBP, HEIC, or HEIF.")
                    imports.stage_bytes(files); _extract(imports, gm); self.redir("/setup"); return
                if p == "/team/confirm":
                    f = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()); state = imports.load(); byslot = {x.slot: x for x in roster.load()}
                    for c in state.candidates:
                        cid = f.get("card__" + c.id, [""])[0]; sl = c.slot.upper().strip()
                        if not cid or not sl: continue
                        card = gm.cards.get(cid)
                        if not card: continue
                        base = "".join(ch for ch in sl if not ch.isdigit()); kind = "SPECIALIST" if base in SPECIALIST_SLOTS else "ROSTER"; byslot[sl] = RosterAssignment(cid, card.get("position") or c.position or base, sl, True, True, observed_overall=c.displayed_ovr, observed_ratings=c.observed_ratings, evidence=c.provenance, assignment_kind=kind)
                    roster.save(list(byslot.values())); self.redir("/roster"); return
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                self.send(product_app.page("Team Setup error", f'<div class="card warn">{html.escape(str(e))}</div>'), 400); return
            super().do_POST()

    return H


def main():
    p = argparse.ArgumentParser(prog="operation-pancake-app"); p.add_argument("--root", type=Path, default=Path.cwd()); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765); a = p.parse_args()
    s = ThreadingHTTPServer((a.host, a.port), create_handler(a.root.resolve())); print(f"Operation Pancake: http://{a.host}:{a.port}"); print(f"Team Setup build: {TEAM_SETUP_BUILD}"); print(f"Team Setup module: {Path(__file__).resolve()}"); s.serve_forever()


if __name__ == "__main__": main()
