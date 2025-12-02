"""
Multi-Cell Line Crash Test

Validates MCB and WCB simulations across different cell types (U2OS vs iPSC).
Tests adaptability of the simulation to different biological parameters.
"""

from cell_os.mcb_crash import MCBTestConfig, run_mcb_crash_test
from cell_os.wcb_crash import WCBTestConfig, run_wcb_crash_test
import pandas as pd

def run_comparison():
    print("=== MULTI-CELL LINE CRASH TEST ===")
    
    # 1. MCB Comparison
    print("\n--- MCB SIMULATION ---")
    
    # U2OS (Robust)
    print("\nRunning U2OS MCB (50 runs)...")
    u2os_config = MCBTestConfig(
        num_simulations=50,
        cell_line="U2OS",
        output_dir="data/dashboard_assets/multi/u2os_mcb"
    )
    u2os_res = run_mcb_crash_test(u2os_config)
    
    # iPSC (Sensitive)
    print("Running iPSC MCB (50 runs)...")
    ipsc_config = MCBTestConfig(
        num_simulations=50,
        cell_line="iPSC",
        output_dir="data/dashboard_assets/multi/ipsc_mcb"
    )
    ipsc_res = run_mcb_crash_test(ipsc_config)
    
    # Compare
    print("\nMCB Results Comparison:")
    print(f"{'Metric':<20} | {'U2OS':<10} | {'iPSC':<10}")
    print("-" * 46)
    print(f"{'Success Rate':<20} | {u2os_res.summary['success_rate']:.1%}     | {ipsc_res.summary['success_rate']:.1%}")
    print(f"{'Median Duration':<20} | {u2os_res.summary['duration_p50']:.1f} days  | {ipsc_res.summary['duration_p50']:.1f} days")
    print(f"{'Median Vials':<20} | {u2os_res.summary['vials_p50']:.0f}         | {ipsc_res.summary['vials_p50']:.0f}")
    
    # 2. WCB Comparison
    print("\n\n--- WCB SIMULATION (1->10 Vials) ---")
    
    # U2OS
    print("\nRunning U2OS WCB (50 runs)...")
    u2os_wcb_config = WCBTestConfig(
        num_simulations=50,
        cell_line="U2OS",
        target_wcb_vials=10,
        output_dir="data/dashboard_assets/multi/u2os_wcb"
    )
    u2os_wcb_res = run_wcb_crash_test(u2os_wcb_config)
    
    # iPSC
    print("Running iPSC WCB (50 runs)...")
    ipsc_wcb_config = WCBTestConfig(
        num_simulations=50,
        cell_line="iPSC",
        target_wcb_vials=10,
        output_dir="data/dashboard_assets/multi/ipsc_wcb"
    )
    ipsc_wcb_res = run_wcb_crash_test(ipsc_wcb_config)
    
    # Compare
    print("\nWCB Results Comparison:")
    print(f"{'Metric':<20} | {'U2OS':<10} | {'iPSC':<10}")
    print("-" * 46)
    print(f"{'Success Rate':<20} | {u2os_wcb_res.summary['success_rate']:.1%}     | {ipsc_wcb_res.summary['success_rate']:.1%}")
    print(f"{'Median Duration':<20} | {u2os_wcb_res.summary['duration_p50']:.1f} days  | {ipsc_wcb_res.summary['duration_p50']:.1f} days")
    
    # Validation Logic
    print("\n\n--- VALIDATION ---")
    if ipsc_res.summary['duration_p50'] > u2os_res.summary['duration_p50']:
        print("✅ PASS: iPSC takes longer to grow than U2OS (slower doubling time).")
    else:
        print("❌ FAIL: iPSC grew as fast or faster than U2OS (unexpected).")
        
    if ipsc_wcb_res.summary['success_rate'] <= u2os_wcb_res.summary['success_rate']:
         print("✅ PASS: iPSC success rate <= U2OS (higher sensitivity).")
    else:
         print("❌ FAIL: iPSC success rate > U2OS (unexpected).")

if __name__ == "__main__":
    run_comparison()
