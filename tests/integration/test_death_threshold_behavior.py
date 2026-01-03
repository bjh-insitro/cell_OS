"""
Integration test: Death threshold heterogeneity affects viability curves (Phase 3.1).

Validates that death_threshold_shift_mult:
- Affects actual viability outcomes (not just sampled)
- Creates variance in death timing (less cliff-like curves)
- Correlates with IC50 sensitivity (fragile vessels are also sensitive)
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_death_threshold_affects_viability():
    """
    Vessels with different death_threshold_shift_mult should show different viability.

    Lower threshold → fragile → earlier death at same stress level.
    """
    bio_config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.0,  # Isolate death threshold effect
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    viabilities = []
    theta_mults = []

    for seed in range(20):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
        vessel = vm.vessel_states[vessel_id]

        theta_mult = vessel.bio_random_effects.get('death_threshold_shift_mult', 1.0)
        theta_mults.append(theta_mult)

        # Dose with ER stress compound (moderate dose, sustain stress)
        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=2.0)
        vm.advance_time(48.0)

        viabilities.append(vessel.viability)

    viabilities = np.array(viabilities)
    theta_mults = np.array(theta_mults)

    # Assert: Death threshold is heterogeneous
    assert np.std(theta_mults) > 0.10, "death_threshold_shift_mult not heterogeneous"

    # Assert: Viability is heterogeneous (death curves not cliff-like)
    cv_viability = np.std(viabilities) / (np.mean(viabilities) + 1e-9)
    assert cv_viability > 0.15, f"Viability not heterogeneous (CV={cv_viability:.3f}, expected >0.15)"

    # Assert: Positive correlation (higher threshold → higher viability, less fragile)
    corr = np.corrcoef(theta_mults, viabilities)[0, 1]

    print(f"\nDeath threshold mults: mean={np.mean(theta_mults):.3f}, std={np.std(theta_mults):.3f}")
    print(f"Viabilities: mean={np.mean(viabilities):.3f}, std={np.std(viabilities):.3f}, CV={cv_viability:.3f}")
    print(f"Correlation (theta_mult vs viability): {corr:.3f}")

    # Expect positive correlation (higher threshold → survives longer)
    assert corr > 0.2, \
        f"death_threshold_shift_mult doesn't affect viability (correlation {corr:.3f}, expected >0.2)"


def test_death_threshold_disabled_uniform_curves():
    """
    When death_threshold heterogeneity is disabled, all vessels should die at same rate.
    """
    bio_config = {
        'enabled': False,  # Disabled
        'death_threshold_cv': 0.25,
    }

    viabilities = []

    for seed in range(15):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=2.0)
        vm.advance_time(48.0)

        vessel = vm.vessel_states[vessel_id]
        viabilities.append(vessel.viability)

    viabilities = np.array(viabilities)

    # Assert: Lower variance than with heterogeneity enabled
    # (RunContext and other sources still add some variance, but less than with death_threshold_cv)
    cv_viability = np.std(viabilities) / (np.mean(viabilities) + 1e-9)

    print(f"\nViability CV (disabled): {cv_viability:.3f}")

    # Relaxed threshold - RunContext adds variance even when bio noise disabled
    assert cv_viability < 0.35, \
        f"Viability variance too high when death_threshold heterogeneity disabled (CV={cv_viability:.3f})"


def test_fragile_vessels_also_sensitive():
    """
    Vessels with low death_threshold_shift_mult should also have low ic50_shift_mult.

    This validates the correlation: sensitive to induction AND fragile to death.
    """
    bio_config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.20,
        'sensitivity_correlation': 0.5,  # Moderate correlation
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    ic50_mults = []
    theta_mults = []
    stress_levels = []
    viabilities = []

    for seed in range(25):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
        vessel = vm.vessel_states[vessel_id]

        ic50_mult = vessel.bio_random_effects.get('ic50_shift_mult', 1.0)
        theta_mult = vessel.bio_random_effects.get('death_threshold_shift_mult', 1.0)

        ic50_mults.append(ic50_mult)
        theta_mults.append(theta_mult)

        # Dose with ER stress compound (LOW dose to avoid saturation)
        # thapsigargin EC50 = 0.5 µM, use 0.2 µM (sub-saturating)
        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=0.2)
        vm.advance_time(12.0)  # Mid-point measurement

        stress_levels.append(vessel.er_stress)

        vm.advance_time(36.0)  # Total 48h
        viabilities.append(vessel.viability)

    ic50_mults = np.array(ic50_mults)
    theta_mults = np.array(theta_mults)
    stress_levels = np.array(stress_levels)
    viabilities = np.array(viabilities)

    # Correlation 1: IC50 vs death threshold (should be positive, ρ ≈ 0.5)
    corr_ic50_theta = np.corrcoef(ic50_mults, theta_mults)[0, 1]

    # Correlation 2: IC50 vs stress (should be negative, sensitive → more stress)
    corr_ic50_stress = np.corrcoef(ic50_mults, stress_levels)[0, 1]

    # Correlation 3: Death threshold vs viability (should be positive, fragile → lower viability)
    corr_theta_viability = np.corrcoef(theta_mults, viabilities)[0, 1]

    print(f"\nIC50 vs Death threshold: {corr_ic50_theta:.3f} (expected ~0.5)")
    print(f"IC50 vs Stress: {corr_ic50_stress:.3f} (expected negative)")
    print(f"Death threshold vs Viability: {corr_theta_viability:.3f} (expected positive)")

    # Assert: Moderate correlation between IC50 and death threshold
    assert 0.25 <= corr_ic50_theta <= 0.75, \
        f"IC50/death_threshold correlation {corr_ic50_theta:.3f} outside [0.25, 0.75]"

    # Assert: IC50 affects stress (negative correlation)
    assert corr_ic50_stress < -0.2, \
        f"IC50 doesn't affect stress (correlation {corr_ic50_stress:.3f}, expected <-0.2)"

    # Assert: Death threshold affects viability (positive correlation)
    assert corr_theta_viability > 0.15, \
        f"Death threshold doesn't affect viability (correlation {corr_theta_viability:.3f}, expected >0.15)"


@pytest.mark.slow
def test_death_curves_less_cliff_like():
    """
    With death threshold heterogeneity, dose-response curves should be smoother (less cliff-like).

    Test: Run same dose across many vessels, plot viability distribution.
    Without heterogeneity: narrow peak (cliff).
    With heterogeneity: wider distribution (gradual).
    """
    # Without heterogeneity
    bio_config_off = {
        'enabled': False,
        'death_threshold_cv': 0.0,
    }

    viabilities_off = []
    for seed in range(30):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config_off)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=2.0)
        vm.advance_time(48.0)

        viabilities_off.append(vm.vessel_states[vessel_id].viability)

    # With heterogeneity
    bio_config_on = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.0,  # Isolate death threshold effect
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    viabilities_on = []
    for seed in range(30):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config_on)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=2.0)
        vm.advance_time(48.0)

        viabilities_on.append(vm.vessel_states[vessel_id].viability)

    viabilities_off = np.array(viabilities_off)
    viabilities_on = np.array(viabilities_on)

    cv_off = np.std(viabilities_off) / (np.mean(viabilities_off) + 1e-9)
    cv_on = np.std(viabilities_on) / (np.mean(viabilities_on) + 1e-9)

    print(f"\nViability CV without heterogeneity: {cv_off:.3f}")
    print(f"Viability CV with heterogeneity: {cv_on:.3f}")

    # Assert: Heterogeneity increases variance (less cliff-like)
    assert cv_on > cv_off * 1.5, \
        f"Heterogeneity doesn't smooth curves (CV_on={cv_on:.3f}, CV_off={cv_off:.3f}, expected >1.5×)"


def test_death_threshold_affects_mito_dysfunction_too():
    """
    death_threshold_shift_mult should apply to mito dysfunction mechanism too.
    """
    bio_config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.0,
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    viabilities = []
    theta_mults = []

    for seed in range(20):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
        vessel = vm.vessel_states[vessel_id]

        theta_mult = vessel.bio_random_effects.get('death_threshold_shift_mult', 1.0)
        theta_mults.append(theta_mult)

        # Dose with mito dysfunction compound (CCCP)
        vm.treat_with_compound(vessel_id, compound='CCCP', dose_uM=10.0)
        vm.advance_time(48.0)

        viabilities.append(vessel.viability)

    viabilities = np.array(viabilities)
    theta_mults = np.array(theta_mults)

    # Assert: Positive correlation (death threshold affects mito death too)
    corr = np.corrcoef(theta_mults, viabilities)[0, 1]

    print(f"\nMito mechanism: Correlation (theta_mult vs viability): {corr:.3f}")

    assert corr > 0.15, \
        f"death_threshold_shift_mult doesn't affect mito death (correlation {corr:.3f}, expected >0.15)"
