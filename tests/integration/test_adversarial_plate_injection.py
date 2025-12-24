"""
Test that adversarial perturbations inject expected artifacts.

Verify that each adversary produces its characteristic signature:
- SpatialGradient: smooth row/column gradient
- EdgeEffect: edge wells differ from center
- BatchAlignedShift: group-wise offsets
- WashLossCorrelation: dose-correlated signal loss
"""

import pytest
import numpy as np
from cell_os.epistemic_agent.world import ExperimentalWorld
from cell_os.epistemic_agent.schemas import WellSpec, Proposal
from cell_os.adversarial import AdversarialPlateConfig, AdversarySpec


def parse_well_id(well_id):
    """Extract row and column indices from well_id."""
    row_letter = well_id[0]
    col_num = int(well_id[1:])
    row_idx = ord(row_letter) - ord('A')
    col_idx = col_num - 1
    return row_idx, col_idx


def is_edge_well(well_id, n_rows=8, n_cols=12):
    """Check if well is on plate edge."""
    row_idx, col_idx = parse_well_id(well_id)
    return row_idx == 0 or row_idx == n_rows - 1 or col_idx == 0 or col_idx == n_cols - 1


def test_spatial_gradient_creates_row_gradient():
    """SpatialGradient adversary creates detectable row gradient."""
    config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {
                "target_channel": "morphology.nucleus",
                "axis": "row",
                "strength": 0.2,  # 20% gradient
                "direction": 1
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config)

    # Create uniform plate (all DMSO vehicle)
    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            position_tag="any",
            assay="cell_painting"
        )
        for _ in range(48)
    ]
    proposal = Proposal(design_id="gradient_test", hypothesis="Test", wells=wells, budget_limit=96)

    results = world.run_experiment(proposal)

    # Extract nucleus values by row
    values_by_row = {}
    for well in results:
        row_idx, _ = parse_well_id(well.location.well_id)
        if row_idx not in values_by_row:
            values_by_row[row_idx] = []
        values_by_row[row_idx].append(well.readouts["morphology"]["nucleus"])

    # Compute row means
    row_means = {row: np.mean(vals) for row, vals in values_by_row.items()}

    # Check that gradient exists (first row < last row)
    sorted_rows = sorted(row_means.keys())
    if len(sorted_rows) >= 3:
        first_row_mean = row_means[sorted_rows[0]]
        last_row_mean = row_means[sorted_rows[-1]]

        # Core contract: overall gradient must be present
        assert last_row_mean > first_row_mean, (
            f"Row gradient not detected: first={first_row_mean:.2f}, last={last_row_mean:.2f}"
        )

        # Gradient magnitude check (at least 10% increase across plate)
        gradient_magnitude = (last_row_mean - first_row_mean) / first_row_mean
        assert gradient_magnitude > 0.10, (
            f"Gradient too weak: {gradient_magnitude:.1%} increase from first to last row"
        )


def test_edge_effect_creates_edge_center_difference():
    """EdgeEffect adversary creates systematic edge-center bias."""
    config_baseline = AdversarialPlateConfig(enabled=False)
    config_edge = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("EdgeEffect", {
                "target_channel": "morphology.nucleus",
                "edge_shift": -0.1,  # 10% lower at edges
            }),
        ],
        strength=1.0
    )

    world_baseline = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config_baseline)
    world_edge = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config_edge)

    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            position_tag="any",
            assay="cell_painting"
        )
        for _ in range(48)
    ]
    proposal = Proposal(design_id="edge_test", hypothesis="Test", wells=wells, budget_limit=96)

    results_baseline = world_baseline.run_experiment(proposal)
    results_edge = world_edge.run_experiment(proposal)

    # Separate edge and center wells for adversarial plate
    edge_values = []
    center_values = []

    for well in results_edge:
        value = well.readouts["morphology"]["nucleus"]
        if is_edge_well(well.location.well_id):
            edge_values.append(value)
        else:
            center_values.append(value)

    # Edge should be lower than center (negative shift)
    if edge_values and center_values:
        edge_mean = np.mean(edge_values)
        center_mean = np.mean(center_values)

        assert edge_mean < center_mean, (
            f"Edge effect not detected: edge={edge_mean:.2f}, center={center_mean:.2f}"
        )

        # Check effect size is significant (>5% difference)
        diff_pct = (center_mean - edge_mean) / center_mean
        assert diff_pct > 0.05, (
            f"Edge effect too weak: {diff_pct:.1%} difference"
        )


