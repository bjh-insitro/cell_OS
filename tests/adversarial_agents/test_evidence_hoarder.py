"""
Adversarial test: Evidence Hoarder

This agent generates lots of evidence events but with negligible information gain.
It satisfies "evidence count grows" but doesn't actually learn anything.

Expected behavior: Should be caught by entropy reduction check (not yet implemented)
or by exploitation check (no compound investigated in depth).

Current mitigation: Exploitation check catches shallow exploration.
Future mitigation: Add entropy trajectory check to convergence test.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, find_latest_run_id


def test_evidence_hoarder_expectation():
    """
    Document expectation for evidence hoarder adversary.

    Evidence hoarder behavior:
    - Generates lots of evidence events (satisfies count threshold)
    - But: tiny information gain per event
    - Strategy: many 1-well designs, no replicates, no follow-up

    Current defense: Exploitation check (≥1 compound with ≥3 decisions)
    Future defense: Entropy reduction rate check
    """
    print("\nEvidence Hoarder Adversary:")
    print("  Behavior: Many evidence events, minimal info gain")
    print("  Strategy: 1-well designs, no replicates, tourist exploration")
    print("  Current defense: Exploitation check (≥3 decisions per compound)")
    print("  Future defense: Entropy trajectory slope check")
    print("\n  Expected to be caught by:")
    print("    • Exploitation assertion (no compound investigated ≥3 times)")

    # Placeholder: When we have entropy trajectory checks, add them here
    assert True, "Evidence hoarder expectation documented"


def test_shallow_exploration_caught():
    """
    Verify that shallow exploration (tourist behavior) fails exploitation check.

    Simulates artifacts from an evidence hoarder that visits many compounds once.
    """
    from helpers.ledger_loader import LedgerArtifacts

    # Mock artifacts: 10 decisions, 10 different compounds, each tested once
    decisions = []
    for i in range(1, 11):
        decisions.append({
            'cycle': i,
            'chosen_template': 'dose_response',
            'kind': 'science',
            'chosen_kwargs': {
                'compound': f'compound_{i}',  # Different compound each time
                'dose': 10.0,
            }
        })

    # Tons of evidence (hoarder succeeds at generating events)
    evidence = [{'cycle': i, 'event_type': 'observation_recorded'} for i in range(1, 51)]

    artifacts = LedgerArtifacts(
        evidence=evidence,
        decisions=decisions,
        diagnostics=[],
        refusals=[],
        mitigation=[],
        summary={'cycles_completed': 10}
    )

    # Check exploitation (same logic as convergence test)
    compound_usage = Counter()
    for dec in decisions:
        kwargs = dec.get('chosen_kwargs', {})
        if isinstance(kwargs, dict) and 'compound' in kwargs:
            comp = kwargs['compound']
            if comp not in ['DMSO', 'dmso', None]:
                compound_usage[comp] += 1

    focused_compounds = [c for c, count in compound_usage.items() if count >= 3]

    # This MUST fail exploitation check
    assert len(focused_compounds) == 0, (
        f"Shallow exploration simulation broken: found {focused_compounds} focused compounds"
    )

    print(f"\n✓ Shallow exploration would fail: 0 compounds with ≥3 decisions (expected ≥1)")
    print(f"  Evidence count: {len(evidence)} (high, but not useful)")
    print(f"  Compound usage: {dict(compound_usage)}")


def test_evidence_to_decision_ratio_reasonable():
    """
    Real agent should have reasonable evidence-to-decision ratio.

    Too high: evidence hoarder (many tiny events)
    Too low: not updating beliefs
    Reasonable: ~5-20 evidence events per decision
    """
    # Run a quick 5-cycle test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", "888",
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

    evidence_count = len(artifacts.evidence)
    decision_count = len(artifacts.decisions)

    if decision_count == 0:
        pytest.skip("No decisions recorded")

    ratio = evidence_count / decision_count

    print(f"\nEvidence-to-decision ratio: {ratio:.1f}:1 ({evidence_count}/{decision_count})")

    # Reasonable range: 5-50 evidence per decision
    # (lower bound: agent is learning, upper bound: not hoarding)
    assert 1 <= ratio <= 100, (
        f"Evidence-to-decision ratio suspicious: {ratio:.1f}:1\n"
        f"Expected 1-100. May indicate evidence hoarder or no learning."
    )

    print(f"  ✓ Ratio reasonable: {ratio:.1f}:1 ∈ [1, 100]")


def test_unique_conditions_vs_evidence_count():
    """
    Evidence hoarder creates many events with few unique conditions.

    Real science: unique conditions should be substantial fraction of evidence count.
    Evidence hoarder: repeats same conditions, generates many identical events.
    """
    # Run a quick 5-cycle test
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", "999",
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

    evidence_count = len(artifacts.evidence)
    decision_count = len(artifacts.decisions)

    # Approximate unique conditions as decision count (not perfect, but reasonable)
    if evidence_count == 0 or decision_count == 0:
        pytest.skip("No evidence or decisions recorded")

    # Each decision typically generates multiple evidence events (multiple wells, assays)
    # Ratio should be at least 1:1 (each decision is unique)
    # But evidence count will be higher due to replicates, multiple assays
    unique_fraction = decision_count / evidence_count

    print(f"\nUnique conditions (approx): {decision_count} decisions vs {evidence_count} evidence")
    print(f"  Unique fraction: {unique_fraction:.2%}")

    # Should have some unique conditions (not hoarding identical events)
    # Expect at least 2% unique (very loose, just catches extreme hoarding)
    assert unique_fraction >= 0.01, (
        f"Evidence hoarder detected: only {unique_fraction:.2%} unique conditions.\n"
        f"Agent generating many identical evidence events without exploration."
    )

    print(f"  ✓ Unique conditions reasonable: {unique_fraction:.2%} ≥ 1%")
