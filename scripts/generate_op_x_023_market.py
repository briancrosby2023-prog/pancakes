"""Generate OP-X-023 market, history, risk, and Moneyball artifacts."""

from pathlib import Path

from operation_pancake.production import build_market_outputs

if __name__ == "__main__":
    print(build_market_outputs(Path(__file__).resolve().parents[1]))
