"""
Tests for observation aggregation correctness.

These tests verify that aggregation is:
1. Deterministic (same inputs → same outputs)
2. Correct (statistics match expected values)
3. Swappable (strategy can be changed without breaking)
"""

import pytest
import numpy as np

from src.cell_os.epistemic_agent.observation_aggregator import (
    aggregate_observation,
    compute_observation_fingerprint
)
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
from src.cell_os.core.observation import RawWellResult
from src.cell_os.core.experiment import SpatialLocation, Treatment
from src.cell_os.core.assay import AssayType


def _make_raw_result(
    well_id: str,
    cell_line: str,
    compound: str,
    dose_uM: float,
    time_h: float,
    morphology: dict
) -> RawWellResult:
    """Helper to create synthetic RawWellResult."""
    return RawWellResult(
        location=SpatialLocation(plate_id="TestPlate", well_id=well_id),
        cell_line=cell_line,
        treatment=Treatment(compound=compound, dose_uM=dose_uM),
        assay=AssayType.CELL_PAINTING,
        observation_time_h=time_h,
        readouts={'morphology': morphology},
        qc={}
    )


def test_aggregation_deterministic():
    """Same raw results should produce identical observations."""
    # Create synthetic raw results
    raw_results = (
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
        _make_raw_result(
            "A02", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
    )

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")
        ],
        budget_limit=100
    )

    # Aggregate twice
    obs1 = aggregate_observation(proposal, raw_results, budget_remaining=98)
    obs2 = aggregate_observation(proposal, raw_results, budget_remaining=98)

    # Should be identical
    assert obs1.design_id == obs2.design_id
    assert len(obs1.conditions) == len(obs2.conditions)
    assert obs1.conditions[0].mean == obs2.conditions[0].mean
    assert obs1.conditions[0].std == obs2.conditions[0].std

    print("✓ Aggregation is deterministic")


def test_aggregation_statistics_correct():
    """Aggregated statistics should match manual computation."""
    # Create synthetic results with known values
    raw_results = (
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
        _make_raw_result(
            "A02", "A549", "DMSO", 0.0, 24.0,
            {'er': 2.0, 'mito': 2.0, 'nucleus': 2.0, 'actin': 2.0, 'rna': 2.0}
        ),
        _make_raw_result(
            "A03", "A549", "DMSO", 0.0, 24.0,
            {'er': 3.0, 'mito': 3.0, 'nucleus': 3.0, 'actin': 3.0, 'rna': 3.0}
        ),
    )

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")
        ],
        budget_limit=100
    )

    # Aggregate
    obs = aggregate_observation(proposal, raw_results, budget_remaining=97)

    # Extract condition
    assert len(obs.conditions) == 1
    cond = obs.conditions[0]

    # Check scalar response (mean of all channels)
    # Well 1: mean([1,1,1,1,1]) = 1.0
    # Well 2: mean([2,2,2,2,2]) = 2.0
    # Well 3: mean([3,3,3,3,3]) = 3.0
    # Condition mean: mean([1.0, 2.0, 3.0]) = 2.0
    assert abs(cond.mean - 2.0) < 1e-6, f"Expected mean=2.0, got {cond.mean}"

    # Check std: std([1, 2, 3], ddof=1) = 1.0
    assert abs(cond.std - 1.0) < 1e-6, f"Expected std=1.0, got {cond.std}"

    # Check sem: std / sqrt(n) = 1.0 / sqrt(3) ≈ 0.577
    expected_sem = 1.0 / np.sqrt(3)
    assert abs(cond.sem - expected_sem) < 1e-6, f"Expected sem={expected_sem}, got {cond.sem}"

    # Check CV: std / mean = 1.0 / 2.0 = 0.5
    assert abs(cond.cv - 0.5) < 1e-6, f"Expected cv=0.5, got {cond.cv}"

    # Check per-channel means
    assert abs(cond.feature_means['er'] - 2.0) < 1e-6, "ER mean should be 2.0"
    assert abs(cond.feature_means['mito'] - 2.0) < 1e-6, "Mito mean should be 2.0"

    print("✓ Aggregated statistics are correct")


