# tests/unit/test_governance_contract.py

from src.cell_os.epistemic_agent.governance.contract import (
    GovernanceAction,
    GovernanceInputs,
    GovernanceThresholds,
    decide_governance,
)


def test_weak_posterior_high_nuisance_must_not_commit():
    t = GovernanceThresholds(
        commit_posterior_min=0.80,
        nuisance_max_for_commit=0.35,
        evidence_min_for_detection=0.70,
    )

    x = GovernanceInputs(
        posterior={"ER_STRESS": 0.55, "MITO_STRESS": 0.35, "MICROTUBULE": 0.10},
        nuisance_prob=0.75,
        evidence_strength=0.85,  # evidence is strong, so NO_DETECTION is forbidden
    )

    d = decide_governance(x, t)

    assert d.action == GovernanceAction.NO_COMMIT
    assert d.mechanism is None
    assert "evidence strong" in d.reason


def test_strong_posterior_low_nuisance_must_commit():
    t = GovernanceThresholds(
        commit_posterior_min=0.80,
        nuisance_max_for_commit=0.35,
        evidence_min_for_detection=0.70,
    )

    x = GovernanceInputs(
        posterior={"MICROTUBULE": 0.92, "ER_STRESS": 0.06, "MITO_STRESS": 0.02},
        nuisance_prob=0.10,
        evidence_strength=0.90,
    )

    d = decide_governance(x, t)

    assert d.action == GovernanceAction.COMMIT
    assert d.mechanism == "MICROTUBULE"
    assert "commit:" in d.reason


def test_strong_evidence_forbids_no_detection_even_if_uncertain():
    t = GovernanceThresholds(
        commit_posterior_min=0.80,
        nuisance_max_for_commit=0.35,
        evidence_min_for_detection=0.70,
    )

    # Strong evidence, but posterior split and nuisance too high to commit.
    x = GovernanceInputs(
        posterior={"ER_STRESS": 0.52, "MITO_STRESS": 0.48},
        nuisance_prob=0.60,
        evidence_strength=0.95,
    )

    d = decide_governance(x, t)

    assert d.action != GovernanceAction.NO_DETECTION
    assert d.action == GovernanceAction.NO_COMMIT


def test_priority_order_never_inverted():
    """
    Verify priority ladder is never inverted during refactors.

    Priority order (from contract):
      1. If evidence strong → NO_DETECTION forbidden
      2. If commit allowed → COMMIT
      3. Else if evidence weak → NO_DETECTION allowed
      4. Default → NO_COMMIT

    This test ensures nobody "simplifies" the if/elif/else logic incorrectly.
    """
    t = GovernanceThresholds(
        commit_posterior_min=0.80,
        nuisance_max_for_commit=0.35,
        evidence_min_for_detection=0.70,
    )

    # Case 1: Strong evidence + commit allowed → COMMIT (not blocked by anti-cowardice)
    x1 = GovernanceInputs(
        posterior={"MICROTUBULE": 0.92},
        nuisance_prob=0.10,
        evidence_strength=0.90,  # Strong evidence
    )
    d1 = decide_governance(x1, t)
    assert d1.action == GovernanceAction.COMMIT
    assert d1.mechanism == "MICROTUBULE"

    # Case 2: Strong evidence + commit NOT allowed → NO_COMMIT (anti-cowardice blocks NO_DETECTION)
    x2 = GovernanceInputs(
        posterior={"ER_STRESS": 0.70},  # Below commit threshold (0.80)
        nuisance_prob=0.25,
        evidence_strength=0.85,  # Strong evidence
    )
    d2 = decide_governance(x2, t)
    assert d2.action == GovernanceAction.NO_COMMIT
    assert "evidence strong" in d2.reason

    # Case 3: Low evidence + commit NOT allowed → NO_DETECTION (safe exit allowed)
    x3 = GovernanceInputs(
        posterior={"ER_STRESS": 0.45},
        nuisance_prob=0.50,
        evidence_strength=0.40,  # Low evidence
    )
    d3 = decide_governance(x3, t)
    assert d3.action == GovernanceAction.NO_DETECTION
    assert "no_detection" in d3.reason
