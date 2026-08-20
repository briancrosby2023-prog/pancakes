#!/usr/bin/env python3
"""Blind historical validator for frozen OP-X-020 offensive models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from op_x_019_defensive_validation import validate_family

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("family", choices=("rb", "fb", "tackle", "guard", "kp"))
    args = parser.parse_args()
    if args.family == "rb":
        report = validate_family(
            family="RB",
            spec_path=ROOT / "data/research/op_x_020/rb/frozen_rb_scoring_spec.json",
            positions={25: "HB", 26: "HB"},
            expected={25: 783, 26: 747},
            control_commit="1d696da59aa195dc7716a27e51e18273d9fc6fdc",
        )
    elif args.family == "fb":
        report = validate_family(
            family="FB",
            spec_path=ROOT / "data/research/op_x_020/fb/frozen_fb_scoring_spec.json",
            positions={25: "FB", 26: "FB"},
            expected={25: 58, 26: 62},
            control_commit="f1a7912f8e984e860ef8945131401507bebf56a2",
        )
    elif args.family == "tackle":
        report = validate_family(
            family="TACKLE",
            spec_path=ROOT / "data/research/op_x_020/tackle/frozen_tackle_scoring_spec.json",
            positions={25: "OT", 26: "OT"},
            expected={25: 743, 26: 719},
            control_commit="6a5c717768d4f13f6296ef1fdb312ca77dbfd4a3",
        )
    elif args.family == "guard":
        report = validate_family(
            family="GUARD",
            spec_path=ROOT / "data/research/op_x_020/guard/frozen_guard_scoring_spec.json",
            positions={25: "G", 26: "G"},
            expected={25: 702, 26: 713},
            control_commit="fb320d746bf1120b4dd9a09ebd2a0480760877fa",
        )
    elif args.family == "kp":
        report = validate_family(
            family="KP",
            spec_path=ROOT / "data/research/op_x_020/kp/frozen_kp_scoring_spec.json",
            positions={25: "KP", 26: "KP"},
            expected={25: 336, 26: 323},
            control_commit="PENDING_PRE_BLIND_COMMIT",
        )
    print(
        json.dumps(
            {
                season: report["seasons"][season]["ranking_accuracy_excluding_ties"]
                for season in ("26", "25")
            },
            indent=2,
        )
    )
    print(report["cross_season_verdict"])


if __name__ == "__main__":
    main()
