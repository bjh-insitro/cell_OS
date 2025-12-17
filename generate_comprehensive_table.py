#!/usr/bin/env python3
"""
Comprehensive Dose-Response Table

Generates full comparison across:
- 4 cell lines
- 8 compounds
- 3 doses (low, mid, high)
- 3 timepoints (12h, 24h, 48h)

This catches any "truth hidden in multiplier" issues.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

cell_lines = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia']
baseline_ldh = {'A549': 50000.0, 'HepG2': 50000.0, 'iPSC_NGN2': 70000.0, 'iPSC_Microglia': 65000.0}

# Compound panel with representative doses
compounds_and_doses = [
    ('H2O2', [30.0, 100.0, 300.0], 'oxidative'),
    ('CCCP', [3.0, 10.0, 30.0], 'mitochondrial'),
    ('oligomycin', [1.0, 3.0, 10.0], 'mitochondrial'),
    ('tunicamycin', [0.3, 1.0, 3.0], 'er_stress'),
    ('MG132', [1.0, 3.0, 10.0], 'proteasome'),
    ('etoposide', [3.0, 10.0, 30.0], 'dna_damage'),
    ('nocodazole', [0.3, 1.0, 10.0], 'microtubule'),
    ('paclitaxel', [0.003, 0.01, 0.1], 'microtubule'),
]

timepoints = [12.0, 24.0, 48.0]

# Seed once for reproducibility (not per-well)
np.random.seed(42)

print("=" * 120)
print("COMPREHENSIVE DOSE-RESPONSE TABLE")
print("=" * 120)
print("Note: 'atp_signal' is actually LDH (high = dead, low = alive)")
print("      Viability = 1 - (LDH / baseline_LDH)")
print("=" * 120)

for compound, doses, stress_type in compounds_and_doses:
    print(f"\n{'=' * 120}")
    print(f"Compound: {compound} ({stress_type})")
    print(f"{'=' * 120}")

    for tp in timepoints:
        print(f"\nTimepoint: {tp}h")
        print("-" * 120)
        print(f"{'Dose (µM)':<12} {'A549':<12} {'HepG2':<12} {'iPSC_NGN2':<15} {'iPSC_Microglia':<15} {'Pattern Check':<40}")
        print("-" * 120)

        for dose in doses:
            viabilities = {}
            agent = CellThalamusAgent(phase=0)  # Create once per dose row

            for cell_line in cell_lines:
                well = WellAssignment(
                    well_id='TEST', cell_line=cell_line, compound=compound,
                    dose_uM=dose, timepoint_h=tp, plate_id='P1',
                    day=1, operator='Test', is_sentinel=False
                )
                result = agent._execute_well(well)
                if result and 'atp_signal' in result:
                    # LDH is inversely proportional to viability:
                    # LDH = baseline × cell_count_factor × (1 - viability)
                    # For standard seeding, cell_count_factor ≈ 1.0
                    # So: viability ≈ 1 - (LDH / baseline)
                    ldh_signal = result['atp_signal']
                    viability = 1.0 - (ldh_signal / baseline_ldh[cell_line])
                    viabilities[cell_line] = max(0, min(1, viability))
                else:
                    viabilities[cell_line] = 0.0

            # Pattern checks based on stress type
            neuron_viab = viabilities['iPSC_NGN2']
            cancer_viabs = [viabilities['A549'], viabilities['HepG2']]
            microglia_viab = viabilities['iPSC_Microglia']

            if stress_type == 'mitochondrial':
                if neuron_viab < min(cancer_viabs):
                    pattern = "✓ Neurons most sensitive"
                else:
                    pattern = f"? Neuron {neuron_viab:.1%} vs cancer {min(cancer_viabs):.1%}"
            elif stress_type == 'microtubule':
                if neuron_viab > max(cancer_viabs):
                    pattern = "✓ Neurons most resistant"
                else:
                    pattern = f"? Neuron {neuron_viab:.1%} vs cancer {max(cancer_viabs):.1%}"
            elif stress_type == 'oxidative':
                if neuron_viab < min(cancer_viabs) and microglia_viab > neuron_viab:
                    pattern = "✓ Neurons sensitive, microglia resistant"
                else:
                    pattern = f"Neuron {neuron_viab:.1%}, Microglia {microglia_viab:.1%}"
            elif stress_type == 'proteasome':
                if microglia_viab < min([viabilities['A549'], viabilities['HepG2'], neuron_viab]):
                    pattern = "✓ Microglia most sensitive"
                else:
                    pattern = f"Microglia {microglia_viab:.1%} not most sensitive"
            else:
                pattern = ""

            print(f"{dose:<12.3f} {viabilities['A549']:>6.1%}{'':<5} {viabilities['HepG2']:>6.1%}{'':<5} "
                  f"{viabilities['iPSC_NGN2']:>6.1%}{'':<8} {viabilities['iPSC_Microglia']:>6.1%}{'':<8} {pattern:<40}")

print("\n" + "=" * 120)
print("TABLE COMPLETE")
print("=" * 120)
