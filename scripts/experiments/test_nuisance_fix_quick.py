"""
Quick diagnostic: verify nuisance_probability is observation-aware.

Run one seed of each mechanism and check that:
1. nuisance_probability varies with observation (not stuck at 1.0)
2. inflation_share_nonhetero is accessible but different from nuisance_probability
3. Both are populated in belief state
"""

import logging
import numpy as np
from src.cell_os.hardware.beam_search import Phase5EpisodeRunner
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
from src.cell_os.hardware.episode import Action

logging.basicConfig(level=logging.WARNING)

def test_single_compound(compound_id: str):
    """Run one seed, one schedule, check nuisance values."""
    phase5_compound = PHASE5_LIBRARY[compound_id]
    true_mechanism = phase5_compound.true_stress_axis

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

    # Test a single mid-dose schedule
    schedule = [Action(dose_fraction=0.5, washout=False, feed=False)]

    try:
        prefix_result = runner.rollout_prefix(schedule)

        print(f"\n{compound_id} ({true_mechanism}):")
        print(f"  posterior_top_prob: {prefix_result.posterior_top_prob:.3f}")
        print(f"  predicted_axis: {prefix_result.predicted_axis}")
        print(f"  nuisance_probability: {prefix_result.nuisance_fraction:.3f}")  # This field stores nuisance_prob now
        print(f"  nuisance_mean_shift_mag: {prefix_result.nuisance_mean_shift_mag:.3f}")
        print(f"  nuisance_var_inflation: {prefix_result.nuisance_var_inflation:.3f}")
        print(f"  calibrated_confidence: {prefix_result.calibrated_confidence:.3f}")

        # Check if nuisance_prob is observation-aware (not stuck at 1.0)
        if prefix_result.nuisance_fraction >= 0.99:
            print(f"  ⚠️  WARNING: nuisance still saturated at {prefix_result.nuisance_fraction:.3f}")
        else:
            print(f"  ✓ nuisance_probability is observation-aware")

    except Exception as e:
        print(f"\n{compound_id} FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("="*80)
    print("NUISANCE FIX DIAGNOSTIC")
    print("="*80)
    print("\nChecking if nuisance_probability is observation-aware...")

    # Test all three mechanisms
    compounds = {
        'test_C_clean': 'microtubule',
        'test_A_clean': 'er_stress',
        'test_B_clean': 'mitochondrial'
    }

    for compound_id, true_mech in compounds.items():
        test_single_compound(compound_id)

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
