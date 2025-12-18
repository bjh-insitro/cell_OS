#!/usr/bin/env python3
"""
Validate Time-Dependent Attrition Signatures

Plot (48h viability - 12h viability) vs dose for each stress class.
Expected pattern:
- ER/proteasome: Strongly negative at high dose, near zero at low dose
- Mito/microtubule: Near zero everywhere (early commitment dominates)
- Oxidative/DNA: Intermediate slope
"""

import sys
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import standalone_cell_thalamus as ct

print("=" * 80)
print("Attrition Signature Validation")
print("=" * 80)

# Test compounds representing each stress axis
test_compounds = {
    'tunicamycin': 'er_stress',
    'MG132': 'proteasome',
    'tBHQ': 'oxidative',
    'CCCP': 'mitochondrial',
    'etoposide': 'dna_damage',
    'paclitaxel': 'microtubule',
}

# Dose ranges (as fractions of EC50)
dose_fractions = [0.0, 0.1, 1.0, 10.0]

results = defaultdict(lambda: defaultdict(lambda: {'12h_ldh': [], '48h_ldh': [], 'dose_uM': 0}))

# Run N replicates to average out noise
N_REPLICATES = 12

for compound, stress_axis in test_compounds.items():
    params = ct.COMPOUND_PARAMS[compound]
    ec50_base = params['ec50_uM']

    for cell_line in ['A549', 'HepG2']:
        for dose_frac in dose_fractions:
            dose_uM = dose_frac * ec50_base

            # Simulate 12h and 48h with replicates
            for replicate in range(N_REPLICATES):
                for timepoint in [12.0, 48.0]:
                    well = ct.WellAssignment(
                        well_id=f"test_{compound}_{cell_line}_{dose_frac}_{timepoint}_{replicate}",
                        cell_line=cell_line,
                        compound=compound,
                        dose_uM=dose_uM,
                        timepoint_h=timepoint,
                        plate_id=f'test_rep{replicate}',
                        day=1,
                        operator='test',
                        is_sentinel=False
                    )

                    result = ct.simulate_well(well, 'test')
                    if result:
                        ldh = result['atp_signal']
                        key = (cell_line, dose_frac)
                        if timepoint == 12.0:
                            results[compound][key]['12h_ldh'].append(ldh)
                        else:
                            results[compound][key]['48h_ldh'].append(ldh)
                        results[compound][key]['dose_uM'] = dose_uM

# Calculate viability and attrition for each compound separately
print("\nAttrition Signatures (48h viability - 12h viability)")
print("=" * 80)

for compound, stress_axis in test_compounds.items():
    print(f"\n{compound.upper()} ({stress_axis})")
    print("-" * 80)
    print(f"{'Cell Line':<10} {'Dose (xEC50)':<15} {'12h Viab%':<12} {'48h Viab%':<12} {'Δ Viability':<15}")
    print("-" * 80)

    # Use theoretical max LDH (100% cell death = baseline_ldh * 1.0)
    # This avoids normalization artifacts from different max values at each timepoint
    baseline_ldh = 50000.0

    for cell_line in ['A549', 'HepG2']:
        for dose_frac in dose_fractions:
            key = (cell_line, dose_frac)
            if key in results[compound]:
                data = results[compound][key]

                # Average across replicates
                ldh_12_list = data.get('12h_ldh', [])
                ldh_48_list = data.get('48h_ldh', [])

                if not ldh_12_list or not ldh_48_list:
                    continue

                ldh_12 = np.mean(ldh_12_list)
                ldh_48 = np.mean(ldh_48_list)

                # viability = 100 - (ldh / baseline * 100)
                # At ldh=0: viability=100%, at ldh=baseline: viability=0%
                viab_12 = 100.0 * (1.0 - ldh_12 / baseline_ldh)
                viab_48 = 100.0 * (1.0 - ldh_48 / baseline_ldh)

                delta_viab = viab_48 - viab_12

                # Color code the delta
                if abs(delta_viab) < 2:
                    marker = "≈"  # Near zero (stable)
                elif delta_viab < -10:
                    marker = "↓↓"  # Strong attrition
                elif delta_viab < -5:
                    marker = "↓"  # Moderate attrition
                else:
                    marker = "?"

                print(f"{cell_line:<10} {dose_frac:<15.1f} {viab_12:<12.1f} {viab_48:<12.1f} {delta_viab:>+7.1f}% {marker}")

print("\n" + "=" * 80)
print("VALIDATION CRITERIA:")
print("=" * 80)
print("✓ ER/Proteasome: Strongly negative (↓↓) at high dose (10×), near zero (≈) at low dose")
print("✓ Mito/Microtubule: Near zero (≈) everywhere (early commitment)")
print("✓ Oxidative/DNA: Intermediate (↓) slope")
print("\nIf these patterns hold, attrition encodes time as a mechanistic feature.")
print("=" * 80)
