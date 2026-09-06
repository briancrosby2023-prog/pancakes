"""Generate the OP-X-022 real-roster GM artifacts."""

from pathlib import Path

from operation_pancake.production import build_roster_outputs

if __name__ == "__main__":
    print(build_roster_outputs(Path(__file__).resolve().parents[1]))
