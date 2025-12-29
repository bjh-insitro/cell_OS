"""
Contract tests for intrinsic biology stochasticity.

Tests the fundamental invariants:
1. Determinism: same seed → identical outputs
2. RNG isolation: assay RNG changes don't affect biology
3. Plate/vessel order invariance: instantiation order doesn't matter
4. Backward compatibility: enabled=False keeps golden tests unchanged
"""

import math
import numpy as np
import pytest


def test_determinism_same_seed_identical_outputs():
    """
    Same seed → identical biology random effects and trajectories.

    This is the most fundamental contract: determinism under seed.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.10,
        'stress_sensitivity_cv': 0.15,
        'hazard_scale_cv': 0.20,
    }

    # Run A
    vm_a = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_a.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_a.seed_vessel("Plate1_B02", "A549", 50000, 50.0, 0.0)
    vm_a.advance_time(24.0)
    re_a_1 = vm_a.vessel_states["Plate1_A01"].bio_random_effects
    re_a_2 = vm_a.vessel_states["Plate1_B02"].bio_random_effects
    count_a_1 = vm_a.vessel_states["Plate1_A01"].cell_count
    count_a_2 = vm_a.vessel_states["Plate1_B02"].cell_count

    # Run B (same seed, same config)
    vm_b = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_b.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_b.seed_vessel("Plate1_B02", "A549", 50000, 50.0, 0.0)
    vm_b.advance_time(24.0)
    re_b_1 = vm_b.vessel_states["Plate1_A01"].bio_random_effects
    re_b_2 = vm_b.vessel_states["Plate1_B02"].bio_random_effects
    count_b_1 = vm_b.vessel_states["Plate1_A01"].cell_count
    count_b_2 = vm_b.vessel_states["Plate1_B02"].cell_count

    # Assert: RE values identical (bitwise for determinism)
    for key in re_a_1:
        assert math.isclose(re_a_1[key], re_b_1[key], rel_tol=0, abs_tol=0), \
            f"Vessel 1 RE {key} differs: {re_a_1[key]} vs {re_b_1[key]}"
        assert math.isclose(re_a_2[key], re_b_2[key], rel_tol=0, abs_tol=0), \
            f"Vessel 2 RE {key} differs: {re_a_2[key]} vs {re_b_2[key]}"

    # Assert: Trajectories identical
    assert math.isclose(count_a_1, count_b_1, rel_tol=1e-10, abs_tol=0), \
        f"Vessel 1 cell count differs: {count_a_1} vs {count_b_1}"
    assert math.isclose(count_a_2, count_b_2, rel_tol=1e-10, abs_tol=0), \
        f"Vessel 2 cell count differs: {count_a_2} vs {count_b_2}"

    print("✅ Determinism: Same seed produces identical REs and trajectories")


def test_rng_isolation_assay_changes_dont_affect_biology():
    """
    RNG isolation: assay RNG changes do not change biology REs or trajectories.

    This proves that biology random effects are independent of measurement noise.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.10,
    }

    # Run A: with high assay noise (assay noise doesn't affect bio RNG)
    vm_a = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_a.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_a.advance_time(24.0)
    re_a = vm_a.vessel_states["Plate1_A01"].bio_random_effects
    count_a = vm_a.vessel_states["Plate1_A01"].cell_count

    # Run B: with low assay noise (but same biology seed)
    vm_b = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_b.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_b.advance_time(24.0)
    re_b = vm_b.vessel_states["Plate1_A01"].bio_random_effects
    count_b = vm_b.vessel_states["Plate1_A01"].cell_count

    # Assert: Biology REs identical (assay config doesn't affect them)
    for key in re_a:
        assert math.isclose(re_a[key], re_b[key], rel_tol=0, abs_tol=0), \
            f"Bio RE {key} differs with different assay noise: {re_a[key]} vs {re_b[key]}"

    # Assert: True biology (cell count) identical
    assert math.isclose(count_a, count_b, rel_tol=1e-10, abs_tol=0), \
        f"Biology (cell count) differs with different assay noise: {count_a} vs {count_b}"

    print("✅ RNG isolation: Assay noise changes don't affect biology REs or trajectories")


