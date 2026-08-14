"""Generate OP-X-009 targeted current-vector acquisition artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_009 import build_op_x_009, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_009(root)
    write_artifacts(root / "data/research/cfb27_op_x_009", analysis)
    print(f"Generated {len(analysis)} OP-X-009 artifacts.")


if __name__ == "__main__":
    main()
