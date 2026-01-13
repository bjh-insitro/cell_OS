#!/usr/bin/env python3
"""
Run Predictive Modeling Experiments

Tests if morphology signatures encode generalizable biological mechanisms.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.cell_os.cell_thalamus.predictive_modeling import (
    MorphologyClassifier,
    TransferLearningExperiments
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run all transfer learning experiments."""

    logger.info("="*70)
    logger.info("PREDICTIVE MODELING: MECHANISM GENERALIZATION TESTS")
    logger.info("="*70)
    logger.info("")
    logger.info("Goal: Validate that morphology signatures encode real,")
    logger.info("      generalizable biological mechanisms")
    logger.info("")
    logger.info("Tests:")
    logger.info("  1. Leave-compounds-out CV (train on 8, test on 2)")
    logger.info("  2. Within-class transfer (tBHQ → H2O2, etc.)")
    logger.info("  3. Cell-line transfer (A549 → HepG2)")
    logger.info("")
    logger.info("="*70)
    logger.info("")

    # Initialize experiments
    experiments = TransferLearningExperiments()

    # Experiment 1: Leave-compounds-out CV
    logger.info("\n" + "="*70)
    logger.info("EXPERIMENT 1: LEAVE-COMPOUNDS-OUT CROSS-VALIDATION")
    logger.info("="*70)
    logger.info("")

    cv_results = experiments.leave_compounds_out_cv(n_folds=5)

    # Experiment 2: Within-class transfer
    logger.info("\n\n" + "="*70)
    logger.info("EXPERIMENT 2: WITHIN-CLASS TRANSFER")
    logger.info("="*70)
    logger.info("")

    within_class_results = experiments.within_class_transfer()

    # Experiment 3: Cell-line transfer
    logger.info("\n\n" + "="*70)
    logger.info("EXPERIMENT 3: CELL-LINE TRANSFER")
    logger.info("="*70)
    logger.info("")

    cell_line_results = experiments.cell_line_transfer()

    # Overall summary
    logger.info("\n\n" + "="*70)
    logger.info("OVERALL SUMMARY")
    logger.info("="*70)
    logger.info("")

    logger.info("Experiment 1: Leave-Compounds-Out CV")
    logger.info(f"  Mean accuracy: {cv_results['mean_accuracy']:.3f}")
    logger.info(f"  Status: {'✅ PASS' if cv_results['mean_accuracy'] > 0.7 else '⚠️ FAIL'} (target: >70%)")

    logger.info("")
    logger.info("Experiment 2: Within-Class Transfer")
    within_class_accs = [r['accuracy'] for r in within_class_results['test_cases']]
    mean_within = sum(within_class_accs) / len(within_class_accs)
    logger.info(f"  Mean accuracy: {mean_within:.3f}")
    logger.info(f"  Status: {'✅ PASS' if mean_within > 0.7 else '⚠️ FAIL'} (target: >70%)")

    logger.info("")
    logger.info("Experiment 3: Cell-Line Transfer")
    logger.info(f"  Mean accuracy: {cell_line_results['mean_accuracy']:.3f}")
    logger.info(f"  Status: {'✅ PASS' if cell_line_results['mean_accuracy'] > 0.6 else '⚠️ FAIL'} (target: >60%)")

    logger.info("")
    logger.info("="*70)

    # Final verdict
    all_pass = (
        cv_results['mean_accuracy'] > 0.7 and
        mean_within > 0.7 and
        cell_line_results['mean_accuracy'] > 0.6
    )

    if all_pass:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("")
        logger.info("Conclusion: Morphology signatures encode REAL, GENERALIZABLE")
        logger.info("            biological mechanisms. Not simulation artifacts!")
    else:
        logger.info("⚠️  MIXED RESULTS")
        logger.info("")
        logger.info("Some tests show generalization, others need investigation.")

    logger.info("="*70)

    return {
        'cv_results': cv_results,
        'within_class_results': within_class_results,
        'cell_line_results': cell_line_results
    }


if __name__ == "__main__":
    results = main()
