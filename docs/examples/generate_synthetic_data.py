"""
Example: Generating Synthetic Dose-Response Data

This script demonstrates how to use BiologicalVirtualMachine to generate
realistic synthetic experimental data for benchmarking and testing.
"""

import pandas as pd
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def generate_dose_response_dataset(
    cell_lines=["HEK293T", "HeLa"],
    compounds=["staurosporine", "doxorubicin"],
    doses=[0.001, 0.01, 0.1, 1.0, 10.0],
    replicates=3,
    random_seed=42
):
    """
    Generate a synthetic dose-response dataset.
    
    Returns:
        pd.DataFrame with columns: cell_line, compound, dose_uM, replicate, 
                                   viability, cell_count, passage_number
    """
    np.random.seed(random_seed)
    vm = BiologicalVirtualMachine(simulation_speed=0.0)
    
    records = []
    
    for cell_line in cell_lines:
        for compound in compounds:
            for dose in doses:
                for rep in range(replicates):
                    # Create unique vessel ID
                    vessel_id = f"{cell_line}_{compound}_{dose}_{rep}"
                    
                    # Seed cells
                    vm.seed_vessel(vessel_id, cell_line, initial_count=1e5)
                    
                    # Treat with compound
                    treatment_result = vm.treat_with_compound(
                        vessel_id, compound, dose_uM=dose
                    )
                    
                    # Incubate for 24h
                    vm.incubate(24 * 3600, 37.0)
                    
                    # Count cells
                    count_result = vm.count_cells(vessel_id, vessel_id=vessel_id)
                    
                    # Record data
                    records.append({
                        "cell_line": cell_line,
                        "compound": compound,
                        "dose_uM": dose,
                        "replicate": rep + 1,
                        "viability": count_result["viability"],
                        "cell_count": count_result["count"],
                        "passage_number": count_result["passage_number"],
                        "ic50": treatment_result["ic50"]
                    })
    
    return pd.DataFrame(records)


def generate_passage_series(
    cell_line="HEK293T",
    n_passages=10,
    days_between_passages=3,
    random_seed=42
):
    """
    Generate a synthetic dataset tracking cell behavior over multiple passages.
    
    Returns:
        pd.DataFrame with passage number, cell count, viability, confluence
    """
    np.random.seed(random_seed)
    vm = BiologicalVirtualMachine(simulation_speed=0.0)
    
    records = []
    current_vessel = "T75_P0"
    
    # Initial seeding
    vm.seed_vessel(current_vessel, cell_line, initial_count=5e5, capacity=1e7)
    
    for passage in range(n_passages):
        # Grow for specified days
        vm.incubate(days_between_passages * 24 * 3600, 37.0)
        
        # Count before passage
        count_result = vm.count_cells(current_vessel, vessel_id=current_vessel)
        
        records.append({
            "passage_number": passage,
            "cell_count": count_result["count"],
            "viability": count_result["viability"],
            "confluence": count_result["confluence"],
            "days_in_culture": days_between_passages * (passage + 1)
        })
        
        # Passage to new vessel
        next_vessel = f"T75_P{passage + 1}"
        vm.passage_cells(current_vessel, next_vessel, split_ratio=4.0)
        current_vessel = next_vessel
    
    return pd.DataFrame(records)


def generate_growth_curve(
    cell_line="HEK293T",
    initial_count=1e5,
    duration_days=7,
    measurement_interval_hours=12,
    random_seed=42
):
    """
    Generate a synthetic cell growth curve.
    
    Returns:
        pd.DataFrame with time_h, cell_count, viability, confluence
    """
    np.random.seed(random_seed)
    vm = BiologicalVirtualMachine(simulation_speed=0.0)
    
    vessel_id = "growth_curve_vessel"
    vm.seed_vessel(vessel_id, cell_line, initial_count=initial_count, capacity=1e7)
    
    records = []
    total_hours = duration_days * 24
    
    for time_h in np.arange(0, total_hours + 1, measurement_interval_hours):
        # Count cells
        count_result = vm.count_cells(vessel_id, vessel_id=vessel_id)
        
        records.append({
            "time_h": time_h,
            "time_days": time_h / 24,
            "cell_count": count_result["count"],
            "viability": count_result["viability"],
            "confluence": count_result["confluence"]
        })
        
        # Incubate until next measurement
        if time_h < total_hours:
            vm.incubate(measurement_interval_hours * 3600, 37.0)
    
    return pd.DataFrame(records)


if __name__ == "__main__":
    print("=" * 60)
    print("Synthetic Data Generation Examples")
    print("=" * 60)
    
    # Example 1: Dose-Response Dataset
    print("\n1. Generating dose-response dataset...")
    dose_response_df = generate_dose_response_dataset()
    print(f"   Generated {len(dose_response_df)} records")
    print("\n   Sample data:")
    print(dose_response_df.head(10).to_string(index=False))
    
    # Save to CSV
    dose_response_df.to_csv("results/synthetic_dose_response.csv", index=False)
    print("\n   Saved to: results/synthetic_dose_response.csv")
    
    # Example 2: Passage Series
    print("\n2. Generating passage series...")
    passage_df = generate_passage_series()
    print(f"   Generated {len(passage_df)} passages")
    print("\n   Sample data:")
    print(passage_df.to_string(index=False))
    
    passage_df.to_csv("results/synthetic_passage_series.csv", index=False)
    print("\n   Saved to: results/synthetic_passage_series.csv")
    
    # Example 3: Growth Curve
    print("\n3. Generating growth curve...")
    growth_df = generate_growth_curve()
    print(f"   Generated {len(growth_df)} time points")
    print("\n   Sample data:")
    print(growth_df.head(10).to_string(index=False))
    
    growth_df.to_csv("results/synthetic_growth_curve.csv", index=False)
    print("\n   Saved to: results/synthetic_growth_curve.csv")
    
    print("\n" + "=" * 60)
    print("All synthetic datasets generated successfully!")
    print("=" * 60)
