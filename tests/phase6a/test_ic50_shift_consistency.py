"""
Phase 3: IC50 shift consistency across all stress mechanisms.

Tests that continuous heterogeneity (ic50_shift_mult) is applied consistently
across death hazards AND stress induction.

Why this matters:
- Agents should not learn "sensitive vessels die faster but don't get stressed faster"
- That's fake separability from implementation asymmetry, not biology

Pattern: Brutal ordering test that fails if any axis forgets the shift.
"""

import pytest


def test_ic50_shift_propagates_to_er_stress_induction():
    """
    IC50 shift must affect ER stress induction, not just death hazards.

    Math setup:
    - dose_uM == ic50_uM, potency_scalar == 1.0
    - No shift: f_axis = dose/(dose+ic50) = 0.5
    - Shift 0.5: f_axis = dose/(dose+0.5*ic50) = 2/3
    - Shift 2.0: f_axis = dose/(dose+2*ic50) = 1/3

    Assert: stress_low_shift > stress_high_shift (strict ordering)
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    # Create two vessels with different IC50 shifts
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vm.seed_vessel("P1_A02", "A549", initial_count=1e6, vessel_type='96-well')

    vessel_low = vm.vessel_states["P1_A01"]
    vessel_high = vm.vessel_states["P1_A02"]

    # Force IC50 shifts (sensitive vs resistant)
    vessel_low.bio_random_effects = {"ic50_shift_mult": 0.5}  # More sensitive
    vessel_high.bio_random_effects = {"ic50_shift_mult": 2.0}  # Less sensitive

    # Set up compound with dose == ic50 for clean math
    ic50_uM = 1.0
    dose_uM = 1.0  # dose == ic50
    compound = "tunicamycin"

    for vessel in [vessel_low, vessel_high]:
        vessel.compounds = {compound: dose_uM}
        vessel.compound_meta = {
            compound: {
                'ic50_uM': ic50_uM,
                'stress_axis': 'er_stress',
                'potency_scalar': 1.0
            }
        }

    # Call ER stress mechanism directly (bypass full VM step)
    vm._er_stress.update(vessel_low, hours=1.0)
    vm._er_stress.update(vessel_high, hours=1.0)

    # Assert strict ordering: more sensitive → more stress
    assert vessel_low.er_stress > vessel_high.er_stress, \
        f"IC50 shift not propagating to ER stress induction! " \
        f"Low shift (0.5): {vessel_low.er_stress:.6f}, " \
        f"High shift (2.0): {vessel_high.er_stress:.6f}. " \
        f"Expected low_shift > high_shift."


def test_ic50_shift_propagates_to_mito_dysfunction_induction():
    """
    IC50 shift must affect mito dysfunction induction, not just death hazards.

    Same math setup as ER test, different axis.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    vm.seed_vessel("P1_B01", "A549", initial_count=1e6, vessel_type='96-well')
    vm.seed_vessel("P1_B02", "A549", initial_count=1e6, vessel_type='96-well')

    vessel_low = vm.vessel_states["P1_B01"]
    vessel_high = vm.vessel_states["P1_B02"]

    vessel_low.bio_random_effects = {"ic50_shift_mult": 0.5}
    vessel_high.bio_random_effects = {"ic50_shift_mult": 2.0}

    ic50_uM = 1.0
    dose_uM = 1.0
    compound = "rotenone"

    for vessel in [vessel_low, vessel_high]:
        vessel.compounds = {compound: dose_uM}
        vessel.compound_meta = {
            compound: {
                'ic50_uM': ic50_uM,
                'stress_axis': 'mitochondrial',
                'potency_scalar': 1.0
            }
        }

    vm._mito_dysfunction.update(vessel_low, hours=1.0)
    vm._mito_dysfunction.update(vessel_high, hours=1.0)

    assert vessel_low.mito_dysfunction > vessel_high.mito_dysfunction, \
        f"IC50 shift not propagating to mito dysfunction induction! " \
        f"Low shift (0.5): {vessel_low.mito_dysfunction:.6f}, " \
        f"High shift (2.0): {vessel_high.mito_dysfunction:.6f}. " \
        f"Expected low_shift > high_shift."


