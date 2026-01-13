#!/usr/bin/env python3
"""
Runner script for identifiability calibration suite (Phase 2C.1).

Usage:
    # Full suite
    python scripts/run_identifiability_suite.py \
        --config configs/calibration/identifiability_2c1.yaml \
        --out artifacts/identifiability/dev_run

    # Scout mode (dose ladder)
    python scripts/run_identifiability_suite.py \
        --config configs/calibration/identifiability_2c1.yaml \
        --scout \
        --out artifacts/identifiability/scout
"""

import argparse
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_runner import (
    run_identifiability_suite,
    run_dose_scout,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run identifiability calibration suite (Phase 2C.1)"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to design config YAML (e.g., configs/calibration/identifiability_2c1.yaml)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/identifiability",
        help="Output directory for artifacts (default: artifacts/identifiability)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run identifier (default: timestamp)"
    )
    parser.add_argument(
        "--scout",
        action="store_true",
        help="Run dose ladder scout mode (empirical dose tuning)"
    )
    parser.add_argument(
        "--scout-compound",
        type=str,
        default="tunicamycin",
        help="Compound for scout mode (default: tunicamycin)"
    )
    parser.add_argument(
        "--scout-range",
        type=str,
        default="0.1,20.0",
        help="Dose range for scout (min,max in µM, log-spaced, default: 0.1,20.0)"
    )
    parser.add_argument(
        "--scout-n-doses",
        type=int,
        default=8,
        help="Number of dose levels for scout (default: 8)"
    )
    parser.add_argument(
        "--scout-wells-per-dose",
        type=int,
        default=16,
        help="Wells per dose for scout (default: 16)"
    )

    args = parser.parse_args()

    try:
        if args.scout:
            # Parse dose range
            dose_min, dose_max = map(float, args.scout_range.split(','))

            scout_dir = run_dose_scout(
                config_path=args.config,
                output_dir=args.out,
                compound=args.scout_compound,
                dose_range=(dose_min, dose_max),
                n_doses=args.scout_n_doses,
                n_wells_per_dose=args.scout_wells_per_dose,
                run_id=args.run_id
            )
            print(f"\n✓ Scout complete: {scout_dir}")
        else:
            run_dir = run_identifiability_suite(
                config_path=args.config,
                output_dir=args.out,
                run_id=args.run_id
            )
            print(f"\n✓ Suite complete: {run_dir}")

        sys.exit(0)

    except Exception as e:
        print(f"\n❌ {'Scout' if args.scout else 'Suite'} failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
