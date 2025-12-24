"""
Visualization of evaporation effects and variance decomposition.

Generates:
1. Spatial heatmap of evaporation exposure (384-well plate)
2. Effective dose amplification heatmap
3. Cross-section showing gradient
4. Variance decomposition bar chart
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

from cell_os.hardware.evaporation_effects import (
    calculate_evaporation_exposure,
    calculate_volume_loss_over_time,
    get_evaporation_contribution_to_effective_dose,
    compute_evaporation_ridge_uncertainty,
    sample_evaporation_rate_from_prior
)


def generate_plate_data(time_hours=48.0, baseline_dose_uM=1.0, sampled_rate=0.5):
    """Generate evaporation data for full 384-well plate."""
    rows = 16  # A-P
    cols = 24  # 1-24

    exposure = np.zeros((rows, cols))
    effective_dose = np.zeros((rows, cols))
    volume_fraction = np.zeros((rows, cols))
    ridge_cv = np.zeros((rows, cols))

    for row_idx in range(rows):
        for col_idx in range(cols):
            row_letter = chr(ord('A') + row_idx)
            col_number = col_idx + 1
            well_position = f"{row_letter}{col_number}"

            # Calculate exposure
            exp = calculate_evaporation_exposure(well_position, plate_format=384)
            exposure[row_idx, col_idx] = exp

            # Calculate volume loss
            initial_volume_ul = 50.0
            volume_result = calculate_volume_loss_over_time(
                initial_volume_ul=initial_volume_ul,
                time_hours=time_hours,
                base_evap_rate_ul_per_h=sampled_rate,
                exposure=exp,
                min_volume_fraction=0.3
            )

            volume_fraction[row_idx, col_idx] = volume_result['volume_fraction']

            # Calculate effective dose
            dose_result = get_evaporation_contribution_to_effective_dose(
                concentration_multiplier=volume_result['concentration_multiplier'],
                baseline_dose_uM=baseline_dose_uM
            )

            effective_dose[row_idx, col_idx] = dose_result['effective_dose_multiplier']

            # Calculate ridge uncertainty
            ridge = compute_evaporation_ridge_uncertainty(
                exposure=exp,
                time_hours=time_hours,
                initial_volume_ul=initial_volume_ul,
                rate_prior_cv=0.30
            )

            ridge_cv[row_idx, col_idx] = ridge['effective_dose_cv']

    return exposure, effective_dose, volume_fraction, ridge_cv


def plot_evaporation_analysis(save_path=None):
    """Generate comprehensive evaporation analysis figure."""
    # Sample rate
    seed = 42
    sampled_rate = sample_evaporation_rate_from_prior(seed, "plate_default")

    print(f"Generating plots with sampled rate: {sampled_rate:.3f} µL/h")

    # Generate plate data
    time_hours = 48.0
    baseline_dose = 1.0
    exposure, effective_dose, volume_fraction, ridge_cv = generate_plate_data(
        time_hours, baseline_dose, sampled_rate
    )

    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)

    # === 1. Evaporation Exposure Spatial Field ===
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(exposure, cmap='YlOrRd', aspect='auto', interpolation='nearest')
    ax1.set_title(f'Evaporation Exposure Field\n(Deterministic Geometry)', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Column')
    ax1.set_ylabel('Row')
    ax1.set_xticks([0, 5, 11, 17, 23])
    ax1.set_xticklabels(['1', '6', '12', '18', '24'])
    ax1.set_yticks([0, 4, 8, 12, 15])
    ax1.set_yticklabels(['A', 'E', 'I', 'M', 'P'])
    cbar1 = plt.colorbar(im1, ax=ax1)
    cbar1.set_label('Exposure Factor', rotation=270, labelpad=20)

    # Annotate corners
    ax1.text(0, 0, 'A1\n1.50×', ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    ax1.text(23, 0, 'A24\n1.50×', ha='center', va='center', color='white', fontweight='bold', fontsize=8)
    ax1.text(11, 8, 'H12\n1.03×', ha='center', va='center', color='black', fontweight='bold', fontsize=8)

    # === 2. Effective Dose Amplification ===
    ax2 = fig.add_subplot(gs[0, 1])
    # Convert to percent increase
    dose_increase_pct = (effective_dose - 1.0) * 100
    im2 = ax2.imshow(dose_increase_pct, cmap='RdYlBu_r', aspect='auto', interpolation='nearest',
                     vmin=0, vmax=100)
    ax2.set_title(f'Dose Amplification after {time_hours:.0f}h\n(Modeled Effect)', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Column')
    ax2.set_ylabel('Row')
    ax2.set_xticks([0, 5, 11, 17, 23])
    ax2.set_xticklabels(['1', '6', '12', '18', '24'])
    ax2.set_yticks([0, 4, 8, 12, 15])
    ax2.set_yticklabels(['A', 'E', 'I', 'M', 'P'])
    cbar2 = plt.colorbar(im2, ax=ax2)
    cbar2.set_label('Dose Increase (%)', rotation=270, labelpad=20)

    # Annotate key wells
    ax2.text(0, 0, f'+{dose_increase_pct[0, 0]:.0f}%', ha='center', va='center',
             color='white', fontweight='bold', fontsize=8)
    ax2.text(23, 0, f'+{dose_increase_pct[0, 23]:.0f}%', ha='center', va='center',
             color='white', fontweight='bold', fontsize=8)
    ax2.text(11, 8, f'+{dose_increase_pct[8, 11]:.0f}%', ha='center', va='center',
             color='black', fontweight='bold', fontsize=8)

    # === 3. Cross-Section (Row H, middle) ===
    ax3 = fig.add_subplot(gs[1, :])
    row_h_idx = 7  # Row H (0-indexed)
    row_h_exposure = exposure[row_h_idx, :]
    row_h_dose_pct = dose_increase_pct[row_h_idx, :]

    cols = np.arange(1, 25)
    ax3_twin = ax3.twinx()

    line1 = ax3.plot(cols, row_h_exposure, 'o-', color='orangered', linewidth=2,
                     markersize=4, label='Exposure Factor')
    line2 = ax3_twin.plot(cols, row_h_dose_pct, 's-', color='steelblue', linewidth=2,
                          markersize=4, label='Dose Increase (%)')

    ax3.set_xlabel('Column Number', fontsize=11)
    ax3.set_ylabel('Evaporation Exposure Factor', fontsize=11, color='orangered')
    ax3_twin.set_ylabel('Dose Increase (%)', fontsize=11, color='steelblue')
    ax3.set_title(f'Cross-Section: Row H (Middle Row)\nShowing Edge-to-Center Gradient',
                  fontsize=12, fontweight='bold')
    ax3.tick_params(axis='y', labelcolor='orangered')
    ax3_twin.tick_params(axis='y', labelcolor='steelblue')
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, 25)
    ax3.set_ylim(0.9, 1.6)
    ax3_twin.set_ylim(0, 110)

    # Combine legends
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, loc='upper center', ncol=2, framealpha=0.9)

    # === 4. Variance Decomposition (Well Comparison) ===
    ax4 = fig.add_subplot(gs[2, 0])

    # Compare A1 (corner) vs H12 (center)
    a1_dose = effective_dose[0, 0] * baseline_dose
    h12_dose = effective_dose[7, 11] * baseline_dose

    delta_modeled = a1_dose - h12_dose
    aleatoric_cv = 0.03  # 3% pipetting variation
    epistemic_cv = np.mean([ridge_cv[0, 0], ridge_cv[7, 11]])  # Average ridge

    # Uncertainties (convert CV to absolute)
    aleatoric_sd = baseline_dose * aleatoric_cv * np.sqrt(2)  # Combined for difference
    epistemic_sd = baseline_dose * epistemic_cv * np.sqrt(2)

    categories = ['Modeled\nDifference', 'Aleatoric\nUncertainty', 'Epistemic\nUncertainty']
    values = [delta_modeled, aleatoric_sd, epistemic_sd]
    colors = ['steelblue', 'lightcoral', 'mediumpurple']

    bars = ax4.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    ax4.set_ylabel('Magnitude (µM)', fontsize=11)
    ax4.set_title('Variance Decomposition: A1 vs H12\n(Corner vs Center)',
                  fontsize=12, fontweight='bold')
    ax4.grid(True, axis='y', alpha=0.3)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.3f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Add percentages
    total_variance = aleatoric_sd**2 + epistemic_sd**2
    aleatoric_pct = 100 * aleatoric_sd**2 / total_variance
    epistemic_pct = 100 * epistemic_sd**2 / total_variance

    ax4.text(1, aleatoric_sd * 0.5, f'{aleatoric_pct:.1f}%\nof variance',
             ha='center', va='center', fontsize=9, style='italic')
    ax4.text(2, epistemic_sd * 0.5, f'{epistemic_pct:.1f}%\nof variance',
             ha='center', va='center', fontsize=9, style='italic')

    # === 5. Ridge Uncertainty Heatmap ===
    ax5 = fig.add_subplot(gs[2, 1])
    # Convert to percentage
    ridge_cv_pct = ridge_cv * 100
    im5 = ax5.imshow(ridge_cv_pct, cmap='Purples', aspect='auto', interpolation='nearest',
                     vmin=0, vmax=60)
    ax5.set_title(f'Epistemic Uncertainty (Ridge)\n(Calibration Uncertainty from Rate Prior)',
                  fontsize=12, fontweight='bold')
    ax5.set_xlabel('Column')
    ax5.set_ylabel('Row')
    ax5.set_xticks([0, 5, 11, 17, 23])
    ax5.set_xticklabels(['1', '6', '12', '18', '24'])
    ax5.set_yticks([0, 4, 8, 12, 15])
    ax5.set_yticklabels(['A', 'E', 'I', 'M', 'P'])
    cbar5 = plt.colorbar(im5, ax=ax5)
    cbar5.set_label('Ridge CV (%)', rotation=270, labelpad=20)

    # Add text box
    textstr = f'Sampled rate: {sampled_rate:.3f} µL/h\\nRate prior CV: 30%\\nTime: {time_hours:.0f}h'
    ax5.text(0.02, 0.98, textstr, transform=ax5.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # Overall title
    fig.suptitle('Evaporation Variance Analysis: Spatial Gradient and Uncertainty Decomposition',
                 fontsize=16, fontweight='bold', y=0.98)

    # Add footer
    footer_text = (
        f'Corner (A1): +{dose_increase_pct[0, 0]:.0f}% dose | '
        f'Center (H12): +{dose_increase_pct[8, 11]:.0f}% dose | '
        f'Difference: +{(dose_increase_pct[0, 0] - dose_increase_pct[8, 11]):.0f}% | '
        f'Ridge CV: {epistemic_cv:.1%}'
    )
    fig.text(0.5, 0.01, footer_text, ha='center', fontsize=10, style='italic',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to: {save_path}")
    else:
        plt.savefig('/Users/bjh/cell_OS/evaporation_variance_analysis.png', dpi=300, bbox_inches='tight')
        print("Saved to: /Users/bjh/cell_OS/evaporation_variance_analysis.png")

    plt.show()

    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Evaporation exposure range:    {exposure.min():.3f} - {exposure.max():.3f}×")
    print(f"Dose amplification range:      +{dose_increase_pct.min():.1f}% - +{dose_increase_pct.max():.1f}%")
    print(f"Ridge uncertainty range:       {ridge_cv_pct.min():.1f}% - {ridge_cv_pct.max():.1f}% CV")
    print(f"\nCorner (A1) vs Center (H12):")
    print(f"  Delta modeled:               {delta_modeled:+.3f} µM ({(delta_modeled/baseline_dose)*100:+.1f}%)")
    print(f"  Aleatoric uncertainty:       ±{aleatoric_sd:.3f} µM ({aleatoric_pct:.1f}% of variance)")
    print(f"  Epistemic uncertainty:       ±{epistemic_sd:.3f} µM ({epistemic_pct:.1f}% of variance)")
    print(f"  Z-score (vs aleatoric):      {delta_modeled/aleatoric_sd:.2f}×")
    print("="*80)


if __name__ == "__main__":
    plot_evaporation_analysis()
