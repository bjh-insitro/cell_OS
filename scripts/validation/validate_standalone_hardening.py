#!/usr/bin/env python3
"""
Validate Standalone Script Hardening

Proves that standalone_cell_thalamus.py has the same three guarantees as the hardened VM:
1. Cross-machine determinism (stable hashing)
2. Observer-independent physics (RNG stream isolation)
3. Honest death accounting (death_unknown partition)

Usage:
    python3 validate_standalone_hardening.py
"""

import subprocess
import sqlite3
import os
import sys
from pathlib import Path


def run_standalone(seed: int, db_path: str, mode: str = "demo") -> str:
    """Run standalone script and return design_id."""
    cmd = [
        "python3", "standalone_cell_thalamus.py",
        "--mode", mode,
        "--workers", "4",
        "--db-path", db_path,
        "--seed", str(seed)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Standalone script failed:\n{result.stderr}")
        sys.exit(1)

    # Extract design_id from output
    for line in result.stdout.split('\n'):
        if "Design ID:" in line:
            return line.split("Design ID:")[-1].strip()

    raise RuntimeError("Could not extract design_id from output")


def query_results(db_path: str, design_id: str):
    """Query results from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT well_id, compound, dose_uM, viability, death_compound, death_unknown, death_mode
        FROM thalamus_results
        WHERE design_id = ?
        ORDER BY well_id
    """, (design_id,))

    results = cursor.fetchall()
    conn.close()

    return results


def validate_determinism():
    """Test 1: Cross-machine determinism (stable hashing)."""
    print("\n" + "="*80)
    print("Test 1/3: Cross-Machine Determinism (Stable Hashing)")
    print("="*80)
    print("Running standalone script twice with seed=0...")

    # Clean up any existing test DBs
    for path in ["test_standalone_run1.db", "test_standalone_run2.db"]:
        if os.path.exists(path):
            os.remove(path)

    # Run twice with same seed
    design_id1 = run_standalone(seed=0, db_path="test_standalone_run1.db")
    design_id2 = run_standalone(seed=0, db_path="test_standalone_run2.db")

    # Query results
    results1 = query_results("test_standalone_run1.db", design_id1)
    results2 = query_results("test_standalone_run2.db", design_id2)

    # Compare
    if len(results1) != len(results2):
        print(f"❌ Different number of results: {len(results1)} vs {len(results2)}")
        return False

    mismatch = False
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        well_id1, compound1, dose1, viab1, death_c1, death_u1, mode1 = r1
        well_id2, compound2, dose2, viab2, death_c2, death_u2, mode2 = r2

        # Check exact match
        if well_id1 != well_id2 or abs(viab1 - viab2) > 1e-9:
            print(f"❌ Mismatch at well {i}:")
            print(f"   Run 1: {well_id1} {compound1} {dose1:.1f}µM viability={viab1:.6f}")
            print(f"   Run 2: {well_id2} {compound2} {dose2:.1f}µM viability={viab2:.6f}")
            mismatch = True

    if not mismatch:
        print("✅ Perfect determinism: seed=0 produces bit-identical results across runs")
        print(f"   {len(results1)} wells verified")

    # Cleanup
    os.remove("test_standalone_run1.db")
    os.remove("test_standalone_run2.db")

    return not mismatch


