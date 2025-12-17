#!/usr/bin/env python3
"""
Compare two Cell Thalamus databases for determinism.

Uses order-independent comparison (sorted row hashes) as the primary signal.
Order-dependent comparison (raw byte equality) is secondary - SQLite internals
can differ for reasons unrelated to biology.

Usage:
    python3 compare_databases.py db1.db db2.db
"""

import sys
import sqlite3
import hashlib


def hash_row(row) -> str:
    """Hash a row for order-independent comparison."""
    # Convert to string and hash
    row_str = str(row).encode('utf-8')
    return hashlib.blake2s(row_str, digest_size=16).hexdigest()


def compare_databases(db1_path: str, db2_path: str) -> bool:
    """Compare two databases for determinism."""

    print("=" * 80)
    print("DATABASE DETERMINISM COMPARISON")
    print("=" * 80)
    print(f"Database 1: {db1_path}")
    print(f"Database 2: {db2_path}")
    print()

    conn1 = sqlite3.connect(db1_path)
    conn2 = sqlite3.connect(db2_path)

    cursor1 = conn1.cursor()
    cursor2 = conn2.cursor()

    # 1. Compare schema
    print("1/3: Checking schema...")
    cursor1.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
    schema1 = cursor1.fetchall()

    cursor2.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
    schema2 = cursor2.fetchall()

    if schema1 != schema2:
        print("❌ FAIL: Different schema")
        print(f"   DB1 tables: {len(schema1)}")
        print(f"   DB2 tables: {len(schema2)}")
        conn1.close()
        conn2.close()
        return False

    print(f"   ✓ Schema identical ({len(schema1)} tables)")
    print()

    # 2. Compare row counts
    print("2/3: Checking row counts...")
    cursor1.execute("SELECT COUNT(*) FROM thalamus_results")
    count1 = cursor1.fetchone()[0]

    cursor2.execute("SELECT COUNT(*) FROM thalamus_results")
    count2 = cursor2.fetchone()[0]

    if count1 != count2:
        print(f"❌ FAIL: Different row counts")
        print(f"   Database 1: {count1} rows")
        print(f"   Database 2: {count2} rows")
        conn1.close()
        conn2.close()
        return False

    print(f"   ✓ Row count matches ({count1} rows)")
    print()

    # 3. Order-independent comparison (sorted row hashes)
    print("3/3: Comparing row hashes (order-independent)...")

    # Get all results sorted deterministically by stable key
    query = """
        SELECT plate_id, cell_line, well_id, compound, dose_uM, timepoint_h,
               viability, death_compound, death_confluence, death_unknown, death_mode,
               morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna,
               atp_signal, transport_dysfunction_score
        FROM thalamus_results
        ORDER BY plate_id, cell_line, well_id, compound, dose_uM, timepoint_h
    """

    cursor1.execute(query)
    results1 = cursor1.fetchall()

    cursor2.execute(query)
    results2 = cursor2.fetchall()

    conn1.close()
    conn2.close()

    # Hash each row and compare
    hashes1 = [hash_row(r) for r in results1]
    hashes2 = [hash_row(r) for r in results2]

    # Check for mismatches
    mismatches = []
    for i, (h1, h2, r1, r2) in enumerate(zip(hashes1, hashes2, results1, results2)):
        if h1 != h2:
            mismatches.append((i, r1, r2))

    if mismatches:
        print(f"❌ FAIL: {len(mismatches)} mismatched rows (showing first 3)")
        print()
        for i, r1, r2 in mismatches[:3]:
            print(f"Row {i} (plate={r1[0]}, well={r1[2]}):")
            print(f"  DB1: viab={r1[6]:.6f}, death_comp={r1[7]:.6f}, morph_er={r1[11]:.6f}")
            print(f"  DB2: viab={r2[6]:.6f}, death_comp={r2[7]:.6f}, morph_er={r2[11]:.6f}")
            print()

        # Check if differences are floating-point noise
        max_diff = 0.0
        for i, r1, r2 in mismatches:
            for v1, v2 in zip(r1, r2):
                if isinstance(v1, float) and isinstance(v2, float):
                    max_diff = max(max_diff, abs(v1 - v2))

        if max_diff > 0 and max_diff < 1e-6:
            print(f"⚠️  Note: Max difference is {max_diff:.2e} (floating point noise)")
            print(f"   This is likely BLAS nondeterminism - set OMP_NUM_THREADS=1")

        return False

    print(f"   ✓ All row hashes match")
    print()

    print("✅ PASS: Databases are deterministically identical")
    print()
    print("Verification complete:")
    print("  ✓ Same schema")
    print("  ✓ Same row count")
    print("  ✓ Identical values (order-independent comparison)")
    print()
    print("Note: This comparison is order-independent. SQLite file bytes may still")
    print("      differ for internal reasons, but biological results are identical.")
    print("=" * 80)

    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 compare_databases.py db1.db db2.db")
        sys.exit(1)

    db1 = sys.argv[1]
    db2 = sys.argv[2]

    success = compare_databases(db1, db2)
    sys.exit(0 if success else 1)
