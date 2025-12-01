#!/usr/bin/env python3
"""
Simple POSH Experiment Simulation
==================================

Simulates a basic POSH screen with:
- U2OS cells
- 1000 gRNA library (targeting ~250 genes, 4 guides each)
- One stressor (e.g., Tunicamycin) at one concentration vs vehicle control
- Cell Painting readout
- DINO embedding analysis for phenotype clustering

This is a minimal end-to-end example for testing the POSH workflow.
"""

import numpy as np
import pandas as pd
import os
from typing import List, Tuple

# Set random seed for reproducibility
np.random.seed(42)


def generate_grna_library(n_genes: int = 250, guides_per_gene: int = 4) -> pd.DataFrame:
    """Generate a synthetic gRNA library.
    
    Parameters
    ----------
    n_genes : int
        Number of genes to target (default: 250)
    guides_per_gene : int
        Number of guides per gene (default: 4)
    
    Returns
    -------
    library : pd.DataFrame
        Library with columns: gene, guide_id, target_sequence
    """
    print(f"\n📚 Generating gRNA library: {n_genes} genes × {guides_per_gene} guides = {n_genes * guides_per_gene} gRNAs")
    
    # Generate gene names (using common cancer-related genes + synthetic ones)
    common_genes = [
        "TP53", "KRAS", "EGFR", "PTEN", "AKT1", "PIK3CA", "BRAF", "NRAS", "MYC", "CDKN2A",
        "RB1", "ATM", "BRCA1", "BRCA2", "MDM2", "ERBB2", "FGFR1", "MET", "ALK", "RET",
        "NOTCH1", "CTNNB1", "APC", "SMAD4", "VHL", "TSC1", "TSC2", "NF1", "NF2", "PBRM1",
    ]
    
    # Extend with synthetic gene names if needed
    all_genes = common_genes[:n_genes]
    if len(all_genes) < n_genes:
        all_genes.extend([f"GENE{i:04d}" for i in range(1, n_genes - len(all_genes) + 1)])
    
    # Generate library
    library_data = []
    for gene in all_genes:
        for guide_num in range(1, guides_per_gene + 1):
            guide_id = f"{gene}_g{guide_num}"
            # Generate random 20bp target sequence
            target_seq = ''.join(np.random.choice(['A', 'C', 'G', 'T'], 20))
            library_data.append({
                'gene': gene,
                'guide_id': guide_id,
                'target_sequence': target_seq
            })
    
    library = pd.DataFrame(library_data)
    print(f"   ✓ Library generated: {len(library)} gRNAs targeting {n_genes} genes")
    return library


