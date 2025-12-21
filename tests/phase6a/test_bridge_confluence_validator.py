"""
Test confluence confounding validator integration with design bridge.

This verifies that:
1. Confounded designs raise InvalidDesignError with structured details
2. Sentinel designs pass validation
3. Refusal artifacts are written with resolution strategies
"""

from src.cell_os.epistemic_agent.design_bridge import (
    proposal_to_design_json,
    validate_design,
)
from src.cell_os.epistemic_agent.exceptions import InvalidDesignError
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec


def test_bridge_rejects_confounded_design():
    """
    Bridge should catch confluence confounding and raise InvalidDesignError.

    Setup: Two conditions at same (cell_line, time_h, assay):
    - Control: DMSO @ 0 µM, 48h (high pressure, grows fast)
    - Treatment: ToxicCompound @ 10000 µM, 48h (low pressure, growth inhibited)

    Expected: InvalidDesignError with violation_code "confluence_confounding"
    """
    # Create a confounded proposal
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control_2"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment_2"
        ),
    ]

    proposal = Proposal(
        design_id="test_confounded_bridge",
        hypothesis="Test confluence confounding rejection",
        wells=wells,
        budget_limit=1000.0
    )

    # Convert to design JSON
    well_positions = ["A01", "A02", "A03", "A04"]
    design = proposal_to_design_json(
        proposal=proposal,
        cycle=1,
        run_id="test_run_001",
        well_positions=well_positions
    )

    # Validate should raise InvalidDesignError
    try:
        validate_design(design, strict=True)
        raise AssertionError("Bridge should have rejected confounded design")
    except InvalidDesignError as e:
        # Verify structured error
        assert e.violation_code == "confluence_confounding", \
            f"Expected confluence_confounding, got {e.violation_code}"
        assert e.design_id == "test_confounded_bridge"
        assert e.cycle == 1
        assert e.validator_mode == "policy_guard"

        # Verify details contain key information
        assert "delta_p" in e.details
        assert e.details["delta_p"] > 0.15, \
            f"delta_p should exceed threshold: {e.details['delta_p']}"
        assert "resolution_strategies" in e.details
        assert len(e.details["resolution_strategies"]) == 3

        print(f"✓ Bridge rejected confounded design: Δp = {e.details['delta_p']:.3f} > 0.15")
        print(f"  Violation code: {e.violation_code}")
        print(f"  Validator mode: {e.validator_mode}")
        print(f"  Message excerpt: {e.message[:100]}...")


def test_bridge_accepts_sentinel_design():
    """
    Bridge should accept designs with DENSITY_SENTINEL escape hatch.

    Setup: Same as confounded design, but include DENSITY_SENTINEL well
    Expected: No error (validator skips group with sentinel)
    """
    # Create a design with sentinel
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="control_2"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=10000.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="treatment_2"
        ),
        WellSpec(
            cell_line="A549",
            compound="DENSITY_SENTINEL",
            dose_uM=0.0,
            time_h=48.0,
            assay="cell_painting",
            position_tag="sentinel"
        ),
    ]

    proposal = Proposal(
        design_id="test_sentinel_bridge",
        hypothesis="Test sentinel escape hatch",
        wells=wells,
        budget_limit=1000.0
    )

    # Convert to design JSON
    well_positions = ["A01", "A02", "A03", "A04", "A05"]
    design = proposal_to_design_json(
        proposal=proposal,
        cycle=1,
        run_id="test_run_002",
        well_positions=well_positions
    )

    # Validate should not raise
    try:
        validate_design(design, strict=True)
        print("✓ Bridge accepted design with DENSITY_SENTINEL")
    except InvalidDesignError as e:
        raise AssertionError(
            f"Bridge should not reject sentinel designs: {e.violation_code} - {e.message}"
        )


def test_bridge_accepts_density_matched_design():
    """
    Bridge should accept designs with similar pressures across arms.

    Setup: Two conditions with delta_p < 0.15
    Expected: No error
    """
    # Create a density-matched design (shorter time, milder dose)
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="control_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="control_2"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=100.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="treatment_1"
        ),
        WellSpec(
            cell_line="A549",
            compound="ToxicCompound",
            dose_uM=100.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="treatment_2"
        ),
    ]

    proposal = Proposal(
        design_id="test_matched_bridge",
        hypothesis="Test density-matched design",
        wells=wells,
        budget_limit=1000.0
    )

    # Convert to design JSON
    well_positions = ["A01", "A02", "A03", "A04"]
    design = proposal_to_design_json(
        proposal=proposal,
        cycle=1,
        run_id="test_run_003",
        well_positions=well_positions
    )

    # Validate should not raise
    try:
        validate_design(design, strict=True)
        print("✓ Bridge accepted density-matched design (Δp < 0.15)")
    except InvalidDesignError as e:
        raise AssertionError(
            f"Bridge should not reject density-matched designs: {e.violation_code} - {e.message}"
        )


if __name__ == "__main__":
    test_bridge_rejects_confounded_design()
    test_bridge_accepts_sentinel_design()
    test_bridge_accepts_density_matched_design()
    print("\n✅ All bridge-level confluence validation tests PASSED")
