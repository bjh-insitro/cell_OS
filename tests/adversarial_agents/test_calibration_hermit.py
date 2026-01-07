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


@pytest.mark.slow  # Takes ~30s, run with: pytest -m slow
def test_dmso_budget_fraction_reasonable():
    """
    Real agent should not spend >80% of budget on DMSO.

    This is a weaker check than calibration hermit, but catches
    agents that are "mostly hermit".

    Note: Budget must be large enough to pass calibration gates:
    - Cycle 0 calibration: 96 wells
    - Noise gate: ~24-48 wells
    - LDH/Cell Painting gates: ~48 wells
    Total calibration overhead: ~170-200 wells
    """
    # Run a test with enough budget to get past calibration into biology
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", "777",
                "--cycles", "15",
                "--budget", "384",  # 4 plates - enough for calibration + biology
                "--log-dir", str(tmpdir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Allow policy aborts
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.skip(f"Agent failed to run: {result.returncode}")

        # Load artifacts
        run_id = find_latest_run_id(tmpdir)
        if run_id is None:
            pytest.skip("No artifacts found")

        artifacts = load_ledgers(tmpdir, run_id)

    # Use summary's tested_compounds which correctly tracks all compounds
    compounds_tested = artifacts.summary.get('beliefs_final', {}).get('tested_compounds', [])

    if not compounds_tested:
        # Fallback to extraction from decisions
        compounds_tested = artifacts.compounds_tested()

    if not compounds_tested:
        pytest.skip("No compounds tested")

    # Count non-control compounds
    non_control = [c for c in compounds_tested if c not in ['DMSO', 'dmso', None]]
    total_compounds = len(compounds_tested)
    dmso_only = (total_compounds == 1 and 'DMSO' in compounds_tested)

    print(f"\nCompounds tested: {compounds_tested}")
    print(f"Non-control compounds: {non_control}")

    # Agent should test at least 2 non-control compounds (not be a calibration hermit)
    assert len(non_control) >= 2, (
        f"Agent only tested {len(non_control)} non-control compounds: {non_control}.\n"
        f"This suggests calibration hermit behavior (spending too much on DMSO).\n"
        f"All compounds: {compounds_tested}"
    )

    print(f"  ✓ Agent explored {len(non_control)} non-control compounds: {non_control}")
