#!/usr/bin/env python3
"""Compare acquisition profiles across a POSH campaign.

Runs the demo with all 4 profiles and generates comparison visualizations.
"""

import subprocess
import pandas as pd
from pathlib import Path

# Try to import plotting libraries
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOTTING = True
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (14, 10)
except ImportError:
    HAS_PLOTTING = False
    print("Note: matplotlib/seaborn not installed. Skipping visualizations.")
    print("Install with: pip install matplotlib seaborn")

PROFILES = ["balanced", "ambitious_postdoc", "cautious_operator", "wise_pi"]
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def run_profile(profile_name: str) -> pd.DataFrame:
    """Run demo with specified profile and return results."""
    print(f"\n{'='*60}")
    print(f"Running profile: {profile_name}")
    print(f"{'='*60}")
    
    # Run demo
    result = subprocess.run(
        ["venv/bin/python", "scripts/run_posh_campaign_demo.py", "--profile", profile_name],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"Error running {profile_name}: {result.stderr}")
        return pd.DataFrame()
    
    # Read results
    df = pd.read_csv("results/posh_demo_hits.csv")
    return df


def plot_comparisons(all_results: dict):
    """Generate comparison plots."""
    if not HAS_PLOTTING:
        print("Skipping plots (matplotlib not available)")
        return None
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Distance to centroid comparison
    ax = axes[0, 0]
    for profile, df in all_results.items():
        if not df.empty:
            ax.plot(range(1, len(df) + 1), df['distance_to_centroid'], 
                   marker='o', label=profile, linewidth=2)
    ax.set_xlabel('Gene Rank', fontsize=12)
    ax.set_ylabel('Distance to Centroid', fontsize=12)
    ax.set_title('Phenotypic Shift by Profile', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Viability comparison
    ax = axes[0, 1]
    for profile, df in all_results.items():
        if not df.empty:
            ax.plot(range(1, len(df) + 1), df['phenotype_score'], 
                   marker='s', label=profile, linewidth=2)
    ax.set_xlabel('Gene Rank', fontsize=12)
    ax.set_ylabel('Phenotype Score (Viability)', fontsize=12)
    ax.set_title('Viability by Profile', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Distance vs Viability scatter
    ax = axes[1, 0]
    for profile, df in all_results.items():
        if not df.empty:
            ax.scatter(df['phenotype_score'], df['distance_to_centroid'], 
                      label=profile, alpha=0.6, s=100)
    ax.set_xlabel('Phenotype Score (Viability)', fontsize=12)
    ax.set_ylabel('Distance to Centroid', fontsize=12)
    ax.set_title('Diversity vs Viability Trade-off', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Top 5 genes per profile
    ax = axes[1, 1]
    top_genes = {}
    for profile, df in all_results.items():
        if not df.empty:
            top_genes[profile] = df.head(5)['gene'].tolist()
    
    # Create text summary
    ax.axis('off')
    y_pos = 0.95
    ax.text(0.5, y_pos, 'Top 5 Hits by Profile', 
           ha='center', fontsize=14, fontweight='bold')
    y_pos -= 0.12
    
    for profile, genes in top_genes.items():
        ax.text(0.05, y_pos, f"{profile}:", fontsize=11, fontweight='bold')
        y_pos -= 0.08
        for i, gene in enumerate(genes, 1):
            ax.text(0.15, y_pos, f"{i}. {gene}", fontsize=10)
            y_pos -= 0.06
        y_pos -= 0.02
    
    plt.tight_layout()
    output_path = RESULTS_DIR / "profile_comparison.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved comparison plot to: {output_path}")
    
    return output_path


def generate_summary_table(all_results: dict) -> pd.DataFrame:
    """Generate summary statistics table."""
    summary_data = []
    
    for profile, df in all_results.items():
        if not df.empty:
            summary_data.append({
                'Profile': profile,
                'N Genes': len(df),
                'Mean Distance': df['distance_to_centroid'].mean(),
                'Mean Viability': df['phenotype_score'].mean(),
                'Max Distance': df['distance_to_centroid'].max(),
                'Min Viability': df['phenotype_score'].min(),
            })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df = summary_df.round(3)
    
    # Save to CSV
    output_path = RESULTS_DIR / "profile_summary.csv"
    summary_df.to_csv(output_path, index=False)
    print(f"✓ Saved summary table to: {output_path}")
    
    return summary_df


def main():
    """Run all profiles and generate comparisons."""
    print("=" * 60)
    print("Acquisition Profile Comparison")
    print("=" * 60)
    
    all_results = {}
    
    # Run each profile
    for profile in PROFILES:
        df = run_profile(profile)
        if not df.empty:
            all_results[profile] = df
    
    if not all_results:
        print("\n❌ No results generated. Check for errors above.")
        return
    
    # Generate visualizations
    print("\n" + "=" * 60)
    print("Generating Comparisons")
    print("=" * 60)
    
    plot_comparisons(all_results)
    summary_df = generate_summary_table(all_results)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)
    print(summary_df.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("Comparison Complete!")
    print("=" * 60)
    print(f"\nView results:")
    print(f"  - Plot: results/profile_comparison.png")
    print(f"  - Table: results/profile_summary.csv")
    print(f"  - Raw data: results/posh_demo_hits.csv")


if __name__ == "__main__":
    main()
