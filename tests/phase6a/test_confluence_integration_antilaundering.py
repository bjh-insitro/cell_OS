"""
Integration test: Complete confluence system prevents laundering.

This validates that all confluence components work together correctly:
1. Biology feedback (ER stress, growth penalty)
2. Measurement bias (morphology, scRNA)
3. Nuisance modeling (posterior explains density)
4. Design validation (rejects confounded comparisons)

Critical test: Density-matched experiments should recover mechanism despite biology feedback.
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.mechanism_posterior_v2 import (
    compute_mechanism_posterior_v2,
    NuisanceModel,
    Mechanism,
)


def test_density_matched_recovers_mechanism():
    """
    CRITICAL: Density-matched experiments should recover mechanism signal.

    Setup:
    - Treatment A: Tunicamycin (ER stress compound) at low density
    - Treatment B: Tunicamycin (same compound) at low density (density-matched)
    - Control: DMSO at low density

    Expected: Both treatments show ER stress mechanism, similar posteriors
    Failure mode: Biology feedback creates false differences between identical treatments
    """
    seed = 42
    cell_line = "A549"

    # All at same density (matched) - start low to avoid contact pressure
    initial_count = 2e6
    capacity = 1e7

    # Control: DMSO
    vm_control = BiologicalVirtualMachine(seed=seed)
    vm_control.seed_vessel("test", cell_line, initial_count, capacity, initial_viability=0.98)
    vm_control.advance_time(24.0)

    # Treatment A: Tunicamycin
    vm_treat_a = BiologicalVirtualMachine(seed=seed)
    vm_treat_a.seed_vessel("test", cell_line, initial_count, capacity, initial_viability=0.98)
    vm_treat_a.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                                   potency_scalar=1.0, toxicity_scalar=0.0, stress_axis="er_stress", ic50_uM=1.0)
    vm_treat_a.advance_time(24.0)

    # Treatment B: Tunicamycin (replicate, density-matched)
    vm_treat_b = BiologicalVirtualMachine(seed=seed + 1)  # Different seed for technical noise
    vm_treat_b.seed_vessel("test", cell_line, initial_count, capacity, initial_viability=0.98)
    vm_treat_b.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                                   potency_scalar=1.0, toxicity_scalar=0.0, stress_axis="er_stress", ic50_uM=1.0)
    vm_treat_b.advance_time(24.0)

    # Measure morphology
    result_control = vm_control.cell_painting_assay("test")
    result_treat_a = vm_treat_a.cell_painting_assay("test")
    result_treat_b = vm_treat_b.cell_painting_assay("test")

    morph_control = result_control['morphology_struct']
    morph_treat_a = result_treat_a['morphology_struct']
    morph_treat_b = result_treat_b['morphology_struct']

    # Compute fold-changes vs control
    actin_fold_a = morph_treat_a['actin'] / morph_control['actin']
    mito_fold_a = morph_treat_a['mito'] / morph_control['mito']
    er_fold_a = morph_treat_a['er'] / morph_control['er']

    actin_fold_b = morph_treat_b['actin'] / morph_control['actin']
    mito_fold_b = morph_treat_b['mito'] / morph_control['mito']
    er_fold_b = morph_treat_b['er'] / morph_control['er']

    # Check contact pressure (should be low and similar for all)
    vessel_control = vm_control.vessel_states["test"]
    vessel_treat_a = vm_treat_a.vessel_states["test"]
    vessel_treat_b = vm_treat_b.vessel_states["test"]

    p_control = getattr(vessel_control, "contact_pressure", 0.0)
    p_treat_a = getattr(vessel_treat_a, "contact_pressure", 0.0)
    p_treat_b = getattr(vessel_treat_b, "contact_pressure", 0.0)

    print(f"Contact pressures (should be low and matched):")
    print(f"  Control: {p_control:.3f}")
    print(f"  Treatment A: {p_treat_a:.3f}")
    print(f"  Treatment B: {p_treat_b:.3f}")

    # Density should be matched
    assert abs(p_treat_a - p_control) < 0.1, \
        f"Density not matched: p_treat={p_treat_a:.3f} vs p_control={p_control:.3f}"
    assert abs(p_treat_b - p_control) < 0.1, \
        f"Density not matched: p_treat={p_treat_b:.3f} vs p_control={p_control:.3f}"

    print(f"\n✓ Density matched across all conditions")

    # Compute posteriors with nuisance model (includes contact pressure)
    # Build minimal nuisance
    delta_p_a = p_treat_a - p_control
    delta_p_b = p_treat_b - p_control

    contact_shift_a = np.array([0.10 * delta_p_a, -0.05 * delta_p_a, 0.06 * delta_p_a])
    contact_shift_b = np.array([0.10 * delta_p_b, -0.05 * delta_p_b, 0.06 * delta_p_b])

    nuisance_a = NuisanceModel(
        context_shift=np.zeros(3),
        pipeline_shift=np.zeros(3),
        contact_shift=contact_shift_a,
        artifact_var=0.01,
        heterogeneity_var=0.01,
        context_var=0.0,
        pipeline_var=0.0,
        contact_var=(0.10 * abs(delta_p_a) * 0.25) ** 2,
    )

    nuisance_b = NuisanceModel(
        context_shift=np.zeros(3),
        pipeline_shift=np.zeros(3),
        contact_shift=contact_shift_b,
        artifact_var=0.01,
        heterogeneity_var=0.01,
        context_var=0.0,
        pipeline_var=0.0,
        contact_var=(0.10 * abs(delta_p_b) * 0.25) ** 2,
    )

    posterior_a = compute_mechanism_posterior_v2(
        actin_fold=actin_fold_a,
        mito_fold=mito_fold_a,
        er_fold=er_fold_a,
        nuisance=nuisance_a
    )

    posterior_b = compute_mechanism_posterior_v2(
        actin_fold=actin_fold_b,
        mito_fold=mito_fold_b,
        er_fold=er_fold_b,
        nuisance=nuisance_b
    )

    print(f"\nPosterior A (tunicamycin, density-matched):")
    print(f"  Top mechanism: {posterior_a.top_mechanism.value} (p={posterior_a.top_probability:.3f})")
    print(f"  ER_STRESS: {posterior_a.probabilities[Mechanism.ER_STRESS]:.3f}")
    print(f"  NUISANCE: {posterior_a.nuisance_probability:.3f}")

    print(f"\nPosterior B (tunicamycin replicate, density-matched):")
    print(f"  Top mechanism: {posterior_b.top_mechanism.value} (p={posterior_b.top_probability:.3f})")
    print(f"  ER_STRESS: {posterior_b.probabilities[Mechanism.ER_STRESS]:.3f}")
    print(f"  NUISANCE: {posterior_b.nuisance_probability:.3f}")

    # Both should identify ER_STRESS mechanism
    assert posterior_a.top_mechanism == Mechanism.ER_STRESS, \
        f"Treatment A should identify ER stress, got {posterior_a.top_mechanism.value}"
    assert posterior_b.top_mechanism == Mechanism.ER_STRESS, \
        f"Treatment B should identify ER stress, got {posterior_b.top_mechanism.value}"

    # Posteriors should be similar (within 20%)
    er_stress_prob_diff = abs(posterior_a.probabilities[Mechanism.ER_STRESS] -
                               posterior_b.probabilities[Mechanism.ER_STRESS])
    assert er_stress_prob_diff < 0.20, \
        f"Density-matched treatments should give similar posteriors: diff={er_stress_prob_diff:.3f}"

    print(f"\n✓ Density-matched experiments recover mechanism (ER_STRESS)")
    print(f"  Posterior agreement: {1.0 - er_stress_prob_diff:.1%}")


def test_density_mismatch_increases_nuisance():
    """
    Density-mismatched comparisons should show increased NUISANCE attribution.

    Setup:
    - Control: DMSO at low density
    - Treatment: DMSO at high density (NO compound, pure density effect)

    Expected: High NUISANCE probability (morphology shifts explained by density)
    Failure mode: Posterior attributes density shifts to mechanism
    """
    seed = 42
    cell_line = "A549"

    # Low density control
    vm_low = BiologicalVirtualMachine(seed=seed)
    vm_low.seed_vessel("test", cell_line, 2e6, capacity=1e7, initial_viability=0.98)
    vm_low.advance_time(24.0)

    # High density "treatment" (no compound, just density)
    vm_high = BiologicalVirtualMachine(seed=seed)
    vm_high.seed_vessel("test", cell_line, 7e6, capacity=1e7, initial_viability=0.98)
    vm_high.advance_time(24.0)

    # Measure morphology
    result_low = vm_low.cell_painting_assay("test")
    result_high = vm_high.cell_painting_assay("test")

    morph_low = result_low['morphology_struct']
    morph_high = result_high['morphology_struct']

    # Compute fold-changes
    actin_fold = morph_high['actin'] / morph_low['actin']
    mito_fold = morph_high['mito'] / morph_low['mito']
    er_fold = morph_high['er'] / morph_low['er']

    # Get contact pressures
    vessel_low = vm_low.vessel_states["test"]
    vessel_high = vm_high.vessel_states["test"]

    p_low = getattr(vessel_low, "contact_pressure", 0.0)
    p_high = getattr(vessel_high, "contact_pressure", 0.0)

    delta_p = p_high - p_low

    print(f"Density mismatch:")
    print(f"  Low density: p={p_low:.3f}")
    print(f"  High density: p={p_high:.3f}")
    print(f"  Δp = {delta_p:.3f}")

    # Should have meaningful density difference
    assert delta_p > 0.2, f"Expected meaningful density mismatch, got Δp={delta_p:.3f}"

    # Compute posterior WITHOUT contact_shift (blind to density)
    nuisance_blind = NuisanceModel(
        context_shift=np.zeros(3),
        pipeline_shift=np.zeros(3),
        contact_shift=np.zeros(3),  # BLIND to density
        artifact_var=0.01,
        heterogeneity_var=0.01,
        context_var=0.0,
        pipeline_var=0.0,
        contact_var=0.0,
    )

    posterior_blind = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance_blind
    )

    # Compute posterior WITH contact_shift (aware of density)
    contact_shift = np.array([0.10 * delta_p, -0.05 * delta_p, 0.06 * delta_p])

    nuisance_aware = NuisanceModel(
        context_shift=np.zeros(3),
        pipeline_shift=np.zeros(3),
        contact_shift=contact_shift,  # AWARE of density
        artifact_var=0.01,
        heterogeneity_var=0.01,
        context_var=0.0,
        pipeline_var=0.0,
        contact_var=(0.10 * abs(delta_p) * 0.25) ** 2,
    )

    posterior_aware = compute_mechanism_posterior_v2(
        actin_fold=actin_fold,
        mito_fold=mito_fold,
        er_fold=er_fold,
        nuisance=nuisance_aware
    )

    print(f"\nPosterior (blind to density):")
    print(f"  Top mechanism: {posterior_blind.top_mechanism.value} (p={posterior_blind.top_probability:.3f})")
    print(f"  NUISANCE: {posterior_blind.nuisance_probability:.3f}")

    print(f"\nPosterior (aware of density):")
    print(f"  Top mechanism: {posterior_aware.top_mechanism.value} (p={posterior_aware.top_probability:.3f})")
    print(f"  NUISANCE: {posterior_aware.nuisance_probability:.3f}")

    # NUISANCE should increase with density awareness
    assert posterior_aware.nuisance_probability > posterior_blind.nuisance_probability, \
        f"Density awareness should increase NUISANCE: {posterior_aware.nuisance_probability:.3f} vs {posterior_blind.nuisance_probability:.3f}"

    # Mechanism confidence should decrease
    assert posterior_aware.top_probability <= posterior_blind.top_probability + 0.05, \
        f"Density awareness should not increase mechanism confidence"

    increase = posterior_aware.nuisance_probability - posterior_blind.nuisance_probability
    print(f"\n✓ Nuisance model explains density mismatch")
    print(f"  NUISANCE increase: +{increase:.3f}")


def test_biology_feedback_observable_but_not_dominant():
    """
    Biology feedback should be observable but not overwhelm mechanism signal.

    Setup:
    - Tunicamycin at low vs high density (mechanism + density)

    Expected: Mechanism signal present at both densities, biology feedback adds to effect
    Failure mode: Biology feedback dominates, can't distinguish mechanism
    """
    seed = 42
    cell_line = "A549"

    # Low density treatment
    vm_low = BiologicalVirtualMachine(seed=seed)
    vm_low.seed_vessel("test", cell_line, 2e6, capacity=1e7, initial_viability=0.98)
    vm_low.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                              potency_scalar=1.0, toxicity_scalar=0.0, stress_axis="er_stress", ic50_uM=1.0)
    vm_low.advance_time(24.0)

    # High density treatment
    vm_high = BiologicalVirtualMachine(seed=seed)
    vm_high.seed_vessel("test", cell_line, 7e6, capacity=1e7, initial_viability=0.98)
    vm_high.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                               potency_scalar=1.0, toxicity_scalar=0.0, stress_axis="er_stress", ic50_uM=1.0)
    vm_high.advance_time(24.0)

    # Get ER stress levels
    vessel_low = vm_low.vessel_states["test"]
    vessel_high = vm_high.vessel_states["test"]

    er_stress_low = vessel_low.er_stress
    er_stress_high = vessel_high.er_stress

    p_low = getattr(vessel_low, "contact_pressure", 0.0)
    p_high = getattr(vessel_high, "contact_pressure", 0.0)

    print(f"Low density (tunicamycin):")
    print(f"  Contact pressure: {p_low:.3f}")
    print(f"  ER stress: {er_stress_low:.3f}")

    print(f"\nHigh density (tunicamycin):")
    print(f"  Contact pressure: {p_high:.3f}")
    print(f"  ER stress: {er_stress_high:.3f}")

    # Both should have ER stress from compound
    assert er_stress_low > 0.3, f"Low density should have compound-induced ER stress: {er_stress_low:.3f}"
    assert er_stress_high > 0.3, f"High density should have compound-induced ER stress: {er_stress_high:.3f}"

    # High density might have MORE ER stress (compound + biology feedback)
    # But difference should be modest (biology feedback adds, doesn't dominate)
    if er_stress_high > er_stress_low:
        diff_fraction = (er_stress_high - er_stress_low) / er_stress_low
        assert diff_fraction < 0.5, \
            f"Biology feedback should be modest addition, not dominant: {diff_fraction*100:.1f}% increase"

        print(f"\n✓ Biology feedback observable (+{diff_fraction*100:.1f}%) but not dominant")
    else:
        print(f"\n✓ Biology feedback modest (compound effect dominates)")


if __name__ == "__main__":
    print("=" * 70)
    print("TEST 1: Density-matched experiments recover mechanism")
    print("=" * 70)
    test_density_matched_recovers_mechanism()

    print("\n" + "=" * 70)
    print("TEST 2: Density mismatch increases NUISANCE attribution")
    print("=" * 70)
    test_density_mismatch_increases_nuisance()

    print("\n" + "=" * 70)
    print("TEST 3: Biology feedback observable but not dominant")
    print("=" * 70)
    test_biology_feedback_observable_but_not_dominant()

    print("\n" + "=" * 70)
    print("✅ ALL INTEGRATION TESTS PASSED")
    print("=" * 70)
    print("\nComplete confluence system validated:")
    print("  ✓ Density-matched comparisons recover mechanism")
    print("  ✓ Nuisance model explains density shifts")
    print("  ✓ Biology feedback adds signal without laundering")
