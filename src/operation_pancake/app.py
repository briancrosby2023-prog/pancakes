"""Zero-dependency local web application for Operation Pancake GM intelligence."""
from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from operation_pancake.production.gm import GMProduct


def _page(title: str, body: str) -> bytes:
    doc = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;margin:0;background:#f6f4ef;color:#1d1d1b}}header,main{{max-width:1100px;margin:auto;padding:24px}}header{{display:flex;gap:24px;align-items:center}}a{{color:#684b00}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}}input,select,button{{font:inherit;padding:9px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd}}.card{{background:white;padding:18px;border-radius:12px;margin:12px 0}}code{{white-space:pre-wrap}}</style></head><body><header><strong>🥞 Operation Pancake</strong><a href="/">Players</a><a href="/compare">Compare</a></header><main>{body}</main></body></html>'''
    return doc.encode()


def create_handler(root: Path):
    gm = GMProduct(root)
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, status: int = 200):
            self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            parsed = urlparse(self.path); q = parse_qs(parsed.query)
            if parsed.path == "/api/player":
                payload = gm.lookup(card_id=q.get("card_id", [None])[0], player_name=q.get("name", [None])[0], position=q.get("position", [None])[0])
                data = json.dumps(payload, indent=2).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data); return
            if parsed.path == "/compare":
                left=q.get("current", [""])[0]; right=q.get("candidate", [""])[0]
                form='<h1>Compare players</h1><form><input name="current" placeholder="Current card ID" value="%s"><input name="candidate" placeholder="Candidate card ID" value="%s"><button>Compare</button></form>'%(html.escape(left),html.escape(right))
                if left and right: form += '<div class="card"><code>%s</code></div>' % html.escape(json.dumps(gm.compare(left,right),indent=2))
                self._send(_page("Compare", form)); return
            if parsed.path != "/": self._send(_page("Not found","<h1>Not found</h1>"),404); return
            name=q.get("name", [""])[0]; position=q.get("position", [""])[0].upper(); rows=[]
            if name or position:
                needle=name.casefold(); candidates=[c for c in gm.population if (not needle or needle in (c.get("player_name") or "").casefold()) and (not position or c.get("position")==position)]
                candidates.sort(key=lambda c: (-(c.get("native_overall") or 0), c.get("player_name") or ""))
                for c in candidates[:100]:
                    s=gm.rank_by_id.get(c["card_id"],{}); rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'%tuple(html.escape(str(x if x is not None else "—")) for x in (c.get("player_name"),c.get("position"),c.get("native_overall"),c.get("program"),s.get("score"),s.get("position_rank"))))
            body='<h1>Player intelligence</h1><p>Search the canonical CFB27 population and see Pancake model score/rank.</p><form><input name="name" placeholder="Player name" value="%s"><input name="position" placeholder="Position (e.g. CB)" value="%s"><button>Search</button></form>'%(html.escape(name),html.escape(position))
            if rows: body += '<table><thead><tr><th>Player</th><th>Pos</th><th>OVR</th><th>Program</th><th>Pancake</th><th>Pos rank</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
            self._send(_page("Players",body))
    return Handler


def main() -> None:
    parser=argparse.ArgumentParser(prog="operation-pancake-app"); parser.add_argument("--root",type=Path,default=Path.cwd()); parser.add_argument("--host",default="127.0.0.1"); parser.add_argument("--port",type=int,default=8765); args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),create_handler(args.root.resolve())); print(f"Operation Pancake: http://{args.host}:{args.port}"); server.serve_forever()

if __name__ == "__main__": main()
