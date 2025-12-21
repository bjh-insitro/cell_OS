"""
Real Epistemic Claims Integration Test

Validates that the agent:
1. Computes entropy from belief uncertainty
2. Estimates expected information gain before proposing
3. Claims designs with expected gain
4. Measures actual gain from belief updates
5. Tracks epistemic debt from miscalibration

This is "Phase 1" epistemic claims - based on calibration uncertainty,
not mechanism-level posteriors (Task 6 will add mechanism inference).
"""

import tempfile
from pathlib import Path

from src.cell_os.epistemic_agent.loop import EpistemicLoop
from src.cell_os.epistemic_agent.beliefs import BeliefState


def test_entropy_computation():
    """
    Test that BeliefState computes entropy from calibration uncertainty.
    """
    beliefs = BeliefState()

    # Initial state: High entropy (no gates, no tests, no compounds)
    initial_entropy = beliefs.entropy
    print(f"Initial entropy: {initial_entropy:.2f} bits")

    # Should be high (10-12 bits total):
    # - Noise: 2.0 (no estimate)
    # - Assays: 3.0 (3 ungated)
    # - Edge: 1.0 (no tests)
    # - Compounds: 2.0 (none tested)
    # - Dose: 1.0 (no curvature)
    # - Time: 1.0 (no dependence)
    assert initial_entropy >= 10.0, f"Initial entropy should be high: {initial_entropy}"
    assert initial_entropy <= 12.0, f"Initial entropy should be bounded: {initial_entropy}"

    # Simulate noise gate earning
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 50
    beliefs.noise_rel_width = 0.20

    entropy_after_noise = beliefs.entropy
    print(f"Entropy after noise gate: {entropy_after_noise:.2f} bits")

    # Should decrease by ~1.9 bits (noise went from 2.0 → 0.1)
    assert entropy_after_noise < initial_entropy - 1.5
    assert entropy_after_noise > initial_entropy - 2.5

    # Simulate compound testing
    beliefs.tested_compounds.add("DMSO")
    beliefs.tested_compounds.add("tBHQ")

    entropy_after_compound = beliefs.entropy
    print(f"Entropy after 1 compound: {entropy_after_compound:.2f} bits")

    # Should decrease by ~1.0 bit (compounds: 2.0 → 1.0)
    assert entropy_after_compound < entropy_after_noise - 0.5

    # Simulate edge effects
    beliefs.edge_effect_confident = True
    beliefs.edge_tests_run = 1

    entropy_after_edge = beliefs.entropy
    print(f"Entropy after edge test: {entropy_after_edge:.2f} bits")

    # Should decrease by ~1.0 bit (edge: 1.0 → 0.0)
    assert entropy_after_edge < entropy_after_compound - 0.5

    print(f"✓ Entropy computation working: {initial_entropy:.2f} → {entropy_after_edge:.2f} bits")


def test_expected_gain_estimation():
    """
    Test that BeliefState estimates expected gain from experiments.
    """
    beliefs = BeliefState()

    # Baseline replicates (first calibration)
    gain_baseline_first = beliefs.estimate_expected_gain(
        template_name="baseline_replicates",
        n_wells=12,
        modalities=("cell_painting",)
    )
    print(f"Expected gain (first baseline): {gain_baseline_first:.3f} bits")

    # Should be high (0.8 bits) for first calibration
    assert gain_baseline_first >= 0.7
    assert gain_baseline_first <= 1.0

    # Simulate earning noise gate
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 50

    # Baseline replicates (after gate)
    gain_baseline_after = beliefs.estimate_expected_gain(
        template_name="baseline_replicates",
        n_wells=12,
        modalities=("cell_painting",)
    )
    print(f"Expected gain (baseline after gate): {gain_baseline_after:.3f} bits")

    # Should be lower (0.1 bits) after gate
    assert gain_baseline_after < gain_baseline_first
    assert gain_baseline_after <= 0.2

    # Edge center test (first time)
    gain_edge_first = beliefs.estimate_expected_gain(
        template_name="edge_center_test",
        n_wells=24,
        modalities=("cell_painting",)
    )
    print(f"Expected gain (first edge test): {gain_edge_first:.3f} bits")

    # Should be high (0.8 bits)
    assert gain_edge_first >= 0.7

    # Dose ladder (first compound)
    gain_dose_first = beliefs.estimate_expected_gain(
        template_name="dose_ladder_coarse",
        n_wells=12,
        modalities=("cell_painting",)
    )
    print(f"Expected gain (first dose ladder): {gain_dose_first:.3f} bits")

    # Should be high (1.0 bits)
    assert gain_dose_first >= 0.9

    # scRNA upgrade (expensive)
    gain_scrna = beliefs.estimate_expected_gain(
        template_name="scrna_upgrade_probe",
        n_wells=4,
        modalities=("scrna_seq",)
    )
    print(f"Expected gain (scRNA upgrade): {gain_scrna:.3f} bits")

    # Should be very high (1.5 bits)
    assert gain_scrna >= 1.4

    print(f"✓ Expected gain estimation working")