def design_plate_layout(library: pd.DataFrame, 
                        n_replicates: int = 3,
                        include_controls: bool = True) -> pd.DataFrame:
    """Design 384-well plate layout for the screen.
    
    Parameters
    ----------
    library : pd.DataFrame
        gRNA library
    n_replicates : int
        Technical replicates per guide (default: 3)
    include_controls : bool
        Include non-targeting controls (default: True)
    
    Returns
    -------
    plate_layout : pd.DataFrame
        Plate layout with columns: well, row, col, gene, guide_id, condition
    """
    print(f"\n🧪 Designing plate layout: {n_replicates} replicates per guide")
    
    # Calculate wells needed
    n_guides = len(library)
    wells_per_condition = n_guides * n_replicates
    
    # Add controls (non-targeting)
    if include_controls:
        n_controls = 32  # 32 control wells per condition
        wells_per_condition += n_controls
    
    total_wells = wells_per_condition * 2  # 2 conditions: stressor + vehicle
    
    print(f"   Wells per condition: {wells_per_condition}")
    print(f"   Total wells needed: {total_wells}")
    
    # Check if fits in 384-well plates
    wells_per_plate = 384
    n_plates = int(np.ceil(total_wells / wells_per_plate))
    print(f"   Plates required: {n_plates} × 384-well plates")
    
    # Generate plate layout
    layout_data = []
    well_idx = 0
    
    # Helper to convert well index to row/col
    def well_to_rowcol(idx):
        row = idx // 24  # 24 columns in 384-well
        col = idx % 24
        row_letter = chr(ord('A') + row)
        return f"{row_letter}{col+1:02d}", row_letter, col + 1
    
    # Add library guides for both conditions
    for condition in ['Stressor', 'Vehicle']:
        for _, row in library.iterrows():
            for rep in range(1, n_replicates + 1):
                well, row_letter, col = well_to_rowcol(well_idx)
                layout_data.append({
                    'well': well,
                    'row': row_letter,
                    'col': col,
                    'plate': (well_idx // wells_per_plate) + 1,
                    'gene': row['gene'],
                    'guide_id': row['guide_id'],
                    'replicate': rep,
                    'condition': condition,
                    'is_control': False
                })
                well_idx += 1
        
        # Add controls
        if include_controls:
            for ctrl_num in range(n_controls):
                well, row_letter, col = well_to_rowcol(well_idx)
                layout_data.append({
                    'well': well,
                    'row': row_letter,
                    'col': col,
                    'plate': (well_idx // wells_per_plate) + 1,
                    'gene': 'NTC',  # Non-targeting control
                    'guide_id': f'NTC_{ctrl_num+1:03d}',
                    'replicate': (ctrl_num % 3) + 1,
                    'condition': condition,
                    'is_control': True
                })
                well_idx += 1
    
    plate_layout = pd.DataFrame(layout_data)
    print(f"   ✓ Layout designed: {len(plate_layout)} wells across {n_plates} plates")
    return plate_layout


def simulate_cell_painting(plate_layout: pd.DataFrame,
                           stressor_name: str = "Tunicamycin",
                           stressor_conc: float = 2.5) -> pd.DataFrame:
    """Simulate Cell Painting imaging and feature extraction.
    
    Parameters
    ----------
    plate_layout : pd.DataFrame
        Plate layout
    stressor_name : str
        Name of the stressor (default: "Tunicamycin")
    stressor_conc : float
        Stressor concentration in µM (default: 2.5)
    
    Returns
    -------
    imaging_data : pd.DataFrame
        Imaging data with Cell Painting features
    """
    print(f"\n🔬 Simulating Cell Painting readout")
    print(f"   Stressor: {stressor_name} @ {stressor_conc} µM")
    print(f"   Channels: DNA, ER, Actin, Mitochondria, AGP")
    
    # Simulate Cell Painting features (simplified)
    # In reality, CellProfiler would extract ~1000 features per cell
    imaging_data = []
    
    for _, well in plate_layout.iterrows():
        # Base phenotype (vehicle control)
        base_features = np.random.randn(50)  # 50 simplified features
        
        # Add gene-specific effect
        if well['gene'] != 'NTC':
            gene_seed = sum(ord(c) for c in well['gene'])
            np.random.seed(gene_seed)
            gene_effect = np.random.randn(50) * 0.3  # Gene-specific shift
        else:
            gene_effect = np.zeros(50)
        
        # Add stressor effect
        if well['condition'] == 'Stressor':
            # ER stress signature (affects specific features)
            stressor_effect = np.zeros(50)
            stressor_effect[10:20] += np.random.randn(10) * 0.5  # ER features
            stressor_effect[20:30] += np.random.randn(10) * 0.3  # Mitochondria
        else:
            stressor_effect = np.zeros(50)
        
        # Combine effects
        features = base_features + gene_effect + stressor_effect
        
        # Simulate cell count and viability
        cell_count = int(np.random.normal(500, 50))
        viability = np.clip(np.random.normal(0.95, 0.05), 0.5, 1.0)
        
        # If stressor, reduce viability for sensitive genes
        if well['condition'] == 'Stressor' and well['gene'] in ['TP53', 'ATM', 'BRCA1']:
            viability *= 0.7
        
        imaging_data.append({
            'well': well['well'],
            'plate': well['plate'],
            'gene': well['gene'],
            'guide_id': well['guide_id'],
            'condition': well['condition'],
            'replicate': well['replicate'],
            'cell_count': cell_count,
            'viability': viability,
            'features': features.tolist(),  # Cell Painting features
        })
    
    imaging_df = pd.DataFrame(imaging_data)
    print(f"   ✓ Imaging complete: {len(imaging_df)} wells imaged")
    print(f"   Average cells/well: {imaging_df['cell_count'].mean():.0f}")
    print(f"   Average viability: {imaging_df['viability'].mean():.2%}")
    
    return imaging_df


def generate_dino_embeddings(imaging_data: pd.DataFrame,
                             embedding_dim: int = 384) -> pd.DataFrame:
    """Generate DINO embeddings from Cell Painting features.
    
    In a real workflow, this would:
    1. Take raw images
    2. Run through DINO vision transformer
    3. Extract embeddings from [CLS] token
    
    Here we simulate by:
    1. Taking Cell Painting features
    2. Projecting to DINO-like embedding space
    
    Parameters
    ----------
    imaging_data : pd.DataFrame
        Imaging data with Cell Painting features
    embedding_dim : int
        DINO embedding dimension (default: 384 for ViT-S)
    
    Returns
    -------
    embeddings_df : pd.DataFrame
        Data with DINO embeddings added
    """
    print(f"\n🤖 Generating DINO embeddings (dim={embedding_dim})")
    print(f"   Simulating ViT-S/16 vision transformer...")
    
    embeddings_data = []
    
    for _, row in imaging_data.iterrows():
        # Simulate DINO embedding from Cell Painting features
        # In reality: image → DINO → embedding
        # Here: features → random projection → embedding
        
        features = np.array(row['features'])
        
        # Random projection to DINO space (simplified)
        np.random.seed(sum(ord(c) for c in row['gene']))
        projection_matrix = np.random.randn(len(features), embedding_dim) * 0.1
        dino_embedding = features @ projection_matrix
        
        # Normalize (DINO embeddings are typically normalized)
        dino_embedding = dino_embedding / (np.linalg.norm(dino_embedding) + 1e-9)
        
        embeddings_data.append({
            'well': row['well'],
            'gene': row['gene'],
            'guide_id': row['guide_id'],
            'condition': row['condition'],
            'replicate': row['replicate'],
            'viability': row['viability'],
            'cell_count': row['cell_count'],
            'dino_embedding': dino_embedding.tolist(),
        })
    
    embeddings_df = pd.DataFrame(embeddings_data)
    print(f"   ✓ DINO embeddings generated: {len(embeddings_df)} wells")
    
    return embeddings_df


def analyze_phenotypes(embeddings_df: pd.DataFrame,
                      top_n: int = 50) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Analyze phenotypes and identify hits.
    
    Parameters
    ----------
    embeddings_df : pd.DataFrame
        Data with DINO embeddings
    top_n : int
        Number of top hits to return (default: 50)
    
    Returns
    -------
    gene_summary : pd.DataFrame
        Per-gene summary statistics
    top_hits : pd.DataFrame
        Top N hits ranked by phenotypic shift
    """
    print(f"\n📊 Analyzing phenotypes and identifying hits")
    
    # Calculate per-gene statistics
    gene_stats = []
    
    # Get control (NTC) centroid for each condition
    ntc_stressor = embeddings_df[
        (embeddings_df['gene'] == 'NTC') & 
        (embeddings_df['condition'] == 'Stressor')
    ]
    ntc_vehicle = embeddings_df[
        (embeddings_df['gene'] == 'NTC') & 
        (embeddings_df['condition'] == 'Vehicle')
    ]
    
    # Calculate centroids
    ntc_stressor_centroid = np.mean([
        np.array(emb) for emb in ntc_stressor['dino_embedding']
    ], axis=0)
    
    ntc_vehicle_centroid = np.mean([
        np.array(emb) for emb in ntc_vehicle['dino_embedding']
    ], axis=0)
    
    # Analyze each gene
    genes = embeddings_df[embeddings_df['gene'] != 'NTC']['gene'].unique()
    
    for gene in genes:
        gene_data = embeddings_df[embeddings_df['gene'] == gene]
        
        # Separate by condition
        stressor_data = gene_data[gene_data['condition'] == 'Stressor']
        vehicle_data = gene_data[gene_data['condition'] == 'Vehicle']
        
        # Calculate mean embeddings
        stressor_emb = np.mean([np.array(e) for e in stressor_data['dino_embedding']], axis=0)
        vehicle_emb = np.mean([np.array(e) for e in vehicle_data['dino_embedding']], axis=0)
        
        # Calculate distances
        dist_stressor_to_ntc = np.linalg.norm(stressor_emb - ntc_stressor_centroid)
        dist_vehicle_to_ntc = np.linalg.norm(vehicle_emb - ntc_vehicle_centroid)
        
        # Phenotypic shift = how much the gene moves away from control
        phenotypic_shift = dist_stressor_to_ntc - dist_vehicle_to_ntc
        
        # Viability metrics
        mean_viability_stressor = stressor_data['viability'].mean()
        mean_viability_vehicle = vehicle_data['viability'].mean()
        viability_drop = mean_viability_vehicle - mean_viability_stressor
        
        gene_stats.append({
            'gene': gene,
            'phenotypic_shift': phenotypic_shift,
            'dist_stressor_to_ntc': dist_stressor_to_ntc,
            'dist_vehicle_to_ntc': dist_vehicle_to_ntc,
            'viability_stressor': mean_viability_stressor,
            'viability_vehicle': mean_viability_vehicle,
            'viability_drop': viability_drop,
            'n_guides': len(gene_data['guide_id'].unique()),
            'n_replicates': len(gene_data),
        })
    
    gene_summary = pd.DataFrame(gene_stats)
    gene_summary = gene_summary.sort_values('phenotypic_shift', ascending=False)
    
    # Get top hits
    top_hits = gene_summary.head(top_n)
    
    print(f"   ✓ Analyzed {len(genes)} genes")
    print(f"   Top {top_n} hits identified")
    print(f"\n   Top 10 hits by phenotypic shift:")
    for i, row in top_hits.head(10).iterrows():
        print(f"      {row['gene']:10s} | shift: {row['phenotypic_shift']:+.3f} | "
              f"viability drop: {row['viability_drop']:+.2%}")
    
    return gene_summary, top_hits


def main():
    """Run the complete POSH experiment simulation."""
    print("=" * 80)
    print("SIMPLE POSH EXPERIMENT SIMULATION")
    print("=" * 80)
    print("\nExperiment Design:")
    print("  • Cell line: U2OS")
    print("  • Library: 1000 gRNAs (250 genes × 4 guides)")
    print("  • Conditions: Tunicamycin 2.5 µM vs Vehicle")
    print("  • Replicates: 3 technical replicates per guide")
    print("  • Readout: Cell Painting → DINO embeddings")
    print("  • Analysis: Phenotypic shift from control")
    
    # Create output directory
    output_dir = "results/posh_simple_demo"
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Generate library
    library = generate_grna_library(n_genes=250, guides_per_gene=4)
    library.to_csv(f"{output_dir}/grna_library.csv", index=False)
    
    # Step 2: Design plate layout
    plate_layout = design_plate_layout(library, n_replicates=3)
    plate_layout.to_csv(f"{output_dir}/plate_layout.csv", index=False)
    
    # Step 3: Simulate Cell Painting
    imaging_data = simulate_cell_painting(plate_layout, 
                                         stressor_name="Tunicamycin",
                                         stressor_conc=2.5)
    imaging_data.to_csv(f"{output_dir}/cell_painting_data.csv", index=False)
    
    # Step 4: Generate DINO embeddings
    embeddings_df = generate_dino_embeddings(imaging_data, embedding_dim=384)
    embeddings_df.to_csv(f"{output_dir}/dino_embeddings.csv", index=False)
    
    # Step 5: Analyze phenotypes
    gene_summary, top_hits = analyze_phenotypes(embeddings_df, top_n=50)
    gene_summary.to_csv(f"{output_dir}/gene_summary.csv", index=False)
    top_hits.to_csv(f"{output_dir}/top_hits.csv", index=False)
    
    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE!")
    print("=" * 80)
    print(f"\nResults saved to: {output_dir}/")
    print("\nOutput files:")
    print(f"  • grna_library.csv       - 1000 gRNA library")
    print(f"  • plate_layout.csv       - 384-well plate design")
    print(f"  • cell_painting_data.csv - Cell Painting features")
    print(f"  • dino_embeddings.csv    - DINO embeddings (384-dim)")
    print(f"  • gene_summary.csv       - Per-gene statistics")
    print(f"  • top_hits.csv           - Top 50 hits")
    
    print("\n📊 Quick Stats:")
    print(f"  • Total wells: {len(plate_layout)}")
    print(f"  • Genes screened: {len(gene_summary)}")
    print(f"  • Top hit: {top_hits.iloc[0]['gene']} (shift: {top_hits.iloc[0]['phenotypic_shift']:.3f})")
    
    return output_dir


if __name__ == "__main__":
    output_dir = main()
    print(f"\n✅ Done! View results: ls -lh {output_dir}/")
