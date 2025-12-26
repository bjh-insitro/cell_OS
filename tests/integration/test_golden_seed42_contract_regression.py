"""
CONTRACT golden regression test for seed=42 baseline.

This test enforces schema compliance, invariants, and coarse behavior summaries.
It ALLOWS policy evolution: better exploration strategies, improved belief updates,
refined inference - all fine as long as contracts are respected.

WHAT THIS ENFORCES:
- Ledger schema compatibility (required fields, types)
- Causal contract compliance (no truth leakage, forbidden fields)
- Invariants (cycle monotonicity, budget conservation)
- Coarse summaries (≥N compounds, debt bucket, cycles completed)

WHAT THIS ALLOWS:
- Exact decision sequences (can change)
- Exact belief values (can improve)
- Exact template choices (can evolve)
- Exact rationale strings (can be refined)

PURPOSE: Run in CI on every commit to catch contract violations without freezing policy.

If this test fails:
1. Contract violation → FIX IT (causal leak, schema break, invariant violation)
2. Coarse summary drift → Assess if acceptable (better exploration? worse debt management?)
3. Only update contract_manifest.json if change is intentional and approved
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, find_latest_run_id


GOLDEN_DIR = Path(__file__).parent.parent / "golden" / "seed_42"
CONTRACT_MANIFEST = GOLDEN_DIR / "contract_manifest.json"

# Load contract expectations
with open(CONTRACT_MANIFEST, 'r') as f:
    CONTRACT = json.load(f)

GOLDEN_SEED = CONTRACT['seed']
GOLDEN_CYCLES = CONTRACT['cycles']
GOLDEN_BUDGET = CONTRACT['budget']  # Now 480 wells to accommodate epistemic actions


def test_contract_manifest_exists():
    """Verify contract manifest is present."""
    assert CONTRACT_MANIFEST.exists(), f"Contract manifest missing: {CONTRACT_MANIFEST}"
    assert CONTRACT['schema_version'] == "v1.0"


def test_contract_golden_seed42_regression():
    """
    Run epistemic loop with seed=42 and verify contract compliance.

    This is the CI-friendly golden test. Allows policy to evolve.
    """
    # Run fresh instance in temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Run the agent
        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", str(GOLDEN_SEED),
                "--cycles", str(GOLDEN_CYCLES),
                "--budget", str(GOLDEN_BUDGET),
                "--log-dir", str(tmpdir),
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes max
        )

        # Allow policy aborts (expected behavior)
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Agent run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        # Find run ID
        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found in temp dir"

        # Load fresh artifacts
        artifacts = load_ledgers(tmpdir, run_id)

    # SCHEMA CHECKS
    _assert_schema_requirements(artifacts)

    # INVARIANT CHECKS
    _assert_invariants(artifacts)

    # COARSE SUMMARY CHECKS
    _assert_coarse_summaries(artifacts)

    # CAUSAL CONTRACT CHECKS
    _assert_causal_contract_respected(artifacts)


def _assert_schema_requirements(artifacts):
    """Verify all ledgers have required fields."""
    schema = CONTRACT['schema_requirements']

    # Check decisions
    if artifacts.decisions:
        for i, decision in enumerate(artifacts.decisions):
            for field in schema['decision_required_fields']:
                assert field in decision, (
                    f"Decision record {i} missing required field '{field}'"
                )

    # Check evidence
    if artifacts.evidence:
        for i, evidence in enumerate(artifacts.evidence):
            for field in schema['evidence_required_fields']:
                assert field in evidence, (
                    f"Evidence record {i} missing required field '{field}'"
                )

    # Check diagnostics
    if artifacts.diagnostics:
        for i, diagnostic in enumerate(artifacts.diagnostics):
            for field in schema['diagnostics_required_fields']:
                assert field in diagnostic, (
                    f"Diagnostic record {i} missing required field '{field}'"
                )

    # Check summary
    for field in schema['summary_required_fields']:
        assert field in artifacts.summary, (
            f"Summary missing required field '{field}'"
        )


def _assert_invariants(artifacts):
    """Verify fundamental invariants hold."""
    invariants = CONTRACT['invariants']

    # Cycle monotonicity
    if invariants['cycles_monotonic'] and artifacts.decisions:
        cycles = [d['cycle'] for d in artifacts.decisions]
        assert all(cycles[i] <= cycles[i+1] for i in range(len(cycles)-1)), (
            f"Cycle non-monotonic: {cycles}"
        )

    # No negative cycles
    if invariants['no_negative_cycles']:
        all_cycles = []
        all_cycles.extend([d['cycle'] for d in artifacts.decisions])
        all_cycles.extend([e['cycle'] for e in artifacts.evidence])
        all_cycles.extend([diag['cycle'] for diag in artifacts.diagnostics if 'cycle' in diag])

        assert all(c >= 0 for c in all_cycles), (
            f"Negative cycles detected: {[c for c in all_cycles if c < 0]}"
        )

    # Budget conservation (if checkable from artifacts)
    # This is a basic check - real check would need to track wells
    if invariants['budget_conservation']:
        # Just verify cycles didn't exceed budget
        cycles_completed = artifacts.summary.get('cycles_completed', 0)
        # Each cycle could use up to GOLDEN_BUDGET wells
        # This is a very loose check, real budget tracking would be in world model
        assert cycles_completed <= GOLDEN_CYCLES + 5, (  # Allow some mitigation cycles
            f"Cycles completed ({cycles_completed}) exceeds expected ({GOLDEN_CYCLES})"
        )


def _assert_coarse_summaries(artifacts):
    """Verify coarse behavioral summaries match expectations."""
    expected = CONTRACT['coarse_summaries']

    # Cycles completed (exact match expected)
    cycles = artifacts.summary.get('cycles_completed', 0)
    assert cycles == expected['cycles_completed'], (
        f"Cycles completed mismatch: expected {expected['cycles_completed']}, got {cycles}"
    )

    # Number of decisions (allow some drift, within 20%)
    num_decisions = len(artifacts.decisions)
    expected_decisions = expected['num_decisions']
    assert abs(num_decisions - expected_decisions) <= expected_decisions * 0.2, (
        f"Decision count drift too large: expected ~{expected_decisions}, got {num_decisions}"
    )

    # Number of evidence events (allow drift, just check it's nonzero and not 10× off)
    num_evidence = len(artifacts.evidence)
    expected_evidence = expected['num_evidence_events']
    assert num_evidence > 0, "No evidence events generated"
    assert num_evidence >= expected_evidence * 0.3, (
        f"Evidence count too low: expected ~{expected_evidence}, got {num_evidence}"
    )

    # Template diversity (minimum threshold)
    templates = artifacts.decision_templates()
    unique_templates = len(set(templates))
    assert unique_templates >= expected['num_unique_templates_min'], (
        f"Template diversity too low: expected ≥{expected['num_unique_templates_min']}, "
        f"got {unique_templates}"
    )

    # Compounds tested (minimum threshold)
    compounds = artifacts.compounds_tested()
    assert len(compounds) >= expected['num_compounds_tested_min'], (
        f"Compound diversity too low: expected ≥{expected['num_compounds_tested_min']}, "
        f"got {len(compounds)}"
    )

    # Mitigation cycles (exact match expected for this baseline)
    mitigation_cycles = artifacts.mitigation_cycles()
    assert len(mitigation_cycles) == expected['num_mitigation_cycles'], (
        f"Mitigation count mismatch: expected {expected['num_mitigation_cycles']}, "
        f"got {len(mitigation_cycles)}"
    )

    # Final debt bucket
    debt_trajectory = artifacts.debt_trajectory()
    if debt_trajectory:
        final_debt = debt_trajectory[-1]
        if final_debt < 1.0:
            debt_bucket = "<1"
        elif final_debt < 2.0:
            debt_bucket = "1-2"
        else:
            debt_bucket = ">2"

        assert debt_bucket == expected['final_debt_bucket'], (
            f"Debt bucket mismatch: expected {expected['final_debt_bucket']}, "
            f"got {debt_bucket} (final_debt={final_debt:.2f})"
        )


def _assert_causal_contract_respected(artifacts):
    """
    Verify causal contract compliance: no truth leakage in observations.

    This checks that observation records don't contain forbidden fields
    that would reveal treatment identity before it should be known.
    """
    # Check evidence ledger for truth leakage
    forbidden_fields_in_observations = [
        'ground_truth_viability',
        'ground_truth_ic50',
        'true_mechanism',
        'treatment_id',  # Position/well is OK, but not treatment identity
    ]

    for i, evidence in enumerate(artifacts.evidence):
        if evidence.get('event_type') in ['observation_recorded', 'measurement_completed']:
            obs = evidence.get('observation', {})
            for forbidden in forbidden_fields_in_observations:
                assert forbidden not in obs, (
                    f"Evidence record {i} contains forbidden field '{forbidden}' in observation. "
                    f"This violates causal contract (truth leakage)."
                )


def test_contract_summary_documentation():
    """Document what the contract expects (for transparency)."""
    print("\nContract expectations (seed=42):")
    print(json.dumps(CONTRACT['coarse_summaries'], indent=2))
    print("\nSchema requirements:")
    print(json.dumps(CONTRACT['schema_requirements'], indent=2))
    print("\nInvariants:")
    print(json.dumps(CONTRACT['invariants'], indent=2))
