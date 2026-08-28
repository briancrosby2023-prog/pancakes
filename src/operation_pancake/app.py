"""Zero-dependency local web application for Operation Pancake GM intelligence."""
from __future__ import annotations

import argparse
import html
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterAssignment, RosterStore


def _page(title: str, body: str) -> bytes:
    doc = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;margin:0;background:#f6f4ef;color:#1d1d1b}}header,main{{max-width:1180px;margin:auto;padding:24px}}header{{display:flex;gap:24px;align-items:center}}a{{color:#684b00}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}input,select,button{{font:inherit;padding:9px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}.card{{background:white;padding:18px;border-radius:12px;margin:12px 0}}.muted{{color:#666}}.error{{background:#fee;padding:10px}}code{{white-space:pre-wrap}}</style></head><body><header><strong>🥞 Operation Pancake</strong><a href="/">Players</a><a href="/roster">Roster</a><a href="/compare">Compare</a></header><main>{body}</main></body></html>'''
    return doc.encode()


def _bool(form: dict[str, list[str]], name: str) -> bool:
    return form.get(name, [""])[0].lower() in {"1", "true", "on", "yes"}


def create_handler(root: Path, roster_path: Path | None = None):
    gm = GMProduct(root)
    store = RosterStore(roster_path or root / ".operation_pancake" / "roster.json", set(gm.cards))

    def enriched():
        rows = []
        for assignment in store.load():
            card = gm.cards.get(assignment.card_id, {})
            score = gm.rank_by_id.get(assignment.card_id, {})
            rows.append((assignment, card, score))
        return sorted(rows, key=lambda row: (row[0].position, row[0].slot))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8"):
            self.send_response(status); self.send_header("Content-Type", content_type); self.end_headers(); self.wfile.write(body)
        def _json(self, payload, status=200): self._send(json.dumps(payload, indent=2).encode(), status, "application/json")
        def _redirect(self, path: str): self.send_response(303); self.send_header("Location", path); self.end_headers()
        def _form(self):
            length = int(self.headers.get("Content-Length", "0")); return parse_qs(self.rfile.read(length).decode())
        def _assignment(self, form):
            card_id=form.get("card_id", [""])[0]; card=gm.cards.get(card_id)
            if not card: raise ValueError("Choose a valid canonical card")
            return RosterAssignment(card_id=card_id, position=form.get("position", [card.get("position") or ""])[0].upper(), slot=form.get("slot", [""])[0].upper(), starter=_bool(form,"starter"), owned=True, protected=_bool(form,"protected"), rerollable=_bool(form,"rerollable"), notes=form.get("notes", [""])[0])
        def do_GET(self):
            parsed=urlparse(self.path); q=parse_qs(parsed.query)
            if parsed.path == "/api/player":
                self._json(gm.lookup(card_id=q.get("card_id",[None])[0], player_name=q.get("name",[None])[0], position=q.get("position",[None])[0])); return
            if parsed.path == "/api/roster":
                self._json({"assignments":[asdict(a) | {"card":gm._identity(c), "pancake_score":s.get("score"), "position_rank":s.get("position_rank")} for a,c,s in enriched()]}); return
            if parsed.path == "/compare":
                left=q.get("current",[""])[0]; right=q.get("candidate",[""])[0]
                body='<h1>Compare players</h1><form><input name="current" placeholder="Current card ID" value="%s"><input name="candidate" placeholder="Candidate card ID" value="%s"><button>Compare</button></form>'%(html.escape(left),html.escape(right))
                if left and right: body += '<div class="card"><code>%s</code></div>' % html.escape(json.dumps(gm.compare(left,right),indent=2))
                self._send(_page("Compare",body)); return
            if parsed.path == "/roster":
                message=q.get("message",[""])[0]; error=q.get("error",[""])[0]
                body='<h1>Roster dashboard</h1><p>Owned cards persist locally and stay linked to the canonical CFB27 population.</p>'
                if message: body += '<div class="card">%s</div>'%html.escape(message)
                if error: body += '<div class="error">%s</div>'%html.escape(error)
                body += '<table><thead><tr><th>Position / slot</th><th>Player</th><th>OVR</th><th>Pancake</th><th>Pos rank</th><th>Depth</th><th>Status</th><th>Actions</th></tr></thead><tbody>'
                for a,c,s in enriched():
                    flags=', '.join(x for x,on in (("PROTECTED",a.protected),("REROLLABLE",a.rerollable)) if on) or '—'
                    edit='<form method="post" action="/roster/update"><input type="hidden" name="old_slot" value="%s"><input type="hidden" name="card_id" value="%s"><input name="position" size="5" value="%s"><input name="slot" size="7" value="%s"><label><input type="checkbox" name="starter" %s>Starter</label><label><input type="checkbox" name="protected" %s>Protected</label><label><input type="checkbox" name="rerollable" %s>Rerollable</label><input name="notes" value="%s" placeholder="Notes"><button>Save</button></form>'%(html.escape(a.slot),html.escape(a.card_id),html.escape(a.position),html.escape(a.slot),'checked' if a.starter else '','checked' if a.protected else '','checked' if a.rerollable else '',html.escape(a.notes))
                    actions='<a href="/compare?%s">Compare / find replacement</a><form method="post" action="/roster/delete"><input type="hidden" name="slot" value="%s"><button>Remove</button></form>'%(urlencode({"current":a.card_id}),html.escape(a.slot))
                    body += '<tr><td><strong>%s</strong><br>%s</td><td>%s<br><span class="muted">%s</span></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s%s</td></tr>'%(html.escape(a.position),html.escape(a.slot),html.escape(c.get("player_name") or a.card_id),html.escape(c.get("program") or ""),c.get("native_overall") or '—',s.get("score") if s.get("score") is not None else '—',s.get("position_rank") or '—','STARTER' if a.starter else 'BACKUP',html.escape(flags),edit,actions)
                body += '</tbody></table>'
                self._send(_page("Roster",body)); return
            if parsed.path != "/": self._send(_page("Not found","<h1>Not found</h1>"),404); return
            name=q.get("name",[""])[0]; position=q.get("position",[""])[0].upper(); rows=[]
            if name or position:
                needle=name.casefold(); candidates=[c for c in gm.population if (not needle or needle in (c.get("player_name") or "").casefold()) and (not position or c.get("position")==position)]
                candidates.sort(key=lambda c:(-(c.get("native_overall") or 0),c.get("player_name") or ""))
                for c in candidates[:100]:
                    s=gm.rank_by_id.get(c["card_id"],{}); add='<form method="post" action="/roster/add"><input type="hidden" name="card_id" value="%s"><input type="hidden" name="position" value="%s"><input name="slot" size="7" placeholder="%s1" required><label><input type="checkbox" name="starter" checked>Starter</label><label><input type="checkbox" name="protected">Protected</label><label><input type="checkbox" name="rerollable">Rerollable</label><button>Add</button></form>'%(html.escape(c["card_id"]),html.escape(c.get("position") or ""),html.escape(c.get("position") or ""))
                    rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'%(html.escape(c.get("player_name") or ""),html.escape(c.get("position") or ""),c.get("native_overall") or '—',html.escape(c.get("program") or ""),s.get("score") if s.get("score") is not None else '—',s.get("position_rank") or '—',add))
            body='<h1>Player intelligence</h1><p>Search the canonical CFB27 population and add owned cards directly to your roster.</p><form><input name="name" placeholder="Player name" value="%s"><input name="position" placeholder="Position (e.g. CB)" value="%s"><button>Search</button></form>'%(html.escape(name),html.escape(position))
            if rows: body += '<table><thead><tr><th>Player</th><th>Pos</th><th>OVR</th><th>Program</th><th>Pancake</th><th>Pos rank</th><th>Roster</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
            self._send(_page("Players",body))
        def do_POST(self):
            parsed=urlparse(self.path); form=self._form()
            try:
                if parsed.path == "/roster/add": store.add(self._assignment(form)); self._redirect("/roster?message=Player+added"); return
                if parsed.path == "/roster/update":
                    a=self._assignment(form); store.update(form.get("old_slot",[""])[0], position=a.position, slot=a.slot, starter=a.starter, owned=True, protected=a.protected, rerollable=a.rerollable, notes=a.notes); self._redirect("/roster?message=Assignment+updated"); return
                if parsed.path == "/roster/delete": store.remove(form.get("slot",[""])[0]); self._redirect("/roster?message=Player+removed"); return
                if parsed.path == "/api/roster": store.add(self._assignment(form)); self._json({"status":"CREATED"},201); return
                self._send(_page("Not found","<h1>Not found</h1>"),404)
            except (ValueError,KeyError,json.JSONDecodeError) as exc:
                if parsed.path.startswith("/api/"): self._json({"error":str(exc)},400)
                else: self._redirect("/roster?"+urlencode({"error":str(exc)}))
        def do_DELETE(self):
            parsed=urlparse(self.path); q=parse_qs(parsed.query)
            if parsed.path != "/api/roster": self._json({"error":"not found"},404); return
            try: removed=store.remove(q.get("slot",[""])[0]); self._json({"status":"DELETED","assignment":asdict(removed)})
            except KeyError: self._json({"error":"assignment not found"},404)
    return Handler


def main() -> None:
    parser=argparse.ArgumentParser(prog="operation-pancake-app"); parser.add_argument("--root",type=Path,default=Path.cwd()); parser.add_argument("--host",default="127.0.0.1"); parser.add_argument("--port",type=int,default=8765); args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),create_handler(args.root.resolve())); print(f"Operation Pancake: http://{args.host}:{args.port}"); server.serve_forever()

if __name__ == "__main__": main()
