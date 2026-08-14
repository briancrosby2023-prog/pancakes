"""Generate OP-X-012 acquisition and coverage artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_012 import build_op_x_012, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_artifacts(root / "data/research/cfb27_op_x_012", build_op_x_012(root))
    print("Generated OP-X-012 acquisition and coverage artifacts.")


if __name__ == "__main__":
    main()
