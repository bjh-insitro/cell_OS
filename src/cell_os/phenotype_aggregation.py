"""Phenotype aggregation and hit calling for POSH screens.

This module provides utilities for aggregating morphological embeddings
into gene-level phenotype summaries and ranking genes by phenotypic shift.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import numpy as np
import pandas as pd


@dataclass
class GenePhenotypeSummary:
    """Summary of a single gene's phenotypic profile.
    
    Attributes
    ----------
    gene : str
        Gene symbol
    phenotype_score : float
        Aggregate phenotype score (e.g., viability), NaN if not available
    distance_to_centroid : float
        L2 distance from this gene's embedding to the global centroid
    embedding_norm : float
        L2 norm of the gene's embedding vector
    rank_by_distance : int
        Rank by distance_to_centroid (1 = most distant, i.e., most shifted)
    """
    gene: str
    phenotype_score: float
    distance_to_centroid: float
    embedding_norm: float
    rank_by_distance: int


def build_gene_phenotype_table(
    embeddings: Dict[str, np.ndarray],
    phenotype_scores: Dict[str, float],
) -> pd.DataFrame:
    """Build a per-gene phenotype summary table.
    
    Computes a global centroid (mean of all embeddings) and measures each
    gene's distance from it. Genes far from the centroid are considered
    phenotypically shifted.
    
    Parameters
    ----------
    embeddings : Dict[str, np.ndarray]
        Morphological embeddings per gene
    phenotype_scores : Dict[str, float]
        Phenotype scores per gene (e.g., viability)
    
    Returns
    -------
    df : pd.DataFrame
        Table with columns: gene, phenotype_score, distance_to_centroid,
        embedding_norm, rank_by_distance
        
        Sorted by distance_to_centroid (desc), then gene (asc).
        Empty DataFrame with correct columns if embeddings is empty.
    
    Notes
    -----
    - If embeddings is empty, returns empty DataFrame with correct columns
    - If only one gene, distance_to_centroid will be 0.0
    - phenotype_score is NaN for genes not in phenotype_scores dict
    - All distances are deterministic (no randomness)
    """
    # Define column order
    columns = [
        "gene",
        "phenotype_score",
        "distance_to_centroid",
        "embedding_norm",
        "rank_by_distance",
    ]
    
    # Handle empty case
    if not embeddings:
        return pd.DataFrame(columns=columns)
    
    # Cast all embeddings to float64 for numerical stability
    embeddings_array = {
        gene: np.asarray(emb, dtype=np.float64)
        for gene, emb in embeddings.items()
    }
    
    # Compute global centroid
    all_embeddings = np.array(list(embeddings_array.values()))
    centroid = all_embeddings.mean(axis=0)
    
    # Build rows
    rows = []
    for gene, emb in embeddings_array.items():
        # L2 norm of embedding
        emb_norm = float(np.linalg.norm(emb))
        
        # L2 distance to centroid
        distance = float(np.linalg.norm(emb - centroid))
        
        # Phenotype score (or NaN)
        pheno_score = phenotype_scores.get(gene, np.nan)
        
        rows.append({
            "gene": gene,
            "phenotype_score": pheno_score,
            "distance_to_centroid": distance,
            "embedding_norm": emb_norm,
        })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Sort: distance desc, then gene asc (for determinism)
    df = df.sort_values(
        by=["distance_to_centroid", "gene"],
        ascending=[False, True],
    ).reset_index(drop=True)
    
    # Add rank (1-indexed)
    df["rank_by_distance"] = range(1, len(df) + 1)
    
    # Reorder columns
    df = df[columns]
    
    return df
