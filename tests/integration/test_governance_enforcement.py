# tests/integration/test_governance_enforcement.py
"""
Integration test that enforces the governance contract choke point.

If this test fails, someone bypassed the contract.
"""

import pytest
from unittest.mock import patch

from src.cell_os.hardware.beam_search import BeamSearch, Phase5EpisodeRunner
from src.cell_os.epistemic_agent.governance.contract import decide_governance


def test_beam_search_must_call_governance_contract():
    """
    Prove that beam search cannot create terminal decisions without calling the governance contract.

    Strategy: Monkeypatch decide_governance to raise RuntimeError, then run beam search.
    If the contract is called, we'll see the RuntimeError.
    If it's not called (someone bypassed it), test fails silently - that's the bug we're guarding against.
    """
    # Set up a minimal beam search
    from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY

    compound_id = 'test_A_clean'  # ER stress compound
    phase5_compound = PHASE5_LIBRARY[compound_id]

    runner = Phase5EpisodeRunner(
        phase5_compound=phase5_compound,
        cell_line="A549",
        horizon_h=12.0,  # Short horizon for speed
        step_h=6.0,
        seed=42,
        lambda_dead=2.0,
        lambda_ops=0.1,
        actin_threshold=1.4
    )

    beam_search = BeamSearch(
        runner=runner,
        beam_width=3,  # Small beam for speed
        max_interventions=2,
        death_tolerance=0.20,
        dose_levels=[0.0, 1.0],  # Minimal action space
    )

    # Monkeypatch the contract to raise if called
    with patch('src.cell_os.hardware.beam_search.decide_governance') as mock_decide:
        mock_decide.side_effect = RuntimeError("CONTRACT_CALLED")

        # Run beam search - should raise RuntimeError if contract is called
        with pytest.raises(RuntimeError, match="CONTRACT_CALLED"):
            beam_search.search(compound_id, phase5_compound)

    # If we get here without exception, someone bypassed the contract
    # pytest.raises will fail the test automatically if RuntimeError isn't raised


def test_contract_enforces_input_validation():
    """Verify that the contract rejects garbage inputs."""
    from src.cell_os.epistemic_agent.governance import decide_governance, GovernanceInputs, GovernanceAction

    # Test 1: nuisance_prob out of range
    bad_inputs_1 = GovernanceInputs(
        posterior={"ER_STRESS": 0.9},
        nuisance_prob=1.5,  # Invalid: > 1.0
        evidence_strength=0.8,
    )
    decision = decide_governance(bad_inputs_1)
    assert decision.action == GovernanceAction.NO_COMMIT
    assert "bad_input" in decision.reason
    assert "nuisance_prob" in decision.reason

    # Test 2: evidence_strength out of range
    bad_inputs_2 = GovernanceInputs(
        posterior={"ER_STRESS": 0.9},
        nuisance_prob=0.2,
        evidence_strength=-0.1,  # Invalid: < 0.0
    )
    decision = decide_governance(bad_inputs_2)
    assert decision.action == GovernanceAction.NO_COMMIT
    assert "bad_input" in decision.reason
    assert "evidence_strength" in decision.reason
