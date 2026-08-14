"""Generate OP-X-011 progression database artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_011 import build_op_x_011, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_artifacts(root / "data/research/cfb27_op_x_011", build_op_x_011(root))
    print("Generated OP-X-011 progression database artifacts.")


if __name__ == "__main__":
    main()
