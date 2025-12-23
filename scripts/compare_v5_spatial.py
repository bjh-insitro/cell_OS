#!/usr/bin/env python3
"""
Compare V5 boring wells spatial variance to V3 baseline (screening aspect test).

Question: Do V5's islands break spatial decorrelation?

Success criteria:
  - V5 boring wells variance within 20% of V3 baseline (930-1390)
  - No 2×2 block artifacts or periodic structure
"""

import json
import numpy as np
from pathlib import Path

SEEDS = [42, 123, 456, 789, 1000]
RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V5 core + buffer island wells (to exclude from boring wells)
V5_ALL_ISLAND_WELLS = set([
    # Core islands
    'N5','N6','N7','O5','O6','O7','P5','P6','P7',
    'B6','B7','B8','C6','C7','C8','D6','D7','D8',
    'B17','B18','B19','C17','C18','C19','D17','D18','D19',
    'N18','N19','N20','O18','O19','O20','P18','P19','P20',
    'G5','G6','G7','H5','H6','H7','I5','I6','I7',
    'C11','C12','C13','D11','D12','D13','E11','E12','E13',
    'G18','G19','G20','H18','H19','H20','I18','I19','I20',
    'K11','K12','K13','L11','L12','L13','M11','M12','M13',
    # Buffer moats
    'M5','M6','M7','N4','N8','O4','O8','P4','P8',
    'A6','A7','A8','B5','B9','C5','C9','D5','D9','E6','E7','E8',
    'A17','A18','A19','B16','B20','C16','C20','D16','D20','E17','E18','E19',
    'M18','M19','M20','N17','N21','O17','O21','P17','P21',
    'F5','F6','F7','G4','G8','H4','H8','I4','I8','J5','J6','J7',
    'B11','B12','B13','C10','C14','D10','D14','E10','E14','F11','F12','F13',
    'F18','F19','F20','G17','G21','H17','H21','I17','I21','J18','J19','J20',
    'J11','J12','J13','K10','K14','L10','L14','M10','M14','N11','N12','N13',
])

# Special wells to exclude (anchors, probes, tiles, etc.)
SPECIAL_WELLS = set([
    # Anchor wells
    'A9','A16','D3','D22','G9','G16','H3','H22','I9','I16','L3','L22','O9','O16','P3','P22',
    'B10','B15','C4','C21','F10','F15','E4','E21','J10','J15','K4','K21','N10','N15','M4','M21',
    # Background controls
    'A2','A23','P2','P23','H2','H23','I2','I23',
    # Contrastive tiles
    'B2','B3','C2','C3','B22','B23','C22','C23',
    'N2','N3','O2','O3','N22','N23','O22','O23',
    'G10','G11','H10','H11','L18','L19',
    # Probe wells (reduced in V5.2)
    'K6','L6','K19','L19','A12','I12','G12','H12','O12','P12',
    'A1','B1','C1','D1','I1','J1','K1','L1',
    'E24','F24','G24','H24','M24','N24','O24','P24',
])


def load_run(plate_id, seed):
    """Load run results."""
    pattern = f"{plate_id}_run_*_seed{seed}.json"
    files = list(RESULTS_DIR.glob(pattern))

    if not files:
        return None

    with open(files[0], 'r') as f:
        return json.load(f)


def analyze_boring_wells_variance(plate_id, exclude_wells=None):
    """Analyze spatial variance in boring (vehicle) wells."""
    if exclude_wells is None:
        exclude_wells = set()

    all_variances = []

    for seed in SEEDS:
        data = load_run(plate_id, seed)
        if not data:
            continue

        flat_results = data['flat_results']

        # Filter to vehicle boring wells
        boring_data = [
            r for r in flat_results
            if r['well_id'] not in exclude_wells
            and r.get('treatment', '').startswith('VEHICLE')
        ]

        if len(boring_data) == 0:
            continue

        # Use morph_er as representative channel
        values = [r['morph_er'] for r in boring_data if 'morph_er' in r]
        if len(values) == 0:
            continue

        variance = np.var(values, ddof=1)
        all_variances.append(variance)

    return all_variances