def test_ic50_shift_propagates_to_transport_dysfunction_induction():
    """
    IC50 shift must affect transport dysfunction induction, not just death hazards.

    Same math setup, microtubule axis.
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    vm.seed_vessel("P1_C01", "A549", initial_count=1e6, vessel_type='96-well')
    vm.seed_vessel("P1_C02", "A549", initial_count=1e6, vessel_type='96-well')

    vessel_low = vm.vessel_states["P1_C01"]
    vessel_high = vm.vessel_states["P1_C02"]

    vessel_low.bio_random_effects = {"ic50_shift_mult": 0.5}
    vessel_high.bio_random_effects = {"ic50_shift_mult": 2.0}

    ic50_uM = 1.0
    dose_uM = 1.0
    compound = "nocodazole"

    for vessel in [vessel_low, vessel_high]:
        vessel.compounds = {compound: dose_uM}
        vessel.compound_meta = {
            compound: {
                'ic50_uM': ic50_uM,
                'stress_axis': 'microtubule',
                'potency_scalar': 1.0
            }
        }

    vm._transport_dysfunction.update(vessel_low, hours=1.0)
    vm._transport_dysfunction.update(vessel_high, hours=1.0)

    assert vessel_low.transport_dysfunction > vessel_high.transport_dysfunction, \
        f"IC50 shift not propagating to transport dysfunction induction! " \
        f"Low shift (0.5): {vessel_low.transport_dysfunction:.6f}, " \
        f"High shift (2.0): {vessel_high.transport_dysfunction:.6f}. " \
        f"Expected low_shift > high_shift."


def test_ic50_shift_direction_is_correct():
    """
    Lower ic50_shift_mult means MORE sensitive (higher induction at same dose).

    This is a sanity check that we didn't accidentally invert the shift.

    Shift 0.5: ic50_effective = 0.5 µM → dose=1µM is 2× EC50 → high stress
    Shift 2.0: ic50_effective = 2.0 µM → dose=1µM is 0.5× EC50 → low stress
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    vm.seed_vessel("P1_D01", "A549", initial_count=1e6, vessel_type='96-well')
    vm.seed_vessel("P1_D02", "A549", initial_count=1e6, vessel_type='96-well')

    sensitive = vm.vessel_states["P1_D01"]
    resistant = vm.vessel_states["P1_D02"]

    # Sensitive = LOW shift mult (easier to hit EC50)
    # Resistant = HIGH shift mult (harder to hit EC50)
    sensitive.bio_random_effects = {"ic50_shift_mult": 0.5}
    resistant.bio_random_effects = {"ic50_shift_mult": 2.0}

    dose_uM = 1.0
    compound = "tunicamycin"

    for vessel in [sensitive, resistant]:
        vessel.compounds = {compound: dose_uM}
        vessel.compound_meta = {
            compound: {
                'ic50_uM': 1.0,
                'stress_axis': 'er_stress',
                'potency_scalar': 1.0
            }
        }

    vm._er_stress.update(sensitive, hours=1.0)
    vm._er_stress.update(resistant, hours=1.0)

    # Sensitive should have MORE stress (not less)
    assert sensitive.er_stress > resistant.er_stress, \
        f"IC50 shift direction is INVERTED! " \
        f"Sensitive (shift 0.5): {sensitive.er_stress:.6f}, " \
        f"Resistant (shift 2.0): {resistant.er_stress:.6f}. " \
        f"Expected sensitive > resistant."


def test_ic50_shift_magnitude_is_reasonable():
    """
    Verify the shift produces reasonable induction ratios.

    Math check:
    - dose=1µM, ic50=1µM, shift=0.5: f = 1/(1+0.5) = 0.667
    - dose=1µM, ic50=1µM, shift=2.0: f = 1/(1+2.0) = 0.333
    - Ratio: 0.667/0.333 = 2.0

    After one 1h step with k_on ~ 0.1-0.2, stress should be roughly proportional.
    We don't check exact values, just that the ratio is in a sane range [1.5, 3.0].
    """
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    vm.seed_vessel("P1_E01", "A549", initial_count=1e6, vessel_type='96-well')
    vm.seed_vessel("P1_E02", "A549", initial_count=1e6, vessel_type='96-well')

    low = vm.vessel_states["P1_E01"]
    high = vm.vessel_states["P1_E02"]

    low.bio_random_effects = {"ic50_shift_mult": 0.5}
    high.bio_random_effects = {"ic50_shift_mult": 2.0}

    compound = "tunicamycin"
    for vessel in [low, high]:
        vessel.compounds = {compound: 1.0}
        vessel.compound_meta = {
            compound: {
                'ic50_uM': 1.0,
                'stress_axis': 'er_stress',
                'potency_scalar': 1.0
            }
        }

    vm._er_stress.update(low, hours=1.0)
    vm._er_stress.update(high, hours=1.0)

    ratio = low.er_stress / max(high.er_stress, 1e-12)

    # Expect ratio roughly 2× (from f_axis ratio)
    # Allow [1.5, 3.0] range for nonlinearity from (1-S) saturation term
    assert 1.5 <= ratio <= 3.0, \
        f"IC50 shift produces unreasonable induction ratio! " \
        f"Low stress: {low.er_stress:.6f}, High stress: {high.er_stress:.6f}, " \
        f"Ratio: {ratio:.2f}. Expected ratio in [1.5, 3.0]."
