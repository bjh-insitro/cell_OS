#!/usr/bin/env python3
"""
Run Phase 1 Epistemic Agent

Test if the agent can discover that mid-dose (0.5-2×IC50) at early timepoints (12h)
provides the best mechanistic information content.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.cell_os.cell_thalamus.epistemic_agent import EpistemicAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run epistemic agent campaign."""

    logger.info("="*70)
    logger.info("PHASE 1: EPISTEMIC AGENT TEST")
    logger.info("="*70)
    logger.info("")
    logger.info("Goal: Discover which dose/timepoint conditions maximize")
    logger.info("      mechanistic information (stress class separation)")
    logger.info("")
    logger.info("Expected Discovery:")
    logger.info("  - Mid-dose (15-60 µM) should be most informative")
    logger.info("  - Early timepoint (12h) should have better separation")
    logger.info("")
    logger.info("="*70)

    # Initialize agent with budget
    agent = EpistemicAgent(budget=200)  # 200 wells for quick test

    # Run campaign
    logger.info("\nStarting autonomous campaign...\n")
    summary = agent.run_campaign(n_iterations=20)

    # Analyze results
    logger.info("\n" + "="*70)
    logger.info("ANALYSIS: Did the agent discover the truth?")
    logger.info("="*70)

    # Check if mid-dose range was preferred
    dose_counts = dict(summary['most_sampled_doses'])
    mid_dose_samples = sum(count for dose, count in dose_counts.items()
                           if 15.0 <= dose <= 60.0)
    total_samples = sum(dose_counts.values())
    mid_dose_fraction = mid_dose_samples / total_samples if total_samples > 0 else 0

    logger.info(f"\nMid-dose sampling (15-60 µM):")
    logger.info(f"  Fraction: {mid_dose_fraction:.1%} of queries")
    logger.info(f"  Count: {mid_dose_samples}/{total_samples}")

    if mid_dose_fraction > 0.5:
        logger.info("  ✅ DISCOVERED: Agent preferentially samples mid-dose!")
    else:
        logger.info("  ❌ NOT YET: Agent hasn't converged to mid-dose")

    # Check timepoint preference
    timepoint_counts = dict(summary['most_sampled_timepoints'])
    early_samples = timepoint_counts.get(12.0, 0)
    timepoint_total = sum(timepoint_counts.values())
    early_fraction = early_samples / timepoint_total if timepoint_total > 0 else 0

    logger.info(f"\nEarly timepoint sampling (12h):")
    logger.info(f"  Fraction: {early_fraction:.1%} of queries")
    logger.info(f"  Count: {early_samples}/{timepoint_total}")

    if early_fraction > 0.5:
        logger.info("  ✅ DISCOVERED: Agent prefers early timepoints!")
    else:
        logger.info("  ℹ️  Agent exploring timepoint space")

    # Overall verdict
    logger.info(f"\nFinal separation ratio: {summary['final_separation_ratio']:.3f}")
    logger.info(f"Budget efficiency: {summary['budget_used']}/{agent.budget} wells used")

    logger.info("\n" + "="*70)
    if mid_dose_fraction > 0.5 and summary['final_separation_ratio'] > 2.0:
        logger.info("🎉 SUCCESS: Agent discovered mechanistically informative conditions!")
    elif mid_dose_fraction > 0.3:
        logger.info("🔄 PROGRESS: Agent is learning - run more iterations")
    else:
        logger.info("🔍 EXPLORING: Agent still in exploration phase")
    logger.info("="*70)

    return summary


if __name__ == "__main__":
    summary = main()
