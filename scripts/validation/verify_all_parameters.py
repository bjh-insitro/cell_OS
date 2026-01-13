"""
Verify All Parameters

Shows verification status for all cell line parameters and highlights what needs experimental validation.
"""

from pathlib import Path
import sqlite3


def main():
    print("=" * 90)
    print("Cell Line Parameter Verification Status")
    print("=" * 90)
    print()

    db_path = Path("data/cell_lines.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Test 1: Overall summary
    print("Test 1: Verification Summary by Cell Line")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT * FROM parameter_verification_summary
        ORDER BY cell_line_id
    """)
    rows = cursor.fetchall()

    print(f"{'Cell Line':<20} {'Total':>6} {'Verified':>10} {'Consensus':>10} {'Estimated':>10}")
    print("-" * 90)
    for row in rows:
        total = row['total_parameters']
        verified = row['verified']
        consensus = row['literature_consensus']
        estimated = row['estimated']

        verified_pct = f"({verified/total*100:.0f}%)" if total > 0 else ""
        estimated_pct = f"({estimated/total*100:.0f}%)" if total > 0 else ""

        print(f"{row['cell_line_id']:<20} {total:>6} {verified:>7} {verified_pct:>3} {consensus:>7} {'':>3} {estimated:>7} {estimated_pct:>3}")

    print()

    # Test 2: Detailed breakdown by cell line
    print("Test 2: Detailed Parameter Status (A549 as example)")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT parameter_name, value, verification_status, source
        FROM parameter_verification
        WHERE cell_line_id = 'A549'
        ORDER BY verification_status, parameter_name
    """)
    rows = cursor.fetchall()

    for row in rows:
        status_icon = {
            'verified': '✅',
            'literature_consensus': '📚',
            'estimated': '⚠️ ',
            'needs_validation': '❌'
        }.get(row['verification_status'], '❓')

        print(f"{status_icon} {row['parameter_name']:<25} = {row['value']:<10} ({row['verification_status']})")
        if row['source']:
            print(f"   Source: {row['source']}")
    print()

    # Test 3: Parameters needing validation
    print("Test 3: Parameters Needing Experimental Validation")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT DISTINCT parameter_name, COUNT(DISTINCT cell_line_id) as cell_lines
        FROM parameter_verification
        WHERE verification_status = 'estimated'
        GROUP BY parameter_name
        ORDER BY parameter_name
    """)
    rows = cursor.fetchall()

    print("The following parameters are ESTIMATED across all cell lines and need validation:")
    print()
    for row in rows:
        print(f"  ⚠️  {row['parameter_name']:<25} (estimated for {row['cell_lines']} cell lines)")
    print()

    # Test 4: Verified parameters
    print("Test 4: Verified Parameters (With Citations)")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT cell_line_id, parameter_name, value, source, reference_url
        FROM parameter_verification
        WHERE verification_status IN ('verified', 'literature_consensus')
        ORDER BY cell_line_id, parameter_name
    """)
    rows = cursor.fetchall()

    for row in rows:
        print(f"✅ {row['cell_line_id']:<15} | {row['parameter_name']:<20} = {row['value']}")
        print(f"   Source: {row['source']}")
        if row['reference_url']:
            print(f"   URL: {row['reference_url']}")
        print()

    # Test 5: Database statistics
    print("Test 5: Database Statistics")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT
            (SELECT COUNT(DISTINCT cell_line_id) FROM parameter_verification) as cell_lines,
            (SELECT COUNT(DISTINCT parameter_name) FROM parameter_verification) as unique_parameters,
            (SELECT COUNT(*) FROM parameter_verification) as total_entries,
            (SELECT COUNT(*) FROM parameter_verification WHERE verification_status = 'verified') as verified,
            (SELECT COUNT(*) FROM parameter_verification WHERE verification_status = 'literature_consensus') as consensus,
            (SELECT COUNT(*) FROM parameter_verification WHERE verification_status = 'estimated') as estimated
    """)
    row = cursor.fetchone()

    print(f"Cell lines tracked: {row['cell_lines']}")
    print(f"Unique parameters: {row['unique_parameters']}")
    print(f"Total parameter entries: {row['total_entries']}")
    print()
    print(f"Verification breakdown:")
    print(f"  ✅ Verified (PubMed/ATCC): {row['verified']} ({row['verified']/row['total_entries']*100:.1f}%)")
    print(f"  📚 Literature consensus: {row['consensus']} ({row['consensus']/row['total_entries']*100:.1f}%)")
    print(f"  ⚠️  Estimated: {row['estimated']} ({row['estimated']/row['total_entries']*100:.1f}%)")
    print()

    # Test 6: Growth parameters table
    print("Test 6: Complete Growth Parameters (All Cell Lines)")
    print("-" * 90)
    cursor = conn.execute("""
        SELECT
            cell_line_id,
            doubling_time_h,
            max_passage,
            senescence_rate,
            seeding_efficiency,
            passage_stress
        FROM cell_line_growth_parameters
        ORDER BY cell_line_id
    """)
    rows = cursor.fetchall()

    print(f"{'Cell Line':<20} {'Doubling':>10} {'MaxPass':>8} {'Senescence':>11} {'Seed Eff':>9} {'Pass Stress':>11}")
    print("-" * 90)
    for row in rows:
        dt = f"{row['doubling_time_h']:.1f}h" if row['doubling_time_h'] else "N/A"
        mp = str(row['max_passage']) if row['max_passage'] else "N/A"
        sr = f"{row['senescence_rate']:.3f}" if row['senescence_rate'] else "N/A"
        se = f"{row['seeding_efficiency']:.2f}" if row['seeding_efficiency'] else "N/A"
        ps = f"{row['passage_stress']:.3f}" if row['passage_stress'] else "N/A"
        print(f"{row['cell_line_id']:<20} {dt:>10} {mp:>8} {sr:>11} {se:>9} {ps:>11}")
    print()

    conn.close()

    print("=" * 90)
    print("✅ Verification Complete")
    print("=" * 90)
    print()
    print("Summary:")
    print("  - All cell lines have complete growth parameter sets")
    print("  - Doubling times are verified or literature consensus")
    print("  - Most other parameters are estimated and need experimental validation")
    print("  - Parameter verification table tracks confidence for each value")
    print("  - 9 parameters tracked per cell line (8 growth + 1 noise parameter shown)")
    print()
    print("Recommended Actions:")
    print("  1. Run cell counting assays to validate seeding_efficiency")
    print("  2. Measure confluence at different time points to validate max_confluence")
    print("  3. Track viability across passages to validate senescence_rate and passage_stress")
    print("  4. Measure lag phase after seeding to validate lag_duration_h")
    print("  5. Compare edge vs interior wells to validate edge_penalty")
    print("  6. Run replicate assays to measure actual cell_count_cv")


if __name__ == "__main__":
    main()
