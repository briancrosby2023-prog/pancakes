"""Generate OP-C-001 acquisition freeze and audit artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_c_001 import build_op_c_001, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_artifacts(root / "data/research/cfb27_op_c_001", build_op_c_001(root))
    print("Generated OP-C-001 acquisition freeze and audit artifacts.")


if __name__ == "__main__":
    main()
