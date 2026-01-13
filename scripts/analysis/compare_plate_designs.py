#!/usr/bin/env python3
"""
Batch simulation runner for comparing plate designs.

Phase 1: Compare CAL_384_RULES_WORLD_v1 vs v2 across multiple seeds.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


# Configuration
DESIGNS = [
    "CAL_384_RULES_WORLD_v1",
    "CAL_384_RULES_WORLD_v2",
]

SEEDS = [42, 123, 456, 789, 1011]

AUTO_PULL = True
AUTO_COMMIT = True


def run_plate_simulation(design_name: str, seed: int, auto_pull: bool = True, auto_commit: bool = True):
    """
    Run a single plate simulation.

    Args:
        design_name: Name of the plate design (without .json extension)
        seed: Random seed for reproducibility
        auto_pull: Whether to git pull before running
        auto_commit: Whether to git commit results after running

    Returns:
        True if successful, False otherwise
    """
    plate_path = f"validation_frontend/public/plate_designs/{design_name}.json"

    # Build command
    cmd = [
        "python3",
        "src/cell_os/plate_executor_v2_parallel.py",
        plate_path,
        "--seed", str(seed)
    ]

    if auto_pull:
        cmd.append("--auto-pull")

    if auto_commit:
        cmd.append("--auto-commit")

    print(f"\n{'='*80}")
    print(f"Running: {design_name} with seed {seed}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*80}\n")

    try:
        result = subprocess.run(cmd, check=True, cwd=Path.cwd())
        print(f"\n✓ Successfully completed: {design_name} (seed={seed})")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed: {design_name} (seed={seed})")
        print(f"Error: {e}")
        return False


def main():
    """Run all plate design comparisons."""
    start_time = datetime.now()

    print(f"\n{'='*80}")
    print(f"PLATE DESIGN COMPARISON - PHASE 1")
    print(f"{'='*80}")
    print(f"\nDesigns to compare: {', '.join(DESIGNS)}")
    print(f"Seeds per design: {len(SEEDS)} ({', '.join(map(str, SEEDS))})")
    print(f"Total simulations: {len(DESIGNS) * len(SEEDS)}")
    print(f"Estimated time: ~{len(DESIGNS) * len(SEEDS) * 2}-{len(DESIGNS) * len(SEEDS) * 3} minutes")
    print(f"\nStarted: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    # Track results
    results = []

    # Run simulations
    for design in DESIGNS:
        for seed in SEEDS:
            success = run_plate_simulation(
                design_name=design,
                seed=seed,
                auto_pull=AUTO_PULL,
                auto_commit=AUTO_COMMIT
            )
            results.append({
                "design": design,
                "seed": seed,
                "success": success
            })

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*80}")
    print(f"COMPARISON COMPLETE")
    print(f"{'='*80}")
    print(f"\nTotal time: {duration/60:.1f} minutes")

    # Results table
    print(f"\nResults:")
    print(f"{'Design':<30} {'Seed':<10} {'Status':<10}")
    print(f"{'-'*50}")

    successes = 0
    for r in results:
        status = "✓ Success" if r["success"] else "✗ Failed"
        print(f"{r['design']:<30} {r['seed']:<10} {status:<10}")
        if r["success"]:
            successes += 1

    print(f"\nSuccess rate: {successes}/{len(results)}")

    if successes == len(results):
        print(f"\n✓ All simulations completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. View results at: validation_frontend/public/demo_results/calibration_plates/")
        print(f"  2. Compare results in the frontend at: http://localhost:5173/calibration-plate")
        print(f"  3. Look for systematic differences between v1 and v2 designs")
        return 0
    else:
        print(f"\n⚠️  Some simulations failed. Check output above for errors.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
