"""Generate OP-X-008 current-team audit artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_008 import build_op_x_008, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_008(root)
    write_artifacts(root / "data/research/cfb27_op_x_008", analysis)
    print(f"Generated {len(analysis)} current-team audit artifacts.")


if __name__ == "__main__":
    main()
