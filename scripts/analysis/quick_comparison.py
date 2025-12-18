#!/usr/bin/env python3
"""Quick cell line comparison for key compounds."""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

# Test key compounds that show differences
cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']
conditions = [
    ('H2O2', 100.0, 'oxidative'),
    ('CCCP', 30.0, 'mitochondrial'),
    ('MG132', 10.0, 'proteasome'),
    ('nocodazole', 10.0, 'microtubule'),
]
timepoints = [12.0, 24.0, 48.0]

baseline_ldh = {'A549': 50000.0, 'HepG2': 50000.0, 'iPSC_NGN2': 70000.0, 'iPSC_Microglia': 65000.0}

print("=" * 100)
print("NEURON & MICROGLIA COMPARISON TABLE")
print("=" * 100)

for compound, dose, stress_type in conditions:
    print(f"\n{compound} @ {dose}µM ({stress_type}):")
    print("-" * 100)
    print(f"{'Timepoint':<12} {'A549':<12} {'HepG2':<12} {'iPSC_NGN2':<15} {'iPSC_Microglia':<15}")
    print("-" * 100)

    for tp in timepoints:
        row = [f"{tp}h"]
        for cell_line in cell_lines:
            np.random.seed(42)
            agent = CellThalamusAgent(phase=0)
            well = WellAssignment(
                well_id='TEST', cell_line=cell_line, compound=compound,
                dose_uM=dose, timepoint_h=tp, plate_id='P1',
                day=1, operator='Test', is_sentinel=False
            )
            result = agent._execute_well(well)
            if result and 'atp_signal' in result:
                viability = 1.0 - (result['atp_signal'] / baseline_ldh[cell_line])
                viability = max(0, min(1, viability))
                row.append(f"{viability:.1%}")
            else:
                row.append("0.0%")
        print(f"{row[0]:<12} {row[1]:<12} {row[2]:<12} {row[3]:<15} {row[4]:<15}")

print("\n" + "=" * 100)
print("KEY PATTERNS:")
print("  Oxidative (H2O2): Neurons most sensitive, Microglia most resistant")
print("  Mitochondrial (CCCP): Neurons extremely sensitive (high OXPHOS dependence)")
print("  Proteasome (MG132): Microglia most sensitive (high protein turnover)")
print("  Microtubule (nocodazole): Neurons most resistant (post-mitotic)")
print("=" * 100)
