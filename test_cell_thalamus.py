"""
Quick test script for Cell Thalamus Phase 0

Tests the full pipeline:
1. Generate design
2. Run simulation
3. Store results
4. Analyze variance
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.cell_thalamus import CellThalamusAgent
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer


def main():
    print("=" * 60)
    print("CELL THALAMUS PHASE 0 - QUICK TEST")
    print("=" * 60)

    # Initialize
    print("\n1. Initializing hardware and database...")
    hardware = BiologicalVirtualMachine()
    db = CellThalamusDB(db_path="data/cell_thalamus_test.db")
    agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)

    # Run quick test (1 cell line, 3 compounds)
    print("\n2. Running quick test (A549, 3 compounds)...")
    design_id = agent.run_quick_test()

    # Get results summary
    print("\n3. Getting results summary...")
    summary = agent.get_results_summary(design_id)
    print(f"\n  Design ID: {design_id}")
    print(f"  Total wells: {summary['total_wells']}")
    print(f"  Experimental wells: {summary['experimental_wells']}")
    print(f"  Sentinel wells: {summary['sentinel_wells']}")

    # Run variance analysis
    print("\n4. Running variance analysis...")
    analyzer = VarianceAnalyzer(db)
    analysis = analyzer.analyze_design(design_id)

    if 'summary' in analysis:
        summary_data = analysis['summary']
        print(f"\n  Biological variance: {summary_data['biological_fraction_mean']*100:.1f}%")
        print(f"  Technical variance: {summary_data['technical_fraction_mean']*100:.1f}%")
        print(f"  Overall pass: {summary_data['overall_pass']}")

        if summary_data['overall_pass']:
            print("\n  ✅ SUCCESS: Phase 0 validation complete!")
        else:
            print("\n  ⚠️  Some criteria not met")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print(f"Database: {db.db_path}")
    print(f"Design ID: {design_id}")
    print("=" * 60)

    # Close database
    db.close()


if __name__ == "__main__":
    main()
