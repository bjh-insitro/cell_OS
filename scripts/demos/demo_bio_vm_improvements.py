"""
Demonstration of BiologicalVirtualMachine Improvements

This script demonstrates the new lag phase and edge effect features.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
import matplotlib.pyplot as plt
import numpy as np

def demo_lag_phase():
    """Demonstrate lag phase dynamics."""
    print("\n" + "="*60)
    print("DEMO 1: Lag Phase Dynamics")
    print("="*60)
    
    vm = BiologicalVirtualMachine(simulation_speed=0.0, use_database=False)
    
    # Seed two vessels
    vm.seed_vessel("fresh", "HEK293T", 1e5)
    vm.seed_vessel("acclimated", "HEK293T", 1e5)
    
    # Simulate that "acclimated" was seeded 24h ago
    vm.vessel_states["acclimated"].seed_time = -24.0
    
    # Track growth over 24 hours
    times = []
    fresh_counts = []
    acclimated_counts = []
    
    for hour in range(25):
        times.append(hour)
        
        fresh = vm.vessel_states["fresh"]
        acclimated = vm.vessel_states["acclimated"]
        
        fresh_counts.append(fresh.cell_count)
        acclimated_counts.append(acclimated.cell_count)
        
        if hour < 24:
            vm.advance_time(1.0)
    
    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(times, fresh_counts, 'b-', linewidth=2, label='Fresh (in lag phase)')
    plt.plot(times, acclimated_counts, 'r-', linewidth=2, label='Acclimated (normal growth)')
    plt.axvline(12, color='gray', linestyle='--', alpha=0.5, label='Lag duration (12h)')
    plt.xlabel('Time (hours)', fontsize=12)
    plt.ylabel('Cell Count', fontsize=12)
    plt.title('Lag Phase Effect on Cell Growth', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('data/lag_phase_demo.png', dpi=150)
    print("\n✅ Plot saved to: data/lag_phase_demo.png")
    
    # Print summary
    print(f"\nFinal counts after 24h:")
    print(f"  Fresh (with lag):      {fresh_counts[-1]:.2e} cells")
    print(f"  Acclimated (no lag):   {acclimated_counts[-1]:.2e} cells")
    print(f"  Difference:            {(acclimated_counts[-1] / fresh_counts[-1] - 1) * 100:.1f}%")

def demo_edge_effects():
    """Demonstrate spatial edge effects."""
    print("\n" + "="*60)
    print("DEMO 2: Spatial Edge Effects")
    print("="*60)
    
    vm = BiologicalVirtualMachine(simulation_speed=0.0, use_database=False)
    
    # Create a 96-well plate layout
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = range(1, 13)
    
    # Seed all wells
    for row in rows:
        for col in cols:
            well_id = f"Plate1_{row}{col:02d}"
            vm.seed_vessel(well_id, "HEK293T", 1e5)
            # Skip lag phase for clearer edge effect demonstration
            vm.vessel_states[well_id].seed_time = -24.0
    
    # Grow for 24 hours
    vm.advance_time(24.0)
    
    # Collect counts
    plate_data = np.zeros((8, 12))
    for i, row in enumerate(rows):
        for j, col in enumerate(cols):
            well_id = f"Plate1_{row}{col:02d}"
            plate_data[i, j] = vm.vessel_states[well_id].cell_count
    
    # Plot heatmap
    plt.figure(figsize=(12, 6))
    im = plt.imshow(plate_data, cmap='YlOrRd', aspect='auto')
    plt.colorbar(im, label='Cell Count')
    plt.xticks(range(12), [f'{i+1}' for i in range(12)])
    plt.yticks(range(8), rows)
    plt.xlabel('Column', fontsize=12)
    plt.ylabel('Row', fontsize=12)
    plt.title('96-Well Plate: Edge Effect on Cell Growth (24h)', fontsize=14, fontweight='bold')
    
    # Add text annotations
    for i in range(8):
        for j in range(12):
            text = plt.text(j, i, f'{plate_data[i, j]/1e5:.1f}',
                          ha="center", va="center", color="black", fontsize=8)
    
    plt.tight_layout()
    plt.savefig('data/edge_effects_demo.png', dpi=150)
    print("\n✅ Plot saved to: data/edge_effects_demo.png")
    
    # Calculate statistics
    edge_wells = []
    center_wells = []
    
    for i, row in enumerate(rows):
        for j, col in enumerate(cols):
            count = plate_data[i, j]
            is_edge = (row in ['A', 'H']) or (col in [1, 12])
            
            if is_edge:
                edge_wells.append(count)
            else:
                center_wells.append(count)
    
    print(f"\nStatistics:")
    print(f"  Center wells (n={len(center_wells)}): {np.mean(center_wells):.2e} ± {np.std(center_wells):.2e}")
    print(f"  Edge wells (n={len(edge_wells)}):     {np.mean(edge_wells):.2e} ± {np.std(edge_wells):.2e}")
    print(f"  Edge penalty:                          {(1 - np.mean(edge_wells)/np.mean(center_wells)) * 100:.1f}%")

def demo_combined():
    """Demonstrate combined effects."""
    print("\n" + "="*60)
    print("DEMO 3: Combined Effects (Lag + Edge)")
    print("="*60)
    
    vm = BiologicalVirtualMachine(simulation_speed=0.0, use_database=False)
    
    # Seed 4 wells representing all combinations
    wells = {
        "Center_Acclimated": ("Plate1_D06", -24.0),  # No lag, no edge
        "Center_Fresh": ("Plate1_D07", 0.0),          # Lag, no edge
        "Edge_Acclimated": ("Plate1_A01", -24.0),     # No lag, edge
        "Edge_Fresh": ("Plate1_A02", 0.0)             # Lag + edge
    }
    
    for name, (well_id, seed_time) in wells.items():
        vm.seed_vessel(well_id, "HEK293T", 1e5)
        vm.vessel_states[well_id].seed_time = seed_time
    
    # Track over 24 hours
    times = []
    counts = {name: [] for name in wells.keys()}
    
    for hour in range(25):
        times.append(hour)
        for name, (well_id, _) in wells.items():
            counts[name].append(vm.vessel_states[well_id].cell_count)
        
        if hour < 24:
            vm.advance_time(1.0)
    
    # Plot
    plt.figure(figsize=(12, 6))
    colors = {'Center_Acclimated': 'green', 'Center_Fresh': 'blue', 
              'Edge_Acclimated': 'orange', 'Edge_Fresh': 'red'}
    
    for name in wells.keys():
        plt.plot(times, counts[name], linewidth=2, label=name, color=colors[name])
    
    plt.xlabel('Time (hours)', fontsize=12)
    plt.ylabel('Cell Count', fontsize=12)
    plt.title('Combined Effects: Lag Phase + Edge Effects', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('data/combined_effects_demo.png', dpi=150)
    print("\n✅ Plot saved to: data/combined_effects_demo.png")
    
    # Print final counts
    print(f"\nFinal counts after 24h:")
    for name in wells.keys():
        print(f"  {name:20s}: {counts[name][-1]:.2e} cells")

if __name__ == "__main__":
    print("\n🔬 BiologicalVirtualMachine Improvements Demo")
    
    demo_lag_phase()
    demo_edge_effects()
    demo_combined()
    
    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)
