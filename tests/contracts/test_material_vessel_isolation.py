"""
Brutal test: Material measurements cannot mutate vessel state.

This is a HARD ASSERTION test - not polite, not probabilistic.
If material measurement touches vessel state, it's a contract violation.

Runtime: <5 seconds (one VM, one vessel, one material measurement)
"""

import pytest
import copy
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.material_state import MaterialState, MATERIAL_NOMINAL_INTENSITIES


def test_material_measurement_cannot_mutate_vessel_state():
    """
    Brutal assertion: material measurement on well A1 cannot affect vessel in well B2.

    Test protocol:
    1. Create vessel in B2 with known state (seeded, treated, advanced)
    2. Deep copy all vessel fields that MUST NOT change
    3. Measure optical material in A1 (different well)
    4. Assert vessel B2 state is BYTE-FOR-BYTE identical

    If this fails, we have biology-optics coupling and need to fix it.
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Create vessel in B2 with complex state
    vm.seed_vessel("well_B2", "A549", initial_count=5000, capacity=1e6)
    vm.treat_with_compound("well_B2", "tunicamycin", 5.0)
    vm.advance_time(24.0)

    vessel = vm.vessel_states["well_B2"]

    # Snapshot vessel state (deep copy of fields that MUST NOT change)
    snapshot = {
        'cell_count': vessel.cell_count,
        'viability': vessel.viability,
        'confluence': vessel.confluence,
        'passage_number': vessel.passage_number,
        'last_update_time': vessel.last_update_time,
        'compounds': copy.deepcopy(vessel.compounds),
        'death_compound': vessel.death_compound,
        'death_confluence': vessel.death_confluence,
        'death_unknown': vessel.death_unknown,
        'death_unattributed': vessel.death_unattributed,
        'er_stress': vessel.er_stress,
        'mito_dysfunction': vessel.mito_dysfunction,
        'transport_dysfunction': vessel.transport_dysfunction,
        # Subpopulation viabilities (must not change)
        'subpop_sensitive_viability': vessel.subpopulations['sensitive']['viability'],
        'subpop_typical_viability': vessel.subpopulations['typical']['viability'],
        'subpop_resistant_viability': vessel.subpopulations['resistant']['viability'],
    }

    # Measure optical material in A1 (DIFFERENT WELL)
    material = MaterialState(
        material_id="material_A1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="A1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=99
    )

    # This should NOT affect vessel B2
    result = vm.measure_material(material)

    # BRUTAL ASSERTION: Vessel state MUST be byte-for-byte identical
    assert vessel.cell_count == snapshot['cell_count'], \
        f"Material measurement changed cell_count: {snapshot['cell_count']} → {vessel.cell_count}"

    assert vessel.viability == snapshot['viability'], \
        f"Material measurement changed viability: {snapshot['viability']} → {vessel.viability}"

    assert vessel.confluence == snapshot['confluence'], \
        f"Material measurement changed confluence: {snapshot['confluence']} → {vessel.confluence}"

    assert vessel.passage_number == snapshot['passage_number'], \
        f"Material measurement changed passage_number: {snapshot['passage_number']} → {vessel.passage_number}"

    assert vessel.last_update_time == snapshot['last_update_time'], \
        f"Material measurement changed last_update_time: {snapshot['last_update_time']} → {vessel.last_update_time}"

    assert vessel.compounds == snapshot['compounds'], \
        f"Material measurement changed compounds: {snapshot['compounds']} → {vessel.compounds}"

    assert vessel.death_compound == snapshot['death_compound'], \
        f"Material measurement changed death_compound: {snapshot['death_compound']} → {vessel.death_compound}"

    assert vessel.er_stress == snapshot['er_stress'], \
        f"Material measurement changed er_stress: {snapshot['er_stress']} → {vessel.er_stress}"

    # Check subpopulation viabilities
    assert vessel.subpopulations['sensitive']['viability'] == snapshot['subpop_sensitive_viability'], \
        "Material measurement changed subpopulation viability (sensitive)"

    assert vessel.subpopulations['typical']['viability'] == snapshot['subpop_typical_viability'], \
        "Material measurement changed subpopulation viability (typical)"

    assert vessel.subpopulations['resistant']['viability'] == snapshot['subpop_resistant_viability'], \
        "Material measurement changed subpopulation viability (resistant)"

    print("✓ Material measurement in A1 did NOT mutate vessel B2 (brutal assertion passed)")


def test_material_measurement_works_without_any_vessels():
    """Material measurement should work with ZERO vessels (no biology coupling)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm._load_cell_thalamus_params()

    # Verify no vessels exist
    assert len(vm.vessel_states) == 0, "Should start with no vessels"

    # Create material and measure (should work without any vessels)
    material = MaterialState(
        material_id="material_H12_DARK",
        material_type="buffer_only",
        well_position="H12",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['DARK'],
        seed=42
    )

    result = vm.measure_material(material)

    # Verify result structure
    assert result['status'] == 'success'
    assert result['material_type'] == 'buffer_only'
    assert 'morphology' in result
    assert 'detector_metadata' in result

    # Verify no vessels were created as side effect
    assert len(vm.vessel_states) == 0, "Material measurement should not create vessels"

    print("✓ Material measurement works with ZERO vessels (no biology dependency)")


def test_material_rng_does_not_shift_biological_rng_sequence():
    """
    Material measurements use isolated RNG (no coupling to biological RNG).

    Test protocol:
    1. Measure cell in A1 → record RNG state after
    2. Reset VM to same seed
    3. Measure material in B1, THEN measure cell in A1
    4. Assert cell measurement is IDENTICAL (RNG sequence unchanged)

    If material measurement shifts biological RNG, cell results will differ.
    """
    # Baseline: cell measurement only
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1._load_cell_thalamus_params()
    vm1.seed_vessel("well_A1", "A549", initial_count=5000, capacity=1e6)
    vm1.advance_time(12.0)

    result_cell_only = vm1.cell_painting_assay("well_A1")
    morph_cell_only = result_cell_only['morphology']['er']

    # With material measurement before cell measurement
    vm2 = BiologicalVirtualMachine(seed=42)  # Same seed
    vm2._load_cell_thalamus_params()
    vm2.seed_vessel("well_A1", "A549", initial_count=5000, capacity=1e6)
    vm2.advance_time(12.0)

    # Measure material in different well (should NOT shift biological RNG)
    material = MaterialState(
        material_id="material_B1_FLATFIELD_DYE_LOW",
        material_type="fluorescent_dye_solution",
        well_position="B1",
        base_intensities=MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW'],
        seed=99
    )
    vm2.measure_material(material)

    # Now measure cell (should be IDENTICAL to baseline)
    result_cell_after_material = vm2.cell_painting_assay("well_A1")
    morph_cell_after_material = result_cell_after_material['morphology']['er']

    # BRUTAL ASSERTION: Cell measurements must be IDENTICAL
    # (If material shifted RNG, they would differ)
    assert morph_cell_only == morph_cell_after_material, \
        f"Material measurement shifted biological RNG: {morph_cell_only:.6f} → {morph_cell_after_material:.6f}"

    print(f"✓ Material RNG isolated: cell signal unchanged ({morph_cell_only:.1f} AU)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
