"""
Tests for observation provenance and round-trip integrity.

These tests verify that:
1. Raw results can reconstruct observations exactly
2. No information is lost in aggregation
3. Provenance is preserved
"""

import pytest
from src.cell_os.epistemic_agent.world import ExperimentalWorld
from src.cell_os.epistemic_agent.observation_aggregator import (
    aggregate_observation,
    compute_observation_fingerprint
)
from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec


def test_raw_results_reconstruct_observation():
    """Given raw results, observation should be reproducible.

    This is the "no information loss" test:
    raw_results → observation → (recompute from raw) → identical observation
    """
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
        WellSpec("A549", "tBHQ", 30.0, 24.0, "cell_painting", "center")
    ]

    proposal = Proposal(
        design_id="test_provenance",
        hypothesis="Test provenance",
        wells=wells,
        budget_limit=100
    )

    # Execute and aggregate
    raw_results = world.run_experiment(proposal)
    obs1 = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )

    # Reconstruct observation from same raw results
    obs2 = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )

    # Should be identical
    assert obs1.design_id == obs2.design_id
    assert len(obs1.conditions) == len(obs2.conditions)
    assert obs1.wells_spent == obs2.wells_spent
    assert obs1.budget_remaining == obs2.budget_remaining

    # Check condition-level identity
    for c1, c2 in zip(obs1.conditions, obs2.conditions):
        assert c1.cell_line == c2.cell_line
        assert c1.compound == c2.compound
        assert c1.dose_uM == c2.dose_uM
        assert c1.time_h == c2.time_h
        assert c1.n_wells == c2.n_wells
        assert abs(c1.mean - c2.mean) < 1e-10, "Means should be identical"
        assert abs(c1.std - c2.std) < 1e-10, "Stds should be identical"
        assert abs(c1.sem - c2.sem) < 1e-10, "SEMs should be identical"

    print("✓ Raw results reconstruct observation exactly")


def test_observation_fingerprint_links_to_raw():
    """Observation fingerprint should deterministically link to raw results."""
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
        WellSpec("A549", "tBHQ", 30.0, 24.0, "cell_painting", "center")
    ]

    proposal = Proposal(
        design_id="test_fp",
        hypothesis="Test fingerprint",
        wells=wells,
        budget_limit=100
    )

    # Execute
    raw_results = world.run_experiment(proposal)

    # Compute fingerprint
    fp1 = compute_observation_fingerprint(proposal, raw_results)

    # Re-execute same proposal (should get same fingerprint)
    world2 = ExperimentalWorld(budget_wells=100, seed=42)  # Same seed
    raw_results2 = world2.run_experiment(proposal)
    fp2 = compute_observation_fingerprint(proposal, raw_results2)

    # Fingerprints should match (deterministic simulation)
    assert fp1 == fp2, "Fingerprint should be deterministic for same seed"

    print("✓ Observation fingerprint links to raw results")


def test_aggregation_preserves_all_channels():
    """Aggregation should preserve all channel information.

    No information loss: all 5 channels should be present in aggregated output.
    """
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")
    ]

    proposal = Proposal(
        design_id="test_channels",
        hypothesis="Test channel preservation",
        wells=wells,
        budget_limit=100
    )

    raw_results = world.run_experiment(proposal)
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )

    # Check that all channels are preserved
    cond = observation.conditions[0]
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        assert ch in cond.feature_means, f"Channel {ch} missing from feature_means"
        assert ch in cond.feature_stds, f"Channel {ch} missing from feature_stds"
        assert cond.feature_means[ch] > 0, f"Channel {ch} mean should be positive"

    print("✓ Aggregation preserves all channel information")


def test_raw_results_contain_qc_metadata():
    """Raw results should preserve QC metadata for audit."""
    world = ExperimentalWorld(budget_wells=100, seed=42)

    wells = [
        WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center")
    ]

    proposal = Proposal(
        design_id="test_qc",
        hypothesis="Test QC metadata",
        wells=wells,
        budget_limit=100
    )

    raw_results = world.run_experiment(proposal)
    result = raw_results[0]

    # Check QC field exists
    assert hasattr(result, 'qc'), "RawWellResult should have qc field"
    assert isinstance(result.qc, dict), "QC should be a dict"

    # QC dict may be empty or contain failure flags
    # Key point: the field exists and can store metadata

    print("✓ Raw results contain QC metadata")


def test_provenance_chain_complete():
    """Complete provenance chain: Proposal → Raw → Observation → Fingerprint.

    This is the "audit trail" test:
    1. Proposal specifies what to do
    2. World produces raw results
    3. Aggregator produces observation
    4. Fingerprint links them together
    """
    world = ExperimentalWorld(budget_wells=100, seed=42)

    proposal = Proposal(
        design_id="provenance_test",
        hypothesis="Test provenance chain",
        wells=[
            WellSpec("A549", "DMSO", 0.0, 24.0, "cell_painting", "center"),
            WellSpec("A549", "tBHQ", 30.0, 24.0, "cell_painting", "center")
        ],
        budget_limit=100
    )

    # Step 1: Execute
    raw_results = world.run_experiment(proposal)
    assert len(raw_results) == 2, "Should have 2 raw results"

    # Step 2: Aggregate
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=world.budget_remaining
    )
    assert observation.design_id == proposal.design_id

    # Step 3: Compute fingerprint
    fingerprint = compute_observation_fingerprint(proposal, raw_results)
    assert len(fingerprint) == 16, "Fingerprint should be 16 hex chars"

    # Provenance chain complete:
    # proposal.design_id → raw_results → observation.design_id → fingerprint
    # All linked and auditable

    print("✓ Complete provenance chain established")
    print(f"  Proposal: {proposal.design_id}")
    print(f"  Raw wells: {len(raw_results)}")
    print(f"  Observation: {len(observation.conditions)} conditions")
    print(f"  Fingerprint: {fingerprint}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
