"""
Facility Stress Test

Simulates a busy facility schedule to identify resource bottlenecks.
"""

from cell_os.facility_sim import FacilityConfig, FacilitySimulator, CampaignRequest
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def run_stress_test():
    print("=== FACILITY STRESS TEST ===")
    
    # 1. Configure Facility
    config = FacilityConfig(
        incubator_capacity_flasks=20, # Constrained
        bsc_hours_per_day=2.0,         # Constrained
        staff_fte=2.0
    )
    
    sim = FacilitySimulator(config)
    
    # 2. Schedule Campaigns
    # 5 MCB campaigns (U2OS) starting daily
    for i in range(5):
        sim.add_campaign(CampaignRequest(
            campaign_type="MCB",
            cell_line="U2OS",
            start_day=i,
            campaign_id=f"MCB_U2OS_{i+1}"
        ))
        
    # 5 WCB campaigns (iPSC) starting daily
    for i in range(5):
        sim.add_campaign(CampaignRequest(
            campaign_type="WCB",
            cell_line="iPSC",
            start_day=i,
            campaign_id=f"WCB_iPSC_{i+1}"
        ))
        
    # 3. Run Simulation
    df = sim.run(duration_days=60)
    
    # 4. Analyze Results
    print("\n--- RESULTS ---")
    
    # Peak Usage
    peak_incubator = df['incubator_usage'].max()
    peak_bsc = df['bsc_hours'].max()
    
    print(f"Peak Incubator Usage: {peak_incubator} flasks (Capacity: {config.incubator_capacity_flasks})")
    print(f"Peak BSC Usage: {peak_bsc:.1f} hours (Capacity: {config.bsc_hours_per_day})")
    
    # Violations
    violations = []
    for _, row in df.iterrows():
        if row['violations']:
            for v in row['violations']:
                violations.append(f"Day {row['day']}: {v}")
                
    if violations:
        print(f"\n❌ {len(violations)} Capacity Violations Detected:")
        for v in violations[:10]: # Show first 10
            print(f"  - {v}")
        if len(violations) > 10:
            print(f"  ... and {len(violations)-10} more.")
    else:
        print("\n✅ No capacity violations detected.")
        
    # Save Results
    output_dir = Path("dashboard_assets_facility")
    output_dir.mkdir(exist_ok=True)
    df.to_csv(output_dir / "facility_load.csv", index=False)
    print(f"\nDetailed load profile saved to {output_dir}/facility_load.csv")

if __name__ == "__main__":
    run_stress_test()
