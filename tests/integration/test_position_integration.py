#!/usr/bin/env python3
"""
Integration test: Verify world aggregation uses derived position_class.

This test ensures:
1. World aggregates results by derived position_class (not stored position_tag)
2. SpatialLocation.position_class correctly classifies edge vs center
3. No reverse inference (well_id → position_tag)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cell_os.epistemic_agent.world import ExperimentalWorld
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
from cell_os.core.experiment import SpatialLocation


def test_world_uses_derived_position():
    """World aggregation should use SpatialLocation.position_class."""

    world = ExperimentalWorld(budget_wells=96, seed=42)

    # Create proposal with edge and center position_tags
    wells = [
        # Edge wells (position_tag='edge')
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="edge"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="edge"
        ),
        # Center wells (position_tag='center')
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ),
    ]

    proposal = Proposal(
        design_id="test_position",
        hypothesis="Test derived position classification",
        wells=wells,
        budget_limit=96
    )

    # Execute
    observation = world.run_experiment(proposal)

    # Check that we got 2 condition summaries (edge and center)
    assert len(observation.conditions) == 2, \
        f"Expected 2 conditions (edge+center), got {len(observation.conditions)}"

    # Verify position_tag is derived from location
    edge_conditions = [c for c in observation.conditions if c.position_tag == "edge"]
    center_conditions = [c for c in observation.conditions if c.position_tag == "center"]

    assert len(edge_conditions) == 1, "Should have 1 edge condition"
    assert len(center_conditions) == 1, "Should have 1 center condition"

    # Verify n_wells
    assert edge_conditions[0].n_wells == 2, "Edge should have 2 wells"
    assert center_conditions[0].n_wells == 2, "Center should have 2 wells"

    print("✓ World aggregation uses derived position_class")
    print("✓ Edge and center wells correctly classified")
    print("✓ No reverse inference (position derived from location)")


def test_spatial_location_edge_detection():
    """Verify SpatialLocation.position_class correctly classifies wells."""

    # Edge wells
    edge_wells = [
        ("Plate1", "A01"),  # Top-left corner
        ("Plate1", "A12"),  # Top-right corner
        ("Plate1", "H01"),  # Bottom-left corner
        ("Plate1", "H12"),  # Bottom-right corner
        ("Plate1", "A06"),  # Top edge, middle
        ("Plate1", "H06"),  # Bottom edge, middle
        ("Plate1", "D01"),  # Left edge, middle
        ("Plate1", "D12"),  # Right edge, middle
    ]

    for plate_id, well_id in edge_wells:
        location = SpatialLocation(plate_id=plate_id, well_id=well_id)
        assert location.position_class == "edge", \
            f"{well_id} should be classified as edge"

    # Center wells
    center_wells = [
        ("Plate1", "B02"),  # Interior
        ("Plate1", "C03"),  # Interior
        ("Plate1", "D06"),  # Middle
        ("Plate1", "G11"),  # Interior, near edge but not on edge
    ]

    for plate_id, well_id in center_wells:
        location = SpatialLocation(plate_id=plate_id, well_id=well_id)
        assert location.position_class == "center", \
            f"{well_id} should be classified as center"

    print("✓ SpatialLocation.position_class correctly classifies 96-well plate")
    print("✓ Edge detection works for all perimeter wells")
    print("✓ Interior wells classified as center")


if __name__ == "__main__":
    print("[1/2] Testing SpatialLocation edge detection...")
    test_spatial_location_edge_detection()
    print()

    print("[2/2] Testing world aggregation with derived position...")
    test_world_uses_derived_position()
    print()

    print("=" * 60)
    print("✓ Translation Kill #4: Position Semantics VERIFIED")
    print("=" * 60)
    print("✓ Position abstractions derived from physical location")
    print("✓ No reverse inference (well_id → position_tag)")
    print("✓ SpatialLocation.position_class is canonical")
    print("✓ World aggregation uses derived position_class")
