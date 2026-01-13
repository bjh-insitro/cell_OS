"""
Demo script for simulation realism profiles (v7).

Runs a small plate with three realism profiles:
- clean: No position effects, no outliers (existing baseline)
- realistic: Moderate position effects + 1% outliers
- hostile: Strong position effects + 3% outliers

Outputs CSV with per-well measurements for plotting.
"""

import argparse
import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def run_plate(profile: str, design: str = 'dmso_only', seed: int = 42) -> list[dict]:
    """
    Run a 96-well plate with specified realism profile.

    Plate design modes:
    - dmso_only: All wells DMSO, A549. Pure detector diagnostic (default).
    - single_condition: One compound+dose everywhere (e.g., all paclitaxel @ 1µM).
    - mixed_randomized: Multiple compounds, randomized across plate (biology uncorrelated with position).

    Args:
        profile: "clean", "realistic", or "hostile"
        design: "dmso_only", "single_condition", or "mixed_randomized"
        seed: Run seed for reproducibility

    Returns:
        List of well records with morphology + metadata
    """
    # Create run context with specified profile
    config = {
        'realism_profile': profile,
        'context_strength': 1.0,
    }
    run_ctx = RunContext.sample(seed=seed, config=config)

    # Create VM
    vm = BiologicalVirtualMachine(run_context=run_ctx)

    # Define all 96 wells
    all_rows = 'ABCDEFGH'
    all_wells = [f"{row}{col}" for row in all_rows for col in range(1, 13)]

    # Assign conditions based on design mode
    if design == 'dmso_only':
        # Every well is DMSO
        well_assignments = [('DMSO', 0.0) for _ in all_wells]

    elif design == 'single_condition':
        # Every well is paclitaxel @ 1µM (or pick your favorite)
        well_assignments = [('paclitaxel', 1.0) for _ in all_wells]

    elif design == 'mixed_randomized':
        # Define condition pool: 4 conditions × 24 wells each = 96 total
        condition_pool = (
            [('DMSO', 0.0)] * 24 +
            [('staurosporine', 1.0)] * 24 +
            [('staurosporine', 10.0)] * 24 +
            [('paclitaxel', 1.0)] * 24
        )
        # Shuffle with seed for deterministic randomization
        import random
        rng = random.Random(seed)
        rng.shuffle(condition_pool)
        well_assignments = condition_pool

    else:
        raise ValueError(f"Unknown design mode: {design}")

    # Seed all vessels and apply treatments
    for well_id, (compound, dose_uM) in zip(all_wells, well_assignments):
        # Seed vessel
        vm.seed_vessel(well_id, cell_line='A549', vessel_type='96-well')

        # Add compound treatment (skip DMSO)
        if compound != 'DMSO':
            vm.treat_with_compound(well_id, compound=compound, dose_uM=dose_uM)

    # Advance time globally (24h)
    vm.advance_time(hours=24.0)

    # Measure all vessels with Cell Painting
    well_records = []

    for well_id, (compound, dose_uM) in zip(all_wells, well_assignments):
        # Measure
        result = vm.cell_painting_assay(
            vessel_id=well_id,
            well_position=well_id,
            plate_id='demo_plate',
            batch_id=run_ctx.batch_id
        )

        # Parse row, col
        row_letter = well_id[0]
        row_idx = ord(row_letter) - ord('A')
        col_idx = int(well_id[1:]) - 1

        # Extract measurements
        morph = result['morphology']
        det_meta = result.get('detector_metadata', {})
        qc_flags = det_meta.get('qc_flags', {})

        # Build well record
        well_record = {
            'well_id': well_id,
            'row': row_idx,
            'col': col_idx,
            'row_letter': row_letter,
            'compound': compound,
            'dose_uM': dose_uM,
            'time_h': 24.0,
            'er': morph['er'],
            'mito': morph['mito'],
            'nucleus': morph['nucleus'],
            'actin': morph['actin'],
            'rna': morph['rna'],
            'batch_id': run_ctx.batch_id,
            'context_id': run_ctx.context_id,
            'profile': profile,
            'design': design,
            'is_outlier': qc_flags.get('is_outlier', False),
            'pathology_type': qc_flags.get('pathology_type', ''),
            'affected_channel': qc_flags.get('affected_channel', ''),
            'edge_distance': det_meta.get('edge_distance', 0.0),
            'exposure_multiplier': det_meta.get('exposure_multiplier', 1.0),
        }

        well_records.append(well_record)

    return well_records


