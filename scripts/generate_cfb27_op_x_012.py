"""Generate OP-X-012 acquisition and coverage artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_012 import build_op_x_012, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_artifacts(root / "data/research/cfb27_op_x_012", build_op_x_012(root))
    print("Generated OP-X-012 acquisition and coverage artifacts.")

    # Temporary proven-runner bridge for OP-X-024. This executes only repository-local
    # canonical CFB27 TE science; it does not reacquire data or alter production models.
    from op_x_024_te_ovr_economics import main as run_op_x_024

    run_op_x_024()
    print("Generated OP-X-024 TE OVR economics artifacts.")


if __name__ == "__main__":
    main()
