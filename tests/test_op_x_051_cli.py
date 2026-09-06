import json
import sys

import pytest

import operation_pancake.gm_cli_entry as cli


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["operation-pancake-gm", *map(str, args)])
    cli.main()
    return json.loads(capsys.readouterr().out)


def test_roster_roles_reads_materialized_artifact(tmp_path, monkeypatch, capsys):
    out = tmp_path / "data/research/op_x_051"
    out.mkdir(parents=True)
    (out / "ROSTER_ROLE_MAP.json").write_text(
        json.dumps({"summary": {"entries": 24}}), encoding="utf-8"
    )
    payload = run_cli(monkeypatch, capsys, "--root", tmp_path, "roster-roles")
    assert payload["summary"]["entries"] == 24


def test_zero_coin_upgrades_preserves_unknown(tmp_path, monkeypatch, capsys):
    out = tmp_path / "data/research/op_x_051"
    out.mkdir(parents=True)
    expected = {"supported_count": 0, "status": "UNKNOWN — evidence absent"}
    (out / "ZERO_COIN_UPGRADES.json").write_text(
        json.dumps(expected), encoding="utf-8"
    )
    payload = run_cli(monkeypatch, capsys, "--root", tmp_path, "zero-coin-upgrades")
    assert payload == expected


def test_target_challenge_selects_exact_materialized_target(
    tmp_path, monkeypatch, capsys
):
    out = tmp_path / "data/research/op_x_051"
    out.mkdir(parents=True)
    targets = [{"status": "AMBIGUOUS CARD VERSION", "n": n} for n in range(1, 6)]
    (out / "TARGET_CHALLENGES.json").write_text(
        json.dumps({"targets": targets}), encoding="utf-8"
    )
    payload = run_cli(
        monkeypatch,
        capsys,
        "--root",
        tmp_path,
        "target-challenge",
        "--index",
        "3",
    )
    assert payload == targets[2]


def test_missing_materialized_artifact_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["operation-pancake-gm", "--root", str(tmp_path), "roster-roles"]
    )
    with pytest.raises(SystemExit, match="artifact not materialized"):
        cli.main()


def test_legacy_commands_delegate_to_existing_gm_cli(monkeypatch):
    called = []
    monkeypatch.setattr(
        sys, "argv", ["operation-pancake-gm", "player", "--name", "Example"]
    )
    monkeypatch.setattr(cli.gm_cli, "main", lambda: called.append(True))
    cli.main()
    assert called == [True]


def test_role_commands_dispatch_to_role_intelligence(tmp_path, monkeypatch, capsys):
    def fake_board(root, pos, role, limit):
        return {"kind": "board", "position": pos, "role": role, "limit": limit}

    monkeypatch.setattr(cli, "role_board", fake_board)
    payload = run_cli(
        monkeypatch,
        capsys,
        "--root",
        tmp_path,
        "role-board",
        "cb",
        "man",
        "--limit",
        "7",
    )
    assert payload == {"kind": "board", "position": "CB", "role": "MAN", "limit": 7}

    def fake_alternatives(root, cid, role, limit):
        return {
            "kind": "alternatives",
            "card_id": cid,
            "role": role,
            "limit": limit,
        }

    monkeypatch.setattr(cli, "role_alternatives", fake_alternatives)
    payload = run_cli(
        monkeypatch,
        capsys,
        "--root",
        tmp_path,
        "role-alternatives",
        "card-1",
        "zone",
        "--limit",
        "4",
    )
    assert payload == {
        "kind": "alternatives",
        "card_id": "card-1",
        "role": "ZONE",
        "limit": 4,
    }
