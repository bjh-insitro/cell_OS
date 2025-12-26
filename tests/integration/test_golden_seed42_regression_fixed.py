"""
Golden output regression test for seed=42 baseline (FIXED VERSION).

**KEY ARCHITECTURAL DECISION**:
This test enforces CONTRACT COMPLIANCE, not POLICY PERSONALITY.

What is enforced (tight):
- Determinism: same seed → same simulator outputs
- Schema stability: ledger structure doesn't change
- Invariants: no contract violations (debt, QC, conservation)
- High-level metrics: cycles completed, budget spent

What is NOT enforced (loose):
- Exact decision sequence (policy can evolve)
- Exact belief trajectory (as long as contracts respected)
- Exact template order (as long as diversity achieved)

If this test fails, either:
1. You broke determinism or a contract → FIX THE BUG
2. You changed policy intentionally → UPDATE GOLDEN with scripts/update_golden_seed42.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, normalize_for_comparison, find_latest_run_id


GOLDEN_DIR = Path(__file__).parent.parent / "golden" / "seed_42"
GOLDEN_MANIFEST = GOLDEN_DIR / "run_manifest.json"

# Fixed parameters for golden run
GOLDEN_SEED = 42
GOLDEN_CYCLES = 10
GOLDEN_BUDGET = 240


def test_golden_baseline_exists():
    """Verify golden baseline was generated."""
    assert GOLDEN_DIR.exists(), f"Golden baseline directory missing: {GOLDEN_DIR}"
    assert GOLDEN_MANIFEST.exists(), f"Golden manifest missing: {GOLDEN_MANIFEST}"

    with open(GOLDEN_MANIFEST, 'r') as f:
        manifest = json.load(f)

    assert manifest['seed'] == GOLDEN_SEED
    assert manifest['cycles'] == GOLDEN_CYCLES
    assert manifest['budget'] == GOLDEN_BUDGET


def test_golden_schema_stability():
    """
    Test that ledger schemas remain stable (keys don't change).

    This catches breaking changes to ledger structure without over-constraining values.
    """
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    # Run fresh instance
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

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
            timeout=120,
        )

        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Agent run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found"

        fresh_artifacts = load_ledgers(tmpdir, run_id)

    # Compare schemas (keys), not values
    _assert_schema_match(golden_artifacts.decisions, fresh_artifacts.decisions, "decisions")
    _assert_schema_match(golden_artifacts.diagnostics, fresh_artifacts.diagnostics, "diagnostics")
    _assert_schema_match([golden_artifacts.summary], [fresh_artifacts.summary], "summary")


def test_golden_determinism():
    """
    Test that same seed produces same high-level metrics.

    This enforces determinism without freezing exact policy choices.
    """
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    # Run fresh instance
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

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
            timeout=120,
        )

        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Agent run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found"

        fresh_artifacts = load_ledgers(tmpdir, run_id)

    # Compare high-level metrics (LOOSE comparison)
    g_summary = golden_artifacts.summary
    f_summary = fresh_artifacts.summary

    # STRICT: cycles completed, budget spent
    assert g_summary.get('cycles_completed') == f_summary.get('cycles_completed'), (
        f"Cycles mismatch: golden={g_summary.get('cycles_completed')}, "
        f"fresh={f_summary.get('cycles_completed')}"
    )

    g_budget = g_summary.get('budget', GOLDEN_BUDGET) - g_summary.get('budget_remaining', 0)
    f_budget = f_summary.get('budget', GOLDEN_BUDGET) - f_summary.get('budget_remaining', 0)
    assert g_budget == f_budget, f"Budget spent mismatch: golden={g_budget}, fresh={f_budget}"

    # LOOSE: template diversity (allow ±1 difference)
    g_templates = set(golden_artifacts.decision_templates())
    f_templates = set(fresh_artifacts.decision_templates())
    template_diff = abs(len(g_templates) - len(f_templates))
    assert template_diff <= 1, (
        f"Template diversity changed significantly:\n"
        f"  Golden: {len(g_templates)} templates ({g_templates})\n"
        f"  Fresh: {len(f_templates)} templates ({f_templates})\n"
        f"  This may indicate policy drift."
    )

    # LOOSE: compound exploration (allow ±1 difference)
    g_compounds = set(golden_artifacts.compounds_tested())
    f_compounds = set(fresh_artifacts.compounds_tested())
    compound_diff = abs(len(g_compounds) - len(f_compounds))
    assert compound_diff <= 1, (
        f"Compound exploration changed significantly:\n"
        f"  Golden: {len(g_compounds)} compounds ({g_compounds})\n"
        f"  Fresh: {len(f_compounds)} compounds ({f_compounds})\n"
        f"  This may indicate policy drift."
    )

    # Print diagnostics
    print(f"\n=== Golden Determinism Check (seed={GOLDEN_SEED}) ===")
    print(f"Cycles: {f_summary.get('cycles_completed')} (golden: {g_summary.get('cycles_completed')})")
    print(f"Budget spent: {f_budget} (golden: {g_budget})")
    print(f"Templates: {len(f_templates)} (golden: {len(g_templates)})")
    print(f"Compounds: {len(f_compounds)} (golden: {len(g_compounds)})")


def test_golden_contract_invariants():
    """
    Test that contract invariants hold (no violations logged).

    This enforces honesty contracts without caring about exact choices.
    """
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    # Run fresh instance
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

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
            timeout=120,
        )

        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Agent run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found"

        fresh_artifacts = load_ledgers(tmpdir, run_id)

    # Check contract violations
    debt_trajectory = fresh_artifacts.debt_trajectory()
    final_debt = debt_trajectory[-1] if debt_trajectory else 0.0

    # INVARIANT 1: Debt should not explode (>5 bits suggests broken enforcement)
    assert final_debt < 5.0, (
        f"Debt explosion detected: {final_debt:.3f} bits (threshold: 5.0)\n"
        f"This suggests epistemic debt enforcement is broken."
    )

    # INVARIANT 2: No silent contract violations in diagnostics
    for diag in fresh_artifacts.diagnostics:
        if 'contract_violation' in str(diag).lower():
            pytest.fail(f"Contract violation detected: {diag}")

    # INVARIANT 3: Refusals should have valid reasons
    for refusal in fresh_artifacts.refusals:
        reason = refusal.get('refusal_reason', '')
        assert len(reason) > 0, f"Refusal with empty reason: {refusal}"

    print(f"\n✓ Contract invariants hold:")
    print(f"  Final debt: {final_debt:.3f} < 5.0 bits")
    print(f"  No contract violations logged")
    print(f"  All refusals have reasons ({len(fresh_artifacts.refusals)} total)")


def _assert_schema_match(golden_records: list, fresh_records: list, ledger_name: str):
    """Assert two ledgers have the same schema (keys), not necessarily same values."""
    if not golden_records or not fresh_records:
        return  # Skip if either is empty

    # Sample first record from each
    g_sample = golden_records[0] if golden_records else {}
    f_sample = fresh_records[0] if fresh_records else {}

    g_keys = set(g_sample.keys())
    f_keys = set(f_sample.keys())

    missing_keys = g_keys - f_keys
    extra_keys = f_keys - g_keys

    if missing_keys or extra_keys:
        pytest.fail(
            f"{ledger_name} schema mismatch:\n"
            f"  Missing keys: {missing_keys}\n"
            f"  Extra keys: {extra_keys}\n"
            f"  This indicates a breaking change to ledger structure."
        )


def test_golden_quick_metrics():
    """
    Sanity check: extract key metrics from golden baseline.

    This documents expected behavior for the golden run.
    """
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    templates = golden_artifacts.decision_templates()
    compounds = golden_artifacts.compounds_tested()
    debt = golden_artifacts.debt_trajectory()

    print(f"\nGolden baseline metrics (seed={GOLDEN_SEED}):")
    print(f"  Unique templates: {len(set(templates))} (templates: {set(templates)})")
    print(f"  Compounds tested: {len(compounds)} (compounds: {compounds})")
    print(f"  Final debt: {debt[-1] if debt else 'N/A'} bits")
    print(f"  Cycles completed: {golden_artifacts.summary.get('cycles_completed', 'N/A')}")

    assert len(golden_artifacts.decisions) > 0, "Golden baseline has no decisions"
    assert len(golden_artifacts.summary) > 0, "Golden baseline has no summary"
