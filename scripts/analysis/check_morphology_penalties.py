#!/usr/bin/env python3
"""
Verify morphology-first principle: neurons under nocodazole should show
cytoskeletal disruption (actin, mito) even when viability remains high.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']
baseline_ldh = {'A549': 50000.0, 'HepG2': 50000.0, 'iPSC_NGN2': 70000.0, 'iPSC_Microglia': 65000.0}

print("=" * 100)
print("MORPHOLOGY-FIRST CHECK: Nocodazole @ 10µM")
print("=" * 100)
print("\nVerifying that neurons show morphology disruption even when viability is high:")
print()

# Test nocodazole at 24h
timepoint = 24.0
compound = 'nocodazole'
dose = 10.0

print(f"{'Cell Line':<20} {'Viability':<12} {'Actin':<12} {'Mito':<12} {'Interpretation':<40}")
print("-" * 100)

for cell_line in cell_lines:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)

    well = WellAssignment(
        well_id='TEST', cell_line=cell_line, compound=compound,
        dose_uM=dose, timepoint_h=timepoint, plate_id='P1',
        day=1, operator='Test', is_sentinel=False
    )

    result = agent._execute_well(well)

    if result and 'atp_signal' in result:
        viability = 1.0 - (result['atp_signal'] / baseline_ldh[cell_line])
        viability = max(0, min(1, viability))

        morph = result.get('morphology', {})
        actin = morph.get('actin', 0)
        mito = morph.get('mito', 0)

        # Interpretation
        if cell_line == 'iPSC_NGN2':
            if viability > 0.9 and (actin < 120 or mito < 140):
                interp = "✓ GOOD: High viability but disrupted morphology"
            elif viability > 0.9:
                interp = "✗ BAD: High viability AND normal morphology"
            else:
                interp = "Viability dropped (expected at high dose)"
        else:
            if viability < 0.3:
                interp = "Cancer: Severe toxicity (expected)"
            else:
                interp = "Cancer: Moderate toxicity"

        print(f"{cell_line:<20} {viability:>6.1%}{'':<5} {actin:>8.1f}{'':<3} {mito:>8.1f}{'':<3} {interp:<40}")

print("\n" + "=" * 100)
print("EXPECTED PATTERN:")
print("  - Neurons: HIGH viability (>95%) but LOW actin/mito (morphology disruption)")
print("  - Cancer: LOW viability (<20%) due to mitotic catastrophe")
print("=" * 100)
