#!/usr/bin/env python3
"""Compatibility entry point for the E.15 historical population pipeline."""
from e15_seed_historical_artifact import main as seed
from e15_historical_te_population_validation_v2 import main

if __name__ == "__main__":
    seed()
    main()
