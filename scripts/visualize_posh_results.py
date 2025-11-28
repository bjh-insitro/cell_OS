#!/usr/bin/env python3
"""
Visualize POSH Experiment Results
==================================

Creates summary plots and statistics from the simple POSH demo.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


def load_results(results_dir: str = "results/posh_simple_demo"):
    """Load all result files."""
    print(f"Loading results from: {results_dir}")
    
    data = {}
    data['library'] = pd.read_csv(f"{results_dir}/grna_library.csv")
    data['layout'] = pd.read_csv(f"{results_dir}/plate_layout.csv")
    data['imaging'] = pd.read_csv(f"{results_dir}/cell_painting_data.csv")
    data['embeddings'] = pd.read_csv(f"{results_dir}/dino_embeddings.csv")
    data['gene_summary'] = pd.read_csv(f"{results_dir}/gene_summary.csv")
    data['top_hits'] = pd.read_csv(f"{results_dir}/top_hits.csv")
    
    print(f"✓ Loaded {len(data)} result files")
    return data


def print_summary_stats(data):
    """Print summary statistics."""
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)
    
    print(f"\n📚 Library:")
    print(f"  • Total gRNAs: {len(data['library'])}")
    print(f"  • Genes targeted: {data['library']['gene'].nunique()}")
    print(f"  • Guides per gene: {len(data['library']) / data['library']['gene'].nunique():.1f}")
    
    print(f"\n🧪 Plate Layout:")
    print(f"  • Total wells: {len(data['layout'])}")
    print(f"  • Plates: {data['layout']['plate'].nunique()}")
    print(f"  • Conditions: {', '.join(data['layout']['condition'].unique())}")
    print(f"  • Controls: {data['layout']['is_control'].sum()} wells")
    
    print(f"\n🔬 Imaging:")
    print(f"  • Wells imaged: {len(data['imaging'])}")
    print(f"  • Mean cells/well: {data['imaging']['cell_count'].mean():.0f}")
    print(f"  • Mean viability: {data['imaging']['viability'].mean():.2%}")
    
    # Viability by condition
    for condition in data['imaging']['condition'].unique():
        cond_data = data['imaging'][data['imaging']['condition'] == condition]
        print(f"    - {condition}: {cond_data['viability'].mean():.2%}")
    
    print(f"\n🎯 Hits:")
    print(f"  • Genes analyzed: {len(data['gene_summary'])}")
    print(f"  • Top hits: {len(data['top_hits'])}")
    
    # Top 5 hits
    print(f"\n  Top 5 hits:")
    for i, row in data['top_hits'].head(5).iterrows():
        print(f"    {i+1}. {row['gene']:10s} | "
              f"shift: {row['phenotypic_shift']:+.4f} | "
              f"viability drop: {row['viability_drop']:+.2%}")


def create_visualizations(data, output_dir: str = "results/posh_simple_demo"):
    """Create summary visualizations."""
    print(f"\n📊 Creating visualizations...")
    
    fig_dir = Path(output_dir) / "figures"
    fig_dir.mkdir(exist_ok=True)
    
    # 1. Phenotypic shift distribution
    plt.figure(figsize=(10, 6))
    plt.hist(data['gene_summary']['phenotypic_shift'], bins=50, edgecolor='black', alpha=0.7)
    plt.axvline(data['gene_summary']['phenotypic_shift'].median(), 
                color='red', linestyle='--', label='Median')
    plt.xlabel('Phenotypic Shift', fontsize=12)
    plt.ylabel('Number of Genes', fontsize=12)
    plt.title('Distribution of Phenotypic Shifts', fontsize=14, fontweight='bold')
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "phenotypic_shift_distribution.png", dpi=300)
    print(f"  ✓ Saved: phenotypic_shift_distribution.png")
    plt.close()
    
    # 2. Viability vs Phenotypic Shift
    plt.figure(figsize=(10, 6))
    plt.scatter(data['gene_summary']['viability_drop'], 
                data['gene_summary']['phenotypic_shift'],
                alpha=0.5, s=50)
    
    # Highlight top hits
    top_genes = data['top_hits']['gene'].values[:10]
    top_data = data['gene_summary'][data['gene_summary']['gene'].isin(top_genes)]
    plt.scatter(top_data['viability_drop'], 
                top_data['phenotypic_shift'],
                color='red', s=100, alpha=0.7, label='Top 10 Hits')
    
    # Annotate top 3
    for _, row in top_data.head(3).iterrows():
        plt.annotate(row['gene'], 
                    (row['viability_drop'], row['phenotypic_shift']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=9, fontweight='bold')
    
    plt.xlabel('Viability Drop (Vehicle → Stressor)', fontsize=12)
    plt.ylabel('Phenotypic Shift', fontsize=12)
    plt.title('Viability vs Phenotypic Shift', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(fig_dir / "viability_vs_shift.png", dpi=300)
    print(f"  ✓ Saved: viability_vs_shift.png")
    plt.close()
    
    # 3. Top 20 hits bar chart
    plt.figure(figsize=(12, 6))
    top_20 = data['top_hits'].head(20)
    colors = ['red' if i < 5 else 'steelblue' for i in range(len(top_20))]
    plt.barh(range(len(top_20)), top_20['phenotypic_shift'], color=colors, alpha=0.7)
    plt.yticks(range(len(top_20)), top_20['gene'])
    plt.xlabel('Phenotypic Shift', fontsize=12)
    plt.ylabel('Gene', fontsize=12)
    plt.title('Top 20 Hits by Phenotypic Shift', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(fig_dir / "top_20_hits.png", dpi=300)
    print(f"  ✓ Saved: top_20_hits.png")
    plt.close()
    
    # 4. Plate heatmap (first plate only)
    plt.figure(figsize=(14, 8))
    plate1_data = data['imaging'][data['imaging']['plate'] == 1].copy()
    
    # Create pivot table for viability
    # Convert well to row/col
    plate1_data['row_num'] = plate1_data['well'].str[0].apply(lambda x: ord(x) - ord('A'))
    plate1_data['col_num'] = plate1_data['well'].str[1:].astype(int) - 1
    
    pivot = plate1_data.pivot_table(values='viability', 
                                     index='row_num', 
                                     columns='col_num',
                                     aggfunc='mean')
    
    sns.heatmap(pivot, cmap='RdYlGn', vmin=0.7, vmax=1.0, 
                cbar_kws={'label': 'Viability'}, 
                xticklabels=5, yticklabels=1)
    plt.title('Plate 1 Viability Heatmap', fontsize=14, fontweight='bold')
    plt.xlabel('Column', fontsize=12)
    plt.ylabel('Row', fontsize=12)
    plt.tight_layout()
    plt.savefig(fig_dir / "plate1_viability_heatmap.png", dpi=300)
    print(f"  ✓ Saved: plate1_viability_heatmap.png")
    plt.close()
    
    print(f"\n✅ All visualizations saved to: {fig_dir}/")


def main():
    """Main function."""
    results_dir = "results/posh_simple_demo"
    
    # Load results
    data = load_results(results_dir)
    
    # Print summary
    print_summary_stats(data)
    
    # Create visualizations
    create_visualizations(data, results_dir)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