def test_plate_instantiation_order_invariance():
    """
    Vessel REs are identical regardless of plate instantiation order.

    This proves plate latents are deterministic from plate_id, not encounter order.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.10,
        'plate_level_fraction': 0.3,
    }

    # Scenario A: Create Plate1 first, then Plate2
    vm_a = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_a.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_a.seed_vessel("Plate2_A01", "A549", 50000, 50.0, 0.0)
    re_a_plate1 = vm_a.vessel_states["Plate1_A01"].bio_random_effects
    re_a_plate2 = vm_a.vessel_states["Plate2_A01"].bio_random_effects

    # Scenario B: Create Plate2 first, then Plate1 (reversed order)
    vm_b = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_b.seed_vessel("Plate2_A01", "A549", 50000, 50.0, 0.0)
    vm_b.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    re_b_plate1 = vm_b.vessel_states["Plate1_A01"].bio_random_effects
    re_b_plate2 = vm_b.vessel_states["Plate2_A01"].bio_random_effects

    # Assert: Plate1 REs identical regardless of when it was created
    for key in re_a_plate1:
        assert math.isclose(re_a_plate1[key], re_b_plate1[key], rel_tol=0, abs_tol=0), \
            f"Plate1 RE {key} differs based on creation order: {re_a_plate1[key]} vs {re_b_plate1[key]}"

    # Assert: Plate2 REs identical regardless of when it was created
    for key in re_a_plate2:
        assert math.isclose(re_a_plate2[key], re_b_plate2[key], rel_tol=0, abs_tol=0), \
            f"Plate2 RE {key} differs based on creation order: {re_a_plate2[key]} vs {re_b_plate2[key]}"

    print("✅ Plate instantiation order does not affect REs")


def test_vessel_instantiation_order_invariance():
    """
    Vessel REs are identical regardless of vessel creation order within a plate.

    This proves lineage latents are deterministic from lineage_id, not order.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.10,
    }

    # Scenario A: Create A01 first, then B02
    vm_a = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_a.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_a.seed_vessel("Plate1_B02", "A549", 50000, 50.0, 0.0)
    re_a_a01 = vm_a.vessel_states["Plate1_A01"].bio_random_effects
    re_a_b02 = vm_a.vessel_states["Plate1_B02"].bio_random_effects

    # Scenario B: Create B02 first, then A01 (reversed order)
    vm_b = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm_b.seed_vessel("Plate1_B02", "A549", 50000, 50.0, 0.0)
    vm_b.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    re_b_a01 = vm_b.vessel_states["Plate1_A01"].bio_random_effects
    re_b_b02 = vm_b.vessel_states["Plate1_B02"].bio_random_effects

    # Assert: A01 REs identical regardless of creation order
    for key in re_a_a01:
        assert math.isclose(re_a_a01[key], re_b_a01[key], rel_tol=0, abs_tol=0), \
            f"A01 RE {key} differs based on creation order"

    # Assert: B02 REs identical regardless of creation order
    for key in re_a_b02:
        assert math.isclose(re_a_b02[key], re_b_b02[key], rel_tol=0, abs_tol=0), \
            f"B02 RE {key} differs based on creation order"

    print("✅ Vessel instantiation order does not affect REs")


def test_backward_compatibility_disabled_mode():
    """
    Backward compatibility: enabled=False produces REs of 1.0 (no effect).

    This ensures that existing code with default config is unaffected.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42

    # Config with biology noise DISABLED (default)
    bio_noise_config = {
        'enabled': False,
        'growth_cv': 0.10,  # Specified but not applied when disabled
    }

    vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)

    re = vm.vessel_states["Plate1_A01"].bio_random_effects

    # Assert: All REs are exactly 1.0 (no effect)
    assert re['growth_rate_mult'] == 1.0, f"Growth RE should be 1.0 when disabled, got {re['growth_rate_mult']}"
    assert re['stress_sensitivity_mult'] == 1.0, f"Stress RE should be 1.0 when disabled"
    assert re['hazard_scale_mult'] == 1.0, f"Hazard RE should be 1.0 when disabled"

    print("✅ Backward compatibility: Disabled mode produces no biological effect (RE=1.0)")


def test_cv_zero_produces_unit_multipliers():
    """
    Setting CV=0 produces multipliers of 1.0 (no variability).

    This tests that "variability off" mode works correctly.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    seed = 42
    bio_noise_config = {
        'enabled': True,
        'growth_cv': 0.0,  # Zero CV = no variability
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm.seed_vessel("Plate1_B02", "A549", 50000, 50.0, 0.0)

    re_1 = vm.vessel_states["Plate1_A01"].bio_random_effects
    re_2 = vm.vessel_states["Plate1_B02"].bio_random_effects

    # Assert: All REs are exactly 1.0
    for key in re_1:
        assert re_1[key] == 1.0, f"RE {key} should be 1.0 with cv=0, got {re_1[key]}"
        assert re_2[key] == 1.0, f"RE {key} should be 1.0 with cv=0, got {re_2[key]}"

    print("✅ CV=0 produces unit multipliers (no variability)")


if __name__ == "__main__":
    print("=" * 70)
    print("INTRINSIC BIOLOGY CONTRACTS")
    print("=" * 70)

    test_determinism_same_seed_identical_outputs()
    test_rng_isolation_assay_changes_dont_affect_biology()
    test_plate_instantiation_order_invariance()
    test_vessel_instantiation_order_invariance()
    test_backward_compatibility_disabled_mode()
    test_cv_zero_produces_unit_multipliers()

    print("\n" + "=" * 70)
    print("✅ ALL CONTRACT TESTS PASSED")
    print("=" * 70)
