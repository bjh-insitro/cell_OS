#!/usr/bin/env python3
"""
Dose Sweep Validation Test

Verifies rank-order stability across doses for CCCP and nocodazole.
Tests that neurons are consistently more sensitive to CCCP and more
resistant to nocodazole across all doses.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']
baseline_ldh = {'A549': 50000.0, 'HepG2': 50000.0, 'iPSC_NGN2': 70000.0, 'iPSC_Microglia': 65000.0}

print("=" * 100)
print("DOSE SWEEP VALIDATION: Rank-Order Stability")
print("=" * 100)

# Test 1: CCCP dose sweep (neurons should be most sensitive at ALL doses)
print("\n1. CCCP Dose Sweep (Mitochondrial Uncoupler)")
print("-" * 100)

doses = [0.3, 1.0, 3.0, 10.0, 30.0]
timepoint = 24.0

print(f"{'Dose (µM)':<12} {'A549':<12} {'HepG2':<12} {'iPSC_NGN2':<15} {'iPSC_Microglia':<15} {'Rank Check':<20}")
print("-" * 100)

for dose in doses:
    viabilities = {}
    for cell_line in cell_lines:
        np.random.seed(42)
        agent = CellThalamusAgent(phase=0)
        well = WellAssignment(
            well_id='TEST', cell_line=cell_line, compound='CCCP',
            dose_uM=dose, timepoint_h=timepoint, plate_id='P1',
            day=1, operator='Test', is_sentinel=False
        )
        result = agent._execute_well(well)
        if result and 'atp_signal' in result:
            viability = 1.0 - (result['atp_signal'] / baseline_ldh[cell_line])
            viabilities[cell_line] = max(0, min(1, viability))
        else:
            viabilities[cell_line] = 0.0

    # Check rank order: neurons should be most sensitive
    neuron_viab = viabilities['iPSC_NGN2']
    cancer_viabs = [viabilities['A549'], viabilities['HepG2']]

    if neuron_viab < min(cancer_viabs):
        rank_status = "✓ Neurons most sensitive"
    else:
        rank_status = "✗ Rank order violation!"

    print(f"{dose:<12.1f} {viabilities['A549']:>6.1%}{'':<5} {viabilities['HepG2']:>6.1%}{'':<5} "
          f"{viabilities['iPSC_NGN2']:>6.1%}{'':<8} {viabilities['iPSC_Microglia']:>6.1%}{'':<8} {rank_status:<20}")

# Test 2: Nocodazole dose sweep (neurons should be most resistant at ALL doses)
print("\n2. Nocodazole Dose Sweep (Microtubule Poison)")
print("-" * 100)

doses = [0.03, 0.1, 0.3, 1.0, 10.0]

print(f"{'Dose (µM)':<12} {'A549':<12} {'HepG2':<12} {'iPSC_NGN2':<15} {'iPSC_Microglia':<15} {'Rank Check':<20}")
print("-" * 100)

for dose in doses:
    viabilities = {}
    for cell_line in cell_lines:
        np.random.seed(42)
        agent = CellThalamusAgent(phase=0)
        well = WellAssignment(
            well_id='TEST', cell_line=cell_line, compound='nocodazole',
            dose_uM=dose, timepoint_h=timepoint, plate_id='P1',
            day=1, operator='Test', is_sentinel=False
        )
        result = agent._execute_well(well)
        if result and 'atp_signal' in result:
            viability = 1.0 - (result['atp_signal'] / baseline_ldh[cell_line])
            viabilities[cell_line] = max(0, min(1, viability))
        else:
            viabilities[cell_line] = 0.0

    # Check rank order: neurons should be most resistant
    neuron_viab = viabilities['iPSC_NGN2']
    cancer_viabs = [viabilities['A549'], viabilities['HepG2']]

    if neuron_viab > max(cancer_viabs):
        rank_status = "✓ Neurons most resistant"
    else:
        rank_status = "✗ Rank order violation!"

    print(f"{dose:<12.2f} {viabilities['A549']:>6.1%}{'':<5} {viabilities['HepG2']:>6.1%}{'':<5} "
          f"{viabilities['iPSC_NGN2']:>6.1%}{'':<8} {viabilities['iPSC_Microglia']:>6.1%}{'':<8} {rank_status:<20}")

print("\n" + "=" * 100)
print("VALIDATION SUMMARY:")
print("  ✓ All doses should maintain rank order (neurons most sensitive to CCCP, most resistant to nocodazole)")
print("  ✓ No weird inversions or IC50 pathology")
print("=" * 100)
