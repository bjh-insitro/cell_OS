#!/usr/bin/env python3
"""
Test Agent High Dose Attrition

Verify that time-dependent attrition kicks in at high doses.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

print("=" * 100)
print("AGENT HIGH DOSE ATTRITION TEST: 10 µM Nocodazole (iPSC_NGN2)")
print("=" * 100)
print()

print(f"{'Time (h)':<10} {'Viability':<12} {'Death Mode':<15} {'Death Compound':<15} {'Actin':<12} {'Dysfunction':<12}")
print("-" * 100)

for timepoint in [12.0, 24.0, 48.0, 72.0, 96.0]:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)

    well = WellAssignment(
        well_id='TEST',
        cell_line='iPSC_NGN2',
        compound='nocodazole',
        dose_uM=10.0,  # High dose (10× IC50)
        timepoint_h=timepoint,
        plate_id='P1',
        day=1,
        operator='Test',
        is_sentinel=False
    )

    # Execute well
    result = agent._execute_well(well)

    # Extract data
    viability = result.get('viability', 0.0)
    death_mode = result.get('death_mode', 'None')
    death_compound = result.get('death_compound', 0.0)

    # Get morphology and dysfunction
    morph = result.get('morphology', {})
    actin = morph.get('actin', 0)
    dysfunction = result.get('transport_dysfunction_score', 0.0)

    print(f"{timepoint:<10.0f} {viability:>6.1%}{'':<5} {str(death_mode):<15} {death_compound:>8.1%}{'':<6} {actin:>8.1f}{'':<3} {dysfunction:>8.3f}{'':<3}")

print()
print("=" * 100)
print("EXPECTED BEHAVIOR:")
print("  12-24h: High viability (~95-98%), morphology disrupted (dysfunction ~0.4)")
print("  48h:    Viability starts declining (~70-90%) as attrition kicks in")
print("  72-96h: Significant death (~30-70%) from sustained transport failure")
print("  Death mode: 'compound' (not 'confluence')")
print("=" * 100)
