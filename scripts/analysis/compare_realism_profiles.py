"""
Compare edge sensitivity across clean, realistic, and hostile profiles.

Loads summary JSONs and creates comparison plots.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def load_summaries(results_dir: Path, design: str = 'dmso_only'):
    """Load summary JSONs for all three profiles."""
    profiles = ['clean', 'realistic', 'hostile']
    summaries = {}

    for profile in profiles:
        summary_path = results_dir / f"{profile}_{design}_summary.json"
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                summaries[profile] = json.load(f)
        else:
            print(f"Warning: {summary_path} not found")

    return summaries


def plot_edge_sensitivity_comparison(summaries, output_path: Path):
    """Plot edge sensitivity across profiles and channels."""
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    profiles = ['clean', 'realistic', 'hostile']
    colors = ['#4daf4a', '#ff7f00', '#e41a1c']  # green, orange, red

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(channels))
    width = 0.25

    for i, (profile, color) in enumerate(zip(profiles, colors)):
        if profile not in summaries:
            continue

        edge_sens = summaries[profile]['edge_sensitivity_per_channel']
        values = [edge_sens[ch] for ch in channels]

        offset = (i - 1) * width
        ax.bar(x + offset, values, width, label=profile.capitalize(), color=color, alpha=0.8)

    ax.set_xlabel('Channel', fontsize=12, fontweight='bold')
    ax.set_ylabel('Edge Sensitivity (correlation)', fontsize=12, fontweight='bold')
    ax.set_title('Vignetting Strength by Profile (DMSO-only plate)\nNegative = dimmer edges',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(channels)
    ax.axhline(0, color='black', linewidth=0.8, linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    ax.grid(True, alpha=0.3, axis='y')

    # Add annotation about design constraint
    ax.text(0.02, 0.98, 'Note: edge_sensitivity undefined for mixed designs',
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"Saved: {output_path}")


def plot_outlier_comparison(summaries, output_path: Path):
    """Plot outlier rates across profiles."""
    profiles = ['clean', 'realistic', 'hostile']
    colors = ['#4daf4a', '#ff7f00', '#e41a1c']

    outlier_rates = []
    profile_labels = []

    for profile in profiles:
        if profile in summaries:
            outlier_rates.append(summaries[profile]['outlier_rate_observed'] * 100)
            profile_labels.append(profile.capitalize())

    fig, ax = plt.subplots(figsize=(8, 6))

    bars = ax.bar(profile_labels, outlier_rates, color=colors, alpha=0.8, width=0.6)

    # Add value labels on bars
    for bar, rate in zip(bars, outlier_rates):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.2f}%',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Outlier Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Detector Pathology Rate by Profile\n(noise spikes, focus misses, etc.)',
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"Saved: {output_path}")


def plot_edge_vs_center_heatmap(summaries, output_path: Path):
    """Plot edge vs center delta as a heatmap."""
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    profiles = ['clean', 'realistic', 'hostile']

    # Compute delta_pct for each profile × channel
    data = np.zeros((len(profiles), len(channels)))

    for i, profile in enumerate(profiles):
        if profile not in summaries:
            continue

        summary = summaries[profile]
        means_center = summary['channel_means_center']
        means_edge = summary['channel_means_edge']

        for j, ch in enumerate(channels):
            delta_pct = 100 * (means_edge[ch] - means_center[ch]) / means_center[ch]
            data[i, j] = delta_pct

    fig, ax = plt.subplots(figsize=(8, 6))

    im = ax.imshow(data, cmap='RdBu_r', aspect='auto', vmin=-20, vmax=20)

    ax.set_xticks(np.arange(len(channels)))
    ax.set_yticks(np.arange(len(profiles)))
    ax.set_xticklabels(channels)
    ax.set_yticklabels([p.capitalize() for p in profiles])

    # Add text annotations
    for i in range(len(profiles)):
        for j in range(len(channels)):
            text = ax.text(j, i, f'{data[i, j]:.1f}%',
                          ha="center", va="center", color="black", fontsize=10)

    ax.set_title('Edge vs Center Intensity Delta (%)\nNegative = dimmer edges (vignetting)',
                 fontsize=14, fontweight='bold')
    ax.set_xlabel('Channel', fontsize=12, fontweight='bold')
    ax.set_ylabel('Profile', fontsize=12, fontweight='bold')

    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Δ Intensity (%)', fontsize=11, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"Saved: {output_path}")


def main():
    results_dir = Path(__file__).parent.parent / "results" / "realism_profiles"

    if not results_dir.exists():
        print(f"Error: {results_dir} does not exist")
        print("Run demo_realism_profiles.py first to generate data")
        return

    # Load summaries
    print("Loading summaries...")
    summaries = load_summaries(results_dir, design='dmso_only')

    if not summaries:
        print("No summary files found!")
        return

    print(f"Loaded {len(summaries)} profiles: {list(summaries.keys())}")

    # Create plots
    plots_dir = results_dir / "comparison_plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    print("\nGenerating comparison plots...")
    plot_edge_sensitivity_comparison(summaries, plots_dir / "edge_sensitivity_comparison.png")
    plot_outlier_comparison(summaries, plots_dir / "outlier_rate_comparison.png")
    plot_edge_vs_center_heatmap(summaries, plots_dir / "edge_delta_heatmap.png")

    print("\nDone!")


if __name__ == '__main__':
    main()
