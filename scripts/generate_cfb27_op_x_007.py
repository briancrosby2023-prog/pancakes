"""Generate OP-X-007 Team Digital Twin artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_007 import build_op_x_007, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_007(root)
    write_artifacts(root / "data/research/cfb27_op_x_007", analysis)
    print(f"Generated {len(analysis)} Digital Twin artifacts.")


if __name__ == "__main__":
    main()
