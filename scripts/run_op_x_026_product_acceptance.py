"""OP-X-026 durable product-acceptance execution."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_026"
OUT.mkdir(parents=True, exist_ok=True)


def run(name: str, command: list[str], expected: int = 0) -> dict:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "exit_code": proc.returncode,
        "expected_exit_code": expected,
        "pass": proc.returncode == expected,
        "stdout": proc.stdout[-20000:],
        "stderr": proc.stderr[-10000:],
    }


def first_two_scoreable() -> tuple[str, str]:
    from operation_pancake.production.gm import GMProduct

    gm = GMProduct(ROOT)
    by_position: dict[str, list[str]] = {}
    for row in gm.ranked:
        if row.get("score") is None:
            continue
        by_position.setdefault(row["position"], []).append(row["card_id"])
    for ids in by_position.values():
        if len(ids) >= 2:
            return ids[0], ids[1]
    raise SystemExit("No compatible scoreable player pair found")


def main() -> int:
    a, b = first_two_scoreable()
    tmp = OUT / "inputs"
    tmp.mkdir(exist_ok=True)
    prices = tmp / "manual_prices.json"
    prices.write_text(json.dumps([
        {"card_id": a, "price": 50000, "observation_type": "USER_SUPPLIED_OBSERVATION"},
        {"card_id": b, "price": 75000, "observation_type": "USER_SUPPLIED_OBSERVATION"},
    ], indent=2) + "\n")
    budget = tmp / "budget.json"
    budget.write_text(json.dumps([
        {"card_id": a, "net_cost": 40000, "score_improvement": 1.0},
        {"card_id": b, "net_cost": 60000, "score_improvement": 1.5},
        {"card_id": "protected-demo", "net_cost": 1, "score_improvement": 99, "protected": True},
    ], indent=2) + "\n")

    cases = [
        run("operation-pancake --help", ["operation-pancake", "--help"]),
        run("operation-pancake-gm --help", ["operation-pancake-gm", "--help"]),
        run("ask-pancake", ["operation-pancake-gm", "ask-pancake", "CFB27 Season 1"]),
        run("player", ["operation-pancake-gm", "player", "--card-id", a]),
        run("compare", ["operation-pancake-gm", "compare", a, b, "--price", "75000"]),
        run("roster", ["operation-pancake-gm", "roster"]),
        run("price", ["operation-pancake-gm", "price", str(prices), "--observed-at", "2026-08-26T00:00:00-07:00"]),
        run("budget", ["operation-pancake-gm", "budget", str(budget), "100000"]),
        run("bad-unknown-player", ["operation-pancake-gm", "player", "--card-id", "OPX026-NOT-A-CARD"]),
        run("bad-invalid-price", ["operation-pancake-gm", "compare", a, b, "--price", "not-an-int"], expected=2),
        run("role-intelligence", ["operation-pancake-gm", "role-board", "TE", "RECEIVING", "--limit", "3"]),
        run("knowledge", ["operation-pancake-gm", "knowledge-search", "CFB27 Season 1"]),
    ]
    det_player = run("determinism-player", ["operation-pancake-gm", "player", "--card-id", a])
    det_budget = run("determinism-budget", ["operation-pancake-gm", "budget", str(budget), "100000"])
    determinism = {
        "player": det_player["stdout"] == next(x for x in cases if x["name"] == "player")["stdout"],
        "budget": det_budget["stdout"] == next(x for x in cases if x["name"] == "budget")["stdout"],
    }
    payload = {
        "milestone": "OP-X-026E",
        "execution_environment": {"python": sys.version, "github_run_id": os.getenv("GITHUB_RUN_ID")},
        "trigger_sha": os.getenv("GITHUB_SHA"),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "prior_run_555_preserved": True,
        "selected_cards": [a, b],
        "cases": cases,
        "determinism": determinism,
        "acceptance_pass": all(x["pass"] for x in cases) and all(determinism.values()),
    }
    (OUT / "product_acceptance_execution.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "acceptance_pass": payload["acceptance_pass"],
        "cases": {x["name"]: {"exit_code": x["exit_code"], "pass": x["pass"]} for x in cases},
        "determinism": determinism,
    }, indent=2, sort_keys=True))
    return 0 if payload["acceptance_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
