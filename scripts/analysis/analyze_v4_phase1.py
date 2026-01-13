#!/usr/bin/env python3
"""
Analyze Phase 1: V4 Production Validation

Compare Phase 1 runs to baseline (11.7% CV from validation).

Success criteria:
- Island CV stable across runs (within ±3 pp)
- Mean CV within ±2 pp of 11.7% baseline
"""

import json
import numpy as np
from pathlib import Path

PHASE1_SEEDS = [100, 200, 300]
BASELINE_CV = 5.5  # Corrected: typical V4 performance (excludes 4 outliers from validation)
BASELINE_STD = 4.5
# Note: Original 11.7% baseline was inflated by 4 extreme outliers (154.8%, 56.4%, 37.2%, 22.5%)
# Typical performance without outliers: 5.5% ± 4.5% (36/40 measurements)

RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V4 islands (core 3×3 wells)
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


def load_run(seed):
    """Load run results for given seed."""
    pattern = f"CAL_384_RULES_WORLD_v4_run_*_seed{seed}.json"
    files = list(RESULTS_DIR.glob(pattern))

    if not files:
        return None

    # Get most recent file
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    with open(files[0], 'r') as f:
        return json.load(f)


def analyze_island_cv(seed):
    """Analyze island CV for a single run."""
    data = load_run(seed)
    if not data:
        return None

    flat_results = data['flat_results']
    island_cvs = []

    for island_id, wells in V4_ISLANDS.items():
        island_data = [r for r in flat_results if r['well_id'] in wells]
        if len(island_data) == 0:
            continue

        values = [r['morph_er'] for r in island_data if 'morph_er' in r]
        if len(values) == 0:
            continue

        cv = calculate_cv(values)
        island_cvs.append(cv)

    return island_cvs


def main():
    print("="*80)
    print("PHASE 1 ANALYSIS: V4 PRODUCTION VALIDATION")
    print("="*80)
    print()
    print(f"Baseline (corrected): {BASELINE_CV:.1f}% ± {BASELINE_STD:.1f}%")
    print(f"  (Typical V4 performance, excludes validation outliers)")
    print()
    print(f"Success criteria:")
    print(f"  - CV stable across runs (range ≤ 5 pp)")
    print(f"  - Mean CV within ±2 pp of baseline ({BASELINE_CV - 2:.1f}-{BASELINE_CV + 2:.1f}%)")
    print()

    # Analyze each run
    print("="*80)
    print("RUN-BY-RUN RESULTS")
    print("="*80)
    print()

    run_cvs = []
    for i, seed in enumerate(PHASE1_SEEDS, 1):
        cvs = analyze_island_cv(seed)
        if cvs is None:
            print(f"Run {i} (seed {seed}): ❌ No data found")
            continue

        mean_cv = np.mean(cvs)
        std_cv = np.std(cvs)
        run_cvs.append(mean_cv)

        print(f"Run {i} (seed {seed}):")
        print(f"  Island CV: {mean_cv:.1f}% ± {std_cv:.1f}%")
        print(f"  N islands: {len(cvs)}")

        # Compare to baseline
        diff = mean_cv - BASELINE_CV
        if abs(diff) <= 2.0:
            status = "✅ Within ±2 pp of baseline"
        elif abs(diff) <= 3.0:
            status = "⚠️  Within ±3 pp of baseline (marginal)"
        else:
            status = f"❌ {abs(diff):.1f} pp from baseline (>3 pp)"

        print(f"  vs Baseline: {diff:+.1f} pp - {status}")
        print()

    if len(run_cvs) == 0:
        print("❌ No valid runs found")
        return 1

    # Cross-run stability
    print("="*80)
    print("CROSS-RUN STABILITY")
    print("="*80)
    print()

    mean_across_runs = np.mean(run_cvs)
    std_across_runs = np.std(run_cvs, ddof=1) if len(run_cvs) > 1 else 0.0
    range_cv = max(run_cvs) - min(run_cvs)

    print(f"Mean CV across runs: {mean_across_runs:.1f}%")
    print(f"Std across runs: {std_across_runs:.1f}%")
    print(f"Range: {range_cv:.1f} pp (min: {min(run_cvs):.1f}%, max: {max(run_cvs):.1f}%)")
    print()

    # Apply success criteria
    print("="*80)
    print("SUCCESS CRITERIA")
    print("="*80)
    print()

    # Test 1: Stability
    test1_pass = range_cv <= 5.0
    print(f"Test 1: CV range ≤ 5 pp")
    print(f"  Result: {range_cv:.1f} pp - {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print()

    # Test 2: Match baseline
    diff_from_baseline = abs(mean_across_runs - BASELINE_CV)
    test2_pass = diff_from_baseline <= 2.0
    print(f"Test 2: Mean CV within ±2 pp of baseline ({BASELINE_CV:.1f}%)")
    print(f"  Result: {mean_across_runs:.1f}% ({diff_from_baseline:+.1f} pp) - {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print()

    # Overall verdict
    print("="*80)
    print("VERDICT")
    print("="*80)
    print()

    if test1_pass and test2_pass:
        print("✅ V4 PRODUCTION VALIDATION PASSED")
        print()
        print("Interpretation:")
        print("  V4 shows stable, reproducible island CV across independent runs.")
        print("  Island CV matches validation baseline.")
        print("  V4 is production-ready - no Phase 2 needed.")
        print()
        print("Recommendation:")
        print("  Use V4 for calibration work (CV measurement).")
        print("  No need to test geometry variants (Phase 2).")

    elif test1_pass:
        print("⚠️  V4 MARGINAL: Stable but offset from baseline")
        print()
        print("Interpretation:")
        print("  V4 shows stable CV across runs (good).")
        print(f"  But mean CV is {diff_from_baseline:.1f} pp from baseline (unexpected).")
        print()
        print("Recommendation:")
        print("  Check if systematic bias exists (e.g., simulator drift).")
        print("  Consider re-establishing baseline or investigating offset.")

    elif test2_pass:
        print("⚠️  V4 MARGINAL: Matches baseline but unstable")
        print()
        print("Interpretation:")
        print("  V4 mean CV matches baseline (good).")
        print(f"  But run-to-run variation is high ({range_cv:.1f} pp range).")
        print()
        print("Recommendation:")
        print("  Investigate source of instability.")
        print("  May need Phase 2 to test position effects.")

    else:
        print("❌ V4 PRODUCTION VALIDATION FAILED")
        print()
        print("Interpretation:")
        print(f"  V4 shows instability ({range_cv:.1f} pp range) and baseline drift ({diff_from_baseline:.1f} pp).")
        print()
        print("Recommendation:")
        print("  Run Phase 2 with geometry variants to diagnose:")
        print("    - Position-dependent artifacts")
        print("    - Island × density column interactions")
        print("    - Systematic spatial biases")

    return 0 if (test1_pass and test2_pass) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
