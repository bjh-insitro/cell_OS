"""Phenotype clustering for POSH screens.

This module provides utilities for clustering genes based on morphological
embeddings and summarizing cluster-level statistics.
"""

from __future__ import annotations
from typing import Dict
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans


def cluster_embeddings_kmeans(
    embeddings: Dict[str, np.ndarray],
    n_clusters: int = 5,
    random_state: int = 0,
) -> Dict[str, int]:
    """Cluster gene embeddings using K-means.
    
    Parameters
    ----------
    embeddings : Dict[str, np.ndarray]
        Morphological embeddings per gene
    n_clusters : int
        Number of clusters (default: 5)
    random_state : int
        Random seed for reproducibility (default: 0)
    
    Returns
    -------
    cluster_assignments : Dict[str, int]
        Mapping from gene to cluster_id (0-indexed)
        Empty dict if embeddings is empty
    
    Notes
    -----
    - If len(embeddings) < n_clusters, n_clusters is reduced to len(embeddings)
    - Genes are sorted alphabetically before clustering for determinism
    - All embeddings are cast to float64 for numerical stability
    """
    # Handle empty case
    if not embeddings:
        return {}
    
    # Adjust n_clusters if needed
    n_genes = len(embeddings)
    n_clusters = min(n_clusters, n_genes)
    
    # Sort genes for deterministic ordering
    genes = sorted(embeddings.keys())
    
    # Stack embeddings into 2D array (stable order)
    X = np.vstack([
        np.asarray(embeddings[g], dtype=np.float64)
        for g in genes
    ])
    
    # Run K-means with deterministic settings
    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init="auto",  # Use sklearn's default for determinism
    )
    labels = kmeans.fit_predict(X)
    
    # Map back to genes
    cluster_assignments = {
        gene: int(label)
        for gene, label in zip(genes, labels)
    }
    
    return cluster_assignments


def add_cluster_labels(
    phenotype_df: pd.DataFrame,
    cluster_assignments: Dict[str, int],
) -> pd.DataFrame:
    """Add cluster_id column to phenotype DataFrame.
    
    Parameters
    ----------
    phenotype_df : pd.DataFrame
        Phenotype table with "gene" column
    cluster_assignments : Dict[str, int]
        Mapping from gene to cluster_id
    
    Returns
    -------
    df : pd.DataFrame
        Copy of input with new "cluster_id" column
        Genes not in cluster_assignments get cluster_id = -1
    
    Notes
    -----
    - Returns a copy, does not modify input
    - cluster_id = -1 indicates gene was not clustered
    """
    df = phenotype_df.copy()
    
    # Map cluster assignments, default to -1 for missing
    df["cluster_id"] = df["gene"].map(cluster_assignments).fillna(-1).astype(int)
    
    return df


def summarize_clusters(
    phenotype_df_with_clusters: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize cluster-level statistics.
    
    Parameters
    ----------
    phenotype_df_with_clusters : pd.DataFrame
        Phenotype table with columns: gene, distance_to_centroid,
        phenotype_score, cluster_id
    
    Returns
    -------
    summary : pd.DataFrame
        Cluster summaries with columns:
        - cluster_id
        - n_genes
        - mean_distance_to_centroid
        - mean_phenotype_score
        
        Sorted by cluster_id ascending.
        Excludes cluster_id == -1 (unclustered genes).
    
    Notes
    -----
    - Genes with cluster_id == -1 are excluded from summaries
    - Empty DataFrame if no valid clusters exist
    """
    # Filter out unclustered genes (cluster_id == -1)
    clustered = phenotype_df_with_clusters[
        phenotype_df_with_clusters["cluster_id"] >= 0
    ]
    
    if clustered.empty:
        # Return empty DataFrame with correct columns
        return pd.DataFrame(columns=[
            "cluster_id",
            "n_genes",
            "mean_distance_to_centroid",
            "mean_phenotype_score",
        ])
    
    # Group by cluster and compute stats
    summary = clustered.groupby("cluster_id").agg(
        n_genes=("gene", "count"),
        mean_distance_to_centroid=("distance_to_centroid", "mean"),
        mean_phenotype_score=("phenotype_score", "mean"),
    ).reset_index()
    
    # Sort by cluster_id
    summary = summary.sort_values("cluster_id").reset_index(drop=True)
    
    return summary
