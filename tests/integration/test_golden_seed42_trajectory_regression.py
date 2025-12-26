"""
TRAJECTORY golden regression test for seed=42 baseline.

This test ensures bitwise-identical behavior (modulo timestamps/paths)
for a canonical fixed-seed run. It fails loudly on ANY behavioral change:
- Policy choice drift (even if better)
- Belief update drift (even if more accurate)
- Exact decision sequences
- Exact inference trajectories

PURPOSE: Run manually when you want to detect "did I change ANYTHING?"
NOT for CI: This test freezes agent behavior completely, blocking policy evolution.

USE CASE: Before/after refactors, policy tuning, or "should this have changed behavior?"

For CI enforcement, use test_golden_seed42_contract_regression.py instead.

If this test fails:
1. Determine if change was intentional (policy improvement, bug fix)
2. Update golden baseline via scripts/update_golden_seed42.py --reason "..."
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, normalize_for_comparison, find_latest_run_id


GOLDEN_DIR = Path(__file__).parent.parent / "golden" / "seed_42"
GOLDEN_MANIFEST = GOLDEN_DIR / "run_manifest.json"

# Fixed parameters for golden run
GOLDEN_SEED = 42
GOLDEN_CYCLES = 10
GOLDEN_BUDGET = 480  # Increased to accommodate epistemic actions (replication)


def test_golden_baseline_exists():
    """Verify golden baseline was generated."""
    assert GOLDEN_DIR.exists(), f"Golden baseline directory missing: {GOLDEN_DIR}"
    assert GOLDEN_MANIFEST.exists(), f"Golden manifest missing: {GOLDEN_MANIFEST}"

    with open(GOLDEN_MANIFEST, 'r') as f:
        manifest = json.load(f)

    assert manifest['seed'] == GOLDEN_SEED
    assert manifest['cycles'] == GOLDEN_CYCLES
    assert manifest['budget'] == GOLDEN_BUDGET


@pytest.mark.manual
def test_golden_seed42_trajectory_regression():
    """
    Run epistemic loop with seed=42 and compare against golden baseline.

    STRICT COMPARISON: Exact match required for all decisions, beliefs, evidence.
    Use this to detect ANY behavioral change, even improvements.

    Run with: pytest tests/integration/test_golden_seed42_trajectory_regression.py -m manual -v
    """
    # Load golden artifacts
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

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
        fresh_artifacts = load_ledgers(tmpdir, run_id)

    # Normalize both for comparison (strip timestamps, paths)
    golden_norm = {
        'evidence': normalize_for_comparison(golden_artifacts.evidence),
        'decisions': normalize_for_comparison(golden_artifacts.decisions),
        'diagnostics': normalize_for_comparison(golden_artifacts.diagnostics),
        'refusals': normalize_for_comparison(golden_artifacts.refusals),
        'mitigation': normalize_for_comparison(golden_artifacts.mitigation),
        'summary': normalize_for_comparison(golden_artifacts.summary),
    }

    fresh_norm = {
        'evidence': normalize_for_comparison(fresh_artifacts.evidence),
        'decisions': normalize_for_comparison(fresh_artifacts.decisions),
        'diagnostics': normalize_for_comparison(fresh_artifacts.diagnostics),
        'refusals': normalize_for_comparison(fresh_artifacts.refusals),
        'mitigation': normalize_for_comparison(fresh_artifacts.mitigation),
        'summary': normalize_for_comparison(fresh_artifacts.summary),
    }

    # Compare ledgers (strict equality)
    _assert_ledger_match(golden_norm['decisions'], fresh_norm['decisions'], "decisions")
    _assert_ledger_match(golden_norm['evidence'], fresh_norm['evidence'], "evidence")
    _assert_ledger_match(golden_norm['diagnostics'], fresh_norm['diagnostics'], "diagnostics")
    _assert_ledger_match(golden_norm['refusals'], fresh_norm['refusals'], "refusals")
    _assert_ledger_match(golden_norm['mitigation'], fresh_norm['mitigation'], "mitigation")

    # Compare summary (key fields only, allow minor drift in paths dict)
    _assert_summary_match(golden_norm['summary'], fresh_norm['summary'])


def _assert_ledger_match(golden: list, fresh: list, ledger_name: str):
    """Assert two ledgers are identical."""
    if len(golden) != len(fresh):
        pytest.fail(
            f"{ledger_name} ledger length mismatch:\n"
            f"  Golden: {len(golden)} records\n"
            f"  Fresh:  {len(fresh)} records\n"
            f"  This indicates policy behavior has changed."
        )

    for i, (g_rec, f_rec) in enumerate(zip(golden, fresh)):
        if g_rec != f_rec:
            # Pretty-print diff
            import pprint
            pytest.fail(
                f"{ledger_name} ledger record {i} mismatch:\n"
                f"Golden:\n{pprint.pformat(g_rec)}\n\n"
                f"Fresh:\n{pprint.pformat(f_rec)}\n\n"
                f"This indicates policy or belief update logic has changed."
            )


def _assert_summary_match(golden: dict, fresh: dict):
    """Assert summary JSON matches on key fields."""
    key_fields = ['cycles_completed', 'abort_reason', 'beliefs_final']

    for field in key_fields:
        if field not in golden or field not in fresh:
            continue  # Skip if field not present in either

        g_val = golden[field]
        f_val = fresh[field]

        if g_val != f_val:
            pytest.fail(
                f"Summary field '{field}' mismatch:\n"
                f"  Golden: {g_val}\n"
                f"  Fresh:  {f_val}\n"
            )


def test_golden_seed42_quick_metrics():
    """
    Sanity check: extract key metrics from golden baseline.

    This documents expected behavior for the golden run.
    """
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    # Document expected properties (adjust thresholds based on actual golden run)
    templates = golden_artifacts.decision_templates()
    compounds = golden_artifacts.compounds_tested()
    debt = golden_artifacts.debt_trajectory()

    # These are documentation, not strict assertions
    # (the main regression test above is the enforcement mechanism)
    print(f"\nGolden baseline metrics (seed={GOLDEN_SEED}):")
    print(f"  Unique templates: {len(set(templates))} (templates: {set(templates)})")
    print(f"  Compounds tested: {len(compounds)} (compounds: {compounds})")
    print(f"  Final debt: {debt[-1] if debt else 'N/A'} bits")
    print(f"  Cycles completed: {golden_artifacts.summary.get('cycles_completed', 'N/A')}")

    # Basic sanity (not strict, just smoke test)
    assert len(golden_artifacts.decisions) > 0, "Golden baseline has no decisions"
    assert len(golden_artifacts.summary) > 0, "Golden baseline has no summary"
