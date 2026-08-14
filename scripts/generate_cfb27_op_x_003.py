"""Generate OP-X-003 historical/market intelligence artifacts."""

from pathlib import Path

from operation_pancake.research.cfb27_op_x_003 import build_op_x_003, write_artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    analysis = build_op_x_003(root)
    write_artifacts(root / "data/research/cfb27_op_x_003", analysis)
    print(
        f"Normalized {len(analysis['ea_cross_year_card_model'])} staged cards and "
        f"{len(analysis['market_observations'])} real display-price observations."
    )


if __name__ == "__main__":
    main()
