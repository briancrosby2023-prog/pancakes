"""Generate OP-X-004 upgrade intelligence artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_004 import build_op_x_004, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_004(root)
    write_artifacts(root / "data/research/cfb27_op_x_004", analysis)
    print(f"Built upgrade intelligence for {len(analysis['pc_upgrade_decision_output'])} cards.")


if __name__ == "__main__":
    main()
