"""
Test beam search with calibrated confidence COMMIT integration.

Single seed, verbose logging, small beam width for readable behavior.
"""

import logging
import sys
from src.cell_os.hardware.beam_search import Phase5EpisodeRunner, BeamSearch
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY

# Set up verbose logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/beam_commit_test.log')
    ]
)
logger = logging.getLogger(__name__)


def test_single_seed_verbose():
    """Run beam search on nocodazole with seed 42, verbose logging."""

    logger.info("=" * 80)
    logger.info("BEAM SEARCH COMMIT INTEGRATION TEST")
    logger.info("Compound: test_C_clean (MICROTUBULE, paclitaxel)")
    logger.info("Seed: 42")
    logger.info("Beam width: 5 (small for readability)")
    logger.info("=" * 80)

    # Get microtubule compound from Phase5 library
    compound_id = "test_C_clean"  # paclitaxel, clean signature
    phase5_compound = PHASE5_LIBRARY[compound_id]

    logger.info(f"Phase5 compound: {phase5_compound.compound_name}")
    logger.info(f"Reference dose: {phase5_compound.reference_dose_uM} uM")
    logger.info(f"Potency scalar: {phase5_compound.potency_scalar}")
    logger.info(f"Toxicity scalar: {phase5_compound.toxicity_scalar}")

    # Create Phase5 episode runner
    runner = Phase5EpisodeRunner(
        phase5_compound=phase5_compound,
        cell_line="A549",
        horizon_h=48.0,
        step_h=6.0,
        seed=42,
        lambda_dead=2.0,
        lambda_ops=0.1,
        actin_threshold=1.4
    )

    logger.info(f"Episode runner: {runner.n_steps} steps, {runner.horizon_h}h horizon")

    # Create beam search with small beam width and debug enabled
    beam_search = BeamSearch(
        runner=runner,
        beam_width=5,  # Small for readability
        max_interventions=2,
        death_tolerance=0.20,
        w_mechanism=2.0,
        w_viability=0.5,
        w_interventions=0.1
    )

    # Enable COMMIT decision logging
    beam_search.debug_commit_decisions = True

    # Lower commit threshold slightly to see COMMIT behavior
    beam_search.commit_conf_threshold = 0.70  # Default is 0.75

    logger.info(f"Beam search config:")
    logger.info(f"  beam_width: {beam_search.beam_width}")
    logger.info(f"  commit_conf_threshold: {beam_search.commit_conf_threshold}")
    logger.info(f"  w_commit_conf: {beam_search.w_commit_conf}")
    logger.info(f"  w_commit_time: {beam_search.w_commit_time}")
    logger.info(f"  debug_commit_decisions: {beam_search.debug_commit_decisions}")

    logger.info("\n" + "=" * 80)
    logger.info("RUNNING BEAM SEARCH...")
    logger.info("=" * 80 + "\n")

    # Run beam search
    try:
        result = beam_search.search(compound_id, phase5_compound)

        logger.info("\n" + "=" * 80)
        logger.info("BEAM SEARCH COMPLETE")
        logger.info("=" * 80)

        logger.info(f"Best reward: {result.best_reward:.4f}")
        logger.info(f"Best receipt:")
        logger.info(f"  actin_fold_12h: {result.best_receipt.actin_fold_12h:.3f}")
        logger.info(f"  viability_48h: {result.best_receipt.viability_48h:.3f}")
        logger.info(f"  washout_count: {result.best_receipt.washout_count}")
        logger.info(f"  feed_count: {result.best_receipt.feed_count}")
        logger.info(f"  mechanism_engaged: {result.best_receipt.mechanism_engaged}")
        logger.info(f"  safe: {result.best_receipt.safe}")

        logger.info(f"\nDiagnostics:")
        logger.info(f"  nodes_expanded: {result.nodes_expanded}")
        logger.info(f"  nodes_pruned_death: {result.nodes_pruned_death}")
        logger.info(f"  nodes_pruned_interventions: {result.nodes_pruned_interventions}")
        logger.info(f"  nodes_pruned_dominated: {result.nodes_pruned_dominated}")

        logger.info(f"\nBest schedule ({len(result.best_schedule)} actions):")
        for i, action in enumerate(result.best_schedule):
            logger.info(f"  t={i}: dose={action.dose_fraction:.2f}, washout={action.washout}, feed={action.feed}")

        return result

    except Exception as e:
        logger.error(f"Beam search failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("Starting single-seed beam search COMMIT integration test...")
    result = test_single_seed_verbose()
    logger.info("\nTest complete. Check /tmp/beam_commit_test.log for full logs.")

    # Print summary to stdout
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Best reward: {result.best_reward:.4f}")
    print(f"Mechanism engaged: {result.best_receipt.mechanism_engaged}")
    print(f"Safe: {result.best_receipt.safe}")
    print(f"Nodes expanded: {result.nodes_expanded}")
    print(f"\nCheck /tmp/beam_commit_test.log for COMMIT decision logs")
    print("=" * 80)
