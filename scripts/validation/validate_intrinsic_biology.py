"""
Empirical validation for intrinsic biology stochasticity.

Validates:
1. Empirical CV matches configured CV (sampling accuracy)
2. Disabled mode produces identical results to baseline (golden regression)
3. Mean preservation (mean of multipliers = 1.0)
"""

import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def validate_cv_calibration():
    """
    Test that empirical CV matches configured CV.

    Sample many vessels and verify that the empirical CV of the multipliers
    matches the requested CV (within statistical tolerance).
    """
    print("\n" + "=" * 70)
    print("VALIDATION 1: CV Calibration")
    print("=" * 70)

    seed = 42
    requested_cv = 0.10
    bio_noise_config = {
        'enabled': True,
        'growth_cv': requested_cv,
        'stress_sensitivity_cv': requested_cv,
        'hazard_scale_cv': requested_cv,
        'plate_level_fraction': 0.0,  # Pure vessel-level for easier validation
    }

    # Sample many vessels
    n_vessels = 1000
    vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)

    for i in range(n_vessels):
        vm.seed_vessel(f"Plate1_{chr(65 + i % 16)}{i:02d}", "A549", 50000, 50.0, 0.0)

    # Get RE summary
    summary = vm.get_biology_random_effects_summary()

    print(f"\nRequested CV: {requested_cv:.4f}")
    print(f"\nEmpirical statistics (n={n_vessels} vessels):")
    for key in ['growth_rate_mult', 'stress_sensitivity_mult', 'hazard_scale_mult']:
        stats = summary[key]
        mean = stats['mean']
        empirical_cv = stats['cv']
        print(f"  {key}:")
        print(f"    Mean: {mean:.6f} (expected: 1.0)")
        print(f"    CV:   {empirical_cv:.6f} (expected: {requested_cv:.4f})")

        # Validate mean preservation
        assert abs(mean - 1.0) < 0.01, f"Mean not preserved: {mean} != 1.0"

        # Validate CV matches (within 10% relative error for n=1000)
        rel_error = abs(empirical_cv - requested_cv) / requested_cv
        assert rel_error < 0.10, f"CV mismatch: empirical={empirical_cv:.4f}, expected={requested_cv:.4f}, rel_error={rel_error:.2%}"

    print("\n✅ CV calibration validated (empirical matches requested within tolerance)")


def validate_golden_regression():
    """
    Test that disabled mode produces identical results to baseline.

    Run a simple DMSO-only experiment with bio noise disabled and verify
    that cell counts match expected deterministic values.
    """
    print("\n" + "=" * 70)
    print("VALIDATION 2: Golden Regression (Disabled Mode)")
    print("=" * 70)

    seed = 42

    # Run with bio noise disabled
    bio_noise_config = {'enabled': False}
    vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
    vm.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm.advance_time(24.0)

    vessel = vm.vessel_states["Plate1_A01"]
    cell_count_disabled = vessel.cell_count
    bio_re = vessel.bio_random_effects

    print(f"\nWith bio noise DISABLED:")
    print(f"  Cell count: {cell_count_disabled:.1f}")
    print(f"  Bio REs: {bio_re}")

    # Run without bio noise config (default)
    vm_baseline = BiologicalVirtualMachine(seed=seed)
    vm_baseline.seed_vessel("Plate1_A01", "A549", 50000, 50.0, 0.0)
    vm_baseline.advance_time(24.0)

    cell_count_baseline = vm_baseline.vessel_states["Plate1_A01"].cell_count

    print(f"\nWith bio noise NOT SPECIFIED (baseline):")
    print(f"  Cell count: {cell_count_baseline:.1f}")

    # Validate: counts should be identical
    assert abs(cell_count_disabled - cell_count_baseline) < 0.01, \
        f"Disabled mode differs from baseline: {cell_count_disabled} vs {cell_count_baseline}"

    # Validate: all REs are 1.0
    for key, value in bio_re.items():
        assert value == 1.0, f"RE {key} should be 1.0 when disabled, got {value}"

    print("\n✅ Golden regression validated (disabled mode = baseline)")


def validate_variance_increase():
    """
    Test that enabling bio noise increases well-to-well variance.

    Run DMSO-only with bio noise OFF vs ON and verify that variance increases.
    """
    print("\n" + "=" * 70)
    print("VALIDATION 3: Variance Increase (Bio Noise ON vs OFF)")
    print("=" * 70)

    seed = 42
    n_wells = 48

    # Run with bio noise OFF
    vm_off = BiologicalVirtualMachine(seed=seed, bio_noise_config={'enabled': False})
    for i in range(n_wells):
        vm_off.seed_vessel(f"Plate1_{chr(65 + i // 12)}{i % 12 + 1:02d}", "A549", 50000, 50.0, 0.0)
    vm_off.advance_time(48.0)

    counts_off = [vm_off.vessel_states[vid].cell_count for vid in vm_off.vessel_states]
    cv_off = np.std(counts_off) / np.mean(counts_off)

    # Run with bio noise ON
    vm_on = BiologicalVirtualMachine(seed=seed, bio_noise_config={
        'enabled': True,
        'growth_cv': 0.10,
        'plate_level_fraction': 0.0,
    })
    for i in range(n_wells):
        vm_on.seed_vessel(f"Plate1_{chr(65 + i // 12)}{i % 12 + 1:02d}", "A549", 50000, 50.0, 0.0)
    vm_on.advance_time(48.0)

    counts_on = [vm_on.vessel_states[vid].cell_count for vid in vm_on.vessel_states]
    cv_on = np.std(counts_on) / np.mean(counts_on)

    print(f"\nCell count variability (n={n_wells} wells, 48h growth):")
    print(f"  Bio noise OFF: CV = {cv_off:.4f}")
    print(f"  Bio noise ON:  CV = {cv_on:.4f}")
    print(f"  Ratio (ON/OFF): {cv_on / cv_off:.2f}x")

    # Validate: variance increases when bio noise is enabled
    assert cv_on > cv_off, f"Bio noise ON should increase variance: {cv_on} vs {cv_off}"
    assert cv_on / cv_off > 2.0, f"Variance increase should be substantial: {cv_on / cv_off:.2f}x"

    print("\n✅ Variance increase validated (bio noise ON > OFF)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("INTRINSIC BIOLOGY STOCHASTICITY: EMPIRICAL VALIDATION")
    print("=" * 70)

    validate_cv_calibration()
    validate_golden_regression()
    validate_variance_increase()

    print("\n" + "=" * 70)
    print("✅ ALL VALIDATIONS PASSED")
    print("=" * 70)
    print("\nKey findings:")
    print("  1. Empirical CV matches requested CV (proper lognormal parameterization)")
    print("  2. Disabled mode = baseline (backward compatibility)")
    print("  3. Enabled mode increases biological variance (as intended)")
    print("\n" + "=" * 70)
