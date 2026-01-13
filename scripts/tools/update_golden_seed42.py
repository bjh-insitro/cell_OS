#!/usr/bin/env python3
"""
Update the golden baseline for seed=42 regression test.

Usage:
    python scripts/update_golden_seed42.py --reason "..." --approved-by "..."

This script:
1. Runs the epistemic agent with fixed parameters (seed=42, cycles=10, budget=240)
2. Copies the ledger artifacts to tests/golden/seed_42/
3. Writes VERSION.json with audit trail (reason, approver, changes)
4. Writes run_manifest.json with run parameters

Only run this when you've intentionally changed behavior and want to
update the regression baseline. Requires explicit reason and approval.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from helpers.ledger_loader import find_latest_run_id


# Golden parameters (must match test_golden_seed42_regression.py)
GOLDEN_SEED = 42
GOLDEN_CYCLES = 10
GOLDEN_BUDGET = 480  # Increased to accommodate epistemic actions (replication)

GOLDEN_DIR = project_root / "tests" / "golden" / "seed_42"


def compute_ledger_diff(old_dir, new_tmp_dir, run_id):
    """Compute summary of changes between old and new golden artifacts."""
    changes = {}

    for ledger_name in ['evidence', 'decisions', 'diagnostics']:
        old_file = old_dir / f"golden_{ledger_name}.jsonl"
        new_file = new_tmp_dir / f"{run_id}_{ledger_name}.jsonl"

        if old_file.exists():
            with open(old_file, 'r') as f:
                old_count = sum(1 for _ in f)
        else:
            old_count = 0

        if new_file.exists():
            with open(new_file, 'r') as f:
                new_count = sum(1 for _ in f)
        else:
            new_count = 0

        if old_count != new_count:
            changes[ledger_name] = f"{old_count} → {new_count} records"
        elif old_count > 0:
            changes[ledger_name] = "Record count unchanged, content may differ"

    return changes if changes else {"all": "No structural changes detected"}


def get_git_commit():
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()[:8]  # Short hash
    except Exception:
        pass
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Update golden baseline for seed=42")
    parser.add_argument(
        "--reason",
        required=True,
        help="Reason for updating golden baseline (e.g., 'Fixed epistemic action bug', 'Improved belief update')"
    )
    parser.add_argument(
        "--approved-by",
        required=True,
        help="Name of person approving this change (e.g., 'bjh', 'alice')"
    )
    parser.add_argument(
        "--skip-confirm",
        action="store_true",
        help="Skip confirmation prompt (for automation)"
    )

    args = parser.parse_args()

    print("="*60)
    print("UPDATING GOLDEN BASELINE (seed=42)")
    print("="*60)
    print(f"  Seed: {GOLDEN_SEED}")
    print(f"  Cycles: {GOLDEN_CYCLES}")
    print(f"  Budget: {GOLDEN_BUDGET}")
    print(f"  Reason: {args.reason}")
    print(f"  Approved by: {args.approved_by}")
    print(f"  Git commit: {get_git_commit()}")
    print()

    # Confirm with user (unless skipped)
    if not args.skip_confirm:
        response = input("This will overwrite the golden baseline. Continue? [y/N] ")
        if response.lower() != 'y':
            print("Aborted.")
            return 1

    # Run agent in temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print("\nRunning epistemic agent...")
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

        # Print output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)

        # Allow policy aborts
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            print(f"\n❌ Agent run failed with exit code {result.returncode}")
            return 1

        # Find run artifacts
        run_id = find_latest_run_id(tmpdir)
        if run_id is None:
            print("\n❌ No run artifacts found in temp dir")
            return 1

        print(f"\n✓ Run completed: {run_id}")

        # Copy artifacts to golden dir
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

        ledger_files = [
            f"{run_id}_evidence.jsonl",
            f"{run_id}_decisions.jsonl",
            f"{run_id}_diagnostics.jsonl",
            f"{run_id}_refusals.jsonl",
            f"{run_id}_mitigation.jsonl",
            f"{run_id}.json",
        ]

        print("\nCopying ledgers to golden baseline:")
        for ledger in ledger_files:
            src = tmpdir / ledger
            if src.exists():
                # Rename to "golden_*.jsonl" for clarity
                dst_name = ledger.replace(run_id, "golden")
                dst = GOLDEN_DIR / dst_name
                shutil.copy2(src, dst)
                print(f"  ✓ {dst_name}")
            else:
                print(f"  ⚠️  {ledger} not found (may be empty)")

        # Compute diff before overwriting
        print("\nComputing changes...")
        changes_summary = compute_ledger_diff(GOLDEN_DIR, tmpdir, run_id)

        # Write run manifest
        manifest = {
            "seed": GOLDEN_SEED,
            "cycles": GOLDEN_CYCLES,
            "budget": GOLDEN_BUDGET,
            "updated_at": datetime.now().isoformat(),
            "run_id": run_id,
            "notes": "Golden baseline for regression testing. Do not modify manually."
        }

        manifest_path = GOLDEN_DIR / "run_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"  ✓ run_manifest.json")

        # Write VERSION.json with audit trail
        version_data = {
            "schema_version": "v1.0",
            "generated_date": datetime.now().isoformat(),
            "generator_script": "scripts/update_golden_seed42.py",
            "cell_os_commit": get_git_commit(),
            "reason": args.reason,
            "approved_by": args.approved_by,
            "changes_summary": changes_summary
        }

        version_path = GOLDEN_DIR / "VERSION.json"
        with open(version_path, 'w') as f:
            json.dump(version_data, f, indent=2)

        print(f"  ✓ VERSION.json")

    print("\n" + "="*60)
    print("✓ GOLDEN BASELINE UPDATED")
    print("="*60)
    print(f"Location: {GOLDEN_DIR}")
    print(f"\nChanges summary:")
    for ledger, change in changes_summary.items():
        print(f"  • {ledger}: {change}")
    print("\nNext steps:")
    print("  1. Run: pytest tests/integration/test_golden_seed42_trajectory_regression.py -m manual -v")
    print("  2. Run: pytest tests/integration/test_golden_seed42_contract_regression.py -v")
    print("  3. Review VERSION.json audit trail")
    print("  4. Commit the updated golden baseline files")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
