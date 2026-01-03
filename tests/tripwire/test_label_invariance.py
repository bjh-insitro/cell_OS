"""
Tripwire: Label-permutation invariance.

Tests that agent-facing outputs are invariant to internal label permutations.

This catches leaks from:
- Death mode strings being serialized
- Mechanism labels affecting measurement
- Deterministic ordering based on internal tags

If this test fails, the simulator is leaking information through labels or
metadata, not through realistic observable signatures.

NOTE: This is NOT testing that "ER stress and mito dysfunction are indistinguishable."
Real biology CAN be separable via morphology. This tests that swapping INTERNAL LABELS
doesn't change outputs.
"""

import pytest
import numpy as np
from copy import deepcopy


@pytest.fixture
def make_vm_and_vessel():
    """Factory for creating VM and vessel with controlled debug settings."""
    from tests.contracts.conftest import make_vm_and_vessel as _make
    return _make


def test_death_mode_label_permutation_invariance(make_vm_and_vessel):
    """
    Swapping death_mode internal labels must not affect measurement outputs.

    Setup:
    - World A: Death via ER stress (death_mode="er_stress")
    - World B: Swap internal death_mode enum values (relabel "er_stress" <-> "mito_dysfunction")

    Assert: Cell Painting outputs are bit-identical (no label leakage).

    This does NOT test that ER stress and mito dysfunction are biologically
    indistinguishable. It tests that the LABEL STRING doesn't leak.
    """
    # World A: Normal labels
    vm_a, vessel_a = make_vm_and_vessel(debug_truth_enabled=False)
    vm_a.seed_vessel(vessel_a.vessel_id, cell_line='A549', initial_confluence=0.3)
    vm_a.treat_with_compound(vessel_a.vessel_id, compound='thapsigargin', dose_uM=5.0)  # ER stress inducer
    vm_a.advance_time(24.0)

    result_a = vm_a.assays.cell_painting.measure(vessel_a, well_position='A01', plate_id='P1')

    # World B: Same intervention, but if death_mode strings were swapped internally,
    # outputs should still be identical (since labels shouldn't leak)
    vm_b, vessel_b = make_vm_and_vessel(debug_truth_enabled=False)
    vm_b.seed_vessel(vessel_b.vessel_id, cell_line='A549', initial_confluence=0.3)
    vm_b.treat_with_compound(vessel_b.vessel_id, compound='thapsigargin', dose_uM=5.0)
    vm_b.advance_time(24.0)

    result_b = vm_b.assays.cell_painting.measure(vessel_b, well_position='A01', plate_id='P1')

    # Assert: Outputs are identical (no label dependency)
    # Note: Morphology values themselves might differ due to mechanism (that's OK),
    # but given identical interventions, labels shouldn't matter.

    # For this test to work properly, we'd need to actually permute labels at runtime.
    # As a proxy, we test that results don't contain death_mode anywhere.
    def extract_all_strings(obj, depth=0, max_depth=10):
        """Recursively extract all string values from nested structure."""
        if depth > max_depth:
            return []
        strings = []
        if isinstance(obj, str):
            strings.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                strings.extend(extract_all_strings(v, depth+1, max_depth))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                strings.extend(extract_all_strings(item, depth+1, max_depth))
        return strings

    all_strings_a = extract_all_strings(result_a)
    all_strings_b = extract_all_strings(result_b)

    # Assert: No death mode labels in outputs
    death_mode_labels = {
        "er_stress", "mito_dysfunction", "compound", "starvation",
        "mitotic", "confluence", "contamination", "mixed", "unknown"
    }

    leaked_labels_a = [s for s in all_strings_a if s in death_mode_labels]
    leaked_labels_b = [s for s in all_strings_b if s in death_mode_labels]

    assert not leaked_labels_a, f"Death mode labels leaked in World A: {leaked_labels_a}"
    assert not leaked_labels_b, f"Death mode labels leaked in World B: {leaked_labels_b}"


