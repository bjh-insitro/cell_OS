#!/usr/bin/env python3
"""
Runner script for epistemic agent experiments.

v0.4.2: CLI wrapper for EpistemicLoop with clean abort handling.

Usage:
    python scripts/run_epistemic_agent.py --cycles 20 --budget 384 --seed 42
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.epistemic_agent.loop import EpistemicLoop


def main():
    parser = argparse.ArgumentParser(
        description="Run epistemic agent with pay-for-calibration regime (v0.4.2)"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=20,
        help="Maximum number of cycles to run (default: 20)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=384,
        help="Total well budget (default: 384)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducibility (default: 0)",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory for logs (default: results/epistemic_agent)",
    )

    args = parser.parse_args()

    # Create and run loop
    loop = EpistemicLoop(
        budget=args.budget,
        max_cycles=args.cycles,
        log_dir=Path(args.log_dir) if args.log_dir else None,
        seed=args.seed,
    )

    try:
        loop.run()

        # Exit 0 even for policy aborts (those are expected, not errors)
        if loop.abort_reason and "ABORT EXPERIMENT" in loop.abort_reason:
            print(f"\n✓ Run completed (policy abort): {loop.abort_reason}")
            sys.exit(0)

        print("\n✓ Run completed successfully")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Run interrupted by user")
        sys.exit(130)  # Standard SIGINT exit code

    except Exception as e:
        print(f"\n❌ Run failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
