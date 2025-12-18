#!/usr/bin/env python3
"""
Detailed Morphology Debug

Add instrumentation to see exactly where morphology values come from.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np

# Manually simulate the morphology calculation to understand accumulation
dose_uM = 0.3
ec50 = 0.5  # nocodazole EC50
hill_slope = 2.0
cell_line = 'iPSC_NGN2'

# IC50 adjustment
prolif = 0.1  # Neuron proliferation
mitosis_mult = 1.0 / max(prolif, 0.3)
functional_dependency = 0.8
ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)
ic50_viability = ec50 * ic50_mult

print("=" * 100)
print("MORPHOLOGY CALCULATION BREAKDOWN")
print("=" * 100)
print(f"Dose: {dose_uM} µM")
print(f"EC50: {ec50} µM")
print(f"IC50 mult: {ic50_mult:.2f}×")
print(f"Adjusted IC50: {ic50_viability:.2f} µM")
print()

# Viability effect (should be constant for fixed dose)
viability_effect_true = 1.0 / (1.0 + (dose_uM / ic50_viability) ** (hill_slope * (0.8 + 0.4 * prolif)))
print(f"Viability effect (constant): {viability_effect_true:.3f}")
print()

# Baseline morphology
baseline_actin = 160.0
baseline_mito = 220.0

# Morphology EC50 calculation
morph_ec50_fraction = 0.3
morph_ec50 = ec50 * morph_ec50_fraction
morph_penalty = dose_uM / (dose_uM + morph_ec50)

print(f"Morphology EC50: {morph_ec50:.3f} µM")
print(f"Morphology penalty: {morph_penalty:.3f}")
print()

# Apply microtubule penalties
structural_actin = baseline_actin * (1.0 - 0.6 * morph_penalty)
structural_mito = baseline_mito * (1.0 - 0.5 * morph_penalty)

print(f"STRUCTURAL morphology (no noise, no viability factor):")
print(f"  Actin: {structural_actin:.1f} ({(1 - structural_actin/baseline_actin):.1%} loss)")
print(f"  Mito: {structural_mito:.1f} ({(1 - structural_mito/baseline_mito):.1%} loss)")
print()

# This should be CONSTANT across all timepoints!
print("=" * 100)
print("EXPECTED: These values should be IDENTICAL at 12h, 24h, 48h, 72h, 96h")
print("=" * 100)
