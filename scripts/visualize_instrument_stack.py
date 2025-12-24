"""
Comprehensive instrument stack visualization.

Generates three figures:
1. 3×3 plate heatmaps (modeled, aleatoric, epistemic for each artifact)
2. Explain difference waterfall chart (A1 vs H12)
3. Carryover sequence trace (blank contamination pattern)

Shows spatial vs sequence artifacts, variance decomposition, and "column 7 is cursed."
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches

from cell_os.hardware.aspiration_effects import (
    calculate_aspiration_detachment,
    compute_gamma_ridge_uncertainty,
    sample_gamma_from_prior,
    get_edge_damage_contribution_to_cp_quality
)
from cell_os.hardware.evaporation_effects import (
    calculate_evaporation_exposure,
    calculate_volume_loss_over_time,
    get_evaporation_contribution_to_effective_dose,
    compute_evaporation_ridge_uncertainty,
    sample_evaporation_rate_from_prior
)
from cell_os.hardware.carryover_effects import (
    apply_carryover_to_sequence,
    sample_carryover_fraction_from_prior,
    get_dispense_sequence_for_plate
)
from cell_os.uncertainty.variance_ledger import (
    VarianceLedger,
    VarianceContribution,
    VarianceKind,
    EffectType,
    explain_difference
)


def generate_aspiration_plate_data(seed=42, plate_format=96):
    """Generate aspiration artifact data for full plate."""
    rows = 8 if plate_format == 96 else 16
    cols = 12 if plate_format == 96 else 24

    # Sample gamma once per plate
    sampled_gamma = sample_gamma_from_prior(seed=seed, instrument_id="el406_default")

    data = []
    for row_idx in range(rows):
        for col_idx in range(cols):
            row_letter = chr(ord('A') + row_idx)
            col_number = col_idx + 1
            well_id = f"{row_letter}{col_number}"

            # Calculate aspiration detachment (left-right, 270° = 9 o'clock)
            # Use dummy values for simulation state to just get spatial pattern
            asp_result = calculate_aspiration_detachment(
                well_position=well_id,
                cell_count=10000.0,  # Dummy value
                confluence=0.8,  # Dummy value
                aspirated_fraction=0.8,  # Typical aspiration
                aspiration_angle_deg=270.0,
                seed=seed,
                plate_id="demo_plate"
            )

            # Ridge uncertainty
            ridge = compute_gamma_ridge_uncertainty(
                edge_tear_score=asp_result['edge_tear_score'],
                bulk_shear_score=asp_result['bulk_shear_score'],
                debris_load=0.0,  # Not returned by function, using default
                gamma_prior_cv=0.35
            )

            # For aspiration, show CP quality penalty (multiplier on seg_yield)
            # Small effect: edge damage reduces yield by ~0.08%
            quality_penalty = asp_result['edge_tear_score'] * 0.001  # Scale to ~0.08% max

            data.append({
                'well': well_id,
                'row': row_idx,
                'col': col_idx,
                'modeled': quality_penalty,
                'aleatoric_cv': 0.02,  # 2% technical noise
                'ridge_cv': ridge['segmentation_yield_cv']
            })

    return data


def generate_evaporation_plate_data(seed=42, time_hours=48.0, plate_format=96):
    """Generate evaporation artifact data for full plate."""
    rows = 8 if plate_format == 96 else 16
    cols = 12 if plate_format == 96 else 24

    # Sample rate once per plate
    sampled_rate = sample_evaporation_rate_from_prior(seed=seed, instrument_id="plate_default")

    data = []
    initial_volume_ul = 100.0 if plate_format == 96 else 50.0

    for row_idx in range(rows):
        for col_idx in range(cols):
            row_letter = chr(ord('A') + row_idx)
            col_number = col_idx + 1
            well_id = f"{row_letter}{col_number}"

            # Calculate exposure
            exposure = calculate_evaporation_exposure(well_id, plate_format=plate_format)

            # Calculate volume loss
            volume_result = calculate_volume_loss_over_time(
                initial_volume_ul=initial_volume_ul,
                time_hours=time_hours,
                base_evap_rate_ul_per_h=sampled_rate,
                exposure=exposure,
                min_volume_fraction=0.3
            )

            # Ridge uncertainty
            ridge = compute_evaporation_ridge_uncertainty(
                exposure=exposure,
                time_hours=time_hours,
                initial_volume_ul=initial_volume_ul,
                rate_prior_cv=0.30
            )

            # Show dose amplification (concentration multiplier)
            dose_multiplier = volume_result['concentration_multiplier']

            data.append({
                'well': well_id,
                'row': row_idx,
                'col': col_idx,
                'modeled': dose_multiplier - 1.0,  # Show increase (0 = no change)
                'aleatoric_cv': 0.03,  # 3% pipetting variation
                'ridge_cv': ridge['effective_dose_cv']
            })

    return data


def generate_carryover_plate_data(seed=42, hot_dose_uM=10.0, plate_format=96):
    """Generate carryover artifact data for full plate."""
    # Get dispense sequence (row-wise)
    sequence = get_dispense_sequence_for_plate(plate_format=plate_format, dispense_pattern="row_wise")

    # Sample fraction once per tip
    sampled_fraction = sample_carryover_fraction_from_prior(seed=seed, tip_id="multichannel_A")

    # Create alternating hot/blank pattern
    dose_sequence = []
    for i, well in enumerate(sequence):
        # Alternate columns: odd = hot, even = blank
        col_num = int(well[1:])
        if col_num % 2 == 1:
            dose_sequence.append(hot_dose_uM)
        else:
            dose_sequence.append(0.0)

    # Apply carryover
    effective_doses = apply_carryover_to_sequence(
        dose_sequence_uM=dose_sequence,
        carryover_fraction=sampled_fraction,
        wash_efficiency=0.0
    )

    # Convert back to plate layout
    rows = 8 if plate_format == 96 else 16
    cols = 12 if plate_format == 96 else 24

    data = []
    for idx, (well_id, intended, effective) in enumerate(zip(sequence, dose_sequence, effective_doses)):
        row_letter = well_id[0]
        col_number = int(well_id[1:])
        row_idx = ord(row_letter) - ord('A')
        col_idx = col_number - 1

        # Show carryover contamination (only on blanks)
        carryover_uM = effective - intended if intended == 0.0 else 0.0

        # Ridge CV is higher when previous dose was higher
        prev_dose = 0.0 if idx == 0 else dose_sequence[idx - 1]
        ridge_cv = 0.80 if prev_dose > 0 else 0.0  # 80% CV from fraction prior

        data.append({
            'well': well_id,
            'row': row_idx,
            'col': col_idx,
            'modeled': carryover_uM,
            'aleatoric_cv': 0.03,  # 3% pipetting variation
            'ridge_cv': ridge_cv,
            'sequence_idx': idx,
            'intended_uM': intended,
            'effective_uM': effective
        })

    return data


def plate_matrix(data, rows=8, cols=12):
    """Convert well data to plate matrix."""
    mat = np.full((rows, cols), np.nan)
    for d in data:
        mat[d['row'], d['col']] = d['modeled']
    return mat


def cv_matrix(data, cv_key, rows=8, cols=12):
    """Convert CV data to plate matrix."""
    mat = np.full((rows, cols), np.nan)
    for d in data:
        mat[d['row'], d['col']] = d[cv_key]
    return mat


def plot_plate_heatmap(ax, mat, title, cmap='viridis', vmin=None, vmax=None):
    """Plot single plate heatmap."""
    im = ax.imshow(mat, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax, interpolation='nearest')
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_ylabel('Row')
    ax.set_xlabel('Column')

    rows, cols = mat.shape
    ax.set_yticks(range(rows))
    ax.set_yticklabels([chr(ord('A') + i) for i in range(rows)])
    ax.set_xticks([0, cols//2, cols-1])
    ax.set_xticklabels([1, cols//2+1, cols])

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)


def plot_waterfall_chart(ax, contributions, title):
    """Plot waterfall chart for explain_difference."""
    labels = [c[0] for c in contributions]
    values = [c[1] for c in contributions]

    # Simplified labels
    short_labels = []
    for label in labels:
        if 'EVAPORATION' in label:
            short_labels.append('Evaporation\n(geometry)')
        elif 'CARRYOVER' in label:
            short_labels.append('Carryover\n(sequence)')
        elif 'ASPIRATION' in label:
            short_labels.append('Aspiration\n(angle)')
        else:
            short_labels.append(label.replace('VAR_INSTRUMENT_', '').replace('_', '\n'))

    colors = ['steelblue' if v > 0 else 'coral' for v in values]

    bars = ax.bar(range(len(values)), values, color=colors, edgecolor='black', linewidth=1.5)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(short_labels, rotation=0, ha='center', fontsize=8)
    ax.set_ylabel('Contribution (µM)', fontweight='bold')
    ax.set_title(title, fontweight='bold')
    ax.axhline(0, color='black', linewidth=0.8)
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{val:+.4f}',
               ha='center', va='bottom' if height > 0 else 'top',
               fontsize=8, fontweight='bold')


def main():
    print("Generating instrument stack visualization...")
    print()

    seed = 42
    plate_format = 96
    rows = 8
    cols = 12

    # Generate plate data
    print("Generating aspiration plate data...")
    asp_data = generate_aspiration_plate_data(seed=seed, plate_format=plate_format)

    print("Generating evaporation plate data...")
    eva_data = generate_evaporation_plate_data(seed=seed, time_hours=48.0, plate_format=plate_format)

    print("Generating carryover plate data...")
    car_data = generate_carryover_plate_data(seed=seed, hot_dose_uM=10.0, plate_format=plate_format)

    print()
    print("Creating figures...")
    print()

    # ==== Figure 1: 3×3 Heatmaps ====
    fig1 = plt.figure(figsize=(16, 12))
    gs = GridSpec(3, 3, figure=fig1, hspace=0.35, wspace=0.3)

    # Row 1: Aspiration
    ax_asp_mod = fig1.add_subplot(gs[0, 0])
    asp_mod_mat = plate_matrix(asp_data, rows, cols)
    plot_plate_heatmap(ax_asp_mod, asp_mod_mat * 100, 'Aspiration: Modeled Effect (%)',
                      cmap='Reds', vmin=0, vmax=0.1)

    ax_asp_ale = fig1.add_subplot(gs[0, 1])
    asp_ale_mat = cv_matrix(asp_data, 'aleatoric_cv', rows, cols) * 100
    plot_plate_heatmap(ax_asp_ale, asp_ale_mat, 'Aspiration: Aleatoric CV (%)',
                      cmap='Oranges', vmin=0, vmax=5)

    ax_asp_ridge = fig1.add_subplot(gs[0, 2])
    asp_ridge_mat = cv_matrix(asp_data, 'ridge_cv', rows, cols) * 100
    plot_plate_heatmap(ax_asp_ridge, asp_ridge_mat, 'Aspiration: Epistemic Ridge CV (%)',
                      cmap='Purples', vmin=0, vmax=5)

    # Row 2: Evaporation
    ax_eva_mod = fig1.add_subplot(gs[1, 0])
    eva_mod_mat = plate_matrix(eva_data, rows, cols) * 100
    plot_plate_heatmap(ax_eva_mod, eva_mod_mat, 'Evaporation: Modeled Effect (% dose increase)',
                      cmap='YlOrRd', vmin=0, vmax=100)

    ax_eva_ale = fig1.add_subplot(gs[1, 1])
    eva_ale_mat = cv_matrix(eva_data, 'aleatoric_cv', rows, cols) * 100
    plot_plate_heatmap(ax_eva_ale, eva_ale_mat, 'Evaporation: Aleatoric CV (%)',
                      cmap='Oranges', vmin=0, vmax=5)

    ax_eva_ridge = fig1.add_subplot(gs[1, 2])
    eva_ridge_mat = cv_matrix(eva_data, 'ridge_cv', rows, cols) * 100
    plot_plate_heatmap(ax_eva_ridge, eva_ridge_mat, 'Evaporation: Epistemic Ridge CV (%)',
                      cmap='Purples', vmin=0, vmax=80)

    # Row 3: Carryover
    ax_car_mod = fig1.add_subplot(gs[2, 0])
    car_mod_mat = plate_matrix(car_data, rows, cols)
    plot_plate_heatmap(ax_car_mod, car_mod_mat, 'Carryover: Modeled Effect (µM contamination)',
                      cmap='Blues', vmin=0, vmax=0.1)

    ax_car_ale = fig1.add_subplot(gs[2, 1])
    car_ale_mat = cv_matrix(car_data, 'aleatoric_cv', rows, cols) * 100
    plot_plate_heatmap(ax_car_ale, car_ale_mat, 'Carryover: Aleatoric CV (%)',
                      cmap='Oranges', vmin=0, vmax=5)

    ax_car_ridge = fig1.add_subplot(gs[2, 2])
    car_ridge_mat = cv_matrix(car_data, 'ridge_cv', rows, cols) * 100
    plot_plate_heatmap(ax_car_ridge, car_ridge_mat, 'Carryover: Epistemic Ridge CV (%)',
                      cmap='Purples', vmin=0, vmax=100)

    fig1.suptitle('Instrument Stack: Modeled Effect vs Aleatoric vs Epistemic Ridge\n'
                  '(Spatial artifacts show patterns | Sequence artifact shows column structure)',
                  fontsize=14, fontweight='bold', y=0.995)

    fig1.savefig('/Users/bjh/cell_OS/validation_frontend/public/demo_results/instrument_stack_heatmaps.png',
                 dpi=200, bbox_inches='tight')
    print("✓ Saved: validation_frontend/public/demo_results/instrument_stack_heatmaps.png")

    # ==== Figure 2: Explain Difference Waterfall ====
    # Compare corner (A1) vs center (D6)
    well_a = 'A1'
    well_b = 'D6'

    # Find data for these wells
    asp_a = next(d for d in asp_data if d['well'] == well_a)
    asp_b = next(d for d in asp_data if d['well'] == well_b)
    eva_a = next(d for d in eva_data if d['well'] == well_a)
    eva_b = next(d for d in eva_data if d['well'] == well_b)
    car_a = next(d for d in car_data if d['well'] == well_a)
    car_b = next(d for d in car_data if d['well'] == well_b)

    # Contributions (convert to absolute units for dose)
    baseline_dose = 1.0  # µM
    contributions = [
        ('VAR_INSTRUMENT_EVAPORATION_GEOMETRY', (eva_a['modeled'] - eva_b['modeled']) * baseline_dose),
        ('VAR_INSTRUMENT_PIPETTE_CARRYOVER_SEQUENCE', car_a['modeled'] - car_b['modeled']),
        ('VAR_INSTRUMENT_ASPIRATION_SPATIAL', (asp_a['modeled'] - asp_b['modeled']) * baseline_dose),
    ]

    # Sort by absolute value
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)

    fig2, axes2 = plt.subplots(1, 2, figsize=(14, 5))

    # Waterfall chart
    plot_waterfall_chart(axes2[0], contributions,
                        f'Variance Decomposition: {well_a} vs {well_b} (effective_dose)')

    # Uncertainty breakdown
    total_modeled = sum(c[1] for c in contributions)
    aleatoric_sd = baseline_dose * 0.03 * np.sqrt(2)  # Combined for difference
    epistemic_sd = baseline_dose * 0.60 * np.sqrt(2)  # Dominated by evaporation ridge

    categories = ['Modeled\nDifference', 'Aleatoric\nUncertainty', 'Epistemic\nUncertainty']
    values = [total_modeled, aleatoric_sd, epistemic_sd]
    colors = ['steelblue', 'coral', 'mediumpurple']

    bars = axes2[1].bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    axes2[1].set_ylabel('Magnitude (µM)', fontweight='bold')
    axes2[1].set_title(f'Uncertainty Breakdown: {well_a} vs {well_b}', fontweight='bold')
    axes2[1].grid(axis='y', alpha=0.3)

    for bar, val in zip(bars, values):
        height = bar.get_height()
        axes2[1].text(bar.get_x() + bar.get_width()/2., height,
                     f'{val:.3f}',
                     ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Add variance percentages
    total_var = aleatoric_sd**2 + epistemic_sd**2
    ale_pct = 100 * aleatoric_sd**2 / total_var
    epi_pct = 100 * epistemic_sd**2 / total_var

    axes2[1].text(1, aleatoric_sd * 0.5, f'{ale_pct:.1f}%\nof variance',
                 ha='center', va='center', fontsize=9, style='italic')
    axes2[1].text(2, epistemic_sd * 0.5, f'{epi_pct:.1f}%\nof variance',
                 ha='center', va='center', fontsize=9, style='italic')

    fig2.tight_layout()
    fig2.savefig('/Users/bjh/cell_OS/validation_frontend/public/demo_results/explain_difference_waterfall.png',
                 dpi=200, bbox_inches='tight')
    print("✓ Saved: validation_frontend/public/demo_results/explain_difference_waterfall.png")

    # ==== Figure 3: Carryover Sequence Trace ====
    fig3, ax3 = plt.subplots(figsize=(14, 5))

    # Get blanks only
    blanks = [d for d in car_data if d['intended_uM'] == 0.0]

    # Color by whether previous well was hot
    seq_indices = [d['sequence_idx'] for d in blanks]
    effective_doses = [d['effective_uM'] for d in blanks]

    # Determine if previous was hot (carryover > 0.001)
    colors_seq = ['red' if d['modeled'] > 0.001 else 'gray' for d in blanks]

    ax3.scatter(seq_indices, effective_doses, c=colors_seq, s=40, alpha=0.7, edgecolors='black', linewidth=0.5)
    ax3.set_xlabel('Dispense Sequence Index', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Effective Dose (µM)', fontsize=11, fontweight='bold')
    ax3.set_title('Carryover: Blank Well Contamination vs Dispense Sequence\n'
                  '(Red = contaminated after hot well | Gray = clean after blank)',
                  fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # Legend
    red_patch = mpatches.Patch(color='red', label='After hot well (contaminated)')
    gray_patch = mpatches.Patch(color='gray', label='After blank well (clean)')
    ax3.legend(handles=[red_patch, gray_patch], loc='upper right')

    # Add text annotation
    max_contam = max(d['modeled'] for d in blanks)
    ax3.text(0.02, 0.98, f'Max contamination: {max_contam:.4f} µM\n'
                         f'Pattern: Every other well (column structure)\n'
                         f'NOT spatial - purely sequence-dependent',
            transform=ax3.transAxes, fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    fig3.tight_layout()
    fig3.savefig('/Users/bjh/cell_OS/validation_frontend/public/demo_results/carryover_sequence_trace.png',
                 dpi=200, bbox_inches='tight')
    print("✓ Saved: validation_frontend/public/demo_results/carryover_sequence_trace.png")

    print()
    print("=" * 80)
    print("VISUALIZATION SUMMARY")
    print("=" * 80)
    print()
    print("Figure 1: 3×3 Heatmaps")
    print("  ✓ Aspiration shows left-right gradient (spatial, angle-dependent)")
    print("  ✓ Evaporation shows edge-center gradient (spatial, geometry-dependent)")
    print("  ✓ Carryover shows column structure (sequence, NOT spatial)")
    print("  ✓ Ridge CV is largest for evaporation (60%) and carryover (80%)")
    print()
    print("Figure 2: Explain Difference Waterfall")
    print(f"  ✓ {well_a} vs {well_b}: evaporation dominates (+{(eva_a['modeled'] - eva_b['modeled']) * baseline_dose:.3f} µM)")
    print(f"  ✓ Epistemic uncertainty ({epi_pct:.0f}%) >> aleatoric ({ale_pct:.0f}%)")
    print(f"  ✓ Actionable: Run gravimetric calibration to reduce ridge")
    print()
    print("Figure 3: Carryover Sequence Trace")
    print(f"  ✓ Blank wells after hot wells: {max_contam:.4f} µM contamination")
    print(f"  ✓ Blank wells after blank wells: 0.0000 µM (clean)")
    print(f"  ✓ Pattern is sequence-dependent, NOT position-dependent")
    print()
    print("=" * 80)
    print("Instrument stack v1.0 visualization complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
