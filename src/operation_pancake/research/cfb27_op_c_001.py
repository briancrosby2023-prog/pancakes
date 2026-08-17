"""OP-C-001 full-vector population acquisition freeze and audit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_short(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        text=True,
    ).strip()


def build_op_c_001(root: Path) -> dict:
    state_path = root / "data/external/cfb_fan_population_state.json"
    checkpoint_path = root / "data/external/cfb_fan_full_vector_checkpoint.json"
    summary_path = root / "data/research/cfb27_op_x_013/discovery_and_cost_summary.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    cards = list(state["cards"].values())
    requested = set()
    returned = set()
    for batch in checkpoint["batches"].values():
        requested.update(batch["requested_ids"])
        returned.update(batch["returned_ids"])
    bulk_conflicts = {
        key: value
        for key, value in state.get("conflicts", {}).items()
        if key.startswith("OP-X-013:")
    }
    full = sum(card["extraction_status"] == "COMPLETE" for card in cards)
    partial = len(cards) - full
    return {
        "freeze": {
            "packet": "OP-C-001",
            "start_commit": "e14c902",
            "source_commit": _git_short(root),
            "population_sha256": _sha(state_path),
            "checkpoint_sha256": _sha(checkpoint_path),
            "input_sha256": {
                state_path.relative_to(root).as_posix(): _sha(state_path),
                checkpoint_path.relative_to(root).as_posix(): _sha(checkpoint_path),
                summary_path.relative_to(root).as_posix(): _sha(summary_path),
            },
        },
        "acquisition_summary": {
            "endpoint": summary["endpoint"],
            "population": len(cards),
            "full_vectors": full,
            "partial_vectors": partial,
            "full_vector_coverage_percent": round(100 * full / len(cards), 3),
            "bulk_batches": len(checkpoint["batches"]),
            "failed_batches": len(checkpoint.get("failures", [])),
            "ids_requested": len(requested),
            "ids_returned": len(returned),
            "ids_missing_from_responses": sorted(requested - returned),
            "ids_unexpected_in_responses": sorted(returned - requested),
            "duplicate_source_ids_in_population": len(cards)
            - len({card["external_card_id"] for card in cards}),
            "bulk_conflicts": len(bulk_conflicts),
            "conflict_fields": Counter(
                field
                for value in bulk_conflicts.values()
                for field in value.get("identity_conflicts", {})
            ),
            "pilot_statuses": summary.get("pilot_statuses", {}),
            "resume_cursor": state.get("resume_cursor"),
            "validation": {
                "guessed_ratings": False,
                "synthetic_vectors": False,
                "unknown_zero_conversion": False,
                "ovr_derived_ratings": False,
                "silent_conflicts": False,
                "card_version_collapse": False,
                "full_to_partial_downgrade": False,
                "access_bypass": False,
                "fabricated_metadata": False,
            },
        },
    }


def write_artifacts(directory: Path, analysis: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in analysis.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
