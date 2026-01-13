#!/usr/bin/env python3
"""
Debug Morphology Accumulation

Check if morphology disruption accumulates over time at low doses.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

baseline_morph = {'iPSC_NGN2': {'actin': 160.0, 'mito': 220.0}}

print("=" * 100)
print("MORPHOLOGY ACCUMULATION CHECK: Does disruption grow over time at low dose?")
print("=" * 100)

dose = 0.3  # Low dose
timepoints = [12.0, 24.0, 48.0, 72.0, 96.0]

print(f"\nNocodazole @ {dose}µM (Low Dose)")
print("-" * 100)
print(f"{'Time (h)':<10} {'Actin':<12} {'Mito':<12} {'Actin Loss':<12} {'Mito Loss':<12} {'Pattern':<30}")
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

    morph = result.get('morphology', {})
    actin = morph.get('actin', 0)
    mito = morph.get('mito', 0)

    actin_loss = (baseline_morph['iPSC_NGN2']['actin'] - actin) / baseline_morph['iPSC_NGN2']['actin']
    mito_loss = (baseline_morph['iPSC_NGN2']['mito'] - mito) / baseline_morph['iPSC_NGN2']['mito']

    if actin_loss < 0.25:
        pattern = "Mild disruption"
    elif actin_loss < 0.35:
        pattern = "Moderate disruption"
    else:
        pattern = "Severe disruption"

    print(f"{tp:<10.0f} {actin:>8.1f}{'':<3} {mito:>8.1f}{'':<3} {actin_loss:>8.1%}{'':<3} {mito_loss:>8.1%}{'':<3} {pattern:<30}")

print("\n" + "=" * 100)
print("INTERPRETATION:")
print("  If actin loss is CONSTANT (~20-25%) across time: Morphology penalty is stable")
print("  If actin loss INCREASES over time: Bug - morphology should be static at fixed dose")
print("=" * 100)
print("\nPOSSIBLE ISSUE:")
print("  Morphology penalty may be applied multiple times during simulation")
print("  OR: Baseline morphology (base dict) may be changing during simulation")
print("=" * 100)
