# tests/phase6a/test_conservation_strict.py
"""
Strict conservation and ledger integrity tests.

These tests enforce:
1. Every tracked death field stays in [0, 1]
2. Death fields are monotone non-decreasing
3. Allocation sums to realized kill (within epsilon)
4. death_unattributed is residual-only (not proposable)

This catches ledger drift before it becomes "the simulator runs but lies".
"""

import math
import pytest


def _mk_vm_and_vessel(seed: int = 1):
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]
    return vm, vessel


def _get_tracked_values(vessel, fields):
    return {f: float(getattr(vessel, f, 0.0)) for f in fields}


def test_tracked_death_fields_bounded_and_monotone_over_steps():
    """
    After each commit step:
      - every tracked death field must be within [0, 1]
      - they must be monotone non-decreasing
    """
    from cell_os.hardware.biological_virtual import TRACKED_DEATH_FIELDS, DEATH_EPS

    vm, vessel = _mk_vm_and_vessel(seed=101)

    # Start clean
    for f in TRACKED_DEATH_FIELDS:
        setattr(vessel, f, 0.0)

    vessel.viability = 1.0
    vessel.bio_random_effects = {"hazard_scale_mult": 2.0}

    prev = _get_tracked_values(vessel, TRACKED_DEATH_FIELDS)

    # Step 1: two causes
    vessel._step_hazard_proposals = {}
    vm._propose_hazard(vessel, 0.10, "death_compound")
    vm._propose_hazard(vessel, 0.05, "death_er_stress")
    vm._commit_step_death(vessel, 1.0)

    cur = _get_tracked_values(vessel, TRACKED_DEATH_FIELDS)
    for f, v in cur.items():
        assert -DEATH_EPS <= v <= 1.0 + DEATH_EPS, f"{f} out of bounds: {v}"
        assert v + DEATH_EPS >= prev[f], f"{f} decreased: prev={prev[f]} cur={v}"
    prev = cur

    # Step 2: different causes
    vessel._step_hazard_proposals = {}
    vm._propose_hazard(vessel, 0.07, "death_mito_dysfunction")
    vm._propose_hazard(vessel, 0.02, "death_confluence")
    vm._commit_step_death(vessel, 0.5)

    cur = _get_tracked_values(vessel, TRACKED_DEATH_FIELDS)
    for f, v in cur.items():
        assert -DEATH_EPS <= v <= 1.0 + DEATH_EPS, f"{f} out of bounds: {v}"
        assert v + DEATH_EPS >= prev[f], f"{f} decreased: prev={prev[f]} cur={v}"


def test_multi_cause_allocation_sums_to_realized_kill_for_proposed_fields():
    """
    For a single step, the sum of increments to the proposed death fields should equal kill_total
    up to eps (because _commit_step_death allocates kill_total proportionally).
    """
    from cell_os.hardware.biological_virtual import DEATH_EPS

    vm, vessel = _mk_vm_and_vessel(seed=202)

    vessel.viability = 1.0
    vessel.bio_random_effects = {"hazard_scale_mult": 3.0}

    # Zero ALL ledgers (including seeding stress)
    proposed_fields = ["death_compound", "death_er_stress", "death_mito_dysfunction"]
    for f in proposed_fields:
        setattr(vessel, f, 0.0)
    vessel.death_unknown = 0.0
    vessel.death_starvation = 0.0
    vessel.death_mitotic_catastrophe = 0.0
    vessel.death_confluence = 0.0
    vessel.death_contamination = 0.0

    before = {f: float(getattr(vessel, f)) for f in proposed_fields}
    v_before = float(vessel.viability)

    vessel._step_hazard_proposals = {}
    vm._propose_hazard(vessel, 0.12, "death_compound")
    vm._propose_hazard(vessel, 0.03, "death_er_stress")
    vm._propose_hazard(vessel, 0.05, "death_mito_dysfunction")

    vm._commit_step_death(vessel, 2.0)

    v_after = float(vessel.viability)
    kill_total = float(max(0.0, v_before - v_after))

    after = {f: float(getattr(vessel, f)) for f in proposed_fields}
    incr_sum = sum(max(0.0, after[f] - before[f]) for f in proposed_fields)

    assert abs(incr_sum - kill_total) <= 1e-9, (
        f"Allocation does not conserve realized kill\n"
        f"  kill_total={kill_total:.12f}\n"
        f"  incr_sum={incr_sum:.12f}\n"
        f"  delta={incr_sum - kill_total:.3e}"
    )

    # Also sanity: commit bookkeeping should match
    assert abs(float(vessel._step_total_kill) - kill_total) <= 1e-12


def test_death_unattributed_is_not_proposable_and_does_not_break_conservation():
    """
    death_unattributed should never be a proposal target.
    Also, its existence should not affect commit or conservation semantics.
    """
    from cell_os.hardware.biological_virtual import DEATH_EPS

    vm, vessel = _mk_vm_and_vessel(seed=303)
    vessel.viability = 1.0
    vessel.bio_random_effects = {"hazard_scale_mult": 1.0}

    # Zero ALL ledgers (including seeding stress)
    vessel.death_compound = 0.0
    vessel.death_unknown = 0.0
    vessel.death_starvation = 0.0
    vessel.death_mitotic_catastrophe = 0.0
    vessel.death_er_stress = 0.0
    vessel.death_mito_dysfunction = 0.0
    vessel.death_confluence = 0.0
    vessel.death_contamination = 0.0

    # Ensure proposing it fails
    vessel._step_hazard_proposals = {}
    with pytest.raises(ValueError, match="Unknown death_field"):
        vm._propose_hazard(vessel, 0.01, "death_unattributed")

    # Run a normal step and ensure viability updates and no weirdness
    v_before = float(vessel.viability)
    vessel._step_hazard_proposals = {}
    vm._propose_hazard(vessel, 0.10, "death_compound")
    vm._commit_step_death(vessel, 1.0)

    assert float(vessel.viability) <= v_before + DEATH_EPS
