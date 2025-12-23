#!/usr/bin/env python3
"""
Test cell line-specific hardware artifacts.

Seeds 384-well plates with three cell lines (HepG2, iPSC_NGN2, U2OS)
and visualizes how hardware artifacts differ by cell line characteristics.

Expected:
- iPSC_NGN2: Poorest attachment (70%), highest fragility (2.0× shear)
- HepG2: Baseline attachment (90%), normal fragility (1.0× shear)
- U2OS: Best attachment (95%), lowest fragility (0.7× shear)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

# Plate dimensions
ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']
COLS = list(range(1, 25))  # 1-24

# Cell lines to test
CELL_LINES = ['HepG2', 'iPSC_NGN2', 'U2OS']

def seed_plate_and_extract(cell_line, seed=5000):
    """
    Seed a 384-well plate with specified cell line and extract data.

    Returns:
        cell_counts: 16×24 array of cell counts
        viabilities: 16×24 array of viabilities
    """
    print(f"Seeding {cell_line}...")

    # Create VM
    vm = BiologicalVirtualMachine(seed=seed)

    # Initialize arrays
    cell_counts = np.zeros((16, 24))
    viabilities = np.zeros((16, 24))

    # Seed all wells
    for row_idx, row in enumerate(ROWS):
        for col_idx, col in enumerate(COLS):
            well_id = f"well_{row}{col}_{cell_line}"

            # Seed with nominal density
            vm.seed_vessel(
                vessel_id=well_id,
                cell_line=cell_line,
                vessel_type="384-well",
                density_level="NOMINAL"
            )

            # Extract state
            state = vm.vessel_states[well_id]
            cell_counts[row_idx, col_idx] = state.cell_count
            viabilities[row_idx, col_idx] = state.viability

    return cell_counts, viabilities


def create_comparison_figure(results, seed):
    """Create multi-panel comparison figure."""
    fig = plt.figure(figsize=(20, 14))

    # Create grid: 3 rows (cell lines) × 3 cols (cells, viability, comparison)
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    for line_idx, cell_line in enumerate(CELL_LINES):
        cells = results[cell_line]['cells']
        viabs = results[cell_line]['viabs']

        # Cell count heatmap
        ax = fig.add_subplot(gs[line_idx, 0])
        im1 = ax.imshow(cells, aspect='auto', cmap='RdYlGn', origin='upper')
        ax.set_title(f'{cell_line} - Cell Count\n({results[cell_line]["attachment"]:.0%} attachment efficiency)',
                     fontsize=12, fontweight='bold')
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')
        ax.set_xticks(range(0, 24, 4))
        ax.set_xticklabels(range(1, 25, 4))
        ax.set_yticks(range(16))
        ax.set_yticklabels(ROWS)
        plt.colorbar(im1, ax=ax, label='Cell Count')

        # Add text annotation with statistics
        mean_cells = cells.mean()
        std_cells = cells.std()
        ax.text(0.02, 0.98, f'Mean: {mean_cells:.0f}\nStd: {std_cells:.0f}\nCV: {100*std_cells/mean_cells:.1f}%',
                transform=ax.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # Viability heatmap
        ax = fig.add_subplot(gs[line_idx, 1])
        im2 = ax.imshow(viabs, aspect='auto', cmap='RdYlGn', origin='upper', vmin=0.75, vmax=1.0)
        ax.set_title(f'{cell_line} - Viability\n({results[cell_line]["shear"]:.1f}× shear sensitivity)',
                     fontsize=12, fontweight='bold')
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')
        ax.set_xticks(range(0, 24, 4))
        ax.set_xticklabels(range(1, 25, 4))
        ax.set_yticks(range(16))
        ax.set_yticklabels(ROWS)
        plt.colorbar(im2, ax=ax, label='Viability')

        # Add text annotation
        mean_viab = viabs.mean()
        std_viab = viabs.std()
        ax.text(0.02, 0.98, f'Mean: {mean_viab:.3f}\nStd: {std_viab:.4f}\nCV: {100*std_viab/mean_viab:.2f}%',
                transform=ax.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # Row-wise comparison (pin effects)
        ax = fig.add_subplot(gs[line_idx, 2])
        row_means_cells = np.mean(cells, axis=1)
        plate_mean = np.mean(cells)
        deviations = 100 * (row_means_cells - plate_mean) / plate_mean

        colors = ['C0' if i % 2 == 0 else 'C1' for i in range(16)]
        bars = ax.bar(ROWS, deviations, color=colors, alpha=0.7, edgecolor='black')
        ax.axhline(0, color='black', linestyle='--', linewidth=1)
        ax.set_title(f'{cell_line} - Row Deviations', fontsize=12, fontweight='bold')
        ax.set_xlabel('Row (Pin)')
        ax.set_ylabel('Deviation from Plate Mean (%)')
        ax.grid(axis='y', alpha=0.3)
        ax.set_ylim(-10, 10)

        # Add pin labels
        for i, (row, deviation) in enumerate(zip(ROWS, deviations)):
            pin_num = (i % 8) + 1
            ax.text(i, deviation + 0.3 if deviation > 0 else deviation - 0.3,
                   f'P{pin_num}', ha='center', va='bottom' if deviation > 0 else 'top',
                   fontsize=7)

    # Overall title
    fig.suptitle(f'Cell Line-Specific Hardware Artifacts (Seed {seed})\n' +
                 'iPSC_NGN2 neurons are fragile | HepG2 hepatocytes are baseline | U2OS cancer cells are robust',
                 fontsize=16, fontweight='bold', y=0.995)

    return fig


def analyze_differences(results):
    """Print detailed analysis of cell line differences."""
    print("\n" + "="*80)
    print("CELL LINE COMPARISON ANALYSIS")
    print("="*80)
    print()

    print(f"{'Cell Line':<15} {'Nominal':<10} {'Observed':<12} {'Attach%':<10} {'Mean Viab':<12} {'Shear':<10}")
    print("-"*80)

    for cell_line in CELL_LINES:
        r = results[cell_line]
        print(f"{cell_line:<15} {r['nominal']:<10} {r['cells'].mean():<12.1f} "
              f"{r['attachment']:<10.2f} {r['viabs'].mean():<12.4f} {r['shear']:<10.1f}")

    print()
    print("Key Differences:")
    print("-" * 80)

    # Cell count ranking
    cell_ranking = sorted(results.items(), key=lambda x: x[1]['cells'].mean(), reverse=True)
    print("\nCell Count (reflects attachment efficiency):")
    for rank, (cell_line, data) in enumerate(cell_ranking, 1):
        ratio = data['cells'].mean() / data['nominal']
        print(f"  {rank}. {cell_line}: {data['cells'].mean():.0f} cells "
              f"({100*ratio:.1f}% of nominal, {100*data['attachment']:.0f}% attachment)")

    # Viability ranking
    viab_ranking = sorted(results.items(), key=lambda x: x[1]['viabs'].mean(), reverse=True)
    print("\nViability (reflects shear sensitivity):")
    for rank, (cell_line, data) in enumerate(viab_ranking, 1):
        print(f"  {rank}. {cell_line}: {data['viabs'].mean():.4f} "
              f"({data['shear']:.1f}× shear sensitivity, "
              f"{data['robustness']:.1f}× robustness)")

    # Gradient analysis
    print("\nGradient Magnitudes (corner wells A1 vs P24):")
    for cell_line in CELL_LINES:
        r = results[cell_line]
        A1_cells = r['cells'][0, 0]
        P24_cells = r['cells'][15, 23]
        gradient = 100 * (A1_cells - P24_cells) / r['cells'].mean()

        A1_viab = r['viabs'][0, 0]
        P24_viab = r['viabs'][15, 23]
        viab_diff = A1_viab - P24_viab

        print(f"  {cell_line}: Cell count {gradient:.1f}% gradient, "
              f"Viability Δ={viab_diff:.4f}")


def main():
    """Run cell line comparison test."""
    print("="*80)
    print("CELL LINE-SPECIFIC HARDWARE ARTIFACTS TEST")
    print("="*80)
    print()

    seed = 5000

    # Get hardware sensitivity parameters
    from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
    import yaml
    from pathlib import Path

    params_file = Path(__file__).parent.parent / "data" / "cell_thalamus_params.yaml"
    with open(params_file, 'r') as f:
        params = yaml.safe_load(f)

    hardware_sens = params.get('hardware_sensitivity', {})

    # Get nominal seeding densities
    from src.cell_os.database.repositories.seeding_density import get_cells_to_seed

    # Seed plates and collect data
    results = {}
    for cell_line in CELL_LINES:
        cells, viabs = seed_plate_and_extract(cell_line, seed=seed)

        sens = hardware_sens.get(cell_line, hardware_sens.get('DEFAULT', {}))
        nominal = get_cells_to_seed(cell_line, "384-well", "NOMINAL")

        results[cell_line] = {
            'cells': cells,
            'viabs': viabs,
            'nominal': nominal,
            'attachment': sens.get('attachment_efficiency', 0.90),
            'shear': sens.get('shear_sensitivity', 1.0),
            'robustness': sens.get('mechanical_robustness', 1.0)
        }

    # Analyze
    analyze_differences(results)

    # Visualize
    print("\nGenerating comparison figure...")
    fig = create_comparison_figure(results, seed)

    # Save
    output_path = Path(__file__).parent.parent / 'validation_frontend' / 'public' / 'demo_results' / 'hardware_artifacts'
    output_path.mkdir(parents=True, exist_ok=True)

    filename = output_path / f'cellline_comparison_seed{seed}.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved visualization: {filename}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print()
    print("Expected patterns:")
    print("  ✓ iPSC_NGN2 shows lowest cell counts (poor attachment)")
    print("  ✓ iPSC_NGN2 shows lowest viability (high shear sensitivity)")
    print("  ✓ U2OS shows highest viability (low shear sensitivity)")
    print("  ✓ All cell lines show same 2D gradient structure (hardware is constant)")


if __name__ == '__main__':
    main()
