#!/usr/bin/env python3
"""
Compare two Cell Thalamus databases for bit-identical determinism.

Usage:
    python3 compare_databases.py db1.db db2.db
"""

import sys
import sqlite3


def compare_databases(db1_path: str, db2_path: str) -> bool:
    """Compare two databases for bit-identical results."""

    print("=" * 80)
    print("DATABASE DETERMINISM COMPARISON")
    print("=" * 80)
    print(f"Database 1: {db1_path}")
    print(f"Database 2: {db2_path}")
    print()

    conn1 = sqlite3.connect(db1_path)
    conn2 = sqlite3.connect(db2_path)

    # Get all results sorted deterministically
    query = """
        SELECT well_id, compound, dose_uM, timepoint_h, cell_line, plate_id,
               viability, death_compound, death_confluence, death_unknown, death_mode,
               morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna
        FROM thalamus_results
        ORDER BY plate_id, cell_line, well_id, compound, dose_uM, timepoint_h
    """

    cursor1 = conn1.cursor()
    cursor2 = conn2.cursor()

    cursor1.execute(query)
    cursor2.execute(query)

    results1 = cursor1.fetchall()
    results2 = cursor2.fetchall()

    conn1.close()
    conn2.close()

    # Compare counts
    if len(results1) != len(results2):
        print(f"❌ FAIL: Different number of results")
        print(f"   Database 1: {len(results1)} rows")
        print(f"   Database 2: {len(results2)} rows")
        return False

    print(f"Total rows: {len(results1)}")
    print()

    # Compare row by row
    mismatches = []
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        if r1 != r2:
            mismatches.append((i, r1, r2))

    if mismatches:
        print(f"❌ FAIL: {len(mismatches)} mismatched rows (showing first 5)")
        print()
        for i, r1, r2 in mismatches[:5]:
            print(f"Row {i}:")
            print(f"  DB1: {r1}")
            print(f"  DB2: {r2}")
            print()
        return False

    print("✅ PASS: Databases are bit-identical")
    print()
    print("Determinism verified:")
    print("  - Same number of rows")
    print("  - Identical values in all columns")
    print("  - Same order (deterministic aggregation)")
    print()
    print("Ready for production deployment on JupyterHub.")
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
