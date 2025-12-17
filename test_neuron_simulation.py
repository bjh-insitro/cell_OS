#!/usr/bin/env python3
"""
Test iPSC-NGN2 neuron simulations

Validates that neurons have expected sensitivities:
- Extremely sensitive to oxidative stress (CCCP, H2O2)
- Extremely sensitive to mitochondrial stress (CCCP, oligomycin)
- Resistant to microtubule drugs (nocodazole, paclitaxel)
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

# Test all three cell lines
cell_lines = ['A549', 'HepG2', 'iPSC_NGN2']
test_compounds = [
    ('CCCP', 30.0, 'mitochondrial'),
    ('oligomycin', 30.0, 'mitochondrial'),
    ('H2O2', 100.0, 'oxidative'),
    ('nocodazole', 10.0, 'microtubule'),
]

print("="*70)
print("NEURON SENSITIVITY TEST")
print("="*70)
print("\nComparing viability across cell lines at same dose:")
print()

for compound, dose, stress_type in test_compounds:
    print(f"\n{compound} {dose}µM ({stress_type} stress):")
    print("-" * 70)

    viabilities = {}

    for cell_line in cell_lines:
        # Initialize agent
        np.random.seed(42)  # Consistent random seed
        agent = CellThalamusAgent(phase=0)

        # Create well
        well = WellAssignment(
            well_id='TEST',
            cell_line=cell_line,
            compound=compound,
            dose_uM=dose,
            timepoint_h=24.0,
            plate_id='TestPlate',
            day=1,
            operator='Test',
            is_sentinel=False
        )

        # Execute
        result = agent._execute_well(well)

        if result and 'atp_signal' in result:
            # LDH is inverse of viability
            baseline_ldh = 50000.0 if cell_line != 'iPSC_NGN2' else 70000.0
            viability = 1.0 - (result['atp_signal'] / baseline_ldh)
            viabilities[cell_line] = max(0, min(1, viability))
        else:
            viabilities[cell_line] = 0.0

    # Print results
    for cell_line in cell_lines:
        marker = ""
        if cell_line == 'iPSC_NGN2':
            if stress_type in ['mitochondrial', 'oxidative']:
                marker = " ← Should be LOW (neurons very sensitive)"
            elif stress_type == 'microtubule':
                marker = " ← Should be HIGH (neurons resistant)"

        print(f"  {cell_line:12s}: {viabilities[cell_line]:.1%}{marker}")

print("\n" + "="*70)
print("EXPECTED PATTERNS:")
print("="*70)
print("✓ Neurons (iPSC_NGN2) should have LOWER viability for:")
print("  - CCCP, oligomycin (mitochondrial stress)")
print("  - H2O2 (oxidative stress)")
print()
print("✓ Neurons should have HIGHER viability for:")
print("  - nocodazole (microtubule drugs)")
print("="*70)
