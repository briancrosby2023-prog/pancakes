from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_026"
OUT.mkdir(parents=True, exist_ok=True)


def run(name: str, command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-10000:],
    }


commands = [
    ("cli_help", ["operation-pancake", "--help"]),
    ("gm_help", ["operation-pancake-gm", "--help"]),
    ("player", ["operation-pancake-gm", "--root", str(ROOT), "player", "--position", "TE", "--overall", "85"]),
    ("roster", ["operation-pancake-gm", "--root", str(ROOT), "roster"]),
    ("role_board", ["operation-pancake-gm", "--root", str(ROOT), "role-board", "TE", "VERTICAL", "--limit", "3"]),
    ("knowledge", ["operation-pancake-gm", "--root", str(ROOT), "ask-pancake", "quarterback"]),
]

results = [run(name, command) for name, command in commands]
player_result = next(row for row in results if row["name"] == "player")
card_ids: list[str] = []
try:
    parsed = json.loads(str(player_result["stdout"]))
    rows = parsed if isinstance(parsed, list) else parsed.get("matches", parsed.get("players", [])) if isinstance(parsed, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                cid = row.get("card_id") or row.get("id")
                if cid:
                    card_ids.append(str(cid))
except Exception:
    pass

if len(card_ids) >= 2:
    results.append(run("compare", ["operation-pancake-gm", "--root", str(ROOT), "compare", card_ids[0], card_ids[1]]))

results.append(run("bad_unknown_player", ["operation-pancake-gm", "--root", str(ROOT), "player", "--name", "__OP_X_026_UNKNOWN_PLAYER__"]))
summary = {
    "python": sys.version,
    "root": str(ROOT),
    "results": results,
    "all_required_successes": all(row["exit_code"] == 0 for row in results if row["name"] != "bad_unknown_player"),
    "bad_input_safe": next(row for row in results if row["name"] == "bad_unknown_player")["exit_code"] != 0,
}
(OUT / "acceptance_results.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
if not summary["all_required_successes"] or not summary["bad_input_safe"]:
    raise SystemExit(1)