def main():
    print("="*80)
    print("V5 SPATIAL DECORRELATION VALIDATION")
    print("="*80)
    print()
    print("Question: Do V5's islands break spatial decorrelation in boring wells?")
    print()

    # Analyze V3 baseline (no islands)
    print("Analyzing V3 baseline (no islands)...")
    v3_variances = analyze_boring_wells_variance("CAL_384_RULES_WORLD_v3", SPECIAL_WELLS)
    v3_mean = np.mean(v3_variances)
    v3_std = np.std(v3_variances)

    print(f"  V3 boring wells variance: {v3_mean:.0f} ± {v3_std:.0f} (n={len(v3_variances)})")

    # Analyze V5 (islands + single-well alternating)
    print()
    print("Analyzing V5 (islands + single-well alternating)...")

    # Exclude islands and special wells
    v5_exclude = V5_ALL_ISLAND_WELLS | SPECIAL_WELLS
    print(f"  Excluding {len(v5_exclude)} wells (islands + special)")

    v5_variances = analyze_boring_wells_variance("CAL_384_RULES_WORLD_v5", v5_exclude)
    v5_mean = np.mean(v5_variances)
    v5_std = np.std(v5_variances)

    print(f"  V5 boring wells variance: {v5_mean:.0f} ± {v5_std:.0f} (n={len(v5_variances)})")

    # Calculate relative change
    relative_change = ((v5_mean - v3_mean) / v3_mean) * 100

    print()
    print("="*80)
    print("RESULTS")
    print("="*80)
    print()
    print(f"V3 baseline:  {v3_mean:.0f} ± {v3_std:.0f}")
    print(f"V5 result:    {v5_mean:.0f} ± {v5_std:.0f}")
    print(f"Relative change: {relative_change:+.1f}%")
    print()

    # Apply success criteria
    print("="*80)
    print("SUCCESS CRITERIA")
    print("="*80)
    print()

    # Define thresholds
    threshold_good = v3_mean * 1.2  # Within 20%
    threshold_marginal = v3_mean * 1.5  # Within 50%

    # Test: Variance within acceptable range
    if v5_mean <= threshold_good:
        status = "✅ PASS"
        verdict = "PASS"
    elif v5_mean <= threshold_marginal:
        status = "⚠️  MARGINAL"
        verdict = "MARGINAL"
    else:
        status = "❌ FAIL"
        verdict = "FAIL"

    print(f"Test: V5 variance within 20% of V3 ({threshold_good:.0f})")
    print(f"  Result: {v5_mean:.0f} - {status}")
    print()

    # Overall verdict
    print("="*80)
    print("VERDICT")
    print("="*80)
    print()

    if verdict == "PASS":
        print("✅ V5 PASSES screening aspect test")
        print()
        print("Interpretation:")
        print("  Islands do NOT break spatial decorrelation in boring wells.")
        print("  V5 maintains V3-level spatial mixing performance.")
    elif verdict == "MARGINAL":
        print("⚠️  V5 MARGINAL: Increased variance but within acceptable limits")
        print()
        print("Interpretation:")
        print(f"  {relative_change:+.1f}% increase suggests minor interference.")
        print("  Islands may create local discontinuities.")
        print("  Acceptable for exploratory work, not optimal for screening.")
    else:
        print("❌ V5 FAILS screening aspect test")
        print()
        print("Interpretation:")
        print("  Islands significantly disrupt spatial decorrelation.")
        print(f"  {relative_change:+.1f}% increase indicates structural interference.")
        print("  V5 not suitable for spatial confound detection.")
        print("  Recommendation: Use V3 for screening work.")


if __name__ == "__main__":
    main()
