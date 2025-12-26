"""
Unit tests for calibration proposal template.

These tests prove the calibration proposal is un-cheatable:
1. Controls-only (no non-control compounds)
2. Identity-blind (no forbidden tokens)
3. Center-heavy (≥80% center wells)
4. Minimum variance support (≥12 wells per cell line)
5. Stable under seed (deterministic)

If these pass, calibration cannot become "exploration in a trench coat."
"""

import random
import pytest
from cell_os.epistemic_agent.calibration_proposal import (
    make_calibration_proposal,
    assert_calibration_proposal_is_identity_blind,
    get_calibration_statistics,
    CalibrationParams,
    ALLOWED_CONTROLS,
)
from cell_os.epistemic_agent.schemas import Proposal, WellSpec


def test_calibration_proposal_controls_only():
    """
    Test 1: Calibration proposal contains only allowed control compounds.

    All wells must have compound in ALLOWED_CONTROLS ({"DMSO"}).
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]

    proposal = make_calibration_proposal(
        reason="high_uncertainty",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng
    )

    # Check all wells
    for well in proposal.wells:
        assert well.compound in ALLOWED_CONTROLS, (
            f"Calibration contains non-control compound: {well.compound}"
        )

        # Also check dose is 0.0
        assert well.dose_uM == 0.0, (
            f"Calibration contains non-zero dose: {well.dose_uM}"
        )

    # Verify statistics
    stats = get_calibration_statistics(proposal)
    assert stats["compounds"] == {"DMSO"}, (
        f"Calibration should only contain DMSO, got: {stats['compounds']}"
    )


def test_calibration_proposal_identity_blind():
    """
    Test 2: Calibration proposal passes identity-blind validator.

    Token scanner should find no forbidden tokens in proposal.
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]

    proposal = make_calibration_proposal(
        reason="drift_detected",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng
    )

    # Should not raise
    assert_calibration_proposal_is_identity_blind(proposal)

    # Manually verify no identity in design_id or hypothesis
    assert "compound" not in proposal.design_id.lower() or "calibration" in proposal.design_id.lower()
    assert "dose" not in proposal.hypothesis.lower() or "calibrate" in proposal.hypothesis.lower()


def test_calibration_proposal_center_heavy():
    """
    Test 3: Calibration proposal is center-heavy (≥80% center wells).

    Reduces edge variance so calibration measures instrument, not plate boundary.
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]
    params = CalibrationParams(center_fraction_min=0.80)

    proposal = make_calibration_proposal(
        reason="routine_calibration",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng,
        params=params
    )

    # Check center fraction
    stats = get_calibration_statistics(proposal)
    center_frac = stats["center_fraction"]

    assert center_frac >= 0.80, (
        f"Calibration should be ≥80% center wells, got {center_frac:.1%}"
    )


def test_calibration_proposal_minimum_variance_support():
    """
    Test 4: Calibration proposal has enough wells to estimate variance.

    Minimum: 12 wells per cell line (sufficient for pooled variance estimation).
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]
    params = CalibrationParams(min_controls_per_line=12)

    proposal = make_calibration_proposal(
        reason="high_uncertainty",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng,
        params=params
    )

    # Check wells per cell line
    stats = get_calibration_statistics(proposal)
    for line, count in stats["wells_per_line"].items():
        assert count >= 12, (
            f"Cell line {line} has insufficient wells for variance: {count} < 12"
        )


def test_calibration_proposal_deterministic_under_seed():
    """
    Test 5: Calibration proposal is deterministic under same seed.

    Same seed → same layout (for reproducibility and testing).
    """
    cell_lines = ["A549", "HepG2"]

    # Generate with seed 42
    rng1 = random.Random(42)
    proposal1 = make_calibration_proposal(
        reason="test",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng1
    )

    # Generate with same seed
    rng2 = random.Random(42)
    proposal2 = make_calibration_proposal(
        reason="test",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng2
    )

    # Should be identical
    assert len(proposal1.wells) == len(proposal2.wells)

    for w1, w2 in zip(proposal1.wells, proposal2.wells):
        assert w1.cell_line == w2.cell_line
        assert w1.compound == w2.compound
        assert w1.dose_uM == w2.dose_uM
        assert w1.time_h == w2.time_h
        assert w1.assay == w2.assay
        assert w1.position_tag == w2.position_tag


def test_calibration_proposal_insufficient_budget_raises():
    """
    Test that calibration raises ValueError if budget is insufficient.

    Prevents attempting calibration when we can't afford it.
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]

    # Insufficient budget (need 96 wells, have 50)
    with pytest.raises(ValueError, match="Insufficient budget"):
        make_calibration_proposal(
            reason="test",
            cell_lines=cell_lines,
            budget_remaining=50,  # Too low
            rng=rng
        )


def test_calibration_validator_rejects_non_control_compound():
    """
    Test that validator rejects proposals with non-control compounds.

    This is the "calibration in a trench coat" defense.
    """
    # Manually create a malicious proposal
    malicious_proposal = Proposal(
        design_id="fake_calibration",
        hypothesis="Sneaky exploration",
        wells=[
            WellSpec(
                cell_line="A549",
                compound="staurosporine",  # NOT ALLOWED
                dose_uM=1.0,  # NOT ZERO
                time_h=12.0,
                assay="cell_painting",
                position_tag="center"
            )
        ],
        budget_limit=100
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="non-control compound"):
        assert_calibration_proposal_is_identity_blind(malicious_proposal)


def test_calibration_validator_rejects_non_zero_dose():
    """
    Test that validator rejects proposals with non-zero doses.
    """
    # Malicious proposal with DMSO but non-zero dose
    malicious_proposal = Proposal(
        design_id="fake_calibration",
        hypothesis="Sneaky treatment",
        wells=[
            WellSpec(
                cell_line="A549",
                compound="DMSO",  # Allowed
                dose_uM=10.0,  # NOT ALLOWED (should be 0.0)
                time_h=12.0,
                assay="cell_painting",
                position_tag="center"
            )
        ],
        budget_limit=100
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="non-zero dose"):
        assert_calibration_proposal_is_identity_blind(malicious_proposal)


def test_calibration_statistics_extraction():
    """
    Test that calibration statistics are correctly extracted.

    Useful for EpisodeSummary and debugging.
    """
    rng = random.Random(42)
    cell_lines = ["A549", "HepG2"]

    proposal = make_calibration_proposal(
        reason="test",
        cell_lines=cell_lines,
        budget_remaining=200,
        rng=rng
    )

    stats = get_calibration_statistics(proposal)

    # Verify structure
    assert "total_wells" in stats
    assert "wells_per_line" in stats
    assert "center_fraction" in stats
    assert "edge_fraction" in stats
    assert "cell_lines" in stats
    assert "compounds" in stats

    # Verify values
    assert stats["total_wells"] == len(proposal.wells)
    assert set(stats["cell_lines"]) == set(cell_lines)
    assert stats["compounds"] == {"DMSO"}
    assert stats["center_fraction"] + stats["edge_fraction"] == pytest.approx(1.0, abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