def test_aggregation_per_channel_stats():
    """Per-channel statistics should be independent of scalar mean."""
    # Create results with different channel patterns
    raw_results = (
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 2.0, 'nucleus': 3.0, 'actin': 4.0, 'rna': 5.0}
        ),
        _make_raw_result(
            "A02", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.5, 'mito': 2.5, 'nucleus': 3.5, 'actin': 4.5, 'rna': 5.5}
        ),
    )

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")
        ],
        budget_limit=100
    )

    obs = aggregate_observation(proposal, raw_results, budget_remaining=98)
    cond = obs.conditions[0]

    # Check per-channel means
    assert abs(cond.feature_means['er'] - 1.25) < 1e-6, "ER mean should be 1.25"
    assert abs(cond.feature_means['mito'] - 2.25) < 1e-6, "Mito mean should be 2.25"
    assert abs(cond.feature_means['nucleus'] - 3.25) < 1e-6, "Nucleus mean should be 3.25"
    assert abs(cond.feature_means['actin'] - 4.25) < 1e-6, "Actin mean should be 4.25"
    assert abs(cond.feature_means['rna'] - 5.25) < 1e-6, "RNA mean should be 5.25"

    # Check per-channel stds
    # std([1.0, 1.5], ddof=1) = 0.353553...
    expected_std = np.std([1.0, 1.5], ddof=1)
    for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        assert abs(cond.feature_stds[ch] - expected_std) < 1e-5, \
            f"{ch} std should be {expected_std}"

    print("✓ Per-channel statistics are correct")


def test_aggregation_groups_by_condition():
    """Wells with same condition should be grouped together."""
    # Create results for 2 conditions
    raw_results = (
        # DMSO condition (2 wells)
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
        _make_raw_result(
            "A02", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
        # tBHQ condition (1 well)
        _make_raw_result(
            "A03", "A549", "tBHQ", 30.0, 24.0,
            {'er': 0.5, 'mito': 0.5, 'nucleus': 0.5, 'actin': 0.5, 'rna': 0.5}
        ),
    )

    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "tBHQ", 30.0, 24.0, "cell_painting", "center")
        ],
        budget_limit=100
    )

    obs = aggregate_observation(proposal, raw_results, budget_remaining=97)

    # Should have 2 conditions
    assert len(obs.conditions) == 2, f"Expected 2 conditions, got {len(obs.conditions)}"

    # Find DMSO condition
    dmso_cond = [c for c in obs.conditions if c.compound == 'DMSO'][0]
    assert dmso_cond.n_wells == 2, "DMSO should have 2 wells"

    # Find tBHQ condition
    tbhq_cond = [c for c in obs.conditions if c.compound == 'tBHQ'][0]
    assert tbhq_cond.n_wells == 1, "tBHQ should have 1 well"

    print("✓ Aggregation groups by condition correctly")


def test_observation_fingerprint_deterministic():
    """Fingerprint should be deterministic for same inputs."""
    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")],
        budget_limit=100
    )

    raw_results = (
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
    )

    fp1 = compute_observation_fingerprint(proposal, raw_results)
    fp2 = compute_observation_fingerprint(proposal, raw_results)

    assert fp1 == fp2, "Fingerprint should be deterministic"
    assert len(fp1) == 16, "Fingerprint should be 16 hex chars"

    print("✓ Observation fingerprint is deterministic")


def test_observation_fingerprint_changes_with_inputs():
    """Fingerprint should change if inputs change."""
    proposal = Proposal(
        design_id="test",
        hypothesis="Test",
        wells=[WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")],
        budget_limit=100
    )

    raw_results1 = (
        _make_raw_result(
            "A01", "A549", "DMSO", 0.0, 24.0,
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
    )

    raw_results2 = (
        _make_raw_result(
            "A02", "A549", "DMSO", 0.0, 24.0,  # Different well_id
            {'er': 1.0, 'mito': 1.0, 'nucleus': 1.0, 'actin': 1.0, 'rna': 1.0}
        ),
    )

    fp1 = compute_observation_fingerprint(proposal, raw_results1)
    fp2 = compute_observation_fingerprint(proposal, raw_results2)

    assert fp1 != fp2, "Fingerprint should change with different inputs"

    print("✓ Observation fingerprint changes with inputs")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
