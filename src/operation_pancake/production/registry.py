"""Machine-readable registry assembled from the frozen research specifications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPEC_PATHS = {
    "WR": "data/research/op_x_018/frozen_wr_scoring_spec.json",
    "CB": "data/research/op_x_018/cb/frozen_cb_scoring_spec.json",
    "S": "data/research/op_x_019/safety/frozen_safety_scoring_spec.json",
    "EDGE": "data/research/op_x_019/edge/frozen_edge_scoring_spec.json",
    "MIKE": "data/research/op_x_019/mike/frozen_mike_scoring_spec.json",
    "DT": "data/research/op_x_019/dt/frozen_dt_scoring_spec.json",
    "SAM": "data/research/op_x_019/sam/frozen_sam_scoring_spec.json",
    "RB": "data/research/op_x_020/rb/frozen_rb_scoring_spec.json",
    "FB": "data/research/op_x_020/fb/frozen_fb_scoring_spec.json",
    "OT": "data/research/op_x_020/tackle/frozen_tackle_scoring_spec.json",
    "G": "data/research/op_x_020/guard/frozen_guard_scoring_spec.json",
    "KP": "data/research/op_x_020/kp/frozen_kp_scoring_spec.json",
}

POSITION_ALIASES = {
    "HB": "RB",
    "FS": "S",
    "SS": "S",
    "LE": "EDGE",
    "RE": "EDGE",
    "MLB": "MIKE",
    "WILL": "SAM",
    "LT": "OT",
    "RT": "OT",
    "LG": "G",
    "RG": "G",
    "K": "KP",
    "P": "KP",
}


def _read(root: Path, relative: str) -> dict[str, Any]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def build_model_registry(root: Path) -> dict[str, Any]:
    """Return the complete immutable model and routing registry."""
    coverage_path = "data/research/op_x_017/coverage_matrix.json"
    coverage = _read(root, coverage_path)
    validation = {(row["model"], row["version"]): row for row in coverage["models"]}
    models: list[dict[str, Any]] = []
    routes: dict[str, dict[str, Any]] = {}

    for family, path in SPEC_PATHS.items():
        spec = _read(root, path)
        model = spec["model"]
        model_id, version = model["id"], model["version"]
        models.append(
            {
                "id": model_id,
                "version": version,
                "family": family,
                "model_type": "position/archetype ranking",
                "capabilities": {
                    "ranking": True,
                    "player_comparison": True,
                    "displayed_overall_prediction": False,
                },
                "production": True,
                "locked": bool(validation.get((model_id, version), {}).get("locked", True)),
                "formula": model["formula"],
                "profiles": spec["weights"],
                "denominators": spec.get(
                    "source_weight_totals",
                    {key: sum(weights.values()) for key, weights in spec["weights"].items()},
                ),
                "missing_attribute_rule": "omit unavailable terms and renormalize",
                "validation": validation.get((model_id, version), {}),
                "provenance": spec.get("provenance", {}),
                "freeze_commit": spec.get("freeze", {}).get("repository_head"),
                "evidence_paths": [path, coverage_path],
                "limitations": ["ranking score only; not a displayed-overall prediction"],
            }
        )
        routes[family] = {
            archetype: {
                "model_id": model_id,
                "version": version,
                "profile": rule["model_archetype"],
                "confidence": rule["status"],
                "basis": rule["basis"],
            }
            for archetype, rule in spec["archetype_mappings"]["CFB26"].items()
        }

    center_path = "data/research/center_exact_validation/madden_center_frozen_model.json"
    center = _read(root, center_path)
    center_weights = center.get("weights") or center.get("model", {}).get("weights")
    center_model = center.get("model", center)
    center_id = center_model.get("id", "C-M19-RANK-001")
    center_version = center_model.get("version", "v1.0")
    models.append(
        {
            "id": center_id,
            "version": center_version,
            "family": "C",
            "model_type": "position ranking",
            "capabilities": {
                "ranking": True,
                "player_comparison": True,
                "displayed_overall_prediction": False,
            },
            "production": True,
            "locked": True,
            "formula": "weighted mean of exact Madden 19 center weights",
            "profiles": {"Center": center_weights},
            "denominators": {"Center": sum(center_weights.values())},
            "missing_attribute_rule": "all weighted attributes required",
            "validation": validation.get((center_id, center_version), {}),
            "provenance": center.get("provenance", {}),
            "freeze_commit": None,
            "evidence_paths": [center_path, coverage_path],
            "limitations": ["center ranking only; exact displayed overall is out of scope"],
        }
    )
    routes["C"] = {
        "*": {
            "model_id": center_id,
            "version": center_version,
            "profile": "Center",
            "confidence": "EXACT_POSITION",
            "basis": "position-shared center ranking model",
        }
    }

    qb_id, qb_version = "QB-SHARED-001", "v1.0"
    qb_weights = {
        "SPD": 3,
        "ACC": 1,
        "AGI": 8,
        "AWR": 10,
        "THP": 18,
        "SAC": 12,
        "MAC": 12,
        "DAC": 18,
        "RUN": 1,
        "TUP": 9,
        "PAC": 4,
        "BSK": 4,
    }
    qb_path = "scripts/op_x_017_historical_qb_validation.py"
    models.append(
        {
            "id": qb_id,
            "version": qb_version,
            "family": "QB",
            "model_type": "shared position ranking",
            "capabilities": {
                "ranking": True,
                "player_comparison": True,
                "displayed_overall_prediction": False,
            },
            "production": True,
            "locked": True,
            "formula": "weighted mean of frozen shared QB vector",
            "profiles": {"Shared": qb_weights},
            "denominators": {"Shared": 100},
            "missing_attribute_rule": "all weighted attributes required",
            "validation": validation.get((qb_id, qb_version), {}),
            "provenance": {"source": "frozen OP-X-017 QB validation"},
            "freeze_commit": None,
            "evidence_paths": [qb_path, coverage_path],
            "limitations": ["Pure Runner is unsupported", "ranking score only"],
        }
    )
    routes["QB"] = {
        name: {
            "model_id": qb_id,
            "version": qb_version,
            "profile": "Shared",
            "confidence": "SUPPORTED",
            "basis": "validated shared QB production model",
        }
        for name in ("Pocket Passer", "Backfield Creator", "Dual Threat")
    }

    te_path = "data/research/op_x_016/frozen_te_scoring_spec.json"
    te = _read(root, te_path)
    for archetype, definition in te["models"].items():
        model_id, version = definition["id"], definition["version"]
        production = definition["production"]
        profile = (
            "Blocking"
            if archetype == "Pure Blocker"
            else "Possession"
            if archetype == "Gritty Possession"
            else "Vertical Threat"
        )
        profiles = {profile: dict(te["madden19_weights"][profile])}
        formula = definition["formula"]
        if archetype == "Vertical Threat":
            profiles[profile].pop("ELU", None)
            profiles[profile]["LBK"] = profiles[profile].get("LBK", 0) + 2
            profiles[profile]["IBL"] = profiles[profile].get("IBL", 0) + 3
        if archetype == "Physical Route Runner":
            profiles = {
                "Vertical Threat": dict(te["madden19_weights"]["Vertical Threat"]),
                "Possession": dict(te["madden19_weights"]["Possession"]),
            }
        models.append(
            {
                "id": model_id,
                "version": version,
                "family": "TE",
                "model_type": "archetype ranking",
                "capabilities": {
                    "ranking": production,
                    "player_comparison": production,
                    "displayed_overall_prediction": False,
                },
                "production": production,
                "locked": bool(validation.get((model_id, version), {}).get("locked", False)),
                "formula": formula,
                "profiles": profiles,
                "denominators": {key: sum(value.values()) for key, value in profiles.items()},
                "missing_attribute_rule": te["historical_missing_attribute_rule"],
                "validation": validation.get((model_id, version), {}),
                "provenance": te["provenance"],
                "freeze_commit": None,
                "evidence_paths": [te_path, coverage_path],
                "limitations": (
                    ["diagnostic/non-production; excluded from rankings"]
                    if not production
                    else ["ranking score only"]
                ),
            }
        )
        routes.setdefault("TE", {})[archetype] = {
            "model_id": model_id,
            "version": version,
            "profile": "Blend" if archetype == "Physical Route Runner" else profile,
            "confidence": "DIAGNOSTIC_ONLY"
            if not production
            else "SUPPORTED_SINGLE_SEASON"
            if archetype == "Physical Route Runner"
            else "SUPPORTED",
            "basis": definition.get("status", formula),
        }

    return {
        "schema_version": "1.0",
        "game": "CFB27",
        "position_aliases": POSITION_ALIASES,
        "models": sorted(models, key=lambda item: (item["family"], item["id"])),
        "routes": routes,
        "controls": {
            "fallback_models": "forbidden",
            "displayed_overall_prediction": "forbidden",
            "prices": "caller-supplied only",
        },
    }
