"""
Unit tests for budget constraint enforcement in proposals.

These tests verify that proposals respect resource reality:
- Replicate proposals shrink to fit budget
- Impossible proposals return None or raise
- Shrinking preserves as much science as possible
"""

import pytest
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
from cell_os.epistemic_agent.accountability import (
    make_replicate_proposal,
    shrink_proposal_to_budget
)


def test_replicate_proposal_shrinks_to_fit_budget():
    """
    Regression test for budget bug: 192 wells requested, 144 remaining.

    Original bug: make_replicate_proposal doubled wells to 192 without checking budget.
    Loop crashed with "Insufficient budget: requested 192, remaining 144".

    Fix: shrink_proposal_to_budget() scales down to fit budget.
    """
    # Create original proposal (96 wells)
    original_wells = [
        WellSpec(
            cell_line='A549',
            compound='DMSO',
            dose_uM=0.0,
            time_h=12.0,
            assay='cell_painting',
            position_tag='center'
        )
        for _ in range(96)
    ]

    original_proposal = Proposal(
        design_id='test_original',
        hypothesis='Original calibration',
        wells=original_wells,
        budget_limit=240
    )

    # Replicate proposal (192 wells requested)
    replicate_proposal = make_replicate_proposal(original_proposal)
    assert len(replicate_proposal.wells) == 192, "Replicate should double wells"

    # Shrink to fit budget (144 wells available)
    remaining_wells = 144
    shrunk_proposal = shrink_proposal_to_budget(replicate_proposal, remaining_wells)

    # Assertions
    assert shrunk_proposal is not None, "Should return valid proposal"
    assert len(shrunk_proposal.wells) == 144, f"Should shrink to {remaining_wells} wells"
    assert len(shrunk_proposal.wells) <= remaining_wells, "Must respect budget"

    # Verify shrinking preserves condition order (takes first N wells)
    assert shrunk_proposal.wells[:96] == replicate_proposal.wells[:96], (
        "Shrinking should preserve original conditions in order"
    )

    print(f"\n✓ Budget shrinking: 192 wells → 144 wells (1.5× replication)")


def test_shrink_proposal_fits_perfectly():
    """Proposal that fits exactly should pass through unchanged."""
    wells = [
        WellSpec('A549', 'compound_A', 10.0, 24.0, 'ldh_cytotoxicity', 'center')
        for _ in range(50)
    ]

    proposal = Proposal(
        design_id='test_fit',
        hypothesis='Fits perfectly',
        wells=wells,
        budget_limit=100
    )

    # Proposal fits perfectly
    remaining_wells = 50
    shrunk = shrink_proposal_to_budget(proposal, remaining_wells)

    assert shrunk is not None
    assert len(shrunk.wells) == 50
    assert shrunk.wells == proposal.wells, "Should not modify if fits"

    print(f"\n✓ Perfect fit: 50 wells requested, 50 available → no change")


def test_shrink_proposal_returns_none_if_impossible():
    """
    Negative test: proposal requiring 100 wells, only 2 available.

    Expected: shrink_proposal_to_budget returns None.
    Minimum viable proposal: 3 wells (arbitrary floor for science).
    """
    wells = [
        WellSpec('HepG2', 'compound_B', 50.0, 48.0, 'cell_painting', 'any')
        for _ in range(100)
    ]

    proposal = Proposal(
        design_id='test_impossible',
        hypothesis='Impossible proposal',
        wells=wells,
        budget_limit=100
    )

    # Only 2 wells remaining (below minimum viable)
    remaining_wells = 2
    shrunk = shrink_proposal_to_budget(proposal, remaining_wells)

    assert shrunk is None, "Should return None when budget < minimum viable (3 wells)"

    print(f"\n✓ Impossible budget: 100 wells requested, 2 available → None")


def test_shrink_proposal_at_minimum_viable():
    """
    Edge case: exactly minimum viable wells (3).

    Expected: returns shrunk proposal with 3 wells.
    """
    wells = [
        WellSpec('A549', 'compound_C', 100.0, 12.0, 'ldh_cytotoxicity', 'edge')
        for _ in range(96)
    ]

    proposal = Proposal(
        design_id='test_minimum',
        hypothesis='Edge case: minimum viable',
        wells=wells,
        budget_limit=96
    )

    # Exactly minimum viable
    remaining_wells = 3
    shrunk = shrink_proposal_to_budget(proposal, remaining_wells)

    assert shrunk is not None, "Should return proposal at minimum viable"
    assert len(shrunk.wells) == 3, "Should shrink to exactly 3 wells"

    print(f"\n✓ Minimum viable: 96 wells requested, 3 available → 3 wells proposal")


def test_shrink_proposal_preserves_well_spec_attributes():
    """Verify shrinking preserves well specifications (doesn't corrupt data)."""
    wells = [
        WellSpec(
            cell_line=f'cell_{i}',
            compound=f'compound_{i}',
            dose_uM=float(i),
            time_h=float(i * 12),
            assay='cell_painting',
            position_tag='center'
        )
        for i in range(20)
    ]

    proposal = Proposal(
        design_id='test_preserve',
        hypothesis='Preserve attributes',
        wells=wells,
        budget_limit=20
    )

    # Shrink to 10 wells
    shrunk = shrink_proposal_to_budget(proposal, 10)

    assert shrunk is not None
    assert len(shrunk.wells) == 10

    # Verify first 10 wells are identical to original
    for i in range(10):
        original_well = proposal.wells[i]
        shrunk_well = shrunk.wells[i]

        assert shrunk_well.cell_line == original_well.cell_line
        assert shrunk_well.compound == original_well.compound
        assert shrunk_well.dose_uM == original_well.dose_uM
        assert shrunk_well.time_h == original_well.time_h
        assert shrunk_well.assay == original_well.assay
        assert shrunk_well.position_tag == original_well.position_tag

    print(f"\n✓ Attribute preservation: shrunk wells match original (no corruption)")


def test_shrink_proposal_updates_hypothesis():
    """Shrunk proposals should have updated hypothesis indicating budget constraint."""
    wells = [WellSpec('A549', 'DMSO', 0.0, 12.0, 'cell_painting', 'center') for _ in range(100)]

    proposal = Proposal(
        design_id='test_hypothesis',
        hypothesis='Original hypothesis',
        wells=wells,
        budget_limit=100
    )

    shrunk = shrink_proposal_to_budget(proposal, 50)

    assert shrunk is not None
    assert 'BUDGET-CONSTRAINED' in shrunk.hypothesis, (
        "Shrunk proposal should indicate budget constraint in hypothesis"
    )
    assert '100→50' in shrunk.hypothesis, "Should show wells reduced"

    print(f"\n✓ Hypothesis updated: '{shrunk.hypothesis}'")
