#!/usr/bin/env python3
"""
Scout CCCP doses for Phase 2C.2 mito-dominant regime.

Focus: **Time-above-threshold**, not just peak stress.

Key metrics:
1. Commitment fraction (target: 30-70% in 120h)
2. Time-above-threshold (fraction of observation window above S_commit=0.60)
3. Stress stability (std dev / mean, lower is better)

This addresses rotenone's problem: spiky stress (0.14-0.88) produces fewer events
than sustained elevation even if peaks are similar.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_runner import run_dose_scout


def analyze_time_above_threshold(scout_dir: Path, threshold: float = 0.60):
    """
    Analyze time-above-threshold for each dose.

    Args:
        scout_dir: Scout run directory
        threshold: Commitment threshold (default: 0.60)

    Returns:
        DataFrame with columns:
            - dose_uM
            - commitment_fraction
            - mean_time_above_pct (% of window above threshold)
            - mean_stress (mean stress across all timepoints)
            - stress_cv (coefficient of variation, std/mean)
    """
    observations = pd.read_csv(scout_dir / "observations.csv")
    events = pd.read_csv(scout_dir / "events.csv")

    # Filter to mito_dysfunction metric
    mito_obs = observations[observations['metric_name'] == 'mito_dysfunction'].copy()

    # Compute per-well stats
    well_stats = []

    for well_id in mito_obs['well_id'].unique():
        well_data = mito_obs[mito_obs['well_id'] == well_id].sort_values('time_h')

        if len(well_data) < 2:
            continue

        stress_values = well_data['value'].values
        time_values = well_data['time_h'].values
        dose_uM = well_data['dose_uM'].iloc[0]

        # Compute time above threshold (trapezoidal integration)
        # For each interval, if both endpoints are above threshold, count full interval
        # If one endpoint is above, count partial (linear interpolation)
        time_above = 0.0
        total_time = time_values[-1] - time_values[0]

        for i in range(len(time_values) - 1):
            dt = time_values[i + 1] - time_values[i]
            s1 = stress_values[i]
            s2 = stress_values[i + 1]

            if s1 >= threshold and s2 >= threshold:
                # Both above: full interval
                time_above += dt
            elif s1 >= threshold or s2 >= threshold:
                # One above: partial interval (linear interpolation)
                # Fraction above = average of (s1>threshold, s2>threshold)
                frac_above = ((s1 >= threshold) + (s2 >= threshold)) / 2.0
                time_above += dt * frac_above

        time_above_pct = 100.0 * (time_above / total_time) if total_time > 0 else 0.0

        # Stress statistics
        mean_stress = np.mean(stress_values)
        std_stress = np.std(stress_values)
        cv_stress = (std_stress / mean_stress) if mean_stress > 0 else 0.0

        # Commitment status
        well_event = events[events['well_id'] == well_id]
        committed = well_event['committed'].iloc[0] if len(well_event) > 0 else False

        well_stats.append({
            'well_id': well_id,
            'dose_uM': dose_uM,
            'committed': committed,
            'time_above_pct': time_above_pct,
            'mean_stress': mean_stress,
            'stress_cv': cv_stress,
        })

    well_df = pd.DataFrame(well_stats)

    # Aggregate by dose
    dose_stats = well_df.groupby('dose_uM').agg({
        'committed': ['sum', 'count'],
        'time_above_pct': 'mean',
        'mean_stress': 'mean',
        'stress_cv': 'mean',
    }).reset_index()

    dose_stats.columns = ['dose_uM', 'n_committed', 'n_wells',
                          'mean_time_above_pct', 'mean_stress', 'stress_cv']
    dose_stats['commitment_fraction'] = dose_stats['n_committed'] / dose_stats['n_wells']

    return dose_stats


def main():
    # Config path
    config_path = str(project_root / "configs" / "calibration" / "identifiability_2c2_cccp.yaml")

    # Scout CCCP doses
    # Test range: 0.5 to 15.0 µM (log-spaced)
    # ec50_uM = 5.0, so this spans 0.1× to 3× EC50
    dose_range = (0.5, 15.0)
    n_doses = 12
    n_wells_per_dose = 4

    output_dir = str(project_root / "data" / "identifiability_scout_cccp")

    print("=" * 60)
    print("CCCP Dose Scout: Time-Above-Threshold Focus")
    print("=" * 60)
    print(f"Dose range: {dose_range[0]:.1f}-{dose_range[1]:.1f} µM")
    print(f"Target: 30-70% commitment in 120h")
    print(f"Key metric: Time above S_commit=0.60 (not just peak stress)")
    print()

    run_dir = run_dose_scout(
        config_path=config_path,
        output_dir=output_dir,
        compound="CCCP",
        dose_range=dose_range,
        n_doses=n_doses,
        n_wells_per_dose=n_wells_per_dose
    )

    # Analyze time-above-threshold
    print("\n" + "=" * 60)
    print("Time-Above-Threshold Analysis")
    print("=" * 60)

    dose_stats = analyze_time_above_threshold(run_dir, threshold=0.60)

    print()
    print("| Dose (µM) | Commit % | Time >0.60 | Mean S | CV |")
    print("|-----------|----------|------------|--------|-----|")
    for _, row in dose_stats.iterrows():
        print(f"| {row['dose_uM']:8.2f} | {row['commitment_fraction']*100:7.1f}% | "
              f"{row['mean_time_above_pct']:9.1f}% | {row['mean_stress']:5.2f} | {row['stress_cv']:4.2f} |")

    # Save extended analysis
    analysis_path = run_dir / "time_above_threshold_analysis.csv"
    dose_stats.to_csv(analysis_path, index=False)
    print(f"\n✓ Saved: {analysis_path}")

    # Suggest doses for identifiability suite
    print("\n" + "=" * 60)
    print("Dose Suggestions for Mito-Dominant Regime")
    print("=" * 60)

    # Find doses with 30-70% commitment
    target_doses = dose_stats[
        (dose_stats['commitment_fraction'] >= 0.30) &
        (dose_stats['commitment_fraction'] <= 0.70)
    ]

    if len(target_doses) >= 4:
        print(f"\n✅ {len(target_doses)} doses in target range (30-70% commitment):")
        print()
        for _, row in target_doses.iterrows():
            print(f"  {row['dose_uM']:.2f} µM → {row['commitment_fraction']*100:.0f}% commit, "
                  f"{row['mean_time_above_pct']:.0f}% time >0.60, CV={row['stress_cv']:.2f}")

        # Pick 4 doses spanning the range
        selected_idx = np.linspace(0, len(target_doses) - 1, 4).astype(int)
        selected = target_doses.iloc[selected_idx]

        print("\n**Recommended 4-dose ladder:**")
        for _, row in selected.iterrows():
            print(f"  - {row['dose_uM']:.2f} µM")

    else:
        print(f"\n⚠️ Only {len(target_doses)} doses in target range.")
        print("Consider adjusting:")
        print("  - Mito baseline hazard (currently 0.40/h)")
        print("  - Observation window (currently 120h)")
        print("  - Dose range or density")

    # Flag if CCCP shows high CV (unstable like rotenone)
    high_cv_doses = dose_stats[dose_stats['stress_cv'] > 0.5]
    if len(high_cv_doses) > 0:
        print("\n⚠️ High stress variability (CV > 0.5) detected at:")
        for _, row in high_cv_doses.iterrows():
            print(f"  {row['dose_uM']:.2f} µM (CV={row['stress_cv']:.2f})")
        print("  → CCCP may be as spiky as rotenone")
        print("  → Consider oligomycin as alternative")

    print("\n" + "=" * 60)
    print(f"Full results: {run_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
