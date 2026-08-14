"""Generate OP-X-001 research artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import build_op_x_001, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_001(root)
    write_artifacts(root / "data/research/cfb27_op_x_001", analysis)
    evaluated = sum(
        row["confidence"] != "NOT_APPLICABLE" for row in analysis["ability_stack_coherence"]
    )
    print(
        f"Evaluated {evaluated} compatible cards from "
        f"{len(analysis['ability_stack_coherence'])} frozen cards."
    )


if __name__ == "__main__":
    main()
