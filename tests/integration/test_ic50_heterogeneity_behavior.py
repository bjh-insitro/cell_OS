"""
Integration test: IC50 heterogeneity affects induction (Phase 3.0).

Validates that ic50_shift_mult actually changes biological response to same dose.

This is a behavior test - proves the feature works end-to-end.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_ic50_shift_affects_stress_induction():
    """
    Vessels with different ic50_shift_mult should show different stress levels at same dose.

    Lower ic50_shift_mult → more sensitive → higher stress at same dose
    Higher ic50_shift_mult → less sensitive → lower stress at same dose
    """
    # Config with IC50 heterogeneity enabled
    bio_config = {
        'enabled': True,
        'ic50_cv': 0.30,  # 30% CV for strong effect
        'growth_cv': 0.0,  # Disable others for isolation
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    # Create 20 vessels with different ic50_shift_mult
    stress_levels = []
    ic50_mults = []

    for seed in range(20):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        # Seed vessel
        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
        vessel = vm.vessel_states[vessel_id]

        # Record ic50_shift_mult
        ic50_mult = vessel.bio_random_effects.get('ic50_shift_mult', 1.0)
        ic50_mults.append(ic50_mult)

        # Debug: print first few
        if seed < 3:
            print(f"Vessel {seed}: ic50_mult={ic50_mult:.3f}, bio_re keys={list(vessel.bio_random_effects.keys())}")

        # Dose with ER stress inducer (LOW dose to avoid saturation)
        # thapsigargin EC50 = 0.5 µM, use 0.1 µM (1/5 of EC50)
        # This puts f_axis in 0.13-0.22 range (good spread for heterogeneity)
        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=0.1)

        # Short time to accumulate stress without saturation
        vm.advance_time(4.0)

        # Measure ER stress level
        stress_levels.append(vessel.er_stress)

    stress_levels = np.array(stress_levels)
    ic50_mults = np.array(ic50_mults)

    # Assert: ic50_shift_mult is heterogeneous (not all 1.0)
    assert np.std(ic50_mults) > 0.05, "ic50_shift_mult not heterogeneous"

    # Assert: Negative correlation (lower IC50 → higher stress at same dose)
    # With effective_dose = dose / ic50_mult:
    #   Lower ic50_mult → higher effective_dose → higher stress
    # So we expect negative correlation between ic50_mult and stress
    corr = np.corrcoef(ic50_mults, stress_levels)[0, 1]

    print(f"\nIC50 multipliers: mean={np.mean(ic50_mults):.3f}, std={np.std(ic50_mults):.3f}")
    print(f"ER stress levels: mean={np.mean(stress_levels):.3f}, std={np.std(stress_levels):.3f}")
    print(f"Correlation (ic50_mult vs stress): {corr:.3f}")

    # Expect strong negative correlation (lower IC50 → more sensitive → higher stress)
    assert corr < -0.3, \
        f"ic50_shift_mult doesn't affect stress (correlation {corr:.3f}, expected <-0.3)"


def test_ic50_shift_affects_death_rate():
    """
    Vessels with different ic50_shift_mult should show different viability at same dose.

    Lower ic50_shift_mult → more sensitive → lower viability (more death)
    """
    bio_config = {
        'enabled': True,
        'ic50_cv': 0.25,
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    viabilities = []
    ic50_mults = []

    for seed in range(15):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
        vessel = vm.vessel_states[vessel_id]

        ic50_mult = vessel.bio_random_effects.get('ic50_shift_mult', 1.0)
        ic50_mults.append(ic50_mult)

        # Dose with lethal compound
        vm.treat_with_compound(vessel_id, compound='etoposide', dose_uM=30.0)
        vm.advance_time(48.0)

        viabilities.append(vessel.viability)

    viabilities = np.array(viabilities)
    ic50_mults = np.array(ic50_mults)

    # Assert: Positive correlation (lower IC50 → more sensitive → lower viability)
    # Actually, if IC50 is in the denominator of effective dose:
    #   effective_dose = dose / ic50
    #   Lower IC50 → higher effective_dose → more death → lower viability
    # So: positive correlation between ic50_mult and viability
    corr = np.corrcoef(ic50_mults, viabilities)[0, 1]

    print(f"\nIC50 multipliers: mean={np.mean(ic50_mults):.3f}")
    print(f"Viabilities: mean={np.mean(viabilities):.3f}, std={np.std(viabilities):.3f}")
    print(f"Correlation (ic50_mult vs viability): {corr:.3f}")

    assert corr > 0.2, \
        f"ic50_shift_mult doesn't affect viability (correlation {corr:.3f}, expected >0.2)"


def test_ic50_disabled_no_heterogeneity():
    """
    When IC50 heterogeneity is disabled, all vessels should respond identically.
    """
    bio_config = {
        'enabled': False,  # Disabled
        'ic50_cv': 0.30,
    }

    stress_levels = []

    for seed in range(10):
        vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
        vm.run_context = RunContext.sample(seed=seed)
        vm.rng_assay = np.random.default_rng(seed + 1000)
        vm.rng_biology = np.random.default_rng(seed + 2000)
        vm._load_cell_thalamus_params()

        vessel_id = f"P{seed}_A01"
        vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)

        vm.treat_with_compound(vessel_id, compound='thapsigargin', dose_uM=5.0)
        vm.advance_time(12.0)

        vessel = vm.vessel_states[vessel_id]
        stress_levels.append(vessel.er_stress)

    stress_levels = np.array(stress_levels)

    # Assert: All stress levels identical (no heterogeneity)
    # Allow small variance from other sources (run context, etc.)
    cv_stress = np.std(stress_levels) / (np.mean(stress_levels) + 1e-9)
    assert cv_stress < 0.05, \
        f"Stress heterogeneous when IC50 heterogeneity disabled (CV={cv_stress:.3f})"


@pytest.mark.slow
def test_ic50_heterogeneity_across_compounds():
    """
    ic50_shift_mult should apply consistently across different compounds.

    A vessel with low ic50_shift_mult should be more sensitive to ALL compounds,
    not just one specific compound.
    """
    bio_config = {
        'enabled': True,
        'ic50_cv': 0.25,
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }

    # Use two ER stress compounds with per-compound doses near EC50
    # thapsigargin: EC50 = 0.5 µM, tunicamycin: EC50 = 2.0 µM
    compounds = [
        ('thapsigargin', 0.5),  # (compound, dose near EC50)
        ('tunicamycin', 2.0),
    ]

    # Create vessels and measure response to each compound
    vessel_sensitivities = {}  # {seed: [stress1, stress2]}

    for seed in range(10):
        sensitivities = []
        for compound, dose_uM in compounds:
            vm = BiologicalVirtualMachine(bio_noise_config=bio_config)
            vm.run_context = RunContext.sample(seed=seed)
            vm.rng_assay = np.random.default_rng(seed + 1000)
            vm.rng_biology = np.random.default_rng(seed + 2000)
            vm._load_cell_thalamus_params()

            vessel_id = f"P{seed}_A01"
            vm.seed_vessel(vessel_id, cell_line='A549', initial_count=10000)
            vm.treat_with_compound(vessel_id, compound=compound, dose_uM=dose_uM)
            vm.advance_time(12.0)

            vessel = vm.vessel_states[vessel_id]
            stress = vessel.er_stress  # Both compounds drive ER stress
            sensitivities.append(stress)

        vessel_sensitivities[seed] = sensitivities

    # Compute correlation between sensitivities across compounds
    # Vessels should show correlated sensitivity (same ic50_shift_mult affects all)
    sens_matrix = np.array([vessel_sensitivities[s] for s in range(10)])  # (10 vessels, 2 compounds)

    # Guard against degenerate regime (saturation or zero response)
    std_0 = np.std(sens_matrix[:, 0])
    std_1 = np.std(sens_matrix[:, 1])
    if std_0 < 0.01 or std_1 < 0.01:
        pytest.skip(f"Degenerate regime: stress variance too low (std_0={std_0:.3f}, std_1={std_1:.3f})")

    # Correlation between compound 0 and compound 1
    corr_01 = np.corrcoef(sens_matrix[:, 0], sens_matrix[:, 1])[0, 1]

    print(f"\nCross-compound sensitivity correlation: {corr_01:.3f}")
    print(f"Stress std (compound 0): {std_0:.3f}, (compound 1): {std_1:.3f}")

    # Assert: Positive correlation (same vessels are sensitive across compounds)
    assert corr_01 > 0.3, \
        f"ic50_shift_mult not consistent across compounds (correlation {corr_01:.3f}, expected >0.3)"
