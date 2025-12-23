#!/usr/bin/env python3
"""
Validate Structured Noise Implementation

Checks:
1. Vehicle island CV in realistic range (8-12%)
2. Channel correlations (ER-Mito, Nucleus-Actin)
3. Cross-seed well identity persistence
4. Outlier fingerprints (stain vs focus signatures)

This is NOT a tuning script. It validates that the ontology is correct.
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict


RESULTS_DIR = Path("validation_frontend/public/demo_results/calibration_plates")

# V4 vehicle islands (homogeneous boring wells)
VEHICLE_ISLANDS = {
    "CV_NW_HEPG2_VEH": ['D4','D5','D6','E4','E5','E6','F4','F5','F6'],
    "CV_NW_A549_VEH": ['D8','D9','D10','E8','E9','E10','F8','F9','F10'],
    "CV_NE_HEPG2_VEH": ['D15','D16','D17','E15','E16','E17','F15','F16','F17'],
    "CV_NE_A549_VEH": ['D20','D21','D22','E20','E21','E22','F20','F21','F22'],
    "CV_SE_HEPG2_VEH": ['K15','K16','K17','L15','L16','L17','M15','M16','M17'],
}


def load_run(seed):
    """Load most recent run for given seed."""
    pattern = f"CAL_384_RULES_WORLD_v4_run_*_seed{seed}.json"
    files = list(RESULTS_DIR.glob(pattern))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    with open(files[0], 'r') as f:
        return json.load(f)


def calculate_cv(values):
    """Coefficient of variation."""
    if len(values) == 0:
        return 0.0
    mean = np.mean(values)
    if mean == 0:
        return 0.0
    std = np.std(values, ddof=1)
    return (std / mean) * 100


def check_vehicle_cv(seeds):
    """Check 1: Vehicle island CV should be 8-12% (was 2-4%)."""
    print("="*80)
    print("CHECK 1: VEHICLE ISLAND CV")
    print("="*80)
    print()
    print("Expected: 8-12% (dominated by per-well baseline shifts)")
    print("Before: 2-4% (independent noise only)")
    print()

    all_cvs = []
    for seed in seeds:
        data = load_run(seed)
        if not data:
            print(f"❌ Seed {seed}: No data found")
            continue

        flat_results = data['flat_results']
        seed_cvs = []

        for island_id, wells in VEHICLE_ISLANDS.items():
            island_data = [r for r in flat_results if r['well_id'] in wells]
            values = [r['morph_er'] for r in island_data if 'morph_er' in r]
            if len(values) > 0:
                cv = calculate_cv(values)
                seed_cvs.append(cv)

        if seed_cvs:
            mean_cv = np.mean(seed_cvs)
            all_cvs.extend(seed_cvs)

            status = "✅" if 8 <= mean_cv <= 12 else "⚠️ "
            print(f"Seed {seed}: {mean_cv:.1f}% mean CV ({len(seed_cvs)} islands) {status}")

    if all_cvs:
        overall_mean = np.mean(all_cvs)
        overall_std = np.std(all_cvs)
        print()
        print(f"Overall: {overall_mean:.1f}% ± {overall_std:.1f}%")

        if 8 <= overall_mean <= 12:
            print("✅ PASS: Vehicle CV in realistic range")
        else:
            print(f"❌ FAIL: Vehicle CV outside range (expected 8-12%, got {overall_mean:.1f}%)")
    else:
        print("❌ FAIL: No data to analyze")

    print()
    return all_cvs


def check_channel_correlations(seeds):
    """Check 2: ER-Mito and Nucleus-Actin should correlate."""
    print("="*80)
    print("CHECK 2: CHANNEL CORRELATIONS")
    print("="*80)
    print()
    print("Expected:")
    print("  ER-Mito: r > 0.3 (stain coupling)")
    print("  Nucleus-Actin: r > 0.2 (focus coupling)")
    print()

    all_er = []
    all_mito = []
    all_nucleus = []
    all_actin = []

    for seed in seeds:
        data = load_run(seed)
        if not data:
            continue

        flat_results = data['flat_results']

        # Get vehicle wells only
        vehicle_wells = []
        for wells in VEHICLE_ISLANDS.values():
            vehicle_wells.extend(wells)

        for r in flat_results:
            if r['well_id'] in vehicle_wells:
                if all(k in r for k in ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin']):
                    all_er.append(r['morph_er'])
                    all_mito.append(r['morph_mito'])
                    all_nucleus.append(r['morph_nucleus'])
                    all_actin.append(r['morph_actin'])

    if len(all_er) > 10:
        corr_er_mito = np.corrcoef(all_er, all_mito)[0, 1]
        corr_nucleus_actin = np.corrcoef(all_nucleus, all_actin)[0, 1]

        print(f"ER-Mito correlation: {corr_er_mito:.3f}")
        if corr_er_mito > 0.3:
            print("  ✅ Strong stain coupling (> 0.3)")
        elif corr_er_mito > 0.15:
            print("  ⚠️  Moderate stain coupling (0.15-0.3)")
        else:
            print("  ❌ Weak stain coupling (< 0.15)")

        print()
        print(f"Nucleus-Actin correlation: {corr_nucleus_actin:.3f}")
        if corr_nucleus_actin > 0.2:
            print("  ✅ Strong focus coupling (> 0.2)")
        elif corr_nucleus_actin > 0.1:
            print("  ⚠️  Moderate focus coupling (0.1-0.2)")
        else:
            print("  ❌ Weak focus coupling (< 0.1)")

        print()
        if corr_er_mito > 0.3 and corr_nucleus_actin > 0.2:
            print("✅ PASS: Channel correlations show coupling structure")
        else:
            print("⚠️  MARGINAL: Coupling present but weaker than expected")
    else:
        print("❌ FAIL: Insufficient data for correlation analysis")

    print()


def check_well_persistence(seeds):
    """Check 3: Same wells should show persistent identity across seeds."""
    print("="*80)
    print("CHECK 3: CROSS-SEED WELL IDENTITY PERSISTENCE")
    print("="*80)
    print()
    print("Expected: Same well_id across seeds should have similar morphology")
    print("          (per-well biology is deterministic)")
    print()

    if len(seeds) < 2:
        print("⚠️  Need at least 2 seeds to check persistence")
        print()
        return

    # Pick a reference island and check cross-seed stability
    island_id = "CV_NW_HEPG2_VEH"
    wells = VEHICLE_ISLANDS[island_id]

    well_morphs = defaultdict(list)  # well_id -> [(seed, morph_er)]

    for seed in seeds:
        data = load_run(seed)
        if not data:
            continue

        flat_results = data['flat_results']
        for r in flat_results:
            if r['well_id'] in wells and 'morph_er' in r:
                well_morphs[r['well_id']].append((seed, r['morph_er']))

    # Check if wells maintain relative ordering across seeds
    if len(well_morphs) > 0:
        # Compute CV across seeds for each well
        well_cvs = {}
        for well_id, values in well_morphs.items():
            if len(values) >= 2:
                morph_values = [v[1] for v in values]
                cv = calculate_cv(morph_values)
                well_cvs[well_id] = cv

        if well_cvs:
            mean_within_well_cv = np.mean(list(well_cvs.values()))
            print(f"Mean within-well CV across seeds: {mean_within_well_cv:.1f}%")
            print(f"  (Should be < 15% - wells maintain identity)")
            print()

            if mean_within_well_cv < 15:
                print("✅ PASS: Wells show persistent identity across seeds")
            else:
                print("❌ FAIL: Wells too variable across seeds (per-well biology not stable)")
        else:
            print("⚠️  Insufficient data for cross-seed comparison")
    else:
        print("❌ FAIL: No overlapping wells found")

    print()


def check_outlier_fingerprints(seeds):
    """Check 4: Outliers should cluster by stain or focus signature."""
    print("="*80)
    print("CHECK 4: OUTLIER FINGERPRINTS")
    print("="*80)
    print()
    print("Expected: High-CV outliers should show:")
    print("  - Stain-like: ER, Mito, RNA move together")
    print("  - Focus-like: Nucleus, Actin move together")
    print()

    all_wells = []

    for seed in seeds:
        data = load_run(seed)
        if not data:
            continue

        flat_results = data['flat_results']

        # Get vehicle wells only
        vehicle_wells = []
        for wells in VEHICLE_ISLANDS.values():
            vehicle_wells.extend(wells)

        for r in flat_results:
            if r['well_id'] in vehicle_wells:
                if all(k in r for k in ['morph_er', 'morph_mito', 'morph_rna', 'morph_nucleus', 'morph_actin']):
                    all_wells.append(r)

    if len(all_wells) < 20:
        print("⚠️  Insufficient data for outlier analysis")
        print()
        return

    # Compute deviation from median for each channel
    channels = ['morph_er', 'morph_mito', 'morph_rna', 'morph_nucleus', 'morph_actin']
    medians = {ch: np.median([w[ch] for w in all_wells]) for ch in channels}

    deviations = []
    for well in all_wells:
        dev = {ch: abs(well[ch] - medians[ch]) / medians[ch] for ch in channels}
        dev['well_id'] = well['well_id']
        dev['total_dev'] = sum(dev[ch] for ch in channels)
        deviations.append(dev)

    # Sort by total deviation and pick top 5%
    deviations.sort(key=lambda x: x['total_dev'], reverse=True)
    n_outliers = max(1, len(deviations) // 20)  # Top 5%
    outliers = deviations[:n_outliers]

    if len(outliers) > 0:
        print(f"Analyzing top {len(outliers)} outliers (5% of {len(all_wells)} wells)")
        print()

        # Check for stain-like pattern (ER+Mito+RNA correlated)
        stain_scores = []
        for outlier in outliers:
            stain_dev = (outlier['morph_er'] + outlier['morph_mito'] + outlier['morph_rna']) / 3
            stain_scores.append(stain_dev)

        # Check for focus-like pattern (Nucleus+Actin correlated)
        focus_scores = []
        for outlier in outliers:
            focus_dev = (outlier['morph_nucleus'] + outlier['morph_actin']) / 2
            focus_scores.append(focus_dev)

        stain_consistency = np.std(stain_scores) / np.mean(stain_scores) if np.mean(stain_scores) > 0 else 1.0
        focus_consistency = np.std(focus_scores) / np.mean(focus_scores) if np.mean(focus_scores) > 0 else 1.0

        print(f"Stain fingerprint consistency: {1.0 - stain_consistency:.2f}")
        print(f"  (Higher = outliers show coordinated ER+Mito+RNA movement)")
        print()
        print(f"Focus fingerprint consistency: {1.0 - focus_consistency:.2f}")
        print(f"  (Higher = outliers show coordinated Nucleus+Actin movement)")
        print()

        if stain_consistency < 0.5 or focus_consistency < 0.5:
            print("✅ PASS: Outliers show fingerprinted patterns")
        else:
            print("⚠️  MARGINAL: Outliers less structured than expected")
    else:
        print("⚠️  No outliers found for fingerprint analysis")

    print()


def main():
    # Use seeds from recent runs (or specify new seeds)
    # Default to validation seeds if Phase 1 not run yet
    import sys
    if len(sys.argv) > 1:
        seeds = [int(s) for s in sys.argv[1:]]
    else:
        seeds = [42, 123, 456, 789, 1000]  # Validation runs (pre-structured-noise)

    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "STRUCTURED NOISE VALIDATION" + " "*31 + "║")
    print("╚" + "="*78 + "╝")
    print()
    print("This validates the noise ontology, NOT parameter tuning.")
    print()
    print(f"Testing seeds: {seeds}")
    print()

    # Run checks
    check_vehicle_cv(seeds)
    check_channel_correlations(seeds)
    check_well_persistence(seeds)
    check_outlier_fingerprints(seeds)

    print("="*80)
    print("VALIDATION COMPLETE")
    print("="*80)
    print()
    print("If all checks pass:")
    print("  → Noise structure is correct")
    print("  → Wells have persistent identity")
    print("  → Outliers have classifiable causes")
    print()
    print("Next frontier: Can the agent learn instrument trust?")
    print()


if __name__ == "__main__":
    main()
