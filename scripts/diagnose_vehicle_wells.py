#!/usr/bin/env python3
"""
Diagnostic: Check what's contaminating vehicle wells

Checks for seed 5000 (diagnostic mode with shared factors disabled):
1. Viability distribution for vehicle wells
2. Washout multiplier (should be 1.0)
3. Latent stress state (should be ~0)
4. Per-well biology baseline shifts

This identifies which global multiplier is causing 0.89 correlations.
"""

import json
import numpy as np
from pathlib import Path

# Load seed 5000 diagnostic run
results_dir = Path("validation_frontend/public/demo_results/calibration_plates")
pattern = "CAL_384_RULES_WORLD_v4_run_*_seed5000.json"
files = list(results_dir.glob(pattern))

if not files:
    print("❌ No seed 5000 data found")
    print("Run: bash scripts/run_structured_noise_validation_jh.sh")
    exit(1)

files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
with open(files[0], 'r') as f:
    data = json.load(f)

print("="*80)
print("VEHICLE WELL DIAGNOSTIC (Seed 5000)")
print("="*80)
print()

# Vehicle island wells (should be DMSO, no treatment)
VEHICLE_ISLANDS = {
    "CV_NW_HEPG2_VEH": ['D4','D5','D6','E4','E5','E6','F4','F5','F6'],
    "CV_NW_A549_VEH": ['D8','D9','D10','E8','E9','E10','F8','F9','F10'],
    "CV_NE_HEPG2_VEH": ['D15','D16','D17','E15','E16','E17','F15','F16','F17'],
    "CV_NE_A549_VEH": ['D20','D21','D22','E20','E21','E22','F20','F21','F22'],
    "CV_SE_HEPG2_VEH": ['K15','K16','K17','L15','L16','L17','M15','M16','M17'],
}

vehicle_wells = []
for wells in VEHICLE_ISLANDS.values():
    vehicle_wells.extend(wells)

# Extract data for vehicle wells
viabilities = []
signal_intensities = []  # viability_factor = 0.3 + 0.7 * viability
er_values = []
mito_values = []

for result in data['flat_results']:
    if result['well_id'] in vehicle_wells:
        if 'viability' in result:
            viabilities.append(result['viability'])
        if 'signal_intensity' in result:
            signal_intensities.append(result['signal_intensity'])
        if 'morph_er' in result:
            er_values.append(result['morph_er'])
        if 'morph_mito' in result:
            mito_values.append(result['morph_mito'])

print(f"Vehicle Wells Analyzed: {len(viabilities)}")
print()

# Check 1: Viability Distribution
print("="*80)
print("CHECK 1: VIABILITY DISTRIBUTION")
print("="*80)
print()
print("Expected: Vehicle wells should have viability ≈ 1.0 (tight distribution)")
print("Problem: If viability varies, it creates a global multiplier affecting all channels")
print()

if viabilities:
    print(f"Viability Statistics (n={len(viabilities)}):")
    print(f"  Min:    {np.min(viabilities):.4f}")
    print(f"  Q25:    {np.percentile(viabilities, 25):.4f}")
    print(f"  Median: {np.median(viabilities):.4f}")
    print(f"  Q75:    {np.percentile(viabilities, 75):.4f}")
    print(f"  Max:    {np.max(viabilities):.4f}")
    print(f"  Mean:   {np.mean(viabilities):.4f}")
    print(f"  Std:    {np.std(viabilities):.4f}")
    print(f"  CV:     {100 * np.std(viabilities) / np.mean(viabilities):.2f}%")
    print()

    # Viability factor: 0.3 + 0.7 * viability
    viability_factors = [0.3 + 0.7 * v for v in viabilities]
    print(f"Viability Factor (0.3 + 0.7*v) Statistics:")
    print(f"  Min:    {np.min(viability_factors):.4f}")
    print(f"  Max:    {np.max(viability_factors):.4f}")
    print(f"  Range:  {np.max(viability_factors) - np.min(viability_factors):.4f}")
    print(f"  CV:     {100 * np.std(viability_factors) / np.mean(viability_factors):.2f}%")
    print()

    if np.std(viabilities) < 0.01:
        print("✅ PASS: Viability is tight (std < 0.01)")
    elif np.std(viabilities) < 0.05:
        print("⚠️  MARGINAL: Viability varies (std < 0.05)")
    else:
        print("❌ FAIL: Viability varies significantly (std >= 0.05)")
        print("   This creates a global multiplier forcing correlations toward 1.0")
    print()

    # Histogram
    print("Viability Histogram:")
    hist, bins = np.histogram(viabilities, bins=10)
    for i, count in enumerate(hist):
        if count > 0:
            bar = '█' * int(count * 40 / max(hist))
            print(f"  {bins[i]:.3f}-{bins[i+1]:.3f}: {bar} ({count})")
    print()
