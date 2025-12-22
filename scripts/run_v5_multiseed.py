#!/usr/bin/env python3
"""
Run V5.2 calibration plate across multiple seeds for validation.

This generates the same format results as V3/V4 for comparison.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cell_os.plate_executor import execute_plate_design


def run_calibration_plate(plate_path: Path, seed: int, output_dir: Path):
    """Run calibration plate simulation for a single seed."""

    print(f"Running {plate_path.stem} with seed {seed}...")

    # Execute plate design (this handles parsing, simulation, and formatting)
    results = execute_plate_design(
        json_path=plate_path,
        seed=seed,
        output_dir=output_dir,
        verbose=True
    )

    print(f"  ✓ Completed simulation")
    return results


def main():
    parser = argparse.ArgumentParser(description="Run V5 calibration plate across multiple seeds")
    parser.add_argument(
        "--seeds",
        type=int,
        nargs='+',
        default=[42, 123, 456, 789, 1000],
        help="Seeds to run (default: 42 123 456 789 1000)"
    )
    parser.add_argument(
        "--plate",
        type=str,
        default="validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v5.json",
        help="Path to plate design JSON"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="validation_frontend/public/demo_results/calibration_plates",
        help="Output directory for results"
    )

    args = parser.parse_args()

    plate_path = Path(args.plate)
    output_dir = Path(args.output_dir)

    if not plate_path.exists():
        print(f"❌ Plate design not found: {plate_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print(f"Running {plate_path.name} with seeds: {args.seeds}")
    print("="*70)
    print()

    results = []
    for seed in args.seeds:
        print(f"\nSeed {seed}:")
        print("-"*70)
        try:
            output_file = run_calibration_plate(plate_path, seed, output_dir)
            results.append({"seed": seed, "success": True, "output": str(output_file)})
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append({"seed": seed, "success": False, "error": str(e)})

    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)

    n_success = sum(1 for r in results if r["success"])
    print(f"Total runs: {len(results)}")
    print(f"Successful: {n_success}/{len(results)}")

    if n_success < len(results):
        print()
        print("Failed runs:")
        for r in results:
            if not r["success"]:
                print(f"  Seed {r['seed']}: {r['error']}")

    return 0 if n_success == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