def compute_plate_summary(well_records: list[dict], profile: str) -> dict:
    """
    Compute plate-level summary metrics.

    Returns dict with:
    - edge_sensitivity_per_channel: correlation of edge_distance with intensity (only for uniform designs)
    - edge_variance_ratio_per_channel: var(edge) / var(center)
    - channel_means_center/edge: raw means for validation
    - channel_std_center/edge: raw stds for validation
    - outlier_rate_observed
    - pathology_counts
    - design_is_uniform: whether edge_sensitivity is valid
    """
    import numpy as np
    from collections import Counter

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    # Check if design is uniform (required for edge_sensitivity to be a detector diagnostic)
    design = well_records[0]['design'] if well_records else 'unknown'
    design_is_uniform = design in {'dmso_only', 'single_condition'}

    # Extract arrays
    edge_distances = np.array([w['edge_distance'] for w in well_records])

    # Edge sensitivity: correlation(edge_distance, signal)
    # ONLY VALID for uniform designs (no biology confound)
    edge_sensitivity = {}
    if design_is_uniform:
        for ch in channels:
            vals = np.array([w[ch] for w in well_records])
            if len(vals) > 1 and np.std(vals) > 0 and np.std(edge_distances) > 0:
                edge_sensitivity[ch] = float(np.corrcoef(edge_distances, vals)[0, 1])
            else:
                edge_sensitivity[ch] = 0.0
    else:
        # Refuse to compute for mixed designs
        for ch in channels:
            edge_sensitivity[ch] = None

    # Edge variance ratio: var(edge) / var(center)
    edge_thresh = 0.8
    center_thresh = 0.2
    edge_wells = [w for w in well_records if w['edge_distance'] >= edge_thresh]
    center_wells = [w for w in well_records if w['edge_distance'] <= center_thresh]

    edge_variance_ratio = {}
    channel_means_center = {}
    channel_means_edge = {}
    channel_std_center = {}
    channel_std_edge = {}

    for ch in channels:
        if edge_wells and center_wells:
            edge_vals = [w[ch] for w in edge_wells]
            center_vals = [w[ch] for w in center_wells]

            # Compute variance ratio
            edge_var = np.var(edge_vals)
            center_var = np.var(center_vals)
            if center_var > 0:
                edge_variance_ratio[ch] = float(edge_var / center_var)
            else:
                edge_variance_ratio[ch] = 1.0

            # Store raw aggregates for validation
            channel_means_center[ch] = float(np.mean(center_vals))
            channel_means_edge[ch] = float(np.mean(edge_vals))
            channel_std_center[ch] = float(np.std(center_vals))
            channel_std_edge[ch] = float(np.std(edge_vals))
        else:
            edge_variance_ratio[ch] = 1.0
            channel_means_center[ch] = 0.0
            channel_means_edge[ch] = 0.0
            channel_std_center[ch] = 0.0
            channel_std_edge[ch] = 0.0

    # Outlier stats
    outliers = [w for w in well_records if w['is_outlier']]
    outlier_rate = len(outliers) / len(well_records) if well_records else 0.0
    pathology_counts = dict(Counter(w['pathology_type'] for w in outliers))

    # Get metadata from first record
    batch_id = well_records[0]['batch_id'] if well_records else ''
    context_id = well_records[0]['context_id'] if well_records else ''

    return {
        'profile': profile,
        'design': design,
        'design_is_uniform': design_is_uniform,
        'n_wells': len(well_records),
        'n_edge_wells': len(edge_wells),
        'n_center_wells': len(center_wells),
        'batch_id': batch_id,
        'context_id': context_id,
        'edge_sensitivity_per_channel': edge_sensitivity,
        'edge_variance_ratio_per_channel': edge_variance_ratio,
        'channel_means_center': channel_means_center,
        'channel_means_edge': channel_means_edge,
        'channel_std_center': channel_std_center,
        'channel_std_edge': channel_std_edge,
        'outlier_rate_observed': float(outlier_rate),
        'outlier_counts_by_pathology': pathology_counts,
        'edge_threshold': edge_thresh,
        'center_threshold': center_thresh,
    }