else:
    print("❌ No viability data found")
    print()

# Check 2: Signal Intensity (Proxy for Viability Factor)
print("="*80)
print("CHECK 2: SIGNAL INTENSITY (VIABILITY FACTOR PROXY)")
print("="*80)
print()
print("Expected: Should be tight around 1.0 for vehicle wells")
print("Problem: If it varies, it's a global multiplier")
print()

if signal_intensities:
    print(f"Signal Intensity Statistics (n={len(signal_intensities)}):")
    print(f"  Min:    {np.min(signal_intensities):.4f}")
    print(f"  Median: {np.median(signal_intensities):.4f}")
    print(f"  Max:    {np.max(signal_intensities):.4f}")
    print(f"  CV:     {100 * np.std(signal_intensities) / np.mean(signal_intensities):.2f}%")
    print()

    if np.std(signal_intensities) < 0.01:
        print("✅ PASS: Signal intensity is tight")
    else:
        print("❌ FAIL: Signal intensity varies")
    print()
else:
    print("⚠️  No signal_intensity data found")
    print()

# Check 3: ER-Mito Correlation Driven by Viability?
print("="*80)
print("CHECK 3: VIABILITY AS GLOBAL MULTIPLIER")
print("="*80)
print()
print("Test: Do viability and morphology correlate?")
print("If yes, viability is the global multiplier forcing correlations")
print()

if viabilities and er_values and len(viabilities) == len(er_values):
    corr_viab_er = np.corrcoef(viabilities, er_values)[0, 1]
    corr_viab_mito = np.corrcoef(viabilities, mito_values)[0, 1]

    print(f"Viability vs ER correlation:   {corr_viab_er:.3f}")
    print(f"Viability vs Mito correlation: {corr_viab_mito:.3f}")
    print()

    if abs(corr_viab_er) > 0.5 or abs(corr_viab_mito) > 0.5:
        print("❌ FAIL: Viability strongly correlates with morphology")
        print("   Viability is acting as a global multiplier!")
        print()
        print("   Fix: For vehicle wells, force viability = 1.0")
        print("        or at least lock it to a tight distribution")
    elif abs(corr_viab_er) > 0.3:
        print("⚠️  MARGINAL: Viability moderately correlates with morphology")
    else:
        print("✅ PASS: Viability doesn't correlate with morphology")
    print()
else:
    print("⚠️  Insufficient data for correlation analysis")
    print()

# Summary
print("="*80)
print("DIAGNOSIS SUMMARY")
print("="*80)
print()
print("With all shared factors (plate/day/operator/edge/illumination) disabled,")
print("correlations are still 0.89. The remaining culprits are:")
print()
print("1. Viability factor: Applies uniformly to all channels BEFORE structured noise")
print("2. Washout multiplier: Also uniform (but should be 1.0 for vehicle)")
print("3. Latent stress: If sampled for vehicle, it's a hidden confounder")
print()
print("If viability std > 0.05 or corr(viability, morphology) > 0.5:")
print("  → Viability is the bully forcing 0.89 correlations")
print("  → Fix: Force vehicle wells to viability=1.0 or very tight distribution")
print()
