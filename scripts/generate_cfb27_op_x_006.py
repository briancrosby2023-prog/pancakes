"""Generate OP-X-006 General Manager decision artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_006 import build_op_x_006, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_006(root)
    write_artifacts(root / "data/research/cfb27_op_x_006", analysis)
    print(f"Generated {len(analysis['decision_engine_v1'])} GM decision records.")


if __name__ == "__main__":
    main()