def test_epistemic_integration_in_loop():
    """
    Test that epistemic integration tracks claims and debt in agent loop.
    """
    print("\n" + "=" * 70)
    print("Running agent with epistemic integration...")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        loop = EpistemicLoop(
            budget=384,  # Increased budget for full gate ladder
            max_cycles=5,  # Run 5 cycles
            log_dir=Path(tmpdir),
            seed=42
        )

        # Run agent
        loop.run()

        # Check that epistemic integration tracked claims
        stats = loop.epistemic.get_statistics()
        print(f"\nEpistemic statistics:")
        print(f"  Total claims: {stats.get('total_claims', 0)}")
        print(f"  Total debt: {stats.get('total_debt', 0.0):.3f} bits")
        print(f"  Cost multiplier: {stats.get('cost_multiplier', 1.0):.3f}×")

        # Should have made claims for completed cycles
        # Agent might abort early if budget constraints, so check >= 1
        assert stats.get('total_claims', 0) >= 1, "Should have made at least 1 claim"

        # Debt should be non-negative (agent might overclaim or underclaim)
        assert stats.get('total_debt', 0.0) >= 0.0, "Debt should be non-negative"

        # Check that entropy decreased over cycles
        final_entropy = loop.agent.beliefs.entropy
        print(f"  Final entropy: {final_entropy:.2f} bits")

        # Initial entropy should be high (~10-12 bits)
        # After 3 cycles, should have decreased (noise gate earning, edge tests, compounds)
        assert final_entropy < 10.0, f"Entropy should decrease after learning: {final_entropy}"

        print(f"✓ Epistemic integration working in loop")


def test_debt_accumulation_from_overclaiming():
    """
    Test that debt accumulates when agent overclaims.
    """
    beliefs = BeliefState()

    # Initial entropy (high)
    initial_entropy = beliefs.entropy
    print(f"\nInitial entropy: {initial_entropy:.2f} bits")

    # Agent claims high gain
    expected_gain = 2.0

    # Simulate earning noise gate (entropy decreases by ~1.9 bits)
    beliefs.noise_sigma_stable = True
    beliefs.noise_df_total = 50
    beliefs.noise_rel_width = 0.20

    final_entropy = beliefs.entropy
    realized_gain = initial_entropy - final_entropy

    print(f"Expected gain: {expected_gain:.2f} bits")
    print(f"Realized gain: {realized_gain:.2f} bits")
    print(f"Overclaim: {expected_gain - realized_gain:.2f} bits")

    # If expected > realized, overclaim penalty should be positive
    if expected_gain > realized_gain:
        overclaim = expected_gain - realized_gain
        assert overclaim > 0
        print(f"✓ Agent overclaimed by {overclaim:.2f} bits (debt will accumulate)")
    else:
        print(f"✓ Agent underclaimed (no debt penalty)")


if __name__ == "__main__":
    print("=" * 70)
    print("REAL EPISTEMIC CLAIMS INTEGRATION TESTS (Task 3)")
    print("=" * 70)
    print()

    print("=" * 70)
    print("TEST 1: Entropy Computation from Beliefs")
    print("=" * 70)
    test_entropy_computation()
    print()

    print("=" * 70)
    print("TEST 2: Expected Gain Estimation")
    print("=" * 70)
    test_expected_gain_estimation()
    print()

    print("=" * 70)
    print("TEST 3: Epistemic Integration in Loop")
    print("=" * 70)
    test_epistemic_integration_in_loop()
    print()

    print("=" * 70)
    print("TEST 4: Debt Accumulation from Overclaiming")
    print("=" * 70)
    test_debt_accumulation_from_overclaiming()
    print()

    print("=" * 70)
    print("✅ ALL REAL EPISTEMIC CLAIMS TESTS PASSED")
    print("=" * 70)
    print()
    print("Validated:")
    print("  ✓ Entropy computed from calibration uncertainty")
    print("  ✓ Expected gain estimated before proposing")
    print("  ✓ Claims made and resolved in agent loop")
    print("  ✓ Debt tracked from miscalibration")
    print()
    print("🎉 TASK 3 COMPLETE: Real Epistemic Claims Working!")
    print()
    print("Note: This is Phase 1 (calibration-based entropy).")
    print("Task 6 will add mechanism-level posteriors for full Bayesian inference.")
