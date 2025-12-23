#!/usr/bin/env python3
"""Debug why validator reports 46.5% CV when actual CV is 6.5%"""
import json
import numpy as np
from pathlib import Path

VEHICLE_ISLANDS = {
    "CV_NW_HEPG2_VEH": ["D4","D5","D6","E4","E5","E6","F4","F5","F6"],
    "CV_NW_A549_VEH": ["D8","D9","D10","E8","E9","E10","F8","F9","F10"],
    "CV_NE_HEPG2_VEH": ["D15","D16","D17","E15","E16","E17","F15","F16","F17"],
    "CV_NE_A549_VEH": ["D20","D21","D22","E20","E21","E22","F20","F21","F22"],
    "CV_SE_HEPG2_VEH": ["K15","K16","K17","L15","L16","L17","M15","M16","M17"]
}

results_dir = Path("validation_frontend/public/demo_results/calibration_plates")
files = sorted(results_dir.glob("*seed5000.json"), key=lambda p: p.stat().st_mtime, reverse=True)

if not files:
    print("❌ No seed 5000 results found")
    exit(1)

print(f"Loading: {files[0].name}")
print()

data = json.load(open(files[0]))
flat_results = data['flat_results']

print("="*80)
print("SEED 5000 - INDIVIDUAL ISLAND CVs")
print("="*80)
print()

island_cvs = []
for island_id, wells in VEHICLE_ISLANDS.items():
    island_data = [r for r in flat_results if r['well_id'] in wells]
    values = [r['morph_er'] for r in island_data if 'morph_er' in r]
    if len(values) > 0:
        cv = 100 * np.std(values) / np.mean(values)
        island_cvs.append(cv)
        print(f"{island_id:20s}: CV={cv:5.1f}% (n={len(values)}, mean={np.mean(values):.1f})")
    else:
        print(f"{island_id:20s}: NO DATA")

print()
print("="*80)
print("AGGREGATE")
print("="*80)
print(f"Mean CV across islands: {np.mean(island_cvs):.1f}%")
print(f"Validator reported:     46.5%")
print()

if np.mean(island_cvs) < 10:
    print("✅ Individual CVs are CORRECT (6-9%)")
    print("❌ But validator reported 46.5%")
    print()
    print("This suggests the validator has a bug in:")
    print("  1. Loading multiple seeds (mixing them incorrectly)")
    print("  2. Aggregating CVs (wrong formula)")
    print("  3. Using wrong wells (mixing islands)")
