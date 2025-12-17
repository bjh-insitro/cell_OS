#!/usr/bin/env python3
"""
Test iPSC-Microglia simulations

Validates that microglia (brain immune cells) have expected sensitivities:
- Resistant to oxidative stress (produce ROS as weapon)
- Moderately sensitive to mitochondrial stress
- Sensitive to proteasome inhibition (high protein turnover)
- Resistant to DNA damage (like other immune cells)
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

# Test all four cell types
cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']
test_compounds = [
    ('H2O2', 100.0, 'oxidative', 'Microglia should be RESISTANT (produce ROS)'),
    ('CCCP', 30.0, 'mitochondrial', 'Microglia moderately sensitive'),
    ('MG132', 10.0, 'proteasome', 'Microglia should be SENSITIVE (high protein turnover)'),
    ('etoposide', 30.0, 'dna_damage', 'Microglia should be RESISTANT (immune cell)'),
]

print("="*70)
print("MICROGLIA (BRAIN IMMUNE CELL) SENSITIVITY TEST")
print("="*70)
print("\nComparing viability across cell types:")
print()

for compound, dose, stress_type, expectation in test_compounds:
    print(f"\n{compound} {dose}µM ({stress_type} stress)")
    print(f"Expectation: {expectation}")
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
            # LDH is inverse of viability (approximately)
            baseline_map = {
                'A549': 50000.0,
                'HepG2': 50000.0,
                'iPSC_NGN2': 70000.0,
                'iPSC_Microglia': 65000.0
            }
            baseline_ldh = baseline_map.get(cell_line, 50000.0)
            viability = 1.0 - (result['atp_signal'] / baseline_ldh)
            viabilities[cell_line] = max(0, min(1, viability))
        else:
            viabilities[cell_line] = 0.0

    # Print results
    for cell_line in cell_lines:
        marker = ""
        if cell_line == 'iPSC_Microglia':
            marker = " ← MICROGLIA"

        print(f"  {cell_line:16s}: {viabilities[cell_line]:.1%}{marker}")

print("\n" + "="*70)
print("EXPECTED PATTERNS:")
print("="*70)
print("✓ Microglia should be MORE RESISTANT than neurons for:")
print("  - H2O2 (oxidative) - microglia produce ROS, neurons accumulate damage")
print("  - CCCP (mitochondrial) - microglia less dependent than neurons")
print()
print("✓ Microglia should be MORE SENSITIVE for:")
print("  - MG132 (proteasome) - high protein turnover for cytokine production")
print()
print("✓ Microglia should be SIMILAR TO or MORE RESISTANT than cancer:")
print("  - etoposide (DNA damage) - immune cells often resist DNA damage")
print("="*70)
