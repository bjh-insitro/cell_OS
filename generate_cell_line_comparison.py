#!/usr/bin/env python3
"""
Generate comprehensive cell line comparison table for neurons and microglia.

Shows viability responses across:
- 4 cell lines: A549, HepG2, iPSC_NGN2 (neurons), iPSC_Microglia
- 8 compounds: H2O2, CCCP, oligomycin, tBHQ, MG132, etoposide, nocodazole, paclitaxel
- 3 timepoints: 12h, 24h, 48h
- Multiple doses
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np
import pandas as pd

# Cell lines to compare
cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']

# Compounds and representative doses
test_conditions = [
    # Oxidative stress
    ('H2O2', 100.0, 'oxidative'),
    ('tBHQ', 30.0, 'oxidative'),

    # Mitochondrial stress
    ('CCCP', 30.0, 'mitochondrial'),
    ('oligomycin', 30.0, 'mitochondrial'),

    # Proteasome inhibition
    ('MG132', 10.0, 'proteasome'),

    # DNA damage
    ('etoposide', 30.0, 'dna_damage'),

    # Microtubule disruption
    ('nocodazole', 10.0, 'microtubule'),
    ('paclitaxel', 1.0, 'microtubule'),
]

# Timepoints
timepoints = [12.0, 24.0, 48.0]

# LDH baseline map
baseline_ldh_map = {
    'A549': 50000.0,
    'HepG2': 50000.0,
    'iPSC_NGN2': 70000.0,
    'iPSC_Microglia': 65000.0
}

print("=" * 120)
print("COMPREHENSIVE CELL LINE COMPARISON: Neurons & Microglia vs Cancer Cell Lines")
print("=" * 120)
print()

# Collect all results
results = []

for compound, dose, stress_type in test_conditions:
    print(f"\n{'=' * 120}")
    print(f"Compound: {compound} @ {dose}µM ({stress_type} stress)")
    print(f"{'=' * 120}")

    for timepoint in timepoints:
        print(f"\nTimepoint: {timepoint}h")
        print("-" * 120)
        print(f"{'Cell Line':<20} {'Viability':<15} {'Interpretation':<80}")
        print("-" * 120)

        viabilities = {}

        for cell_line in cell_lines:
            # Initialize agent
            np.random.seed(42)  # Consistent seed for reproducibility
            agent = CellThalamusAgent(phase=0)

            # Create well
            well = WellAssignment(
                well_id='TEST',
                cell_line=cell_line,
                compound=compound,
                dose_uM=dose,
                timepoint_h=timepoint,
                plate_id='ComparisonPlate',
                day=1,
                operator='Test',
                is_sentinel=False
            )

            # Execute
            result = agent._execute_well(well)

            if result and 'atp_signal' in result:
                # LDH is inverse of viability
                baseline_ldh = baseline_ldh_map[cell_line]
                viability = 1.0 - (result['atp_signal'] / baseline_ldh)
                viability = max(0, min(1, viability))
                viabilities[cell_line] = viability
            else:
                viabilities[cell_line] = 0.0

            # Generate interpretation
            interpretation = ""
            if cell_line == 'iPSC_NGN2':
                if stress_type in ['mitochondrial', 'oxidative']:
                    interpretation = "NEURON: Extremely sensitive (high metabolic dependence)"
                elif stress_type == 'microtubule':
                    interpretation = "NEURON: Resistant (post-mitotic, need functional microtubules)"
                elif stress_type == 'proteasome':
                    interpretation = "NEURON: Sensitive (accumulate misfolded proteins)"
                else:
                    interpretation = "NEURON: Expected neuronal response"
            elif cell_line == 'iPSC_Microglia':
                if stress_type == 'oxidative':
                    interpretation = "MICROGLIA: Resistant (produce ROS as weapon, high antioxidants)"
                elif stress_type == 'proteasome':
                    interpretation = "MICROGLIA: Very sensitive (high protein turnover for cytokines)"
                elif stress_type == 'dna_damage':
                    interpretation = "MICROGLIA: Resistant (immune cell trait)"
                else:
                    interpretation = "MICROGLIA: Expected immune cell response"
            elif cell_line == 'A549':
                interpretation = "CANCER: Lung cancer (NRF2-primed, fast cycling)"
            else:
                interpretation = "CANCER: Hepatoma (high ER/OXPHOS dependence)"

            print(f"{cell_line:<20} {viability:>6.1%}{'':<8} {interpretation:<80}")

            # Store for DataFrame
            results.append({
                'Compound': compound,
                'Dose_uM': dose,
                'Stress_Type': stress_type,
                'Timepoint_h': timepoint,
                'Cell_Line': cell_line,
                'Viability': viability,
                'Interpretation': interpretation
            })

print("\n" + "=" * 120)
print("KEY BIOLOGICAL INSIGHTS:")
print("=" * 120)
print()
print("NEURONS (iPSC_NGN2):")
print("  - Extremely sensitive to oxidative stress (H2O2, tBHQ) - accumulate ROS damage")
print("  - Extremely sensitive to mitochondrial stress (CCCP, oligomycin) - total OXPHOS dependence")
print("  - Resistant to microtubule drugs (nocodazole, paclitaxel) - post-mitotic, need functional transport")
print("  - Sensitive to proteasome inhibition (MG132) - accumulate misfolded proteins")
print()
print("MICROGLIA (iPSC_Microglia):")
print("  - Resistant to oxidative stress (H2O2, tBHQ) - produce ROS as weapon, high antioxidant capacity")
print("  - Very sensitive to proteasome inhibition (MG132) - high protein turnover for cytokine production")
print("  - Resistant to DNA damage (etoposide) - immune cell survival trait")
print("  - Moderate sensitivity to mitochondrial stress - metabolically active but not neuron-level dependent")
print()
print("CANCER CELLS (A549, HepG2):")
print("  - A549: NRF2-primed (oxidative resistant), fast cycling (microtubule sensitive)")
print("  - HepG2: High ER load (ER stress sensitive), OXPHOS-dependent (mito stress sensitive)")
print("=" * 120)

# Create DataFrame
df = pd.DataFrame(results)

# Pivot table for easy comparison
print("\n" + "=" * 120)
print("PIVOT TABLE: Viability by Cell Line and Compound (24h timepoint)")
print("=" * 120)
pivot = df[df['Timepoint_h'] == 24.0].pivot(index='Compound', columns='Cell_Line', values='Viability')
print(pivot.to_string())

# Save to CSV
output_file = '/Users/bjh/cell_OS/cell_line_comparison.csv'
df.to_csv(output_file, index=False)
print(f"\n✓ Full results saved to: {output_file}")
