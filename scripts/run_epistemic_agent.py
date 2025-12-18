#!/usr/bin/env python3
"""
Run Epistemic Agent: Watch it learn about the world from scratch.

Usage:
    python scripts/run_epistemic_agent.py --cycles 10 --budget 200
    python scripts/run_epistemic_agent.py --cycles 20 --budget 384 --seed 42
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.epistemic_agent.loop import EpistemicLoop


def main():
    parser = argparse.ArgumentParser(description="Run epistemic agent experiment loop")
    parser.add_argument(
        '--cycles',
        type=int,
        default=10,
        help='Maximum number of experiment cycles (default: 10)'
    )
    parser.add_argument(
        '--budget',
        type=int,
        default=200,
        help='Total well budget (default: 200)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=0,
        help='Random seed for reproducibility (default: 0)'
    )
    parser.add_argument(
        '--log-dir',
        type=Path,
        default=None,
        help='Directory for log files (default: results/epistemic_agent/)'
    )

    args = parser.parse_args()

    print("="*60)
    print("EPISTEMIC AGENCY - MINIMAL PROTOTYPE v0.1")
    print("="*60)
    print(f"Cycles: {args.cycles}")
    print(f"Budget: {args.budget} wells")
    print(f"Seed: {args.seed}")
    print()

    # Create and run loop
    loop = EpistemicLoop(
        budget=args.budget,
        max_cycles=args.cycles,
        log_dir=args.log_dir,
        seed=args.seed
    )

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Complete!")


if __name__ == '__main__':
    main()
