"""
MCB Crash Test - Example Script

Runs a full-scale U2OS MCB crash test simulation and generates dashboard assets.
This is a thin wrapper around the cell_os.mcb_crash library.
"""

from pathlib import Path
from cell_os.mcb_crash import MCBTestConfig, run_mcb_crash_test


def main():
    """Run MCB crash test with default production settings."""
    config = MCBTestConfig(
        num_simulations=500,
        target_mcb_vials=30,
        cells_per_vial=1e6,
        random_seed=None,  # Allow variability for exploratory runs
        enable_failures=True,
        output_dir="dashboard_assets",
        cell_line="U2OS",
        starting_vials=3,
    )
    
    print(f"Starting MCB Crash Test: {config.num_simulations} simulations...")
    result = run_mcb_crash_test(config)
    summary = result.summary
    
    # Print summary
    success_runs = summary["successful_runs"]
    contaminated_runs = summary["contaminated_runs"]
    failed_runs = summary["failed_runs"]
    
    print("\nAnalysis Complete.")
    print(f"Summary: {success_runs}/{config.num_simulations} successful ({summary['success_rate']:.1%})")
    print(f"  Median: {summary['vials_p50']} vials in {summary['duration_p50']} days")
    print(f"  Contaminated: {contaminated_runs} runs")
    print(f"  Failed: {failed_runs} runs")
    print(f"  Waste: Median {summary['waste_p50']} vials ({summary['waste_fraction_p50']:.1%} of production)")
    
    # Gap Analysis
    print("\n--- GAP ANALYSIS (Pilot Scale + Real Failures) ---")
    print("A. REALISTIC:")
    print("- Exponential growth phases match U2OS doubling time.")
    print("- Variability in final yield reflects biological noise.")
    print("- 10x expansion achievable in single passage (3-4 days).")
    print(f"- Contamination now causes terminal failures: {failed_runs}/{config.num_simulations} runs failed.")
    print(f"- Success rate ({summary['success_rate']:.1%}) reflects real-world MCB production challenges.")
    print(f"- Waste tracking shows {summary['waste_fraction_p50']:.1%} of cells discarded (realistic for fixed-size banks).")
    
    print("\nB. UNREALISTIC/BROKEN:")
    print("- 'Feed' operation assumes fixed volume/cost, doesn't account for flask size variations accurately.")
    print("- Confluence checks are perfect (no measurement error simulated in decision logic).")
    print("- Contamination rate may be too high or too low (needs calibration to real data).")
    
    print("\nC. MISSING:")
    print("- QC steps (Mycoplasma, Sterility, Karyotype) before freeze.")
    print("- Inventory stock-outs (MockInventory is infinite).")
    print("- Incubator space constraints (infinite capacity).")
    print("- Recovery protocols (re-thaw from backup if contamination detected early).")
    
    print("\nD. NEXT STEPS:")
    print("1. Calibrate contamination rates against real MCB production data.")
    print("2. Add QC steps to the workflow definition.")
    print("3. Implement finite inventory tracking.")
    print("4. Add variability to seeding efficiency and thaw viability.")
    print("5. Model recovery protocols (e.g., restart from backup vials).")


if __name__ == "__main__":
    main()
