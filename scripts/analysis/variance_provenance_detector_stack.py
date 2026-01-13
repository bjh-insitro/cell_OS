"""
Variance provenance decomposition for detector realism stack.

Runs counterfactual measurements with layer toggles to decompose variance
into components: geometry, noise, pathology, residual.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.analysis.variance_provenance import (
    load_wells_csv,
    compute_deltas,
    compute_variance_budget,
    save_deltas_csv,
    save_variance_budget_csv,
    CHANNELS
)

import numpy as np


def create_counterfactual_configs(base_profile: str) -> dict:
    """
    Create counterfactual realism configs for layer decomposition.

    Returns dict with keys: 'bio', 'geo', 'noise', 'path', 'obs'
    - bio: all layers off (baseline)
    - geo: only position/geometry effects on
    - noise: only edge noise inflation on
    - path: only QC pathologies on
    - obs: all layers on (observed, from base_profile)
    """
    # Get full profile config
    if base_profile == "realistic":
        obs_config = {
            'position_row_bias_pct': 2.0,
            'position_col_bias_pct': 2.0,
            'edge_mean_shift_pct': -5.0,
            'edge_noise_multiplier': 2.0,
            'outlier_rate': 0.01,
            'batch_effect_strength': 1.0,
        }
    elif base_profile == "hostile":
        obs_config = {
            'position_row_bias_pct': 3.0,
            'position_col_bias_pct': 3.0,
            'edge_mean_shift_pct': -7.0,
            'edge_noise_multiplier': 2.5,
            'outlier_rate': 0.03,
            'batch_effect_strength': 1.5,
        }
    else:  # clean or unknown
        obs_config = {
            'position_row_bias_pct': 0.0,
            'position_col_bias_pct': 0.0,
            'edge_mean_shift_pct': 0.0,
            'edge_noise_multiplier': 1.0,
            'outlier_rate': 0.0,
            'batch_effect_strength': 1.0,
        }

    # Biology-only: all layers off
    bio_config = {
        'position_row_bias_pct': 0.0,
        'position_col_bias_pct': 0.0,
        'edge_mean_shift_pct': 0.0,
        'edge_noise_multiplier': 1.0,
        'outlier_rate': 0.0,
        'batch_effect_strength': 1.0,
    }

    # Geometry-only: position effects on
    geo_config = {
        'position_row_bias_pct': obs_config['position_row_bias_pct'],
        'position_col_bias_pct': obs_config['position_col_bias_pct'],
        'edge_mean_shift_pct': obs_config['edge_mean_shift_pct'],
        'edge_noise_multiplier': 1.0,  # OFF
        'outlier_rate': 0.0,  # OFF
        'batch_effect_strength': 1.0,
    }

    # Noise-only: edge noise inflation on
    noise_config = {
        'position_row_bias_pct': 0.0,  # OFF
        'position_col_bias_pct': 0.0,  # OFF
        'edge_mean_shift_pct': 0.0,  # OFF
        'edge_noise_multiplier': obs_config['edge_noise_multiplier'],
        'outlier_rate': 0.0,  # OFF
        'batch_effect_strength': 1.0,
    }

    # Pathology-only: QC pathologies on
    path_config = {
        'position_row_bias_pct': 0.0,  # OFF
        'position_col_bias_pct': 0.0,  # OFF
        'edge_mean_shift_pct': 0.0,  # OFF
        'edge_noise_multiplier': 1.0,  # OFF
        'outlier_rate': obs_config['outlier_rate'],
        'batch_effect_strength': 1.0,
    }

    return {
        'bio': bio_config,
        'geo': geo_config,
        'noise': noise_config,
        'path': path_config,
        'obs': obs_config,
    }


def run_plate_with_config_override(
    profile: str,
    seed: int,
    realism_config_override: dict,
    plate_format: int = 96,
    small_mode: bool = False
) -> list[dict]:
    """
    Run a DMSO-only plate with realism_config override.

    Args:
        profile: Profile name (for context, but overridden by realism_config_override)
        seed: Run seed for reproducibility
        realism_config_override: Counterfactual realism config
        plate_format: 96 or 384
        small_mode: If True, run only 12 representative wells

    Returns:
        List of well records with morphology + metadata
    """
    # Create run context (profile is used for non-realism factors like batch effects)
    config = {
        'realism_profile': profile,
        'context_strength': 1.0,
    }
    run_ctx = RunContext.sample(seed=seed, config=config)

    # Create VM
    vm = BiologicalVirtualMachine(run_context=run_ctx)

    # Define wells
    if plate_format == 384:
        all_rows = 'ABCDEFGHIJKLMNOP'
        all_cols = range(1, 25)
    else:  # 96
        all_rows = 'ABCDEFGH'
        all_cols = range(1, 13)

    if small_mode:
        # Small mode: 12 representative wells spanning edge distances
        # Pick from corners, edges, and center
        all_wells = [
            'A1', 'A6', 'A12',   # Top row: corner, mid, corner
            'D1', 'D6', 'D12',   # Mid row: edge, center, edge
            'H1', 'H6', 'H12',   # Bottom row: corner, mid, corner
            'B2', 'G11', 'E7',   # Additional spread
        ]
    else:
        all_wells = [f"{row}{col}" for row in all_rows for col in all_cols]

    # DMSO-only design (no biology confounds)
    well_assignments = [('DMSO', 0.0) for _ in all_wells]

    # Seed all vessels
    for well_id, (compound, dose_uM) in zip(all_wells, well_assignments):
        vm.seed_vessel(well_id, cell_line='A549', vessel_type='96-well')
        if compound != 'DMSO':
            vm.treat_with_compound(well_id, compound=compound, dose_uM=dose_uM)

    # Advance time (24h)
    vm.advance_time(hours=24.0)

    # Measure all vessels with realism_config_override
    well_records = []

    for well_id, (compound, dose_uM) in zip(all_wells, well_assignments):
        # Measure with override
        result = vm.cell_painting_assay(
            vessel_id=well_id,
            well_position=well_id,
            plate_id='variance_provenance_plate',
            batch_id=run_ctx.batch_id,
            realism_config_override=realism_config_override  # Counterfactual toggle
        )

        # Parse position
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
            'edge_distance': det_meta.get('edge_distance', 0.0),
            'realism_config_source': det_meta.get('realism_config_source', ''),
            'realism_config_hash': det_meta.get('realism_config_hash', ''),
            'is_outlier': qc_flags.get('is_outlier', False),
            'pathology_type': qc_flags.get('pathology_type', ''),
        }

        well_records.append(well_record)

    return well_records


def save_wells_csv(wells: list[dict], output_path: Path):
    """Save wells to CSV."""
    fieldnames = [
        'well_id', 'row', 'col', 'row_letter', 'compound', 'dose_uM', 'time_h',
        'er', 'mito', 'nucleus', 'actin', 'rna',
        'edge_distance', 'realism_config_source', 'realism_config_hash',
        'is_outlier', 'pathology_type'
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(wells)


def generate_markdown_report(
    output_dir: Path,
    args: argparse.Namespace,
    budget: dict,
    counterfactual_configs: dict
):
    """Generate markdown report with variance provenance summary."""
    report_path = output_dir / "VARIANCE_PROVENANCE_REPORT.md"

    with open(report_path, 'w') as f:
        f.write("# Variance Provenance Report\n\n")
        f.write("Decomposition of detector-induced variance into components.\n\n")

        f.write("## Run Configuration\n\n")
        f.write(f"- **Profile**: {args.profile}\n")
        f.write(f"- **Design**: dmso_only (biology held constant)\n")
        f.write(f"- **Seed**: {args.seed}\n")
        f.write(f"- **Plate format**: {args.plate_format}-well\n")
        f.write(f"- **Small mode**: {args.small}\n")
        f.write(f"- **Replicates**: {args.replicates}\n\n")

        f.write("## Counterfactual Toggles\n\n")
        f.write("Five measurements per well with different realism layer combinations:\n\n")
        f.write("1. **bio**: All layers OFF (biology-only baseline)\n")
        f.write("2. **geo**: Position effects (row/col gradients + edge dimming)\n")
        f.write("3. **noise**: Edge noise inflation (heteroscedastic detector noise)\n")
        f.write("4. **path**: QC pathologies (channel dropout, focus miss, noise spike)\n")
        f.write("5. **obs**: All layers ON (observed, full profile)\n\n")

        f.write("## Variance Budget\n\n")
        f.write("Per-channel variance decomposition:\n\n")
        f.write("| Channel | Var(total) | Var(geo) | Var(noise) | Var(path) | Var(resid) |\n")
        f.write("|---------|------------|----------|------------|-----------|------------|\n")

        for ch in CHANNELS:
            b = budget[ch]
            f.write(f"| {ch:7s} | {b['Var_total']:10.2f} | {b['Var_geo']:8.2f} | "
                   f"{b['Var_noise']:10.2f} | {b['Var_path']:9.2f} | {b['Var_resid']:10.2f} |\n")

        f.write("\n## Variance Fractions\n\n")
        f.write("Fraction of total variance attributable to each component:\n\n")
        f.write("| Channel | Geo (%) | Noise (%) | Path (%) | Resid (%) |\n")
        f.write("|---------|---------|-----------|----------|----------|\n")

        for ch in CHANNELS:
            b = budget[ch]
            f.write(f"| {ch:7s} | {100*b['frac_geo']:7.1f} | {100*b['frac_noise']:9.1f} | "
                   f"{100*b['frac_path']:8.1f} | {100*b['frac_resid']:9.1f} |\n")

        f.write(f"\n**Summary**:\n")
        f.write(f"- Total variance explained (geo + noise + path): {100*budget['summary']['total_variance_explained']:.1f}%\n")
        f.write(f"- Mean residual fraction: {100*budget['summary']['mean_residual_fraction']:.1f}%\n\n")

        f.write("## Residual Interpretation\n\n")
        f.write("The **residual** quantifies non-additivity and interactions between layers.\n\n")
        f.write("- **Small residual (<10%)**: Layers are roughly independent (additive variance)\n")
        f.write("- **Large residual (>20%)**: Layers interact (e.g., edge noise inflation is multiplicative with geometry)\n\n")
        f.write("**Note**: A large residual is not a bug—it's honest accounting of layer interactions.\n\n")

        f.write("## Output Files\n\n")
        f.write(f"- `bio_wells.csv` - Biology-only measurements\n")
        f.write(f"- `geo_wells.csv` - Geometry-only measurements\n")
        f.write(f"- `noise_wells.csv` - Noise-only measurements\n")
        f.write(f"- `path_wells.csv` - Pathology-only measurements\n")
        f.write(f"- `obs_wells.csv` - Observed measurements (all layers)\n")
        f.write(f"- `deltas.csv` - Per-well deltas for all components\n")
        f.write(f"- `variance_budget.csv` - Per-channel variance budget\n")

        if args.plot:
            f.write(f"- `variance_fractions_stacked.png` - Stacked bar plot of variance fractions\n")
            f.write(f"- `delta_heatmaps_{args.channel}.png` - Plate heatmaps of delta components\n")
            f.write(f"- `variance_total_by_channel.png` - Total variance by channel\n")

        f.write("\n")

    print(f"\nWrote report: {report_path}")


def plot_variance_fractions(budget: dict, output_path: Path):
    """Plot stacked bar chart of variance fractions."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))

    channels = CHANNELS
    x = np.arange(len(channels))
    width = 0.6

    # Extract fractions
    frac_geo = [budget[ch]['frac_geo'] for ch in channels]
    frac_noise = [budget[ch]['frac_noise'] for ch in channels]
    frac_path = [budget[ch]['frac_path'] for ch in channels]
    frac_resid = [budget[ch]['frac_resid'] for ch in channels]

    # Stacked bars
    p1 = ax.bar(x, frac_geo, width, label='Geometry', color='#4daf4a', alpha=0.9)
    p2 = ax.bar(x, frac_noise, width, bottom=frac_geo, label='Noise', color='#377eb8', alpha=0.9)

    bottom = np.array(frac_geo) + np.array(frac_noise)
    p3 = ax.bar(x, frac_path, width, bottom=bottom, label='Pathology', color='#e41a1c', alpha=0.9)

    bottom = bottom + np.array(frac_path)
    p4 = ax.bar(x, frac_resid, width, bottom=bottom, label='Residual', color='#999999', alpha=0.9)

    ax.set_xlabel('Channel', fontsize=12, fontweight='bold')
    ax.set_ylabel('Variance Fraction', fontsize=12, fontweight='bold')
    ax.set_title('Variance Provenance: Detector Layer Contributions', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(channels)
    ax.legend(loc='upper right', frameon=True)
    ax.set_ylim([0, 1.0])
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"  Saved: {output_path}")


