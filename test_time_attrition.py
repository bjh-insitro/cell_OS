#!/usr/bin/env python3
"""Test time-dependent attrition at 48h for ER stress compounds"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import standalone simulation
import standalone_cell_thalamus as ct

print("="*80)
print("Testing Time-Dependent Attrition (12h vs 48h)")
print("="*80)

# Create wells for tunicamycin (ER stress - high attrition rate)
test_wells = []

for timepoint in [12.0, 48.0]:
    for dose in [0.0, 0.1, 1.0, 10.0]:
        well = ct.WellAssignment(
            well_id=f"T{int(timepoint)}_D{dose}",
            cell_line='HepG2',
            compound='tunicamycin',
            dose_uM=dose,
            timepoint_h=timepoint,
            plate_id=f"Test_T{int(timepoint)}",
            day=1,
            operator='Test',
            is_sentinel=False
        )
        test_wells.append(well)

# Simulate
design_id = 'test_attrition'
results = []
for well in test_wells:
    result = ct.simulate_well(well, design_id)
    if result:
        results.append(result)

# Analyze
print("\nTunicamycin (ER Stress) - HepG2")
print("-" * 80)
print(f"{'Dose (µM)':<12} {'12h LDH':<12} {'12h Viab%':<12} {'48h LDH':<12} {'48h Viab%':<12} {'Attrition':<12}")
print("-" * 80)

max_ldh = max(r['atp_signal'] for r in results)

by_dose = {}
for r in results:
    dose = r['dose_uM']
    if dose not in by_dose:
        by_dose[dose] = {'12h': None, '48h': None}

    timepoint = '12h' if r['timepoint_h'] == 12.0 else '48h'
    by_dose[dose][timepoint] = {
        'ldh': r['atp_signal'],
        'viability': 100.0 - (r['atp_signal'] / max_ldh * 100.0)
    }

for dose in sorted(by_dose.keys()):
    data = by_dose[dose]
    ldh_12 = data['12h']['ldh']
    viab_12 = data['12h']['viability']
    ldh_48 = data['48h']['ldh']
    viab_48 = data['48h']['viability']

    attrition = viab_12 - viab_48
    attrition_str = f"{attrition:+.1f}%" if dose > 0 else "n/a"

    print(f"{dose:<12.1f} {ldh_12:<12.0f} {viab_12:<12.1f} {ldh_48:<12.0f} {viab_48:<12.1f} {attrition_str:<12}")

print("\n" + "="*80)
print("Expected Behavior:")
print("- Low dose (0.1 µM): Minimal attrition (~0-2%)")
print("- Mid dose (1.0 µM): Moderate attrition (~5-10%)")
print("- High dose (10.0 µM): Strong attrition (15-25%) → apocalyptic by 48h")
print("="*80)
