#!/usr/bin/env python3
"""
Direct Dysfunction Score Test

Directly compute the dysfunction score from structural morphology (before viability scaling)
to verify it stays constant at fixed dose across timepoints.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np

# Nocodazole parameters for iPSC_NGN2
dose_uM = 0.3
ec50 = 0.5  # Base EC50
cell_line = 'iPSC_NGN2'

# IC50 adjustment (from standalone_cell_thalamus.py lines 715-726)
prolif = 0.1  # iPSC_NGN2 proliferation
mitosis_mult = 1.0 / max(prolif, 0.3)
functional_dependency = 0.8  # iPSC_NGN2
ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)
ic50_mult = max(0.3, min(5.0, ic50_mult))

print("=" * 100)
print("DYSFUNCTION SCORE DIRECT CALCULATION")
print("=" * 100)
print(f"Cell line: {cell_line}")
print(f"Compound: nocodazole")
print(f"Dose: {dose_uM} µM")
print(f"EC50 (base): {ec50} µM")
print(f"IC50 multiplier: {ic50_mult:.3f}×")
print(f"Adjusted IC50: {ec50 * ic50_mult:.3f} µM")
print()

# Morphology EC50 calculation (from lines 765-772)
morph_ec50_fraction = 0.3  # iPSC_NGN2
morph_ec50 = ec50 * morph_ec50_fraction
morph_penalty = dose_uM / (dose_uM + morph_ec50)

print(f"Morphology EC50: {morph_ec50:.3f} µM")
print(f"Morphology penalty: {morph_penalty:.3f}")
print()

# Baseline morphology
baseline_actin = 160.0  # iPSC_NGN2 baseline
baseline_mito = 220.0   # iPSC_NGN2 baseline

# Structural morphology (from lines 778-780)
structural_actin = baseline_actin * (1.0 - 0.6 * morph_penalty)
structural_mito = baseline_mito * (1.0 - 0.5 * morph_penalty)

print(f"STRUCTURAL morphology (before noise, before viability scaling):")
print(f"  Actin: {structural_actin:.1f} AU (baseline: {baseline_actin:.1f})")
print(f"  Mito: {structural_mito:.1f} AU (baseline: {baseline_mito:.1f})")
print()

# Dysfunction score (from lines 791-792)
actin_disruption = max(0.0, 1.0 - structural_actin / baseline_actin)
mito_disruption = max(0.0, 1.0 - structural_mito / baseline_mito)
transport_dysfunction_score = 0.5 * (actin_disruption + mito_disruption)
transport_dysfunction_score = min(1.0, max(0.0, transport_dysfunction_score))

print(f"DYSFUNCTION SCORE (should be constant across all timepoints):")
print(f"  Actin disruption: {actin_disruption:.1%}")
print(f"  Mito disruption: {mito_disruption:.1%}")
print(f"  Transport dysfunction: {transport_dysfunction_score:.3f}")
print()

# Attrition scaling (from lines 951-952)
attrition_scale = 1.0 + 2.0 * (transport_dysfunction_score ** 2.0)
base_mt_attrition = 0.25
attrition_rate = base_mt_attrition * attrition_scale

print(f"ATTRITION CALCULATION:")
print(f"  Base MT attrition rate: {base_mt_attrition:.3f}")
print(f"  Attrition scale: {attrition_scale:.3f}×")
print(f"  Effective attrition rate: {attrition_rate:.3f}")
print()

# Now simulate viability decline over time using this CONSTANT dysfunction
print("=" * 100)
print("VIABILITY OVER TIME (using constant dysfunction score)")
print("=" * 100)

hill_slope = 2.0
ic50_viability = ec50 * ic50_mult
hill_v = hill_slope * (0.8 + 0.4 * prolif)

# Base viability effect from dose (instant, not time-dependent)
viability_effect_base = 1.0 / (1.0 + (dose_uM / ic50_viability) ** hill_v)

print(f"Base viability effect (instant): {viability_effect_base:.1%}")
print()

print(f"{'Time (h)':<10} {'Viability':<12} {'Attrition':<15} {'Observed Actin':<15} {'Observed Mito':<15}")
print("-" * 100)

for timepoint_h in [12.0, 24.0, 48.0, 72.0, 96.0]:
    # Time-dependent death continuation (from lines 920-967)
    viability_effect = viability_effect_base

    if timepoint_h > 12 and viability_effect < 0.5:
        # Calculate stress severity
        dose_ratio = dose_uM / ic50_viability

        # Time scaling
        time_factor = (timepoint_h - 12.0) / 36.0  # 0 at 12h, 1 at 48h, >1 after 48h

        # Additional death from attrition (using CONSTANT dysfunction score)
        if dose_ratio >= 1.0:
            stress_multiplier = dose_ratio / (1.0 + dose_ratio)
            additional_death = attrition_rate * stress_multiplier * time_factor
            viability_effect = viability_effect * (1.0 - additional_death)
            viability_effect = max(0.01, viability_effect)
            attrition_applied = additional_death
        else:
            attrition_applied = 0.0
    else:
        attrition_applied = 0.0

    # Observed morphology (structural × viability factor)
    # Dead cells retain 30% signal
    viability_factor = 0.3 + 0.7 * viability_effect
    observed_actin = structural_actin * viability_factor
    observed_mito = structural_mito * viability_factor

    print(f"{timepoint_h:<10.0f} {viability_effect:>6.1%}{'':<5} {attrition_applied:>8.1%}{'':<6} {observed_actin:>10.1f}{'':<4} {observed_mito:>10.1f}{'':<4}")

print()
print("=" * 100)
print("KEY INSIGHT:")
print(f"  Dysfunction score: {transport_dysfunction_score:.3f} (CONSTANT at all timepoints)")
print(f"  Observed morphology: VARIES with viability (measurement effect)")
print("=" * 100)
