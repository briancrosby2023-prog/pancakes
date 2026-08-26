from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from operation_pancake.production.gm import GMProduct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_026"
OUT.mkdir(parents=True, exist_ok=True)


def run(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-50000:],
        "stderr": completed.stderr[-20000:],
    }


def parsed(result: dict[str, Any]) -> Any:
    try:
        return json.loads(result["stdout"])
    except (TypeError, json.JSONDecodeError):
        return None


def command(*parts: str) -> list[str]:
    return ["operation-pancake-gm", "--root", str(ROOT), *parts]


product = GMProduct(ROOT)
scoreable = [
    row
    for row in product.ranked
    if row.get("score") is not None and row.get("card_id") in product.cards
]
scoreable.sort(key=lambda row: (row.get("position") or "", row.get("position_rank") or 99999, row["card_id"]))

by_position: dict[str, list[dict[str, Any]]] = {}
for row in scoreable:
    by_position.setdefault(row.get("position") or "UNKNOWN", []).append(row)

compare_position, compare_rows = next(
    (position, rows) for position, rows in sorted(by_position.items()) if len(rows) >= 2
)
player_a, player_b = compare_rows[0], compare_rows[1]
card_a, card_b = player_a["card_id"], player_b["card_id"]

results: list[dict[str, Any]] = []
results.append(run("cli_help", ["operation-pancake", "--help"]))
results.append(run("gm_help", ["operation-pancake-gm", "--help"]))
results.append(run("player", command("player", "--card-id", card_a)))
results.append(run("compare", command("compare", card_a, card_b)))
results.append(run("compare_repeat", command("compare", card_a, card_b)))
results.append(run("roster", command("roster")))

price_file = OUT / "manual_prices.json"
price_file.write_text(
    json.dumps(
        [
            {"canonical_card_id": card_a, "observed_price": 25000},
            {"canonical_card_id": card_b, "observed_price": 40000},
        ],
        indent=2,
    ),
    encoding="utf-8",
)
results.append(run("price", command("price", str(price_file), "--observed-at", "2026-08-26T03:25:00-07:00")))
results.append(
    run(
        "compare_priced",
        command("compare", card_a, card_b, "--price", "40000", "--resale", "15000"),
    )
)

budget_candidates: list[dict[str, Any]] = []
for index, (position, rows) in enumerate(sorted(by_position.items())):
    if len(rows) < 2:
        continue
    best = rows[0]
    worst = rows[-1]
    gain = float(best.get("score") or 0) - float(worst.get("score") or 0)
    if gain <= 0:
        continue
    budget_candidates.append(
        {
            "card_id": best["card_id"],
            "current_card_id": worst["card_id"],
            "position": position,
            "net_cost": 20000 + 5000 * len(budget_candidates),
            "score_improvement": round(gain, 6),
            "protected": False,
        }
    )
    if len(budget_candidates) == 2:
        break
budget_file = OUT / "budget_candidates.json"
budget_file.write_text(json.dumps(budget_candidates, indent=2), encoding="utf-8")
results.append(run("budget", command("budget", str(budget_file), "60000")))
results.append(run("budget_repeat", command("budget", str(budget_file), "60000")))

role_result = run("role_board", command("role-board", "TE", "HYBRID", "--limit", "3"))
results.append(role_result)

knowledge = json.loads((ROOT / "data/research/op_x_040/knowledge_base.json").read_text(encoding="utf-8"))
claims = knowledge.get("claims", []) if isinstance(knowledge, dict) else []
knowledge_query = str(claims[0].get("claim_id")) if claims else "quarterback"
results.append(run("knowledge", command("ask-pancake", knowledge_query)))
results.append(run("knowledge_unknown", command("ask-pancake", "__OP_X_026_NO_MATCH__")))

results.append(run("bad_unknown_player", command("player", "--name", "__OP_X_026_UNKNOWN_PLAYER__")))
invalid_price_file = OUT / "invalid_prices.json"
invalid_price_file.write_text(
    json.dumps(
        [
            {"canonical_card_id": card_a, "observed_price": -1},
            {"canonical_card_id": card_b},
        ],
        indent=2,
    ),
    encoding="utf-8",
)
results.append(
    run(
        "bad_invalid_prices",
        command("price", str(invalid_price_file), "--observed-at", "2026-08-26T03:25:00-07:00"),
    )
)
results.append(run("git_diff_check", ["git", "diff", "--check"]))

