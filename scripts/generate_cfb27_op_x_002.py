"""Generate OP-X-002 artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_002 import build_op_x_002, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_002(root)
    write_artifacts(root / "data/research/cfb27_op_x_002", analysis)
    print("Generated all five primary and five secondary OP-X-002 gates.")


if __name__ == "__main__":
    main()
