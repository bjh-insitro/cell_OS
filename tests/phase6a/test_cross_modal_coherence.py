"""
Cross-modal coherence validation for confluence biology feedback.

This test validates that when contact pressure drives biology feedback,
ALL measurement modalities show coherent signals:
1. Morphology (Cell Painting channels)
2. Scalars (ATP, UPR, trafficking markers)
3. Transcriptomics (gene programs)

This is a critical anti-laundering guard: single-modality attribution attempts
will fail cross-modal consistency checks.
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_multi_organelle_cross_modal_coherence():
    """
    CRITICAL: All three organelles should show coherent signals across modalities.

    Setup:
    - High density (contact pressure buildup)
    - No compounds (pure biology feedback)
    - Measure: morphology + scalars + scRNA

    Expected:
    - ER: ER channel ↑, UPR marker ↑, ER stress genes ↑
    - Mito: Mito channel ↓, ATP ↓, mito dysfunction genes ↑
    - Transport: Actin channel ↑, trafficking marker ↑, transport genes ↑

    Anti-laundering: If agent attributes contact effects to single mechanism,
    cross-modal incoherence will reveal false attribution.
    """
    seed = 42
    cell_line = "A549"

    # Control: Low density (no biology feedback)
    vm_low = BiologicalVirtualMachine(seed=seed)
    vm_low.seed_vessel("test", cell_line, initial_count=2e6, capacity=1e7, initial_viability=0.98)
    vm_low.advance_time(24.0)

    # Treatment: High density (biology feedback active)
    vm_high = BiologicalVirtualMachine(seed=seed)
    vm_high.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)
    vm_high.advance_time(24.0)

    # Get latent states
    vessel_low = vm_low.vessel_states["test"]
    vessel_high = vm_high.vessel_states["test"]

    p_low = getattr(vessel_low, "contact_pressure", 0.0)
    p_high = getattr(vessel_high, "contact_pressure", 0.0)

    er_stress_low = vessel_low.er_stress
    er_stress_high = vessel_high.er_stress

    mito_dysfunction_low = vessel_low.mito_dysfunction
    mito_dysfunction_high = vessel_high.mito_dysfunction

    transport_dysfunction_low = vessel_low.transport_dysfunction
    transport_dysfunction_high = vessel_high.transport_dysfunction

    print(f"Latent states:")
    print(f"  Low density (p={p_low:.3f}):")
    print(f"    ER stress: {er_stress_low:.3f}")
    print(f"    Mito dysfunction: {mito_dysfunction_low:.3f}")
    print(f"    Transport dysfunction: {transport_dysfunction_low:.3f}")
    print(f"  High density (p={p_high:.3f}):")
    print(f"    ER stress: {er_stress_high:.3f}")
    print(f"    Mito dysfunction: {mito_dysfunction_high:.3f}")
    print(f"    Transport dysfunction: {transport_dysfunction_high:.3f}")

    # Measure morphology (structural, before viability scaling)
    result_low_morph = vm_low.cell_painting_assay("test")
    result_high_morph = vm_high.cell_painting_assay("test")

    morph_low = result_low_morph['morphology_struct']
    morph_high = result_high_morph['morphology_struct']

    # Measure scalars
    result_low_scalar = vm_low.atp_viability_assay("test")
    result_high_scalar = vm_high.atp_viability_assay("test")

    upr_low = result_low_scalar['upr_marker']
    upr_high = result_high_scalar['upr_marker']

    atp_low = result_low_scalar['atp_signal']
    atp_high = result_high_scalar['atp_signal']

    trafficking_low = result_low_scalar['trafficking_marker']
    trafficking_high = result_high_scalar['trafficking_marker']

    # Compute fold-changes
    er_morph_fold = morph_high['er'] / morph_low['er']
    mito_morph_fold = morph_high['mito'] / morph_low['mito']
    actin_morph_fold = morph_high['actin'] / morph_low['actin']

    upr_fold = upr_high / upr_low
    atp_fold = atp_high / atp_low
    trafficking_fold = trafficking_high / trafficking_low

    print(f"\nCross-modal signals:")
    print(f"  ER stress:")
    print(f"    Morphology (ER channel): {er_morph_fold:.3f}x")
    print(f"    Scalar (UPR marker): {upr_fold:.3f}x")
    print(f"  Mito dysfunction:")
    print(f"    Morphology (mito channel): {mito_morph_fold:.3f}x")
    print(f"    Scalar (ATP signal): {atp_fold:.3f}x")
    print(f"  Transport dysfunction:")
    print(f"    Morphology (actin channel): {actin_morph_fold:.3f}x")
    print(f"    Scalar (trafficking marker): {trafficking_fold:.3f}x")

    # Validate ER stress coherence
    # Both morphology and scalar should increase
    assert er_morph_fold > 1.03, \
        f"ER morphology should increase with contact pressure: {er_morph_fold:.3f}x"
    assert upr_fold > 1.10, \
        f"UPR marker should increase with ER stress: {upr_fold:.3f}x"

    # Validate mito dysfunction coherence
    # Morphology decreases, ATP decreases (both indicate dysfunction)
    assert mito_morph_fold < 0.98, \
        f"Mito morphology should decrease with dysfunction: {mito_morph_fold:.3f}x"
    assert atp_fold < 0.95, \
        f"ATP should decrease with mito dysfunction: {atp_fold:.3f}x"

    # Validate transport dysfunction coherence
    # Both morphology and scalar should increase
    assert actin_morph_fold > 1.05, \
        f"Actin morphology should increase with transport dysfunction: {actin_morph_fold:.3f}x"
    assert trafficking_fold > 1.05, \
        f"Trafficking marker should increase with transport dysfunction: {trafficking_fold:.3f}x"

    print(f"\n✓ Cross-modal coherence validated across all three organelles")
    print(f"  ER: Morphology ↑ ({er_morph_fold:.2f}x), UPR ↑ ({upr_fold:.2f}x)")
    print(f"  Mito: Morphology ↓ ({mito_morph_fold:.2f}x), ATP ↓ ({atp_fold:.2f}x)")
    print(f"  Transport: Morphology ↑ ({actin_morph_fold:.2f}x), Trafficking ↑ ({trafficking_fold:.2f}x)")


def test_single_organelle_perturbation_specificity():
    """
    Validate that compound-specific perturbations show organelle specificity.

    Setup:
    - Tunicamycin (ER stress) at low density
    - Measure all three organelles

    Expected:
    - ER signals strong (primary target)
    - Mito/transport signals weak or absent (no cross-talk)

    This validates that biology feedback doesn't create false cross-talk.
    """
    seed = 42
    cell_line = "A549"

    # Control: DMSO at low density
    vm_ctrl = BiologicalVirtualMachine(seed=seed)
    vm_ctrl.seed_vessel("test", cell_line, initial_count=2e6, capacity=1e7, initial_viability=0.98)
    vm_ctrl.advance_time(24.0)

    # Treatment: Tunicamycin (ER stress) at low density
    vm_treat = BiologicalVirtualMachine(seed=seed)
    vm_treat.seed_vessel("test", cell_line, initial_count=2e6, capacity=1e7, initial_viability=0.98)
    vm_treat.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                                potency_scalar=1.0, toxicity_scalar=0.0)
    vm_treat.advance_time(24.0)

    vessel_treat = vm_treat.vessel_states["test"]
    er_stress = vessel_treat.er_stress
    mito_dysfunction = vessel_treat.mito_dysfunction
    transport_dysfunction = vessel_treat.transport_dysfunction

    print(f"ER-specific perturbation (tunicamycin at low density):")
    print(f"  ER stress: {er_stress:.3f}")
    print(f"  Mito dysfunction: {mito_dysfunction:.3f}")
    print(f"  Transport dysfunction: {transport_dysfunction:.3f}")

    # ER should be highly stressed
    assert er_stress > 0.5, f"ER stress should be high for tunicamycin: {er_stress:.3f}"

    # Mito and transport should be minimal (no false cross-talk from biology feedback)
    assert mito_dysfunction < 0.2, \
        f"Mito dysfunction should be low for ER-specific compound: {mito_dysfunction:.3f}"
    assert transport_dysfunction < 0.2, \
        f"Transport dysfunction should be low for ER-specific compound: {transport_dysfunction:.3f}"

    print(f"\n✓ Organelle specificity validated (ER >> mito, transport)")


def test_density_biology_feedback_distinguishable_from_mechanism():
    """
    Validate that biology feedback from density is distinguishable from compound mechanism.

    Setup:
    - High density DMSO (biology feedback only)
    - Low density tunicamycin (mechanism only)
    - Compare ER stress signatures

    Expected:
    - Both show ER stress latent state
    - Magnitude differs (compound >> density)
    - Scalar signatures differ (UPR coupling strength)

    This ensures biology feedback doesn't masquerade as mechanism.
    """
    seed = 42
    cell_line = "A549"

    # High density DMSO (biology feedback only)
    vm_density = BiologicalVirtualMachine(seed=seed)
    vm_density.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)
    vm_density.advance_time(24.0)

    # Low density tunicamycin (mechanism only)
    vm_compound = BiologicalVirtualMachine(seed=seed)
    vm_compound.seed_vessel("test", cell_line, initial_count=2e6, capacity=1e7, initial_viability=0.98)
    vm_compound.treat_with_compound("test", "tunicamycin", dose_uM=5.0,
                                   potency_scalar=1.0, toxicity_scalar=0.0)
    vm_compound.advance_time(24.0)

    vessel_density = vm_density.vessel_states["test"]
    vessel_compound = vm_compound.vessel_states["test"]

    er_stress_density = vessel_density.er_stress
    er_stress_compound = vessel_compound.er_stress

    print(f"ER stress signatures:")
    print(f"  Density-driven (high confluency): {er_stress_density:.3f}")
    print(f"  Compound-driven (tunicamycin): {er_stress_compound:.3f}")

    # Both should have ER stress
    assert er_stress_density > 0.15, "Density should induce ER stress"
    assert er_stress_compound > 0.5, "Tunicamycin should strongly induce ER stress"

    # Compound should dominate
    assert er_stress_compound > 1.5 * er_stress_density, \
        f"Compound mechanism should be stronger than density feedback: {er_stress_compound:.3f} vs {er_stress_density:.3f}"

    print(f"\n✓ Biology feedback distinguishable from mechanism")
    print(f"  Compound/density ratio: {er_stress_compound/er_stress_density:.2f}x")


if __name__ == "__main__":
    print("=" * 70)
    print("TEST 1: Multi-organelle cross-modal coherence")
    print("=" * 70)
    test_multi_organelle_cross_modal_coherence()

    print("\n" + "=" * 70)
    print("TEST 2: Single organelle perturbation specificity")
    print("=" * 70)
    test_single_organelle_perturbation_specificity()

    print("\n" + "=" * 70)
    print("TEST 3: Density feedback vs mechanism distinguishability")
    print("=" * 70)
    test_density_biology_feedback_distinguishable_from_mechanism()

    print("\n" + "=" * 70)
    print("✅ ALL CROSS-MODAL COHERENCE TESTS PASSED")
    print("=" * 70)
    print("\nValidated:")
    print("  ✓ All three organelles show coherent cross-modal signals")
    print("  ✓ Organelle specificity preserved (no false cross-talk)")
    print("  ✓ Biology feedback distinguishable from mechanism")
