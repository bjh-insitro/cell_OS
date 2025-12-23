#!/usr/bin/env python3
"""
Phase 1: V4 Production Validation

Run V4A (original validated plate) 3 times to test production stability.

Goal: Verify 11.7% island CV baseline holds across independent runs.
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cell_os.plate_executor_v2_parallel import execute_plate_design_parallel


def main():
    parser = argparse.ArgumentParser(
        description="Phase 1: V4 Production Validation (3 replicates)"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs='+',
        default=[100, 200, 300],  # Different from validation seeds (42, 123, 456, 789, 1000)
        help="Seeds for 3 independent runs (default: 100 200 300)"
    )
    parser.add_argument(
        "--plate",
        type=str,
        default="validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v4.json",
        help="Path to V4 plate design"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="validation_frontend/public/demo_results/calibration_plates",
        help="Output directory"
    )

    args = parser.parse_args()

    plate_path = Path(args.plate)
    output_dir = Path(args.output_dir)

    if not plate_path.exists():
        print(f"❌ Plate design not found: {plate_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("PHASE 1: V4 PRODUCTION VALIDATION")
    print("="*80)
    print()
    print(f"Plate: {plate_path.name}")
    print(f"Seeds: {args.seeds}")
    print(f"Output: {output_dir}")
    print()
    print("Goal: Verify 11.7% island CV baseline holds across independent runs")
    print()

    results = []
    for i, seed in enumerate(args.seeds, 1):
        print(f"\n{'='*80}")
        print(f"Run {i}/3 (seed={seed})")
        print(f"{'='*80}")

        try:
            result = execute_plate_design_parallel(
                json_path=plate_path,
                seed=seed,
                output_dir=output_dir,
                verbose=True,
                workers=None  # Auto-detect (up to 32)
            )
            results.append({"run": i, "seed": seed, "success": True})
            print(f"\n✅ Run {i} completed successfully")

        except Exception as e:
            print(f"\n❌ Run {i} failed: {e}")
            results.append({"run": i, "seed": seed, "success": False, "error": str(e)})

    # Summary
    print()
    print("="*80)
    print("PHASE 1 COMPLETE")
    print("="*80)
    print()

    n_success = sum(1 for r in results if r["success"])
    print(f"Completed: {n_success}/{len(results)} runs")

    if n_success == len(results):
        print()
        print("✅ All runs successful!")
        print()
        print("Next step: Run analysis script to check stability:")
        print("  python3 scripts/analyze_v4_phase1.py")
    else:
        print()
        print("⚠️  Some runs failed - check errors above")
        for r in results:
            if not r["success"]:
                print(f"  Run {r['run']} (seed {r['seed']}): {r.get('error', 'Unknown error')}")

    return 0 if n_success == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
