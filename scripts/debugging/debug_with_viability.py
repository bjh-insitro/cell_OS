#!/usr/bin/env python3
"""Check viability alongside morphology."""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

baseline_ldh = {'iPSC_NGN2': 70000.0}
baseline_morph = {'iPSC_NGN2': {'actin': 160.0, 'mito': 220.0}}

dose = 0.3
timepoints = [12.0, 24.0, 48.0, 72.0, 96.0]

print("=" * 100)
print(f"Nocodazole @ {dose}µM: Viability + Morphology Over Time")
print("=" * 100)
print(f"{'Time':<10} {'Viability':<12} {'Actin':<12} {'Actin Loss':<12} {'Pattern':<30}")
print("-" * 100)

for tp in timepoints:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)
    well = WellAssignment(
        well_id='TEST', cell_line='iPSC_NGN2', compound='nocodazole',
        dose_uM=dose, timepoint_h=tp, plate_id='P1',
        day=1, operator='Test', is_sentinel=False
    )
    result = agent._execute_well(well)

    viability = 1.0 - (result['atp_signal'] / baseline_ldh['iPSC_NGN2'])
    viability = max(0, min(1, viability))

    morph = result.get('morphology', {})
    actin = morph.get('actin', 0)
    actin_loss = (baseline_morph['iPSC_NGN2']['actin'] - actin) / baseline_morph['iPSC_NGN2']['actin']

    if viability < 0.50:
        pattern = "Low viability affects signal?"
    else:
        pattern = "Viability high, should be stable"

    print(f"{tp:<10.0f} {viability:>6.1%}{'':<5} {actin:>8.1f}{'':<3} {actin_loss:>8.1%}{'':<3} {pattern:<30}")

print("\n" + "=" * 100)
print("HYPOTHESIS: If viability drops significantly, morphology signal drops (measurement effect)")
print("=" * 100)
