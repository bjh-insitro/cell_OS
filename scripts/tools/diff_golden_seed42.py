#!/usr/bin/env python3
"""
Show diff between current behavior and golden baseline for seed=42.

Usage:
    python scripts/diff_golden_seed42.py

This script:
1. Runs the epistemic agent with golden parameters (seed=42)
2. Compares output against golden baseline
3. Shows first differing line per ledger + summary delta

Useful for understanding what changed before regenerating golden baseline.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from helpers.ledger_loader import load_ledgers, find_latest_run_id, normalize_for_comparison

# Golden parameters
GOLDEN_SEED = 42
GOLDEN_CYCLES = 10
GOLDEN_BUDGET = 240
GOLDEN_DIR = project_root / "tests" / "golden" / "seed_42"


def show_first_diff(golden_records, fresh_records, ledger_name):
    """Show first differing record between golden and fresh."""
    if len(golden_records) != len(fresh_records):
        print(f"\n  Length mismatch: {len(golden_records)} → {len(fresh_records)} records")
        return

    for i, (g_rec, f_rec) in enumerate(zip(golden_records, fresh_records)):
        if g_rec != f_rec:
            print(f"\n  First diff at record {i}:")
            # Show diff of a few key fields
            for key in ['cycle', 'chosen_template', 'event_type', 'kind']:
                if key in g_rec or key in f_rec:
                    g_val = g_rec.get(key, '<missing>')
                    f_val = f_rec.get(key, '<missing>')
                    if g_val != f_val:
                        print(f"    {key}: {g_val} → {f_val}")
            return

    print("  Records identical (structure)")


def main():
    print("="*60)
    print("DIFF: Current behavior vs Golden baseline (seed=42)")
    print("="*60)
    print(f"  Seed: {GOLDEN_SEED}")
    print(f"  Cycles: {GOLDEN_CYCLES}")
    print(f"  Budget: {GOLDEN_BUDGET}")
    print()

    # Load golden baseline
    print("Loading golden baseline...")
    golden_artifacts = load_ledgers(GOLDEN_DIR, "golden")

    # Run fresh instance in temp dir
    print("Running fresh instance...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = project_root / "scripts" / "run_epistemic_agent.py"
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

        # Allow policy aborts
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            print("\n❌ Fresh run failed:")
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr, file=sys.stderr)
            return 1

        # Find run ID
        run_id = find_latest_run_id(tmpdir)
        if run_id is None:
            print("\n❌ No run artifacts found")
            return 1

        # Load fresh artifacts
        fresh_artifacts = load_ledgers(tmpdir, run_id)

    # Normalize both
    golden_norm = {
        'evidence': normalize_for_comparison(golden_artifacts.evidence),
        'decisions': normalize_for_comparison(golden_artifacts.decisions),
        'diagnostics': normalize_for_comparison(golden_artifacts.diagnostics),
    }

    fresh_norm = {
        'evidence': normalize_for_comparison(fresh_artifacts.evidence),
        'decisions': normalize_for_comparison(fresh_artifacts.decisions),
        'diagnostics': normalize_for_comparison(fresh_artifacts.diagnostics),
    }

    # Compare ledgers
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)

    all_match = True

    for ledger_name in ['decisions', 'evidence', 'diagnostics']:
        golden_recs = golden_norm[ledger_name]
        fresh_recs = fresh_norm[ledger_name]

        if golden_recs == fresh_recs:
            print(f"\n✓ {ledger_name}: MATCH ({len(golden_recs)} records)")
        else:
            all_match = False
            print(f"\n✗ {ledger_name}: DIFF")
            show_first_diff(golden_recs, fresh_recs, ledger_name)

    # Show summary delta
    print("\n" + "="*60)
    print("SUMMARY DELTA")
    print("="*60)

    golden_templates = golden_artifacts.decision_templates()
    fresh_templates = fresh_artifacts.decision_templates()
    print(f"Templates: {len(set(golden_templates))} → {len(set(fresh_templates))}")

    golden_compounds = golden_artifacts.compounds_tested()
    fresh_compounds = fresh_artifacts.compounds_tested()
    print(f"Compounds: {len(golden_compounds)} → {len(fresh_compounds)}")

    golden_debt = golden_artifacts.debt_trajectory()
    fresh_debt = fresh_artifacts.debt_trajectory()
    if golden_debt and fresh_debt:
        print(f"Final debt: {golden_debt[-1]:.3f} → {fresh_debt[-1]:.3f} bits")

    print(f"Evidence events: {len(golden_artifacts.evidence)} → {len(fresh_artifacts.evidence)}")
    print(f"Decisions: {len(golden_artifacts.decisions)} → {len(fresh_artifacts.decisions)}")

    # Overall result
    print("\n" + "="*60)
    if all_match:
        print("✓ BEHAVIOR IDENTICAL TO GOLDEN BASELINE")
    else:
        print("✗ BEHAVIOR DIFFERS FROM GOLDEN BASELINE")
        print("\nTo update golden baseline:")
        print('  python scripts/update_golden_seed42.py --reason "..." --approved-by "..."')
    print("="*60)

    return 0 if all_match else 1


if __name__ == "__main__":
    sys.exit(main())