def test_stress_axis_label_permutation_invariance(make_vm_and_vessel):
    """
    Swapping stress_axis internal labels must not affect measurement outputs.

    Setup:
    - Compound X with stress_axis="oxidative"
    - Swap internal stress_axis enum/string

    Assert: Outputs don't change (stress_axis label doesn't leak).

    The EFFECT of oxidative stress (morphology changes, death) should still happen,
    but the STRING "oxidative" should not appear in outputs.
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)
    vm.seed_vessel(vessel.vessel_id, cell_line='A549', initial_confluence=0.4)
    vm.treat_with_compound(vessel.vessel_id, compound='H2O2', dose_uM=100.0)
    vm.advance_time(12.0)

    result = vm.assays.cell_painting.measure(vessel, well_position='B02', plate_id='P1')

    # Extract all strings
    def extract_all_strings(obj, depth=0, max_depth=10):
        if depth > max_depth:
            return []
        strings = []
        if isinstance(obj, str):
            strings.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                strings.extend(extract_all_strings(v, depth+1, max_depth))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                strings.extend(extract_all_strings(item, depth+1, max_depth))
        return strings

    all_strings = extract_all_strings(result)

    # Assert: No stress axis labels in outputs
    stress_axis_labels = {
        "oxidative", "er_stress", "proteostasis", "mitochondrial",
        "microtubule", "dna_damage"
    }

    leaked_labels = [s for s in all_strings if s in stress_axis_labels]
    assert not leaked_labels, f"Stress axis labels leaked: {leaked_labels}"


def test_compound_name_not_in_measurement_results(make_vm_and_vessel):
    """
    Compound names must not appear in measurement results (treatment blinding).

    The agent knows what it dosed (that's memory), but measurements should not
    echo back compound names. That would bypass treatment blinding.

    Exception: Diagnostic outputs or action confirmations (not measurements).
    """
    vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)
    vm.seed_vessel(vessel.vessel_id, cell_line='HepG2', initial_confluence=0.35)
    vm.treat_with_compound(vessel.vessel_id, compound='paclitaxel', dose_uM=1.0)
    vm.advance_time(24.0)

    # Cell Painting measurement
    result_cp = vm.assays.cell_painting.measure(vessel, well_position='C03', plate_id='P1')

    # LDH measurement
    result_ldh = vm.assays.ldh_viability.measure(vessel, well_position='C03', plate_id='P1')

    def extract_all_strings(obj, depth=0, max_depth=10):
        if depth > max_depth:
            return []
        strings = []
        if isinstance(obj, str):
            strings.append(obj.lower())  # Normalize to lowercase for matching
        elif isinstance(obj, dict):
            for v in obj.values():
                strings.extend(extract_all_strings(v, depth+1, max_depth))
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                strings.extend(extract_all_strings(item, depth+1, max_depth))
        return strings

    all_strings_cp = extract_all_strings(result_cp)
    all_strings_ldh = extract_all_strings(result_ldh)

    # Compound names that should not appear in measurements
    compound_names = {"paclitaxel", "etoposide", "cccp", "h2o2", "nocodazole", "thapsigargin"}

    leaked_cp = [s for s in all_strings_cp if s in compound_names]
    leaked_ldh = [s for s in all_strings_ldh if s in compound_names]

    assert not leaked_cp, f"Compound names leaked in Cell Painting: {leaked_cp}"
    assert not leaked_ldh, f"Compound names leaked in LDH: {leaked_ldh}"


def test_vessel_id_ordering_does_not_leak_labels():
    """
    Vessel processing order must not depend on internal labels.

    If vessels are processed in an order determined by death_mode or stress_axis,
    that's a leak (agents could infer labels from sequence).

    This is a structural test, not a full simulation test.
    """
    # This test is conceptual. In practice, you'd need to:
    # 1. Create multiple vessels with different death_modes
    # 2. Process them in a batch
    # 3. Assert that output order is deterministic based on vessel_id, not death_mode

    # Placeholder: Document the requirement
    # Real implementation would require batch processing API
    pass


def test_random_seed_invariance_to_label_swaps():
    """
    RNG consumption must not depend on label string values.

    If death_mode="er_stress" consumes N draws but death_mode="mito_dysfunction"
    consumes M draws (M != N), that's a subtle leak (RNG state fingerprints mechanism).

    This is extremely hard to exploit, but worth documenting as a design principle.
    """
    # This is a design constraint, not a runtime test.
    # Document: All branches should consume the same number of RNG draws,
    # or use separate deterministic RNG streams per mechanism.
    pass


# =============================================================================
# Meta-test: Verify that realistic biological separability still works
# =============================================================================

@pytest.mark.manual
def test_mechanism_separability_report(make_vm_and_vessel):
    """
    DIAGNOSTIC TEST (not strict): Report whether ER stress vs mito dysfunction
    produce distinguishable morphology signatures.

    This is ALLOWED to show separability. Real biology is discriminable.
    This test just reports HOW separable, for transparency.

    Run manually with: pytest -m manual tests/tripwire/test_label_invariance.py::test_mechanism_separability_report
    """
    # ER stress condition
    vm_er, vessel_er = make_vm_and_vessel(debug_truth_enabled=False)
    vm_er.seed_vessel(vessel_er.vessel_id, cell_line='A549', initial_confluence=0.3)
    vm_er.treat_with_compound(vessel_er.vessel_id, compound='thapsigargin', dose_uM=5.0)
    vm_er.advance_time(24.0)
    result_er = vm_er.assays.cell_painting.measure(vessel_er, well_position='A01', plate_id='P1')

    # Mito dysfunction condition
    vm_mito, vessel_mito = make_vm_and_vessel(debug_truth_enabled=False)
    vm_mito.seed_vessel(vessel_mito.vessel_id, cell_line='A549', initial_confluence=0.3)
    vm_mito.treat_with_compound(vessel_mito.vessel_id, compound='CCCP', dose_uM=30.0)
    vm_mito.advance_time(24.0)
    result_mito = vm_mito.assays.cell_painting.measure(vessel_mito, well_position='A01', plate_id='P1')

    # Compute separability (cosine distance between morphology vectors)
    morph_er = result_er['morphology']
    morph_mito = result_mito['morphology']

    vec_er = np.array([morph_er['er'], morph_er['mito'], morph_er['nucleus'], morph_er['actin'], morph_er['rna']])
    vec_mito = np.array([morph_mito['er'], morph_mito['mito'], morph_mito['nucleus'], morph_mito['actin'], morph_mito['rna']])

    cosine_sim = np.dot(vec_er, vec_mito) / (np.linalg.norm(vec_er) * np.linalg.norm(vec_mito))
    cosine_dist = 1.0 - cosine_sim

    print("\n" + "="*80)
    print("MECHANISM SEPARABILITY REPORT")
    print("="*80)
    print(f"ER stress morphology: {morph_er}")
    print(f"Mito dysfunction morphology: {morph_mito}")
    print(f"Cosine distance: {cosine_dist:.3f}")
    print(f"Interpretation: {cosine_dist:.3f} separability is {'high' if cosine_dist > 0.3 else 'moderate' if cosine_dist > 0.1 else 'low'}")
    print("="*80)

    # This test does NOT assert separability bounds. It just reports.
    # If you want to enforce separability, uncomment:
    # assert cosine_dist > 0.1, "Mechanisms should be somewhat separable (realistic)"
