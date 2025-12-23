#!/usr/bin/env python3
"""Debug why CV_SE_HEPG2_VEH has 161% CV and mean ER=252"""
import json
import numpy as np
from pathlib import Path

results_dir = Path("validation_frontend/public/demo_results/calibration_plates")
files = sorted(results_dir.glob("*seed5000.json"), key=lambda p: p.stat().st_mtime, reverse=True)

if not files:
    print("❌ No seed 5000 results found")
    exit(1)

data = json.load(open(files[0]))

print("="*80)
print("CV_SE_HEPG2_VEH ISLAND DIAGNOSIS")
print("="*80)
print()
print("Expected: HepG2 vehicle wells with ER~100-130, CV~8-12%")
print("Actual: mean ER=252, CV=161%")
print()

se_wells = ["K15","K16","K17","L15","L16","L17","M15","M16","M17"]
se_island = [r for r in data['flat_results'] if r['well_id'] in se_wells]

print(f"Wells in SE island (n={len(se_island)}):")
print()
print(f"{'Well':<6} {'ER':>8} {'Mito':>8} {'Nucleus':>8} {'Cell_line':<10} {'Compound':<12} {'Dose_uM':>8}")
print("-"*80)

for r in se_island:
    print(f"{r['well_id']:<6} {r['morph_er']:8.1f} {r['morph_mito']:8.1f} {r['morph_nucleus']:8.1f} "
          f"{r.get('cell_line','?'):<10} {r.get('compound','?'):<12} {r.get('dose_uM',0):8.2f}")

ers = [r['morph_er'] for r in se_island]
print()
print("="*80)
print("STATISTICS")
print("="*80)
print(f"ER range: {np.min(ers):.1f} - {np.max(ers):.1f}")
print(f"ER mean: {np.mean(ers):.1f}")
print(f"ER std: {np.std(ers):.1f}")
print(f"ER CV: {100*np.std(ers)/np.mean(ers):.1f}%")
print()

# Check if any wells are outliers
threshold = np.mean(ers) + 2*np.std(ers)
outliers = [r for r in se_island if r['morph_er'] > threshold]
if outliers:
    print("="*80)
    print(f"OUTLIERS (ER > {threshold:.1f}):")
    print("="*80)
    for r in outliers:
        print(f"  {r['well_id']}: ER={r['morph_er']:.1f}")
    print()

# Compare to NW island (should be similar since both HepG2 vehicle)
nw_wells = ["D4","D5","D6","E4","E5","E6","F4","F5","F6"]
nw_island = [r for r in data['flat_results'] if r['well_id'] in nw_wells]
nw_ers = [r['morph_er'] for r in nw_island]

print("="*80)
print("COMPARISON: NW vs SE (both HepG2 vehicle)")
print("="*80)
print(f"NW island (D4-F6): mean ER={np.mean(nw_ers):.1f}, CV={100*np.std(nw_ers)/np.mean(nw_ers):.1f}%")
print(f"SE island (K15-M17): mean ER={np.mean(ers):.1f}, CV={100*np.std(ers)/np.mean(ers):.1f}%")
print()
print(f"SE is {np.mean(ers)/np.mean(nw_ers):.1f}× higher than NW")
print()

if np.mean(ers) > 2 * np.mean(nw_ers):
    print("❌ SE island has massive inflation (>2×)")
    print()
    print("Possible causes:")
    print("  1. Edge effect multiplier too strong (K,L,M are near bottom edge)")
    print("  2. Spatial gradient (illumination, focus)")
    print("  3. Different treatment (check plate design)")
    print("  4. Stain/focus factor dominating")
