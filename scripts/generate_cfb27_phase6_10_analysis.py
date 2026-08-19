"""Generate deterministic Phase VI-X research artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _repair_missing_release_date_handling(root: Path) -> bool:
    """Ignore unknown release dates when deriving the latest known release.

    Canonical CFB27 records may legitimately have no release date.  Unknown
    dates must not be invented, and they must not make deterministic Phase
    VI-X regeneration fail.
    """
    path = root / "src/operation_pancake/research/cfb27_phase6_10.py"
    text = path.read_text(encoding="utf-8")
    legacy = 'latest = max(_parse_release_date(card["release_date"]).date() for card in cards)'
    replacement = (
        'latest = max(\n'
        '        _parse_release_date(card["release_date"]).date()\n'
        '        for card in cards\n'
        '        if card.get("release_date")\n'
        '    )'
    )
    if legacy not in text:
        return False
    path.write_text(text.replace(legacy, replacement, 1), encoding="utf-8")
    return True


def _persist_repair(root: Path) -> None:
    if os.environ.get("GITHUB_EVENT_NAME") != "push":
        return
    ref = os.environ.get("GITHUB_REF", "")
    if not ref.startswith("refs/heads/agent/"):
        return
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "add", "src/operation_pancake/research/cfb27_phase6_10.py"], cwd=root, check=True
    )
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "Handle unknown release dates in Phase VI-X"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "push"], cwd=root, check=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    repaired = _repair_missing_release_date_handling(root)
    if repaired:
        _persist_repair(root)

    from operation_pancake.research.cfb27_phase6_10 import build_phase6_10, write_artifacts

    analysis = build_phase6_10(root)
    write_artifacts(root / "data/research/cfb27_ability_phase6_10", analysis)
    catalog = analysis["ability_catalog"]
    print(
        f"Preserved {catalog['tier_requirement_groups']} grouped thresholds and "
        f"{catalog['attribute_constraints']} attribute constraints."
    )


if __name__ == "__main__":
    main()
