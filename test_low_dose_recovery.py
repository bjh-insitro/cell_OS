#!/usr/bin/env python3
"""
Low Dose Recovery Test

Verifies that low doses of nocodazole DON'T cause inevitable death.
Tests the attrition ceiling mechanism (dys^2 scaling).

Key principle: Mild morphology disruption (<30%) should allow cells to adapt/survive.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

baseline_ldh = {'iPSC_NGN2': 70000.0}
baseline_morph = {'iPSC_NGN2': {'actin': 160.0, 'mito': 220.0}}

print("=" * 100)
print("LOW DOSE RECOVERY TEST: Attrition Ceiling Mechanism")
print("=" * 100)

# Test multiple low doses
doses = [0.1, 0.3, 0.5, 1.0]
timepoints = [24.0, 48.0, 72.0, 96.0]

print("\nLow Doses: Should NOT cause inevitable death at 96h")
print("-" * 100)
print(f"{'Dose (µM)':<12} {'24h Viab':<12} {'96h Viab':<12} {'Actin Loss':<12} {'Pattern Check':<40}")
print("-" * 100)

for dose in doses:
    results = {}

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

        results[tp] = {'viability': viability, 'actin_loss': actin_loss}

    viab_24h = results[24.0]['viability']
    viab_96h = results[96.0]['viability']
    actin_loss = results[96.0]['actin_loss']

    # Pattern check: low doses should maintain viability
    if actin_loss < 0.30:  # Mild disruption
        if viab_96h > 0.70:
            pattern = "✓ Mild disruption, adapted/survived"
        else:
            pattern = f"? Died despite mild disruption ({viab_96h:.1%})"
    else:  # Severe disruption
        if viab_96h < 0.70:
            pattern = "✓ Severe disruption, death expected"
        else:
            pattern = "Severe disruption but still alive"

    print(f"{dose:<12.1f} {viab_24h:>6.1%}{'':<5} {viab_96h:>6.1%}{'':<5} {actin_loss:>8.1%}{'':<3} {pattern:<40}")

print("\n" + "=" * 100)
print("EXPECTED BEHAVIOR:")
print("  Low doses (<1µM): Mild morphology disruption (<30%) → Attrition ceiling → Survive to 96h")
print("  High doses (>5µM): Severe disruption (>30%) → High attrition → Death by 96h")
print("=" * 100)
print("\nNote: dys^2 scaling means:")
print("  20% disruption → attrition_scale = 1 + 2×(0.2)^2 = 1.08× (mild, allows recovery)")
print("  40% disruption → attrition_scale = 1 + 2×(0.4)^2 = 1.32× (moderate)")
print("  60% disruption → attrition_scale = 1 + 2×(0.6)^2 = 1.72× (severe, leads to death)")
print("=" * 100)