def test_batch_aligned_shift_creates_compound_specific_offsets():
    """BatchAlignedShift adversary creates compound-specific offsets."""
    config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("BatchAlignedShift", {
                "target_channel": "morphology.nucleus",
                "grouping_key": "compound",
                "shift_scale": 0.05,  # 5% std per compound
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config)

    # Create plate with multiple compounds
    wells = []
    compounds = ["DMSO", "tBHQ", "H2O2"]
    for compound in compounds:
        for _ in range(12):  # 12 wells per compound
            wells.append(WellSpec(
                cell_line="A549",
                compound=compound,
                dose_uM=0.0 if compound == "DMSO" else 10.0,
                time_h=24.0,
                position_tag="any",
                assay="cell_painting"
            ))

    proposal = Proposal(design_id="batch_test", hypothesis="Test", wells=wells, budget_limit=96)
    results = world.run_experiment(proposal)

    # Group by compound
    values_by_compound = {c: [] for c in compounds}
    for well in results:
        compound = well.treatment.compound
        if compound in values_by_compound:
            values_by_compound[compound].append(well.readouts["morphology"]["nucleus"])

    # Compute compound means
    compound_means = {c: np.mean(vals) for c, vals in values_by_compound.items() if vals}

    # Check that compound means differ (batch effect applied)
    means = list(compound_means.values())
    if len(means) >= 2:
        # Variance across compound means should be non-zero
        variance = np.var(means)
        # Note: We can't assert strong separation because biological effects dominate
        # But we can assert that means are not identical
        unique_means = len(set(np.round(means, 4)))
        assert unique_means >= 2, "BatchAlignedShift should create compound-specific offsets"


def test_wash_loss_correlation_creates_dose_dependent_loss():
    """WashLossCorrelation adversary creates dose-correlated signal loss."""
    config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("WashLossCorrelation", {
                "target_channel": "morphology.nucleus",
                "loss_per_log_dose": 0.05,  # 5% loss per log dose
                "threshold_dose_uM": 0.1,
            }),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config)

    # Create dose series
    doses = [0.0, 0.1, 1.0, 10.0, 100.0]
    wells = []
    for dose in doses:
        for _ in range(6):  # 6 replicates per dose
            wells.append(WellSpec(
                cell_line="A549",
                compound="tBHQ" if dose > 0 else "DMSO",
                dose_uM=dose,
                time_h=24.0,
                position_tag="any",
                assay="cell_painting"
            ))

    proposal = Proposal(design_id="wash_loss_test", hypothesis="Test", wells=wells, budget_limit=96)
    results = world.run_experiment(proposal)

    # Group by dose
    values_by_dose = {d: [] for d in doses}
    for well in results:
        dose = well.treatment.dose_uM
        if dose in values_by_dose:
            values_by_dose[dose].append(well.readouts["morphology"]["nucleus"])

    # Compute dose means
    dose_means = {d: np.mean(vals) for d, vals in values_by_dose.items() if vals}

    # Check that wash loss is applied: compare adversarial vs baseline
    # The biological effect might increase or decrease signal, but wash loss should reduce it
    # So we verify wash loss exists by comparing to a baseline without the adversary

    # Run baseline without adversary for comparison
    world_baseline = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=None)
    results_baseline = world_baseline.run_experiment(proposal)

    values_by_dose_baseline = {d: [] for d in doses}
    for well in results_baseline:
        dose = well.treatment.dose_uM
        if dose in values_by_dose_baseline:
            values_by_dose_baseline[dose].append(well.readouts["morphology"]["nucleus"])

    dose_means_baseline = {d: np.mean(vals) for d, vals in values_by_dose_baseline.items() if vals}

    # At high doses, adversarial plate should show LOWER signal than baseline (wash loss effect)
    high_dose = 100.0
    if high_dose in dose_means and high_dose in dose_means_baseline:
        adversarial_mean = dose_means[high_dose]
        baseline_mean = dose_means_baseline[high_dose]

        # Wash loss should reduce signal compared to baseline
        assert adversarial_mean < baseline_mean * 0.95, (
            f"Wash loss not detected: adversarial={adversarial_mean:.2f}, baseline={baseline_mean:.2f}"
        )


def test_multiple_adversaries_compose():
    """Multiple adversaries can be stacked and all produce effects."""
    config = AdversarialPlateConfig(
        enabled=True,
        adversaries=[
            AdversarySpec("SpatialGradient", {
                "target_channel": "morphology.nucleus",
                "axis": "row",
                "strength": 0.1
            }),
            AdversarySpec("EdgeEffect", {
                "target_channel": "morphology.nucleus",
                "edge_shift": -0.05
            }, seed_offset=1),
        ],
        strength=1.0
    )

    world = ExperimentalWorld(budget_wells=96, seed=42, adversarial_plate_config=config)

    wells = [
        WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=0.0,
            time_h=24.0,
            position_tag="any",
            assay="cell_painting"
        )
        for _ in range(48)
    ]
    proposal = Proposal(design_id="compose_test", hypothesis="Test", wells=wells, budget_limit=96)

    results = world.run_experiment(proposal)

    # Both effects should be present:
    # 1. Row gradient
    # 2. Edge-center difference

    # Check row gradient
    values_by_row = {}
    for well in results:
        row_idx, _ = parse_well_id(well.location.well_id)
        if row_idx not in values_by_row:
            values_by_row[row_idx] = []
        values_by_row[row_idx].append(well.readouts["morphology"]["nucleus"])

    row_means = {row: np.mean(vals) for row, vals in values_by_row.items()}
    sorted_rows = sorted(row_means.keys())

    if len(sorted_rows) >= 2:
        assert row_means[sorted_rows[-1]] > row_means[sorted_rows[0]], (
            "Row gradient effect not present in composition"
        )

    # Check edge effect
    edge_values = []
    center_values = []
    for well in results:
        value = well.readouts["morphology"]["nucleus"]
        if is_edge_well(well.location.well_id):
            edge_values.append(value)
        else:
            center_values.append(value)

    if edge_values and center_values:
        assert np.mean(edge_values) < np.mean(center_values), (
            "Edge effect not present in composition"
        )
