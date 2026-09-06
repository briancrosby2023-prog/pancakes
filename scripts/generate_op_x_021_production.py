"""Generate the OP-X-021 production registry and CFB27 decision artifacts."""

from pathlib import Path

from operation_pancake.production import build_production_outputs

if __name__ == "__main__":
    print(build_production_outputs(Path(__file__).resolve().parents[1]))
