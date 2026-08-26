from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def test_op_x_026_product_acceptance_runner() -> None:
    completed = _run("python", "scripts/op_x_026_product_acceptance.py")
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    payload = json.loads((ROOT / "data/research/op_x_026/acceptance_results.json").read_text())
    assert payload["acceptance_pass"] is True
    assert all(payload["checks"].values())
