#!/usr/bin/env python3
"""
Scout oligomycin doses for Phase 2C.2 mito-dominant regime.

Oligomycin blocks ATP synthase → often more stable dose-response than
rotenone (complex I) or CCCP (protonophore uncoupler).

Same metrics as CCCP scout:
1. Commitment fraction (target: 30-70% in 120h)
2. Time-above-threshold (fraction above S_commit=0.60)
3. Stress stability (CV, lower is better)
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
        DataFrame with dose-level stats
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
        time_above = 0.0
        total_time = time_values[-1] - time_values[0]

        for i in range(len(time_values) - 1):
            dt = time_values[i + 1] - time_values[i]
            s1 = stress_values[i]
            s2 = stress_values[i + 1]

            if s1 >= threshold and s2 >= threshold:
                time_above += dt
            elif s1 >= threshold or s2 >= threshold:
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

    # Scout oligomycin doses
    # ec50_uM = 1.0, test range 0.1 to 10.0 µM (0.1× to 10× EC50)
    dose_range = (0.1, 10.0)
    n_doses = 12
    n_wells_per_dose = 4

    output_dir = str(project_root / "data" / "identifiability_scout_oligomycin")

    print("=" * 60)
    print("Oligomycin Dose Scout: Time-Above-Threshold Focus")
    print("=" * 60)
    print("Compound: oligomycin (ATP synthase inhibitor)")
    print(f"Dose range: {dose_range[0]:.1f}-{dose_range[1]:.1f} µM")
    print(f"Target: 30-70% commitment in 120h")
    print(f"Key metric: Time above S_commit=0.60 + stress CV")
    print()
    print("Hypothesis: Oligomycin should show lower CV than rotenone/CCCP")
    print("            (steadier ATP depletion vs. spiky ROS/uncoupling)")
    print()

    run_dir = run_dose_scout(
        config_path=config_path,
        output_dir=output_dir,
        compound="oligomycin",
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

    # Compare CV to CCCP
    print("\n" + "=" * 60)
    print("Stress Stability Assessment")
    print("=" * 60)

    commitment_doses = dose_stats[dose_stats['commitment_fraction'] > 0]
    if len(commitment_doses) > 0:
        median_cv = commitment_doses['stress_cv'].median()
        print(f"\nMedian CV at commitment-producing doses: {median_cv:.2f}")

        if median_cv < 0.5:
            print("✅ STABLE: CV < 0.5 (good for identifiability)")
        elif median_cv < 0.7:
            print("⚠️ MODERATE: CV 0.5-0.7 (acceptable but not ideal)")
        else:
            print("❌ UNSTABLE: CV > 0.7 (poor for identifiability)")
            print("   → Oligomycin not better than CCCP/rotenone")
    else:
        print("No commitment events to assess CV")

    # Suggest doses for identifiability suite
    print("\n" + "=" * 60)
    print("Dose Suggestions for Mito-Dominant Regime")
    print("=" * 60)

    # Find doses with 30-70% commitment AND low CV
    target_doses = dose_stats[
        (dose_stats['commitment_fraction'] >= 0.30) &
        (dose_stats['commitment_fraction'] <= 0.70) &
        (dose_stats['stress_cv'] < 0.7)  # Require reasonable stability
    ]

    if len(target_doses) >= 4:
        print(f"\n✅ {len(target_doses)} doses in target range (30-70% commit, CV<0.7):")
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
        print(f"\n⚠️ Only {len(target_doses)} doses meet criteria (30-70% commit + CV<0.7).")

        # Relax CV requirement
        relaxed_doses = dose_stats[
            (dose_stats['commitment_fraction'] >= 0.30) &
            (dose_stats['commitment_fraction'] <= 0.70)
        ]

        if len(relaxed_doses) >= 4:
            print(f"   {len(relaxed_doses)} doses meet commitment target (ignoring CV):")
            for _, row in relaxed_doses.iterrows():
                print(f"     {row['dose_uM']:.2f} µM (CV={row['stress_cv']:.2f})")
        else:
            print("\nNo suitable doses found. Consider:")
            print("  - Extending observation window (120h → 240h)")
            print("  - Raising mito baseline hazard further (0.40 → 0.60/h)")
            print("  - Accepting that mito is less identifiable than ER")

    print("\n" + "=" * 60)
    print(f"Full results: {run_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
