#!/usr/bin/env python3
"""
Test hardware artifacts from EL406 Culture plating.

Seeds a 384-well plate with HepG2 cells using EL406 Culture,
then visualizes the resulting cell count and viability patterns.

Expected:
- Row-wise structure (pin-specific biases)
- Column-wise structure (serpentine temporal gradient)
- 2D interaction creates corner-to-corner gradient
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

def seed_plate_and_extract(seed=5000):
    """
    Seed a 384-well plate with HepG2 cells and extract cell counts + viability.

    Returns:
        cell_counts: 16×24 array of cell counts
        viabilities: 16×24 array of viabilities
    """
    print(f"Seeding 384-well plate with seed={seed}...")

    # Create VM
    vm = BiologicalVirtualMachine(seed=seed)

    # Initialize arrays
    cell_counts = np.zeros((16, 24))
    viabilities = np.zeros((16, 24))

    # Seed all wells
    for row_idx, row in enumerate(ROWS):
        for col_idx, col in enumerate(COLS):
            well_id = f"well_{row}{col}_HepG2"

            # Seed with nominal density (3000 cells for 384-well)
            vm.seed_vessel(
                vessel_id=well_id,
                cell_line="HepG2",
                vessel_type="384-well",
                density_level="NOMINAL"
            )

            # Extract state
            state = vm.vessel_states[well_id]
            cell_counts[row_idx, col_idx] = state.cell_count
            viabilities[row_idx, col_idx] = state.viability

    print(f"✓ Seeded {len(ROWS) * len(COLS)} wells")
    return cell_counts, viabilities


def analyze_gradients(cell_counts, viabilities):
    """Analyze and print gradient statistics."""
    print("\n" + "="*80)
    print("GRADIENT ANALYSIS")
    print("="*80)

    # Overall statistics
    print("\nCell Count Statistics:")
    print(f"  Mean:   {np.mean(cell_counts):.1f} cells")
    print(f"  Std:    {np.std(cell_counts):.1f} cells")
    print(f"  CV:     {100 * np.std(cell_counts) / np.mean(cell_counts):.1f}%")
    print(f"  Range:  {np.min(cell_counts):.1f} - {np.max(cell_counts):.1f}")

    print("\nViability Statistics:")
    print(f"  Mean:   {np.mean(viabilities):.4f}")
    print(f"  Std:    {np.std(viabilities):.4f}")
    print(f"  CV:     {100 * np.std(viabilities) / np.mean(viabilities):.2f}%")
    print(f"  Range:  {np.min(viabilities):.4f} - {np.max(viabilities):.4f}")

    # Row-wise analysis (pin-specific)
    print("\n" + "-"*80)
    print("ROW-WISE ANALYSIS (Pin-Specific Biases):")
    print("-"*80)
    print(f"{'Row':<5} {'Pin':<5} {'Mean Cells':<12} {'Mean Viab':<12} {'vs Plate Mean':<15}")
    print("-"*80)

    plate_mean_cells = np.mean(cell_counts)
    for row_idx, row in enumerate(ROWS):
        pin_num = (row_idx % 8) + 1
        row_mean_cells = np.mean(cell_counts[row_idx, :])
        row_mean_viab = np.mean(viabilities[row_idx, :])
        deviation = 100 * (row_mean_cells - plate_mean_cells) / plate_mean_cells

        print(f"{row:<5} {pin_num:<5} {row_mean_cells:<12.1f} {row_mean_viab:<12.4f} {deviation:+.2f}%")

    # Column-wise analysis (serpentine temporal)
    print("\n" + "-"*80)
    print("COLUMN-WISE ANALYSIS (Serpentine Temporal Gradient):")
    print("-"*80)
    print(f"{'Col':<5} {'Mean Cells':<12} {'Mean Viab':<12} {'vs Plate Mean':<15}")
    print("-"*80)

    # Show every 4th column for readability
    for col_idx in range(0, 24, 4):
        col = col_idx + 1
        col_mean_cells = np.mean(cell_counts[:, col_idx])
        col_mean_viab = np.mean(viabilities[:, col_idx])
        deviation = 100 * (col_mean_cells - plate_mean_cells) / plate_mean_cells

        print(f"{col:<5} {col_mean_cells:<12.1f} {col_mean_viab:<12.4f} {deviation:+.2f}%")

    # Corner wells
    print("\n" + "-"*80)
    print("CORNER WELLS (Extreme Combinations):")
    print("-"*80)
    print(f"{'Well':<8} {'Cells':<10} {'Viability':<12} {'vs Plate Mean':<15}")
    print("-"*80)

    corners = [
        ('A1', 0, 0),
        ('A24', 0, 23),
        ('P1', 15, 0),
        ('P24', 15, 23),
    ]

    for well_name, row_idx, col_idx in corners:
        cells = cell_counts[row_idx, col_idx]
        viab = viabilities[row_idx, col_idx]
        deviation = 100 * (cells - plate_mean_cells) / plate_mean_cells

        print(f"{well_name:<8} {cells:<10.1f} {viab:<12.4f} {deviation:+.2f}%")


def visualize_gradients(cell_counts, viabilities, seed):
    """Create visualization of 2D gradient structure."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Cell count heatmap
    ax = axes[0, 0]
    im1 = ax.imshow(cell_counts, aspect='auto', cmap='RdYlGn', origin='upper')
    ax.set_title(f'Cell Count per Well (Seed {seed})', fontsize=14, fontweight='bold')
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')
    ax.set_xticks(range(0, 24, 4))
    ax.set_xticklabels(range(1, 25, 4))
    ax.set_yticks(range(16))
    ax.set_yticklabels(ROWS)
    plt.colorbar(im1, ax=ax, label='Cell Count')

    # Viability heatmap
    ax = axes[0, 1]
    im2 = ax.imshow(viabilities, aspect='auto', cmap='RdYlGn', origin='upper')
    ax.set_title(f'Viability per Well (Seed {seed})', fontsize=14, fontweight='bold')
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')
    ax.set_xticks(range(0, 24, 4))
    ax.set_xticklabels(range(1, 25, 4))
    ax.set_yticks(range(16))
    ax.set_yticklabels(ROWS)
    plt.colorbar(im2, ax=ax, label='Viability')

    # Row means (pin-specific)
    ax = axes[1, 0]
    row_means_cells = np.mean(cell_counts, axis=1)
    plate_mean = np.mean(cell_counts)
    deviations = 100 * (row_means_cells - plate_mean) / plate_mean

    colors = ['C0' if i % 2 == 0 else 'C1' for i in range(16)]  # Color by odd/even row
    bars = ax.bar(ROWS, deviations, color=colors, alpha=0.7, edgecolor='black')
    ax.axhline(0, color='black', linestyle='--', linewidth=1)
    ax.set_title('Row-Wise Deviation (Pin-Specific Biases)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Row (Pin)')
    ax.set_ylabel('Deviation from Plate Mean (%)')
    ax.grid(axis='y', alpha=0.3)

    # Add pin labels
    for i, (row, deviation) in enumerate(zip(ROWS, deviations)):
        pin_num = (i % 8) + 1
        ax.text(i, deviation + 0.2, f'P{pin_num}', ha='center', va='bottom', fontsize=8)

    # Column means (serpentine temporal)
    ax = axes[1, 1]
    col_means_cells = np.mean(cell_counts, axis=0)
    deviations = 100 * (col_means_cells - plate_mean) / plate_mean

    ax.plot(range(1, 25), deviations, marker='o', linewidth=2, markersize=6, color='C2')
    ax.axhline(0, color='black', linestyle='--', linewidth=1)
    ax.set_title('Column-Wise Deviation (Serpentine Temporal Gradient)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Column')
    ax.set_ylabel('Deviation from Plate Mean (%)')
    ax.set_xticks(range(1, 25, 2))
    ax.grid(alpha=0.3)

    # Mark odd/even serpentine pattern
    ax.axvspan(0.5, 24.5, alpha=0.1, color='blue', label='Serpentine Pattern')

    plt.tight_layout()

    # Save figure
    output_path = Path(__file__).parent.parent / 'validation_frontend' / 'public' / 'demo_results' / 'hardware_artifacts'
    output_path.mkdir(parents=True, exist_ok=True)

    filename = output_path / f'seeding_gradient_seed{seed}.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved visualization: {filename}")

    return fig


def main():
    """Run test and analysis."""
    print("="*80)
    print("HARDWARE ARTIFACTS TEST: EL406 Culture Plating")
    print("="*80)
    print()
    print("Test design:")
    print("  - Seed 384-well plate with HepG2 (3000 cells/well nominal)")
    print("  - Extract cell count and viability immediately after seeding")
    print("  - Analyze row-wise (pin-specific) and column-wise (serpentine) patterns")
    print()

    # Run test
    seed = 5000
    cell_counts, viabilities = seed_plate_and_extract(seed=seed)

    # Analyze
    analyze_gradients(cell_counts, viabilities)

    # Visualize
    visualize_gradients(cell_counts, viabilities, seed)

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print()
    print("Expected patterns:")
    print("  ✓ Row-wise variation (pin-specific biases, ±2-5%)")
    print("  ✓ Column-wise gradient (serpentine temporal, ±2-4%)")
    print("  ✓ Corner wells show extreme combinations (A1 high, P24 low)")
    print("  ✓ 2D structure visible in heatmap")
    print()
    print("If you see structured patterns (not random), hardware artifacts are working!")


if __name__ == '__main__':
    main()
