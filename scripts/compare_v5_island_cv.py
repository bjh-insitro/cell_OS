#!/usr/bin/env python3
"""
Compare V5 island CV to V4 baseline (calibration aspect test).

Question: Does V5's single-well alternating base hurt island purity?

Success criteria:
  - V5 island CV ≤ 20% (acceptable calibration performance)
  - V5 island CV within 50% of V4 baseline (13.3%)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

SEEDS = [42, 123, 456, 789, 1000]
RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V5 core island wells (role=core, excluding buffers)
V5_CORE_ISLANDS = {
    "CV_NW_HEPG2_VEH": ['N5','N6','N7','O5','O6','O7','P5','P6','P7'],
    "CV_NW_A549_VEH": ['B6','B7','B8','C6','C7','C8','D6','D7','D8'],
    "CV_NE_HEPG2_VEH": ['B17','B18','B19','C17','C18','C19','D17','D18','D19'],
    "CV_NE_A549_VEH": ['N18','N19','N20','O18','O19','O20','P18','P19','P20'],
    "CV_SW_HEPG2_MORPH": ['G5','G6','G7','H5','H6','H7','I5','I6','I7'],
    "CV_SW_A549_MORPH": ['C11','C12','C13','D11','D12','D13','E11','E12','E13'],
    "CV_SE_HEPG2_VEH": ['G18','G19','G20','H18','H19','H20','I18','I19','I20'],
    "CV_SE_A549_DEATH": ['K11','K12','K13','L11','L12','L13','M11','M12','M13'],
}

# V4 islands for comparison
V4_ISLANDS = {
    "CV_NW_HEPG2_VEH": ['D4','D5','D6','E4','E5','E6','F4','F5','F6'],
    "CV_NW_A549_VEH": ['D8','D9','D10','E8','E9','E10','F8','F9','F10'],
    "CV_NE_HEPG2_VEH": ['D15','D16','D17','E15','E16','E17','F15','F16','F17'],
    "CV_NE_A549_VEH": ['D20','D21','D22','E20','E21','E22','F20','F21','F22'],
    "CV_SW_HEPG2_MORPH": ['K4','K5','K6','L4','L5','L6','M4','M5','M6'],
    "CV_SW_A549_MORPH": ['K8','K9','K10','L8','L9','L10','M8','M9','M10'],
    "CV_SE_HEPG2_VEH": ['K15','K16','K17','L15','L16','L17','M15','M16','M17'],
    "CV_SE_A549_DEATH": ['K20','K21','K22','L20','L21','L22','M20','M21','M22'],
}


def calculate_cv(values):
    """Calculate coefficient of variation."""
    if len(values) == 0:
        return 0.0
    mean = np.mean(values)
    if mean == 0:
        return 0.0
    std = np.std(values, ddof=1)
    return (std / mean) * 100


def load_run(plate_id, seed):
    """Load run results."""
    pattern = f"{plate_id}_run_*_seed{seed}.json"
    files = list(RESULTS_DIR.glob(pattern))

    if not files:
        return None

    with open(files[0], 'r') as f:
        return json.load(f)


def analyze_island_cv(plate_id, island_wells_dict):
    """Analyze island CV across all seeds."""
    all_cvs = []

    for seed in SEEDS:
        data = load_run(plate_id, seed)
        if not data:
            continue

        flat_results = data['flat_results']

        # Calculate CV for each island
        for island_id, wells in island_wells_dict.items():
            island_data = [r for r in flat_results if r['well_id'] in wells]
            if len(island_data) == 0:
                continue

            # Use morph_er as representative channel
            values = [r['morph_er'] for r in island_data if 'morph_er' in r]
            if len(values) == 0:
                continue

            cv = calculate_cv(values)
            all_cvs.append(cv)

    return all_cvs


def main():
    print("="*80)
    print("V5 ISLAND CV VALIDATION")
    print("="*80)
    print()
    print("Question: Does V5's single-well alternating base hurt island purity?")
    print()

    # Analyze V4 baseline
    print("Analyzing V4 baseline...")
    v4_cvs = analyze_island_cv("CAL_384_RULES_WORLD_v4", V4_ISLANDS)
    v4_mean = np.mean(v4_cvs)
    v4_std = np.std(v4_cvs)

    print(f"  V4 island CV: {v4_mean:.1f}% ± {v4_std:.1f}% (n={len(v4_cvs)})")

    # Analyze V5
    print()
    print("Analyzing V5...")
    v5_cvs = analyze_island_cv("CAL_384_RULES_WORLD_v5", V5_CORE_ISLANDS)
    v5_mean = np.mean(v5_cvs)
    v5_std = np.std(v5_cvs)

    print(f"  V5 island CV: {v5_mean:.1f}% ± {v5_std:.1f}% (n={len(v5_cvs)})")

    # Calculate relative change
    relative_change = ((v5_mean - v4_mean) / v4_mean) * 100

    print()
    print("="*80)
    print("RESULTS")
    print("="*80)
    print()
    print(f"V4 baseline:  {v4_mean:.1f}% ± {v4_std:.1f}%")
    print(f"V5 result:    {v5_mean:.1f}% ± {v5_std:.1f}%")
    print(f"Relative change: {relative_change:+.1f}%")
    print()

    # Apply success criteria
    print("="*80)
    print("SUCCESS CRITERIA")
    print("="*80)
    print()

    # Test 1: Absolute threshold
    test1_pass = v5_mean <= 20.0
    print(f"Test 1: V5 CV ≤ 20%")
    print(f"  Result: {v5_mean:.1f}% - {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print()

    # Test 2: Relative to V4
    test2_pass = v5_mean <= v4_mean * 1.5
    print(f"Test 2: V5 CV within 50% of V4 ({v4_mean * 1.5:.1f}%)")
    print(f"  Result: {v5_mean:.1f}% - {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print()

    # Overall verdict
    print("="*80)
    print("VERDICT")
    print("="*80)
    print()

    if test1_pass and test2_pass:
        print("✅ V5 PASSES calibration aspect test")
        print()
        print("Interpretation:")
        print("  Single-well alternating base does NOT interfere with island purity.")
        print("  V5 maintains acceptable calibration performance.")
    elif test1_pass:
        print("⚠️  V5 MARGINAL: Passes absolute threshold but shows degradation")
        print()
        print("Interpretation:")
        print("  Island CV acceptable but higher than V4.")
        print(f"  {relative_change:+.1f}% increase suggests minor interference.")
    else:
        print("❌ V5 FAILS calibration aspect test")
        print()
        print("Interpretation:")
        print("  Single-well alternating base interferes with island purity.")
        print("  V5 not suitable for precision CV measurement.")
        print("  Recommendation: Use V4 for calibration work.")


if __name__ == "__main__":
    main()