def plot_delta_heatmaps(deltas: dict, channel: str, output_path: Path):
    """Plot plate heatmaps for delta components."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    components = ['geo', 'noise', 'path', 'total', 'resid']
    titles = ['Geometry', 'Noise', 'Pathology', 'Total', 'Residual']

    # Determine plate dimensions from data
    rows = [w['row'] for w in deltas['total']]
    cols = [w['col'] for w in deltas['total']]
    n_rows = max(rows) + 1
    n_cols = max(cols) + 1

    for i, (component, title) in enumerate(zip(components, titles)):
        ax = axes[i]

        # Build plate array
        plate = np.full((n_rows, n_cols), np.nan)
        for w in deltas[component]:
            plate[w['row'], w['col']] = w[channel]

        # Plot heatmap
        vmax = np.nanmax(np.abs(plate))
        im = ax.imshow(plate, cmap='RdBu_r', aspect='auto', vmin=-vmax, vmax=vmax)

        ax.set_title(f'{title} ({channel})', fontsize=12, fontweight='bold')
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        plt.colorbar(im, ax=ax)

    # Hide unused subplot
    axes[5].axis('off')

    plt.suptitle(f'Delta Component Heatmaps: {channel.upper()} Channel',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"  Saved: {output_path}")


def plot_variance_total_by_channel(budget: dict, output_path: Path):
    """Plot total variance by channel."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))

    channels = CHANNELS
    var_total = [budget[ch]['Var_total'] for ch in channels]

    bars = ax.bar(channels, var_total, color='#377eb8', alpha=0.8, width=0.6)

    # Add value labels
    for bar, val in zip(bars, var_total):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.1f}',
                ha='center', va='bottom', fontsize=10)

    ax.set_xlabel('Channel', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Variance', fontsize=12, fontweight='bold')
    ax.set_title('Total Detector-Induced Variance by Channel', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"  Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Variance provenance decomposition for detector realism stack"
    )
    parser.add_argument('--out', type=str, required=True,
                       help='Output directory for results')
    parser.add_argument('--seed', type=int, default=42,
                       help='Run seed for reproducibility')
    parser.add_argument('--profile', type=str, default='realistic',
                       choices=['clean', 'realistic', 'hostile'],
                       help='Realism profile (realistic or hostile)')
    parser.add_argument('--plate-format', type=int, default=96,
                       choices=[96, 384],
                       help='Plate format (96 or 384)')
    parser.add_argument('--channel', type=str, default='er',
                       choices=CHANNELS,
                       help='Channel for heatmap plots (default: er)')
    parser.add_argument('--replicates', type=int, default=1,
                       help='Number of replicates (default: 1)')
    parser.add_argument('--small', action='store_true',
                       help='Small mode: run only 12 representative wells')
    parser.add_argument('--plot', action='store_true',
                       help='Generate plots (requires matplotlib)')

    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Variance Provenance Decomposition")
    print(f"Profile: {args.profile}, Seed: {args.seed}, Format: {args.plate_format}-well")
    print(f"Small mode: {args.small}, Replicates: {args.replicates}")
    print()

    # Create counterfactual configs
    counterfactual_configs = create_counterfactual_configs(args.profile)

    # Save configs for reference
    with open(output_dir / "counterfactual_configs.json", 'w') as f:
        json.dump(counterfactual_configs, f, indent=2)

    # Run counterfactual measurements
    print("Running counterfactual measurements...")
    wells_by_component = {}

    for component_name in ['bio', 'geo', 'noise', 'path', 'obs']:
        print(f"  {component_name}...")
        config = counterfactual_configs[component_name]
        wells = run_plate_with_config_override(
            profile=args.profile,
            seed=args.seed,
            realism_config_override=config,
            plate_format=args.plate_format,
            small_mode=args.small
        )
        wells_by_component[component_name] = wells

        # Save per-component CSV
        csv_path = output_dir / f"{component_name}_wells.csv"
        save_wells_csv(wells, csv_path)
        print(f"    Wrote: {csv_path}")

    # Compute deltas
    print("\nComputing deltas...")
    deltas = compute_deltas(
        bio=wells_by_component['bio'],
        geo=wells_by_component['geo'],
        noise=wells_by_component['noise'],
        path=wells_by_component['path'],
        obs=wells_by_component['obs']
    )

    # Save deltas CSV
    deltas_path = output_dir / "deltas.csv"
    save_deltas_csv(deltas, deltas_path)
    print(f"  Wrote: {deltas_path}")

    # Compute variance budget
    print("\nComputing variance budget...")
    budget = compute_variance_budget(deltas)

    # Save variance budget CSV
    budget_path = output_dir / "variance_budget.csv"
    save_variance_budget_csv(budget, budget_path)
    print(f"  Wrote: {budget_path}")

    # Print summary
    print("\nVariance Budget Summary:")
    print(f"  Total variance explained: {100*budget['summary']['total_variance_explained']:.1f}%")
    print(f"  Mean residual fraction: {100*budget['summary']['mean_residual_fraction']:.1f}%")

    # Generate plots
    if args.plot:
        print("\nGenerating plots...")

        plot_variance_fractions(budget, output_dir / "variance_fractions_stacked.png")
        plot_delta_heatmaps(deltas, args.channel, output_dir / f"delta_heatmaps_{args.channel}.png")
        plot_variance_total_by_channel(budget, output_dir / "variance_total_by_channel.png")

    # Generate markdown report
    generate_markdown_report(output_dir, args, budget, counterfactual_configs)

    print("\nDone!")


if __name__ == '__main__':
    main()
