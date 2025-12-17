#!/usr/bin/env python3
"""
Neuron Death Arc Test

Verifies that neurons under high-dose nocodazole:
1. Show immediate morphology disruption (12-24h)
2. Maintain high viability initially (24h)
3. Gradually lose viability over time (48-96h)
4. Die faster when morphology is more disrupted

This tests the morphology → attrition → viability causal arc.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

baseline_ldh = {'iPSC_NGN2': 70000.0, 'A549': 50000.0}
baseline_morph = {'iPSC_NGN2': {'actin': 160.0, 'mito': 220.0}}

print("=" * 100)
print("NEURON DEATH ARC TEST: High-Dose Nocodazole")
print("=" * 100)

# Test neurons at high dose (10 µM) across multiple timepoints
print("\n1. Neurons: Nocodazole @ 10µM (High Dose)")
print("-" * 100)

timepoints = [12.0, 24.0, 48.0, 72.0, 96.0]

print(f"{'Time':<8} {'Viability':<12} {'Actin':<12} {'Mito':<12} {'Actin Loss':<12} {'Mito Loss':<12} {'Pattern':<30}")
print("-" * 100)

for tp in timepoints:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)
    well = WellAssignment(
        well_id='TEST', cell_line='iPSC_NGN2', compound='nocodazole',
        dose_uM=10.0, timepoint_h=tp, plate_id='P1',
        day=1, operator='Test', is_sentinel=False
    )
    result = agent._execute_well(well)

    viability = 1.0 - (result['atp_signal'] / baseline_ldh['iPSC_NGN2'])
    viability = max(0, min(1, viability))

    morph = result.get('morphology', {})
    actin = morph.get('actin', 0)
    mito = morph.get('mito', 0)

    actin_loss = (baseline_morph['iPSC_NGN2']['actin'] - actin) / baseline_morph['iPSC_NGN2']['actin']
    mito_loss = (baseline_morph['iPSC_NGN2']['mito'] - mito) / baseline_morph['iPSC_NGN2']['mito']

    # Determine pattern
    if tp <= 24:
        if viability > 0.95 and actin_loss > 0.2:
            pattern = "✓ High viab, morphology disrupted"
        else:
            pattern = "? Unexpected"
    elif tp == 48:
        if viability > 0.90:
            pattern = "? Too resistant (expect decline)"
        elif 0.70 < viability <= 0.90:
            pattern = "✓ Gradual decline starting"
        else:
            pattern = "✓ Significant decline"
    else:  # 72-96h
        if viability > 0.85:
            pattern = "? Too resistant (expect death)"
        elif 0.40 < viability <= 0.85:
            pattern = "✓ Continued decline"
        else:
            pattern = "✓ Severe death (morphology → viability)"

    print(f"{tp:<8.0f} {viability:>6.1%}{'':<5} {actin:>8.1f}{'':<3} {mito:>8.1f}{'':<3} "
          f"{actin_loss:>8.1%}{'':<3} {mito_loss:>8.1%}{'':<3} {pattern:<30}")

# Test cancer cells for comparison (should die fast)
print("\n2. Cancer (A549): Nocodazole @ 10µM (High Dose)")
print("-" * 100)

print(f"{'Time':<8} {'Viability':<12} {'Pattern':<30}")
print("-" * 100)

for tp in [12.0, 24.0, 48.0]:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)
    well = WellAssignment(
        well_id='TEST', cell_line='A549', compound='nocodazole',
        dose_uM=10.0, timepoint_h=tp, plate_id='P1',
        day=1, operator='Test', is_sentinel=False
    )
    result = agent._execute_well(well)

    viability = 1.0 - (result['atp_signal'] / baseline_ldh['A549'])
    viability = max(0, min(1, viability))

    pattern = "✓ Mitotic catastrophe (fast death)" if viability < 0.30 else "? Too resistant"

    print(f"{tp:<8.0f} {viability:>6.1%}{'':<5} {pattern:<30}")

# Test lower dose (should be less severe)
print("\n3. Neurons: Nocodazole @ 1µM (Low Dose)")
print("-" * 100)

print(f"{'Time':<8} {'Viability':<12} {'Actin Loss':<12} {'Pattern':<30}")
print("-" * 100)

for tp in [24.0, 48.0, 96.0]:
    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)
    well = WellAssignment(
        well_id='TEST', cell_line='iPSC_NGN2', compound='nocodazole',
        dose_uM=1.0, timepoint_h=tp, plate_id='P1',
        day=1, operator='Test', is_sentinel=False
    )
    result = agent._execute_well(well)

    viability = 1.0 - (result['atp_signal'] / baseline_ldh['iPSC_NGN2'])
    viability = max(0, min(1, viability))

    morph = result.get('morphology', {})
    actin = morph.get('actin', 0)
    actin_loss = (baseline_morph['iPSC_NGN2']['actin'] - actin) / baseline_morph['iPSC_NGN2']['actin']

    pattern = "✓ Mild disruption, high viability" if viability > 0.85 else "? Unexpected decline"

    print(f"{tp:<8.0f} {viability:>6.1%}{'':<5} {actin_loss:>8.1%}{'':<3} {pattern:<30}")

print("\n" + "=" * 100)
print("EXPECTED DEATH ARC (High Dose, 10µM):")
print("  12-24h: High viability (>95%), significant morphology disruption (>25%)")
print("  48h:    Viability starts declining (70-90%) as attrition accumulates")
print("  72-96h: Significant death (40-70%) from sustained transport failure")
print("=" * 100)
print("\nLow Dose (1µM): Mild disruption, viability stays high (>85%) even at 96h")
print("Cancer: Mitotic catastrophe, dead by 24h (<30% viability)")
print("=" * 100)
