"""
Fast contract tests for additive floor noise (detector read noise).

Tests verify:
1. Primitive correctness (mean ~0, std ~sigma)
2. Clamp bias (positive bias at low signal due to max(0, y + noise))
3. Biology isolation (measurements vary, biology unchanged)
4. Golden-preserving behavior (sigma=0.0 → no change)

Runtime: <5 seconds (deterministic, no simulation loops)
"""

import numpy as np
import pytest
from cell_os.hardware._impl import additive_floor_noise


def test_additive_floor_primitive_correctness():
    """Primitive generates correct distribution (mean ~0, std ~sigma)."""
    rng = np.random.default_rng(42)
    sigma = 2.0
    n_samples = 10000

    samples = [additive_floor_noise(rng, sigma) for _ in range(n_samples)]

    # Mean should be near 0 (symmetric Gaussian)
    mean = np.mean(samples)
    assert abs(mean) < 0.1, f"Mean {mean:.3f} far from 0"

    # Std should be near sigma
    std = np.std(samples, ddof=1)
    assert 1.8 < std < 2.2, f"Std {std:.3f} not near sigma={sigma}"

    # Dormant mode (sigma=0) should return 0.0 without drawing
    assert additive_floor_noise(rng, 0.0) == 0.0
    assert additive_floor_noise(rng, -1.0) == 0.0


def test_additive_floor_clamp_bias():
    """Clamping at 0 creates positive bias at low signal."""
    rng = np.random.default_rng(123)
    sigma = 3.0
    y_true = 1.0  # Low signal near floor

    # Sample many noisy measurements with clamp
    n_samples = 10000
    noisy = []
    for _ in range(n_samples):
        noise = additive_floor_noise(rng, sigma)
        y_noisy = max(0.0, y_true + noise)  # Clamp at 0
        noisy.append(y_noisy)

    # Mean should be HIGHER than y_true due to clamp bias
    mean_noisy = np.mean(noisy)
    assert mean_noisy > y_true, f"Expected positive bias, got mean={mean_noisy:.3f}"

    # Bias should be substantial (sigma=3, y_true=1 → many negatives clamped)
    bias = mean_noisy - y_true
    assert bias > 0.3, f"Expected significant bias, got {bias:.3f}"

    print(f"Clamp bias test: y_true={y_true:.2f}, mean={mean_noisy:.3f}, bias={bias:.3f}")


def test_additive_floor_biology_isolation():
    """Additive noise varies measurements but doesn't affect biology."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    # Create VM with additive floor enabled
    vm = BiologicalVirtualMachine(seed=42)

    # Manually enable additive floor (overwrite YAML default)
    vm._load_cell_thalamus_params()
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 2.0
    vm.thalamus_params['technical_noise']['additive_floor_sigma_mito'] = 2.5

    # Seed vessel and treat
    vm.seed_vessel("test_well", "A549", initial_count=5000, capacity=1e6)
    vm.treat_with_compound("test_well", "tBHQ", dose_uM=10.0)
    vm.advance_time(12.0)

    vessel = vm.vessel_states["test_well"]

    # Capture biology state
    bio_before = (vessel.cell_count, vessel.viability, vessel.er_stress, vessel.mito_dysfunction)

    # Measure twice (different measurements, same biology)
    result1 = vm.cell_painting_assay("test_well")
    result2 = vm.cell_painting_assay("test_well")

    # Biology should be UNCHANGED
    bio_after = (vessel.cell_count, vessel.viability, vessel.er_stress, vessel.mito_dysfunction)
    assert bio_before == bio_after, "Measurement mutated biology (observer dependence violation)"

    # Measurements should DIFFER (additive noise is stochastic)
    morph1 = result1['morphology']
    morph2 = result2['morphology']

    # At least one channel should differ (sigma > 0 → stochastic)
    diffs = [abs(morph1[ch] - morph2[ch]) for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']]
    assert any(d > 0.5 for d in diffs), "Measurements identical despite additive noise"

    print(f"Biology isolation test: measurements differ, biology unchanged")


def test_additive_floor_golden_preserving():
    """sigma=0.0 (dormant) preserves golden file behavior."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    # Create two VMs with same seed
    vm1 = BiologicalVirtualMachine(seed=42)
    vm2 = BiologicalVirtualMachine(seed=42)

    # VM1: Default (all sigmas = 0.0)
    # VM2: Explicitly set sigmas to 0.0 (redundant but shows intent)
    vm2._load_cell_thalamus_params()
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 0.0
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_mito'] = 0.0
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_nucleus'] = 0.0
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_actin'] = 0.0
    vm2.thalamus_params['technical_noise']['additive_floor_sigma_rna'] = 0.0

    # Run identical protocol on both
    for vm in [vm1, vm2]:
        vm.seed_vessel("well_A1", "A549", initial_count=5000, capacity=1e6)
        vm.treat_with_compound("well_A1", "CCCP", dose_uM=5.0)
        vm.advance_time(24.0)

    # Measurements should be IDENTICAL (dormant mode, same seed)
    result1 = vm1.cell_painting_assay("well_A1")
    result2 = vm2.cell_painting_assay("well_A1")

    morph1 = result1['morphology']
    morph2 = result2['morphology']

    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        diff = abs(morph1[ch] - morph2[ch])
        assert diff < 1e-12, f"Channel {ch} differs by {diff:.2e} in dormant mode"

    print("Golden-preserving test: sigma=0.0 → deterministic behavior")


def test_additive_floor_rng_stream_isolation():
    """Additive floor uses only rng_assay (observer independence)."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    # Enable additive floor
    vm._load_cell_thalamus_params()
    vm.thalamus_params['technical_noise']['additive_floor_sigma_er'] = 1.5

    # Seed and advance time
    vm.seed_vessel("well_A1", "A549", initial_count=5000, capacity=1e6)
    vm.advance_time(12.0)

    # Get RNG audit before measurement
    vm.get_rng_audit(reset=True)

    # Measure (should use only rng_assay)
    vm.cell_painting_assay("well_A1")

    # Check RNG audit
    audit = vm.get_rng_audit(reset=False)

    # Only rng_assay should be called
    assert audit['assay_calls'] > 0, "rng_assay not used (expected for additive floor)"
    assert audit['growth_calls'] == 0, "rng_growth contaminated (observer independence violation)"
    assert audit['treatment_calls'] == 0, "rng_treatment contaminated"
    assert audit['operations_calls'] == 0, "rng_operations contaminated"

    print(f"RNG stream isolation test: assay_calls={audit['assay_calls']}, others=0")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
