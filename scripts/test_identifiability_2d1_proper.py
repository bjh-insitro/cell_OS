#!/usr/bin/env python3
"""Proper end-to-end test of Phase 2D.1 identifiability suite (sufficient scale)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scripts.run_identifiability_2d1 import run_full_suite

if __name__ == "__main__":
    output_dir = Path("output/identifiability_2d1_proper")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Running proper end-to-end test...")
    print("Scale: 32 vessels, 7 days (168h), 12h sampling")
    print("Expected events: B~13.4, C~6.7 (meets preconditions)")
    print()

    # Override defaults for faster runtime
    from cell_os.calibration import identifiability_runner_2d1
    identifiability_runner_2d1.DEFAULT_N_VESSELS = 32
    identifiability_runner_2d1.DEFAULT_DURATION_H = 168.0
    identifiability_runner_2d1.DEFAULT_SAMPLING_INTERVAL_H = 12.0

    run_full_suite(output_dir)
