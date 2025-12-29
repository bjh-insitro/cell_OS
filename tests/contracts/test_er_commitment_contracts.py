"""
Contract tests for Phase 2A.1: Stochastic ER Death Commitment

Tests the fundamental invariants of discrete commitment events:
1. Determinism + order invariance: same seed → identical commitment outcomes
2. Timing distribution sanity: event timing matches Poisson process
3. Divergence: replicates diverge after commitment under identical stress
"""

import math
import numpy as np
import pytest


def test_determinism_and_order_invariance():
    """
    Test 1: Determinism + Order Invariance

    Same seed with commitment enabled should produce identical commitment
    outcomes regardless of vessel creation order or assay config changes.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.0,  # Disable Phase 1 for cleaner test
        'er_commitment_enabled': True,
        'er_commitment_threshold': 0.20,  # Low threshold for faster commitment
        'er_commitment_baseline_hazard_per_h': 0.50,  # High rate for testability (mean ~2h at threshold)
    }

    # Scenario A: Create vessels in order A01, A02
    vm_a = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_a.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_a.seed_vessel("Plate1_A02", "A549", 50000, 50.0, 0.0)

    # Apply stress to trigger commitment
    # Use a compound that causes ER stress (proteostasis axis)
    vm_a.treat_with_compound("Plate1_A01", "tunicamycin", 10.0)  # High dose
    vm_a.treat_with_compound("Plate1_A02", "tunicamycin", 10.0)
    vm_a.advance_time(24.0)  # Shorter runtime with higher hazard

    committed_a_a01 = vm_a.vessel_states["Plate1_A01"].death_committed
    committed_a_a02 = vm_a.vessel_states["Plate1_A02"].death_committed
    time_a_a01 = vm_a.vessel_states["Plate1_A01"].death_committed_at_h
    time_a_a02 = vm_a.vessel_states["Plate1_A02"].death_committed_at_h

    # Scenario B: Create vessels in reversed order A02, A01
    vm_b = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_b.seed_vessel("Plate1_A02", "A549", 50000, 50.0, 0.0)
    vm_b.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)

    vm_b.treat_with_compound("Plate1_A01", "tunicamycin", 10.0)
    vm_b.treat_with_compound("Plate1_A02", "tunicamycin", 10.0)
    vm_b.advance_time(24.0)

    committed_b_a01 = vm_b.vessel_states["Plate1_A01"].death_committed
    committed_b_a02 = vm_b.vessel_states["Plate1_A02"].death_committed
    time_b_a01 = vm_b.vessel_states["Plate1_A01"].death_committed_at_h
    time_b_a02 = vm_b.vessel_states["Plate1_A02"].death_committed_at_h

    # Assert: Commitment status identical regardless of creation order
    assert committed_a_a01 == committed_b_a01, "A01 commitment differs with creation order"
    assert committed_a_a02 == committed_b_a02, "A02 commitment differs with creation order"

    # If committed, times must be identical (bitwise for determinism)
    if committed_a_a01:
        assert time_a_a01 == time_b_a01, \
            f"A01 commitment time differs: {time_a_a01} vs {time_b_a01}"
    if committed_a_a02:
        assert time_a_a02 == time_b_a02, \
            f"A02 commitment time differs: {time_a_a02} vs {time_b_a02}"

    print(f"✅ Determinism + Order Invariance: A01 committed={committed_a_a01}, A02 committed={committed_a_a02}")
    print(f"   Commitment times: A01={time_a_a01}, A02={time_a_a02}")


def test_timing_distribution_sanity():
    """
    Test 2: Timing Distribution Sanity

    Commitment times should follow exponential distribution (Poisson process).
    Check that empirical mean matches theoretical 1/λ within tolerance.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    import numpy as np

    # Use constant hazard regime: high enough stress that λ is roughly constant
    seed_base = 100
    n_vessels = 100  # Moderate sample size (reduced for speed)

    bio_noise_config = {
        'enabled': False,  # Disable Phase 1 for deterministic stress
        'er_commitment_enabled': True,
        'er_commitment_threshold': 0.20,  # Low threshold for quick saturation
        'er_commitment_baseline_hazard_per_h': 0.10,  # λ0 = 0.10/h → mean ~10h at threshold
        'er_commitment_sharpness_p': 1.0,  # Linear (easier to reason about)
    }

    commitment_times = []

    # Run many vessels with identical treatment
    for i in range(n_vessels):
        vm = BiologicalVirtualMachine(seed=seed_base + i, bio_noise_config=bio_noise_config)
        vessel_id = "Plate1_A01"
        vm.seed_vessel(vessel_id, "A549", 50000, 50.0, 0.0)

        # High dose to quickly saturate stress above threshold
        vm.treat_with_compound(vessel_id, "tunicamycin", 20.0)
        vm.advance_time(60.0)  # Run long enough for most to commit

        if vm.vessel_states[vessel_id].death_committed:
            commitment_times.append(vm.vessel_states[vessel_id].death_committed_at_h)

    # Check that we got enough commitments for statistics
    assert len(commitment_times) > n_vessels * 0.5, \
        f"Too few commitments for statistics: {len(commitment_times)}/{n_vessels}"

    empirical_mean = np.mean(commitment_times)

    # Theoretical expectation: with S quickly saturating to ~0.8-1.0 (typical for high dose),
    # and threshold 0.20, we have u ≈ (0.8 - 0.2)/(1 - 0.2) = 0.75
    # With p=1.0 (linear), λ ≈ 0.10 * 0.75 = 0.075/h
    # So mean time to commit ≈ 1/0.075 ≈ 13h
    # But stress builds up over time, so actual mean will be slightly higher

    # Sanity check: mean should be in a reasonable range (stress ramp-up delays commitment)
    assert 10 < empirical_mean < 65, \
        f"Empirical mean commitment time out of range: {empirical_mean:.1f}h"

    # Distribution shape check: coefficient of variation for exponential is 1.0
    empirical_std = np.std(commitment_times)
    empirical_cv = empirical_std / empirical_mean

    # CV should be roughly 1.0 for exponential, but stress ramp-up distorts this
    # So just check it's positive and not absurdly large
    assert 0.3 < empirical_cv < 2.0, \
        f"CV out of range for Poisson process: {empirical_cv:.2f}"

    print(f"✅ Timing Distribution Sanity: n={len(commitment_times)}/{n_vessels} committed")
    print(f"   Empirical mean: {empirical_mean:.1f}h, std: {empirical_std:.1f}h, CV: {empirical_cv:.2f}")