# Exercise one stable non-scoreable record when the current population contains one.
non_scoreable = []
for card in product.population:
    lookup = product.lookup(card_id=card["card_id"])
    if lookup.get("status") not in {"SCORED", "RANKED", "OK"}:
        non_scoreable.append(card["card_id"])
        break
if non_scoreable:
    results.append(run("partial_or_unsupported", command("player", "--card-id", non_scoreable[0])))

payloads = {row["name"]: parsed(row) for row in results}
player_payload = payloads["player"] or {}
compare_payload = payloads["compare"] or {}
compare_repeat_payload = payloads["compare_repeat"] or {}
roster_payload = payloads["roster"]
price_payload = payloads["price"] or {}
priced_payload = payloads["compare_priced"] or {}
budget_payload = payloads["budget"] or {}
budget_repeat_payload = payloads["budget_repeat"] or {}
role_payload = payloads["role_board"] or {}
knowledge_payload = payloads["knowledge"] or {}
knowledge_unknown_payload = payloads["knowledge_unknown"] or {}
unknown_player_payload = payloads["bad_unknown_player"] or {}
invalid_price_payload = payloads["bad_invalid_prices"] or {}

selected = budget_payload.get("selected", []) if isinstance(budget_payload, dict) else []
selected_ids = [row.get("card_id") for row in selected if isinstance(row, dict)]
selected_positions = [row.get("position") for row in selected if isinstance(row, dict)]

checks = {
    "cli_help": next(row for row in results if row["name"] == "cli_help")["exit_code"] == 0,
    "gm_help": next(row for row in results if row["name"] == "gm_help")["exit_code"] == 0,
    "player": (
        next(row for row in results if row["name"] == "player")["exit_code"] == 0
        and isinstance(player_payload, dict)
        and player_payload.get("card", {}).get("card_id") == card_a
        and player_payload.get("status") != "UNRESOLVED IDENTITY"
    ),
    "compare": (
        next(row for row in results if row["name"] == "compare")["exit_code"] == 0
        and isinstance(compare_payload, dict)
        and compare_payload.get("status") == "OK"
        and compare_payload == compare_repeat_payload
    ),
    "roster": next(row for row in results if row["name"] == "roster")["exit_code"] == 0 and roster_payload is not None,
    "price_value": (
        next(row for row in results if row["name"] == "price")["exit_code"] == 0
        and len(price_payload.get("accepted", [])) == 2
        and not price_payload.get("rejected")
        and isinstance(priced_payload, dict)
        and priced_payload.get("status") == "OK"
    ),
    "budget": (
        next(row for row in results if row["name"] == "budget")["exit_code"] == 0
        and budget_payload == budget_repeat_payload
        and budget_payload.get("spent", 60001) <= 60000
        and len(selected_ids) == len(set(selected_ids))
        and len(selected_positions) == len(set(selected_positions))
    ),
    "bad_input": (
        unknown_player_payload.get("status") == "UNRESOLVED IDENTITY"
        and len(invalid_price_payload.get("accepted", [])) == 0
        and len(invalid_price_payload.get("rejected", [])) == 2
        and knowledge_unknown_payload.get("answer") == "UNKNOWN"
        and knowledge_unknown_payload.get("research_request_required") is True
    ),
    "role_intelligence": (
        next(row for row in results if row["name"] == "role_board")["exit_code"] == 0
        and role_payload.get("status") == "SUPPORTED"
        and bool(role_payload.get("rows"))
    ),
    "knowledge": (
        next(row for row in results if row["name"] == "knowledge")["exit_code"] == 0
        and knowledge_payload.get("answer") != "UNKNOWN"
        and knowledge_payload.get("status") is not None
        and knowledge_payload.get("confidence") is not None
        and knowledge_payload.get("sources") is not None
    ),
    "git_diff_check": next(row for row in results if row["name"] == "git_diff_check")["exit_code"] == 0,
}

summary = {
    "python": sys.version,
    "root": str(ROOT),
    "canonical_selection": {
        "position": compare_position,
        "player_a": product.cards[card_a],
        "player_b": product.cards[card_b],
    },
    "checks": checks,
    "acceptance_pass": all(checks.values()),
    "results": results,
}
(OUT / "acceptance_results.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
)
print(json.dumps(summary, indent=2, sort_keys=True))
if not summary["acceptance_pass"]:
    raise SystemExit(1)