def print_summary(well_records: list[dict], profile: str):
    """Print summary statistics for the plate."""
    import numpy as np

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    print(f"\n{'='*60}")
    print(f"Profile: {profile.upper()}")
    print(f"{'='*60}")
    print(f"Total wells: {len(well_records)}")

    # Overall channel means
    print(f"\nChannel means:")
    for ch in channels:
        vals = [w[ch] for w in well_records]
        print(f"  {ch:8s}: {np.mean(vals):6.2f} ± {np.std(vals):5.2f}")

    # Edge vs center analysis
    edge_wells = [w for w in well_records if w['edge_distance'] > 0.7]
    center_wells = [w for w in well_records if w['edge_distance'] < 0.3]

    if edge_wells and center_wells:
        print(f"\nEdge vs Center (n_edge={len(edge_wells)}, n_center={len(center_wells)}):")
        for ch in channels:
            edge_vals = [w[ch] for w in edge_wells]
            center_vals = [w[ch] for w in center_wells]
            edge_mean = np.mean(edge_vals)
            center_mean = np.mean(center_vals)
            delta_pct = 100 * (edge_mean - center_mean) / center_mean
            print(f"  {ch:8s}: edge={edge_mean:6.2f}, center={center_mean:6.2f}, delta={delta_pct:+5.1f}%")

    # Outlier stats
    outliers = [w for w in well_records if w['is_outlier']]
    print(f"\nOutliers: {len(outliers)} / {len(well_records)} ({100*len(outliers)/len(well_records):.2f}%)")
    if outliers:
        from collections import Counter
        pathology_counts = Counter(w['pathology_type'] for w in outliers)
        for ptype, count in pathology_counts.items():
            print(f"  {ptype}: {count}")

    # Compute and print plate-level metrics
    summary = compute_plate_summary(well_records, profile)

    # Edge sensitivity (only for uniform designs)
    if summary['design_is_uniform']:
        print(f"\nEdge sensitivity (correlation with edge_distance):")
        for ch in channels:
            print(f"  {ch:8s}: {summary['edge_sensitivity_per_channel'][ch]:+6.3f}")
    else:
        print(f"\nEdge sensitivity: SKIPPED (design={summary['design']}, not uniform)")
        print(f"  → edge_sensitivity is only valid for dmso_only or single_condition designs")
        print(f"  → mixed_randomized confounds biology with position")

    print(f"\nEdge variance ratio (edge/center):")
    for ch in channels:
        print(f"  {ch:8s}: {summary['edge_variance_ratio_per_channel'][ch]:6.3f}×")


