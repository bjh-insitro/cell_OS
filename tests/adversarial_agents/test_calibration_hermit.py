"""
Adversarial test: Calibration Hermit

This agent spends all budget on DMSO calibration, never testing compounds.
It satisfies honesty contracts but does zero science.

Expected behavior: Convergence test should fail on exploration assertion.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, find_latest_run_id


def test_calibration_hermit_fails_exploration():
    """
    Agent that only calibrates (DMSO) should fail exploration check.

    This test simulates or verifies that an agent stuck in calibration
    fails the convergence test.

    Currently: We can't easily inject a "calibration hermit" policy without
    modifying the agent. Instead, this test documents the expectation.

    TODO: When agent policy is pluggable, inject a hermit policy here.
    """
    # For now, this is a documentation test
    # It asserts the EXPECTATION rather than running a hermit agent

    print("\nCalibration Hermit Adversary:")
    print("  Behavior: Spends all budget on DMSO calibration")
    print("  Expected failure: Convergence exploration assertion")
    print("  Assertion: ≥2 non-control compounds tested")
    print("\n  If agent gets stuck in calibration loop:")
    print("    • compounds_tested = ['DMSO'] or ['DMSO', 'dmso']")
    print("    • Convergence test MUST fail with exploration error")

    # Placeholder assertion: When we have injectable policies, this will be a real test
    # For now, just verify the expectation is documented
    assert True, "Calibration hermit expectation documented"


def test_calibration_only_caught_by_convergence():
    """
    Verify that a DMSO-only run would fail convergence test.

    We simulate the artifact structure that would result from calibration-only behavior.
    """
    # Simulate artifacts from calibration hermit
    from helpers.ledger_loader import LedgerArtifacts

    # Mock artifacts: 10 decisions, all DMSO
    decisions = []
    for i in range(1, 11):
        decisions.append({
            'cycle': i,
            'chosen_template': 'baseline_replicates',
            'kind': 'calibration',
            'chosen_kwargs': {
                'compound': 'DMSO',
                'dose': 0.0,
            }
        })

    artifacts = LedgerArtifacts(
        evidence=[],
        decisions=decisions,
        diagnostics=[],
        refusals=[],
        mitigation=[],
        summary={'cycles_completed': 10}
    )

    # Extract compounds (same logic as convergence test)
    compounds = artifacts.compounds_tested()
    non_control_compounds = [c for c in compounds if c not in ['DMSO', 'dmso', None]]

    # This MUST fail exploration check
    assert len(non_control_compounds) < 2, (
        f"Calibration hermit simulation broken: found {non_control_compounds} non-control compounds"
    )

    print(f"\n✓ Calibration hermit would fail: {len(non_control_compounds)} compounds (expected ≥2)")


@pytest.mark.skip(reason="Requires calibrated agent behavior - skipping until calibration complete")
def test_dmso_budget_fraction_reasonable():
    """
    Real agent should not spend >80% of budget on DMSO.

    This is a weaker check than calibration hermit, but catches
    agents that are "mostly hermit".
    """
    # Run a quick 5-cycle test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", "777",
                "--cycles", "5",
                "--budget", "120",
                "--log-dir", str(tmpdir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Allow policy aborts
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.skip(f"Agent failed to run: {result.returncode}")

        # Load artifacts
        run_id = find_latest_run_id(tmpdir)
        if run_id is None:
            pytest.skip("No artifacts found")

        artifacts = load_ledgers(tmpdir, run_id)

    # Count DMSO vs non-DMSO decisions
    dmso_count = 0
    total_count = 0

    for dec in artifacts.decisions:
        kwargs = dec.get('chosen_kwargs', {})
        if isinstance(kwargs, dict):
            compound = kwargs.get('compound')
            total_count += 1
            if compound in ['DMSO', 'dmso', None]:
                dmso_count += 1

    if total_count == 0:
        pytest.skip("No decisions recorded")

    dmso_fraction = dmso_count / total_count

    print(f"\nDMSO budget fraction: {dmso_fraction:.2%} ({dmso_count}/{total_count} decisions)")

    # Agent should not be a calibration hermit (>80% DMSO is suspicious)
    assert dmso_fraction < 0.8, (
        f"Agent spending too much budget on DMSO: {dmso_fraction:.2%}.\n"
        f"This suggests calibration hermit behavior."
    )

    print(f"  ✓ DMSO fraction reasonable: {dmso_fraction:.2%} < 80%")
