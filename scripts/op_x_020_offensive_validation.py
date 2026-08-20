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
    parser.add_argument("family", choices=("rb", "fb"))
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