def plot_edge_diagnostics(well_records: list[dict], output_dir: str, profile: str):
    """
    Plot edge distance vs signal diagnostics (optional, requires matplotlib).

    Creates two plots:
    1. Edge distance vs mean intensity (binned)
    2. Edge distance vs std intensity (binned)
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nWarning: matplotlib not available, skipping plots")
        return

    import numpy as np
    from pathlib import Path

    # Create output directory
    plot_dir = Path(output_dir) / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']  # ColorBrewer Set1

    # Extract data
    edge_distances = np.array([w['edge_distance'] for w in well_records])

    # Bin edge distances (10 bins from 0 to 1)
    n_bins = 10
    bins = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    # Plot 1: Edge distance vs mean intensity
    fig, ax = plt.subplots(figsize=(8, 6))

    for ch, color in zip(channels, colors):
        vals = np.array([w[ch] for w in well_records])

        # Compute mean per bin
        bin_means = []
        for i in range(n_bins):
            mask = (edge_distances >= bins[i]) & (edge_distances < bins[i+1])
            if np.sum(mask) > 0:
                bin_means.append(np.mean(vals[mask]))
            else:
                bin_means.append(np.nan)

        ax.plot(bin_centers, bin_means, 'o-', label=ch, color=color, linewidth=2, markersize=6)

    ax.set_xlabel('Edge Distance (0 = center, 1 = corner)', fontsize=12)
    ax.set_ylabel('Mean Intensity (AU)', fontsize=12)
    ax.set_title(f'Edge Effect on Mean Signal ({profile.capitalize()} Profile)', fontsize=14, fontweight='bold')
    ax.legend(loc='best', frameon=True)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = plot_dir / f"{profile}_edge_vs_mean.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Saved: {out_path}")

    # Plot 2: Edge distance vs std intensity
    fig, ax = plt.subplots(figsize=(8, 6))

    for ch, color in zip(channels, colors):
        vals = np.array([w[ch] for w in well_records])

        # Compute std per bin
        bin_stds = []
        for i in range(n_bins):
            mask = (edge_distances >= bins[i]) & (edge_distances < bins[i+1])
            if np.sum(mask) > 1:  # Need at least 2 points for std
                bin_stds.append(np.std(vals[mask]))
            else:
                bin_stds.append(np.nan)

        ax.plot(bin_centers, bin_stds, 'o-', label=ch, color=color, linewidth=2, markersize=6)

    ax.set_xlabel('Edge Distance (0 = center, 1 = corner)', fontsize=12)
    ax.set_ylabel('Std Intensity (AU)', fontsize=12)
    ax.set_title(f'Edge Effect on Variance ({profile.capitalize()} Profile)', fontsize=14, fontweight='bold')
    ax.legend(loc='best', frameon=True)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = plot_dir / f"{profile}_edge_vs_std.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Demo realism profiles for Cell Painting")
    parser.add_argument(
        '--profile',
        type=str,
        choices=['clean', 'realistic', 'hostile'],
        default='realistic',
        help='Realism profile to run'
    )
    parser.add_argument(
        '--design',
        type=str,
        choices=['dmso_only', 'single_condition', 'mixed_randomized'],
        default='dmso_only',
        help='Plate design mode (default: dmso_only for clean detector diagnostics)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for CSV and plots (default: print summary only)'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate diagnostic plots (requires matplotlib)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    print(f"Running {args.profile} profile with {args.design} design (seed={args.seed})...")
    well_records = run_plate(profile=args.profile, design=args.design, seed=args.seed)

    # Print summary
    print_summary(well_records, args.profile)

    # Write outputs if requested
    if args.output:
        from pathlib import Path
        import json

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write CSV
        csv_path = output_dir / f"{args.profile}_{args.design}_wells.csv"
        fieldnames = [
            'well_id', 'row', 'col', 'row_letter', 'compound', 'dose_uM', 'time_h',
            'er', 'mito', 'nucleus', 'actin', 'rna',
            'batch_id', 'context_id', 'profile', 'design',
            'is_outlier', 'pathology_type', 'affected_channel',
            'edge_distance', 'exposure_multiplier'
        ]

        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(well_records)

        print(f"\nWrote {len(well_records)} wells to {csv_path}")

        # Write summary JSON (plate-level metrics)
        summary = compute_plate_summary(well_records, args.profile)
        summary['seed'] = args.seed
        summary_path = output_dir / f"{args.profile}_{args.design}_summary.json"

        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"Wrote plate summary to {summary_path}")

        # Generate plots if requested
        if args.plot:
            print("\nGenerating diagnostic plots...")
            plot_edge_diagnostics(well_records, str(output_dir), args.profile)


if __name__ == '__main__':
    main()
