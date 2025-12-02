"""
WCB Crash Test - Example Script

Runs a full-scale U2OS WCB crash test simulation and generates dashboard assets.
This is a thin wrapper around the cell_os.wcb_crash library.
"""

from pathlib import Path
from cell_os.wcb_crash import WCBTestConfig, run_wcb_crash_test


def main():
    """Run WCB crash test with default production settings."""
    config = WCBTestConfig(
        num_simulations=100,
        target_wcb_vials=10,
        cells_per_vial=1e6,
        random_seed=None,
        enable_failures=True,
        output_dir="data/dashboard_assets/wcb",
        cell_line="U2OS",
        starting_mcb_passage=3,
        include_qc=True
    )
    
    print(f"Starting WCB Crash Test: {config.num_simulations} simulations...")
    result = run_wcb_crash_test(config)
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
    print(f"  Max Passage (P95): P{summary['max_passage_p95']:.0f}")
    
    # Gap Analysis
    print("\n--- GAP ANALYSIS (WCB Scale) ---")
    print("A. REALISTIC:")
    print("- Expansion from 1 vial to 10 vials (1 passage).")
    print("- Passage number accumulation tracked (starts at P3, ends P3 or P4).")
    print("- QC steps (Mycoplasma, Sterility) included in workflow.")
    
    print("\nB. UNREALISTIC/BROKEN:")
    print("- Senescence risk not fully modeled (U2OS is immortal, but primary cells would fade).")
    print("- Incubator capacity for 10 vials worth of flasks not constrained.")
    
    print("\nC. MISSING:")
    print("- Genetic drift analysis at higher passages.")
    print("- Detailed cost analysis of media consumption.")


if __name__ == "__main__":
    main()
