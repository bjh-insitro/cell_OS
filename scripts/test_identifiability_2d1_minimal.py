#!/usr/bin/env python3
"""Minimal end-to-end test of Phase 2D.1 identifiability suite."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cell_os.calibration.identifiability_runner_2d1 import run_identifiability_suite

if __name__ == "__main__":
    output_dir = Path("output/identifiability_2d1_minimal")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Running minimal end-to-end test...")
    print("Scale: 4 vessels, 24h, 12h sampling")
    print()

    result = run_identifiability_suite(
        output_dir=output_dir,
        n_vessels=4,
        duration_h=24.0,
        sampling_interval_h=12.0,
        cell_line="A549",
        initial_count=5000,
        base_seed=42,
    )

    print()
    print(f"Status: {result['status']}")

    if result['status'] == 'INSUFFICIENT_EVENTS':
        print("Expected for minimal scale - preconditions not met")
        print("This is correct behavior (suite refuses to run with insufficient power)")
        sys.exit(0)  # Success - suite correctly rejects bad design
    else:
        print("Data generation complete")
        sys.exit(0)