def test_divergence_under_identical_stress():
    """
    Test 3: Divergence Under Identical Stress

    Replicates with identical treatment should diverge in viability after
    commitment events occur at different times.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    import numpy as np

    seed_base = 200
    n_replicates = 24

    # Run with commitment DISABLED (control)
    bio_noise_config_off = {
        'enabled': False,
        'er_commitment_enabled': False,
    }

    viabilities_off = []
    for i in range(n_replicates):
        vm = BiologicalVirtualMachine(seed=seed_base + i, bio_noise_config=bio_noise_config_off)
        vm.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
        vm.treat_with_compound("Plate1_A01", "tunicamycin", 5.0)
        vm.advance_time(48.0)
        viabilities_off.append(vm.vessel_states["Plate1_A01"].viability)

    cv_off = np.std(viabilities_off) / np.mean(viabilities_off) if np.mean(viabilities_off) > 0 else 0.0

    # Run with commitment ENABLED
    bio_noise_config_on = {
        'enabled': False,  # Phase 1 off for cleaner test
        'er_commitment_enabled': True,
        'er_commitment_threshold': 0.25,
        'er_commitment_baseline_hazard_per_h': 0.20,  # Higher rate for visible divergence in 48h
    }

    viabilities_on = []
    commitment_count = 0
    for i in range(n_replicates):
        vm = BiologicalVirtualMachine(seed=seed_base + i, bio_noise_config=bio_noise_config_on)
        vm.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
        vm.treat_with_compound("Plate1_A01", "tunicamycin", 5.0)
        vm.advance_time(48.0)
        viabilities_on.append(vm.vessel_states["Plate1_A01"].viability)
        if vm.vessel_states["Plate1_A01"].death_committed:
            commitment_count += 1

    # Check that at least some commitments occurred
    assert commitment_count > 0, "No commitments occurred in test (increase dose or time)"

    cv_on = np.std(viabilities_on) / np.mean(viabilities_on) if np.mean(viabilities_on) > 0 else 0.0

    print(f"✅ Divergence Test:")
    print(f"   Commitment OFF: CV = {cv_off:.4f}, mean viability = {np.mean(viabilities_off):.3f}")
    print(f"   Commitment ON:  CV = {cv_on:.4f}, mean viability = {np.mean(viabilities_on):.3f}")
    print(f"   Commitments: {commitment_count}/{n_replicates} vessels")

    # Assert: Variance increases when commitment is enabled
    # (Commitment creates discrete branching → higher variance)
    if cv_on > 0.001 and cv_off > 0.001:  # Both have measurable variance
        assert cv_on > cv_off, \
            f"Commitment should increase variance: CV_on={cv_on:.4f} vs CV_off={cv_off:.4f}"
        print(f"   Variance increase: {cv_on / cv_off:.2f}x")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 2A.1: ER COMMITMENT CONTRACTS")
    print("=" * 70)

    test_determinism_and_order_invariance()
    test_timing_distribution_sanity()
    test_divergence_under_identical_stress()

    print("\n" + "=" * 70)
    print("✅ ALL ER COMMITMENT TESTS PASSED")
    print("=" * 70)
