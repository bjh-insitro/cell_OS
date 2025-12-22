#!/usr/bin/env python3
"""Check if v4 island wells have realistic biological variance."""

import json
import numpy as np
from pathlib import Path

v4_files = sorted(Path("validation_frontend/public/demo_results/calibration_plates").glob("CAL_384_RULES_WORLD_v4_run_*_seed42.json"))

if not v4_files:
    print("No v4 results found for seed 42")
    exit(1)

v4_file = v4_files[0]
print(f"Analyzing: {v4_file.name}\n")

with open(v4_file) as f:
    data = json.load(f)

# Check first island (CV_NW_HEPG2_VEH)
island_wells = ['D4', 'D5', 'D6', 'E4', 'E5', 'E6', 'F4', 'F5', 'F6']
island_results = [r for r in data['flat_results'] if r['well_id'] in island_wells]

print("Island Well Values (CV_NW_HEPG2_VEH - morph_nucleus):")
for r in sorted(island_results, key=lambda x: x['well_id']):
    print(f"  {r['well_id']}: {r['morph_nucleus']:.2f}")

values = [r['morph_nucleus'] for r in island_results]
mean = np.mean(values)
std = np.std(values, ddof=1)
cv = (std / mean) * 100

print(f"\nStatistics:")
print(f"  Mean: {mean:.2f}")
print(f"  Std:  {std:.2f}")
print(f"  CV:   {cv:.2f}%")
print()

# Compare to a v3 tile for reference
v3_files = sorted(Path("validation_frontend/public/demo_results/calibration_plates").glob("CAL_384_RULES_WORLD_v3_run_*_seed42.json"))
if v3_files:
    with open(v3_files[0]) as f:
        v3_data = json.load(f)

    v3_tile = ['B2', 'B3', 'C2', 'C3']
    v3_results = [r for r in v3_data['flat_results'] if r['well_id'] in v3_tile]
    v3_values = [r['morph_nucleus'] for r in v3_results]
    v3_cv = (np.std(v3_values, ddof=1) / np.mean(v3_values)) * 100

    print(f"Comparison: V3 tile (B2-C3) CV = {v3_cv:.2f}%")
    print()

# Sanity checks
if std < 0.01:
    print("⚠️  WARNING: Island wells have near-zero variance!")
    print("   This suggests a bug in execution or collapsed values")
elif cv < 5:
    print("⚠️  WARNING: Island CV suspiciously low (<5%)")
    print("   Verify this is real biological variance")
elif cv < 20:
    print("✅ Island CV looks reasonable (5-20% range)")
    print("   Homogeneous islands working as designed")
else:
    print("⚠️  Island CV higher than expected (>20%)")
    print("   May indicate technical noise dominates")
