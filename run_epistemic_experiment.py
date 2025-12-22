#!/usr/bin/env python3
"""
Run epistemic agent experiment with improved cost-aware batch sizing.

This generates JSONL files for the Epistemic Documentary visualization.

Output files:
- results/epistemic_agent/run_TIMESTAMP_evidence.jsonl
- results/epistemic_agent/run_TIMESTAMP_decisions.jsonl
- results/epistemic_agent/run_TIMESTAMP_diagnostics.jsonl
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cell_os.epistemic_agent.loop import EpistemicLoop
from cell_os.epistemic_agent.world import ExperimentalWorld

def main():
    """Run a standard epistemic agent experiment."""

    print("=" * 70)
    print("Epistemic Agent Experiment (with Real Cost Data)")
    print("=" * 70)

    # Create agent loop
    print("\nCreating agent loop...")
    loop = EpistemicLoop(
        budget=500,  # Generous well budget
        max_cycles=20  # Up to 20 cycles
    )

    # Run the experiment
    print("\nStarting experiment...\n")

    try:
        result = loop.run()

        print("\n" + "=" * 70)
        print("Experiment Complete!")
        print("=" * 70)

        print(f"\nCycles completed: {result.cycles_completed}")
        print(f"Wells consumed: {result.wells_consumed} / 500")
        print(f"Final regime: {result.final_regime}")

        # Show gate status
        final_beliefs = result.final_beliefs
        print(f"\nGate Status:")
        print(f"  Noise gate: {'✓ EARNED' if final_beliefs.noise_sigma_stable else '✗ NOT EARNED'}")
        print(f"  Edge effects: {'✓ KNOWN' if final_beliefs.edge_effect_confident else '? UNKNOWN'}")

        # Show cost summary from decisions
        print(f"\n{result.path_evidence}")
        print(f"{result.path_decisions}")

        print(f"\nView in Documentary:")
        print(f"  1. Copy JSONL files to validation_frontend/public/demo_results/epistemic_agent/")
        print(f"  2. Update RUN_BASE in EpistemicDocumentaryPage.tsx")
        print(f"  3. Run: cd validation_frontend && npm run dev")

    except KeyboardInterrupt:
        print("\n\nExperiment interrupted by user.")
    except Exception as e:
        print(f"\n\nError during experiment: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