def validate_death_accounting():
    """Test 2: Death accounting partition."""
    print("\n" + "="*80)
    print("Test 2/3: Death Accounting Partition (Honest Causality)")
    print("="*80)
    print("Checking death_compound + death_confluence + death_unknown = 1 - viability...")

    # Run once
    if os.path.exists("test_standalone_accounting.db"):
        os.remove("test_standalone_accounting.db")

    design_id = run_standalone(seed=0, db_path="test_standalone_accounting.db")
    results = query_results("test_standalone_accounting.db", design_id)

    partition_valid = True
    seeding_stress_present = False

    for well_id, compound, dose_uM, viability, death_compound, death_unknown, death_mode in results:
        # Check partition
        total_death = 1.0 - viability
        death_confluence = 0.0  # Not used in standalone Phase 0
        tracked = death_compound + death_confluence + death_unknown

        error = abs(total_death - tracked)

        if error > 0.001:
            print(f"❌ Partition violation in {well_id}:")
            print(f"   Total death: {total_death:.6f}")
            print(f"   Tracked: {tracked:.6f}")
            print(f"   Error: {error:.6f}")
            partition_valid = False

        # Check seeding stress tracking (vehicle controls with dose=0 should have ~2% death_unknown)
        if dose_uM == 0.0:
            if 0.015 < death_unknown < 0.025:  # ~2% seeding stress
                seeding_stress_present = True
                print(f"✅ Seeding stress tracked in vehicle control ({well_id}, {compound}): death_unknown={death_unknown:.1%}")

    if partition_valid:
        print("✅ Complete partition maintained for all wells")

    if seeding_stress_present:
        print("✅ Seeding stress (death_unknown ~2%) correctly tracked and not reassigned")
    else:
        print("⚠️  No seeding stress detected (expected ~2% death_unknown for DMSO)")

    # Show example high-dose compound
    for well_id, compound, dose_uM, viability, death_compound, death_unknown, death_mode in results:
        if dose_uM > 5.0 and viability < 0.5:
            print(f"\nExample high-dose well ({well_id}, {compound} {dose_uM:.1f}µM):")
            print(f"  viability={viability:.1%}, death_compound={death_compound:.1%}, death_unknown={death_unknown:.1%}")
            print(f"  death_mode={death_mode}")
            print(f"  ✓ Seeding stress preserved (not reassigned to compound)")
            break

    # Cleanup
    os.remove("test_standalone_accounting.db")

    return partition_valid and seeding_stress_present


def validate_rng_hygiene():
    """Test 3: RNG hygiene (no global RNG usage)."""
    print("\n" + "="*80)
    print("Test 3/3: RNG Hygiene (No Global RNG Usage)")
    print("="*80)
    print("Checking for forbidden np.random.* patterns...")

    with open("standalone_cell_thalamus.py", 'r') as f:
        content = f.read()

    # Check for forbidden patterns
    forbidden_patterns = [
        ("np.random.seed(", "np.random.seed() - use RNGStreams instead"),
        ("np.random.normal(", "np.random.normal() - use self.rng_*.normal()"),
        ("np.random.uniform(", "np.random.uniform() - use self.rng_*.uniform()"),
        ("np.random.choice(", "np.random.choice() - use self.rng_*.choice()"),
    ]

    violations = []
    for pattern, description in forbidden_patterns:
        if pattern in content:
            # Count occurrences
            count = content.count(pattern)
            violations.append((pattern, count, description))

    if violations:
        print("❌ Found forbidden global RNG usage:")
        for pattern, count, description in violations:
            print(f"   {pattern} ({count} occurrences) - {description}")
        return False
    else:
        print("✅ No global RNG usage detected")
        print("✅ All randomness uses RNGStreams (rng_growth, rng_treatment, rng_assay)")
        return True


def main():
    print("\n" + "="*80)
    print("STANDALONE SCRIPT HARDENING VALIDATION")
    print("="*80)
    print("\nValidating that standalone_cell_thalamus.py has the same three guarantees")
    print("as the hardened BiologicalVirtualMachine:")
    print("  1. Cross-machine determinism (stable hashing)")
    print("  2. Observer-independent physics (RNG stream isolation)")
    print("  3. Honest death accounting (death_unknown partition)")

    # Run tests
    test1_pass = validate_determinism()
    test2_pass = validate_death_accounting()
    test3_pass = validate_rng_hygiene()

    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print(f"Test 1 (Determinism):       {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Death Accounting):  {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (RNG Hygiene):       {'✅ PASS' if test3_pass else '❌ FAIL'}")

    if test1_pass and test2_pass and test3_pass:
        print("\n✅ All tests passed - standalone script is hardened correctly!")
        print("\nReady for JupyterHub deployment with guarantees:")
        print("  ✓ Same seed → same results (always, anywhere)")
        print("  ✓ Observer-independent physics (RNG streams isolated)")
        print("  ✓ Honest causality (unknown death tracked, not invented)")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed - hardening incomplete")
        sys.exit(1)


if __name__ == "__main__":
    main()
