#!/usr/bin/env python3
"""Quick test of Phase 2D.1 identifiability suite with reduced scale."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scripts.run_identifiability_2d1 import run_full_suite

if __name__ == "__main__":
    output_dir = Path("output/identifiability_2d1_quick_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Override runner to use smaller scale
    from cell_os.calibration import identifiability_runner_2d1
    original_defaults = (
        identifiability_runner_2d1.DEFAULT_N_VESSELS,
        identifiability_runner_2d1.DEFAULT_DURATION_H,
    )

    # Quick test: 16 vessels, 48h, 12h sampling
    identifiability_runner_2d1.DEFAULT_N_VESSELS = 16
    identifiability_runner_2d1.DEFAULT_DURATION_H = 48.0
    identifiability_runner_2d1.DEFAULT_SAMPLING_INTERVAL_H = 12.0

    try:
        run_full_suite(output_dir)
    finally:
        # Restore defaults
        identifiability_runner_2d1.DEFAULT_N_VESSELS = original_defaults[0]
        identifiability_runner_2d1.DEFAULT_DURATION_H = original_defaults[1]
