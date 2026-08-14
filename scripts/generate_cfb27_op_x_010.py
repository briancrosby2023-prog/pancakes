"""Generate OP-X-010 canonical database V2 artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_010 import build_op_x_010, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_010(root)
    write_artifacts(root / "data/research/cfb27_op_x_010", analysis)
    print("Generated OP-X-010 canonical database V2 artifacts.")


if __name__ == "__main__":
    main()
