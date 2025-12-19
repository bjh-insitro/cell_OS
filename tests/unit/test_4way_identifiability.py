"""
4-way identifiability test for Phase 2 completion.

Verifies that Control, ER stress, Mito dysfunction, and Transport dysfunction
can be distinguished from each other using readout patterns.

Pass criteria: >85% separation accuracy at 12h using directional signatures.
"""

import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_4way_identifiability():
    """
    4-way identifiability: Control vs ER vs Mito vs Transport.

    Uses directional signatures to distinguish latent states:
    - Control: All channels near baseline
    - ER stress: ER channel UP, UPR UP, others stable
    - Mito dysfunction: Mito channel DOWN, ATP DOWN, others stable
    - Transport dysfunction: Actin channel UP, trafficking marker UP, others stable

    Pass criteria: Each condition's primary signature should be >2× stronger
    than cross-talk from other conditions.
    """
    print("\n=== 4-Way Identifiability Test ===")

    # Setup four conditions
    conditions = {
        'Control': None,
        'ER stress': ('tunicamycin', 0.5),
        'Mito dysfunction': ('cccp', 1.0),
        'Transport dysfunction': ('paclitaxel', 0.005)
    }

    results = {}

    for condition_name, treatment in conditions.items():
        vm = BiologicalVirtualMachine(seed=42)
        vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

        # Baseline measurement
        baseline_morph = vm.cell_painting_assay("test")
        baseline_scalars = vm.atp_viability_assay("test")

        # Apply treatment if not control
        if treatment is not None:
            compound, dose = treatment
            vm.treat_with_compound("test", compound, dose_uM=dose)

        # Advance time
        vm.advance_time(12.0)

        # Measure readouts
        morph = vm.cell_painting_assay("test")
        scalars = vm.atp_viability_assay("test")
        vessel = vm.vessel_states["test"]

        # Use STRUCTURAL morphology (latent-driven, before viability scaling)
        morph_struct = morph['morphology_struct']
        baseline_struct = baseline_morph['morphology_struct']

        # Compute relative changes
        er_change = (morph_struct['er'] - baseline_struct['er']) / baseline_struct['er']
        mito_change = (morph_struct['mito'] - baseline_struct['mito']) / baseline_struct['mito']
        actin_change = (morph_struct['actin'] - baseline_struct['actin']) / baseline_struct['actin']

        upr_change = (scalars['upr_marker'] - baseline_scalars['upr_marker']) / baseline_scalars['upr_marker']
        atp_change = (scalars['atp_signal'] - baseline_scalars['atp_signal']) / baseline_scalars['atp_signal']
        trafficking_change = (scalars['trafficking_marker'] - baseline_scalars['trafficking_marker']) / baseline_scalars['trafficking_marker']

        results[condition_name] = {
            'er_change': er_change,
            'mito_change': mito_change,
            'actin_change': actin_change,
            'upr_change': upr_change,
            'atp_change': atp_change,
            'trafficking_change': trafficking_change,
            'viability': vessel.viability,
            'er_stress': vessel.er_stress,
            'mito_dysfunction': vessel.mito_dysfunction,
            'transport_dysfunction': vessel.transport_dysfunction
        }

    # Print results table
    print("\n=== Readout Changes (Structural Features) ===")
    print(f"{'Condition':<25} {'ER':>8} {'Mito':>8} {'Actin':>8} {'UPR':>8} {'ATP':>8} {'Traffic':>8} {'Viab':>6}")
    print("-" * 95)

    for condition_name, data in results.items():
        print(f"{condition_name:<25} "
              f"{data['er_change']:>7.1%} "
              f"{data['mito_change']:>7.1%} "
              f"{data['actin_change']:>7.1%} "
              f"{data['upr_change']:>7.1%} "
              f"{data['atp_change']:>7.1%} "
              f"{data['trafficking_change']:>7.1%} "
              f"{data['viability']:>6.2f}")

    print("\n=== Latent States ===")
    print(f"{'Condition':<25} {'ER Stress':>12} {'Mito Dys':>12} {'Transport':>12}")
    print("-" * 65)

    for condition_name, data in results.items():
        print(f"{condition_name:<25} "
              f"{data['er_stress']:>12.3f} "
              f"{data['mito_dysfunction']:>12.3f} "
              f"{data['transport_dysfunction']:>12.3f}")

    # Identifiability checks
    print("\n=== Identifiability Checks ===")

    # 1. Control: minimal changes
    control = results['Control']
    max_control_change = max(
        abs(control['er_change']),
        abs(control['mito_change']),
        abs(control['actin_change']),
        abs(control['upr_change']),
        abs(control['atp_change']),
        abs(control['trafficking_change'])
    )
    print(f"Control max drift: {max_control_change:.1%} (should be <25%)")
    assert max_control_change < 0.25, f"Control drift too high: {max_control_change:.1%}"

    # 2. ER stress: ER channel + UPR should dominate
    er_data = results['ER stress']
    er_primary = max(abs(er_data['er_change']), abs(er_data['upr_change']))
    er_crosstalk = max(
        abs(er_data['mito_change']),
        abs(er_data['actin_change']),
        abs(er_data['atp_change']),
        abs(er_data['trafficking_change'])
    )
    er_separation = er_primary / max(0.01, er_crosstalk)
    print(f"ER stress separation: {er_separation:.1f}× (primary vs crosstalk, should be >2×)")
    assert er_separation > 2.0, f"ER stress not separable: {er_separation:.1f}×"

    # 3. Mito dysfunction: Mito channel + ATP should dominate
    mito_data = results['Mito dysfunction']
    mito_primary = max(abs(mito_data['mito_change']), abs(mito_data['atp_change']))
    mito_crosstalk = max(
        abs(mito_data['er_change']),
        abs(mito_data['actin_change']),
        abs(mito_data['upr_change']),
        abs(mito_data['trafficking_change'])
    )
    mito_separation = mito_primary / max(0.01, mito_crosstalk)
    print(f"Mito dysfunction separation: {mito_separation:.1f}× (primary vs crosstalk, should be >2×)")
    assert mito_separation > 2.0, f"Mito dysfunction not separable: {mito_separation:.1f}×"

    # 4. Transport dysfunction: Actin channel + trafficking marker should dominate
    transport_data = results['Transport dysfunction']
    transport_primary = max(abs(transport_data['actin_change']), abs(transport_data['trafficking_change']))
    transport_crosstalk = max(
        abs(transport_data['er_change']),
        abs(transport_data['mito_change']),
        abs(transport_data['upr_change']),
        abs(transport_data['atp_change'])
    )
    transport_separation = transport_primary / max(0.01, transport_crosstalk)
    print(f"Transport dysfunction separation: {transport_separation:.1f}× (primary vs crosstalk, should be >2×)")
    assert transport_separation > 2.0, f"Transport dysfunction not separable: {transport_separation:.1f}×"

    # 5. Directional signatures
    print("\n=== Directional Signatures ===")
    print(f"ER stress: ER {'+' if er_data['er_change'] > 0 else '-'}, UPR {'+' if er_data['upr_change'] > 0 else '-'}")
    print(f"Mito dysfunction: Mito {'+' if mito_data['mito_change'] > 0 else '-'}, ATP {'+' if mito_data['atp_change'] > 0 else '-'}")
    print(f"Transport dysfunction: Actin {'+' if transport_data['actin_change'] > 0 else '-'}, Trafficking {'+' if transport_data['trafficking_change'] > 0 else '-'}")

    # Check directions are correct
    assert er_data['er_change'] > 0.10, f"ER channel should increase with ER stress: {er_data['er_change']:.1%}"
    assert er_data['upr_change'] > 0.10, f"UPR should increase with ER stress: {er_data['upr_change']:.1%}"

    assert mito_data['mito_change'] < -0.10, f"Mito channel should decrease with mito dysfunction: {mito_data['mito_change']:.1%}"
    assert mito_data['atp_change'] < -0.10, f"ATP should decrease with mito dysfunction: {mito_data['atp_change']:.1%}"

    assert transport_data['actin_change'] > 0.10, f"Actin should increase with transport dysfunction: {transport_data['actin_change']:.1%}"
    assert transport_data['trafficking_change'] > 0.10, f"Trafficking marker should increase with transport dysfunction: {transport_data['trafficking_change']:.1%}"

    # 6. Overall identifiability score
    min_separation = min(er_separation, mito_separation, transport_separation)
    print(f"\n=== Overall Identifiability Score ===")
    print(f"Minimum separation: {min_separation:.1f}× (target >2×)")
    print(f"Average separation: {(er_separation + mito_separation + transport_separation) / 3:.1f}×")

    # Final verdict
    print("\n✓ PASSED: 4-way identifiability verified")
    print(f"  Control: max drift {max_control_change:.0%}")
    print(f"  ER stress: {er_separation:.1f}× separation (ER +{er_data['er_change']:.0%}, UPR +{er_data['upr_change']:.0%})")
    print(f"  Mito dysfunction: {mito_separation:.1f}× separation (Mito {mito_data['mito_change']:.0%}, ATP {mito_data['atp_change']:.0%})")
    print(f"  Transport dysfunction: {transport_separation:.1f}× separation (Actin +{transport_data['actin_change']:.0%}, Trafficking +{transport_data['trafficking_change']:.0%})")

    if min_separation > 5.0:
        print("\n🎉 Phase 2 EARNED: >5× separation achieved! Agent-ready simulator.")
    elif min_separation > 2.0:
        print("\n✓ Phase 2 EARNED: >2× separation verified. Latents are identifiable.")


if __name__ == "__main__":
    test_4way_identifiability()
    print("\n=== Phase 2 Complete ===")
