"""
DINO Embedding Analysis for POSH Screens.

Analyzes morphological embeddings from DINO (self-supervised vision transformer)
to quantify phenotypic effects and call hits.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DINOEmbedding:
    """Represents a DINO embedding for a perturbation."""
    gene: str
    guide_id: str
    embedding: np.ndarray  # Shape: (embedding_dim,)
    plate: str = "unknown"
    well: str = "unknown"


class DINOAnalyzer:
    """
    Analyzes DINO embeddings to quantify morphological effects.
    
    Computes distance metrics (D_M) between perturbed cells and controls,
    performs dimensionality reduction, and calls hits.
    """
    
    def __init__(self, embedding_dim: int = 384):
        """
        Initialize DINO analyzer.
        
        Args:
            embedding_dim: Dimension of DINO embeddings (default: 384 for DINOv2-S)
        """
        self.embedding_dim = embedding_dim
        self.embeddings: List[DINOEmbedding] = []
        self.control_mean: Optional[np.ndarray] = None
        
    def add_embedding(self, gene: str, guide_id: str, embedding: np.ndarray, 
                      plate: str = "unknown", well: str = "unknown"):
        """Add an embedding to the analyzer."""
        assert embedding.shape[0] == self.embedding_dim, f"Expected {self.embedding_dim}D, got {embedding.shape[0]}D"
        
        self.embeddings.append(DINOEmbedding(
            gene=gene,
            guide_id=guide_id,
            embedding=embedding,
            plate=plate,
            well=well
        ))
    
    def load_from_dataframe(self, df: pd.DataFrame, embedding_col: str = "embedding"):
        """
        Load embeddings from a DataFrame.
        
        Args:
            df: DataFrame with columns: gene, guide_id, embedding (list or array)
            embedding_col: Name of the embedding column
        """
        for _, row in df.iterrows():
            embedding = np.array(row[embedding_col])
            self.add_embedding(
                gene=row.get('gene', 'unknown'),
                guide_id=row.get('guide_id', 'unknown'),
                embedding=embedding,
                plate=row.get('plate', 'unknown'),
                well=row.get('well', 'unknown')
            )
    
    def compute_control_mean(self, control_genes: List[str] = ['NTC', 'non-targeting']):
        """Compute mean embedding for control perturbations."""
        control_embeddings = [
            emb.embedding for emb in self.embeddings 
            if emb.gene in control_genes
        ]
        
        if not control_embeddings:
            raise ValueError(f"No control embeddings found for genes: {control_genes}")
        
        self.control_mean = np.mean(control_embeddings, axis=0)
        return self.control_mean
    
    def compute_distance_matrix(self, metric: str = 'cosine') -> pd.DataFrame:
        """
        Compute pairwise distance matrix between all embeddings.
        
        Args:
            metric: Distance metric ('cosine', 'euclidean', 'correlation')
        
        Returns:
            DataFrame with genes as index/columns
        """
        from scipy.spatial.distance import pdist, squareform
        
        embeddings_array = np.array([emb.embedding for emb in self.embeddings])
        genes = [emb.gene for emb in self.embeddings]
        
        if metric == 'cosine':
            distances = pdist(embeddings_array, metric='cosine')
        elif metric == 'euclidean':
            distances = pdist(embeddings_array, metric='euclidean')
        elif metric == 'correlation':
            distances = pdist(embeddings_array, metric='correlation')
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        distance_matrix = squareform(distances)
        
        return pd.DataFrame(distance_matrix, index=genes, columns=genes)
    
    def compute_d_m(self, aggregate: str = 'mean') -> pd.DataFrame:
        """
        Compute D_M (morphological distance from control) for each gene.
        
        Args:
            aggregate: How to aggregate multiple guides per gene ('mean', 'median', 'max')
        
        Returns:
            DataFrame with columns: gene, d_m, n_guides
        """
        if self.control_mean is None:
            self.compute_control_mean()
        
        # Compute distance for each embedding
        results = []
        for emb in self.embeddings:
            if emb.gene in ['NTC', 'non-targeting']:
                continue  # Skip controls
            
            # Cosine distance
            cos_dist = 1 - np.dot(emb.embedding, self.control_mean) / (
                np.linalg.norm(emb.embedding) * np.linalg.norm(self.control_mean)
            )
            
            results.append({
                'gene': emb.gene,
                'guide_id': emb.guide_id,
                'd_m': cos_dist,
                'plate': emb.plate,
                'well': emb.well
            })
        
        df = pd.DataFrame(results)
        
        # Aggregate by gene
        if aggregate == 'mean':
            agg_func = 'mean'
        elif aggregate == 'median':
            agg_func = 'median'
        elif aggregate == 'max':
            agg_func = 'max'
        else:
            raise ValueError(f"Unknown aggregate: {aggregate}")
        
        gene_d_m = df.groupby('gene').agg({
            'd_m': agg_func,
            'guide_id': 'count'
        }).rename(columns={'guide_id': 'n_guides'}).reset_index()
        
        return gene_d_m.sort_values('d_m', ascending=False)
    
    def call_hits(self, threshold: float = 2.0, min_guides: int = 2) -> pd.DataFrame:
        """
        Call hits based on D_M threshold.
        
        Args:
            threshold: D_M threshold for hit calling (default: 2.0 std devs from control)
            min_guides: Minimum number of guides required
        
        Returns:
            DataFrame of hits with columns: gene, d_m, n_guides, hit_status
        """
        gene_d_m = self.compute_d_m()
        
        # Filter by min guides
        gene_d_m = gene_d_m[gene_d_m['n_guides'] >= min_guides].copy()
        
        # Compute z-score
        mean_d_m = gene_d_m['d_m'].mean()
        std_d_m = gene_d_m['d_m'].std()
        gene_d_m['z_score'] = (gene_d_m['d_m'] - mean_d_m) / std_d_m
        
        # Call hits
        gene_d_m['hit_status'] = gene_d_m['z_score'] > threshold
        
        return gene_d_m.sort_values('z_score', ascending=False)
    
    def reduce_dimensions(self, method: str = 'umap', n_components: int = 2, **kwargs) -> pd.DataFrame:
        """
        Reduce embedding dimensions for visualization.
        
        Args:
            method: 'umap' or 'tsne'
            n_components: Number of components (typically 2 for plotting)
            **kwargs: Additional arguments for the reduction method
        
        Returns:
            DataFrame with columns: gene, guide_id, dim1, dim2
        """
        embeddings_array = np.array([emb.embedding for emb in self.embeddings])
        
        if method == 'umap':
            from umap import UMAP
            reducer = UMAP(n_components=n_components, **kwargs)
        elif method == 'tsne':
            from sklearn.manifold import TSNE
            reducer = TSNE(n_components=n_components, **kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        reduced = reducer.fit_transform(embeddings_array)
        
        df = pd.DataFrame({
            'gene': [emb.gene for emb in self.embeddings],
            'guide_id': [emb.guide_id for emb in self.embeddings],
            'dim1': reduced[:, 0],
            'dim2': reduced[:, 1] if n_components > 1 else 0
        })
        
        # Add D_M if available
        if self.control_mean is not None:
            gene_d_m = self.compute_d_m()
            df = df.merge(gene_d_m[['gene', 'd_m']], on='gene', how='left')
        
        return df
    
    def export_hits(self, output_path: str, threshold: float = 2.0, min_guides: int = 2):
        """Export hit list to CSV."""
        hits = self.call_hits(threshold=threshold, min_guides=min_guides)
        hits.to_csv(output_path, index=False)
        print(f"✅ Exported {len(hits)} genes to: {output_path}")
        print(f"   Hits (z > {threshold}): {hits['hit_status'].sum()}")


def load_dino_embeddings_from_csv(csv_path: str) -> DINOAnalyzer:
    """
    Load DINO embeddings from a CSV file.
    
    CSV format:
        gene, guide_id, embedding (as JSON array or comma-separated)
    
    Returns:
        Initialized DINOAnalyzer
    """
    df = pd.read_csv(csv_path)
    
    # Parse embeddings (handle different formats)
    if 'embedding' in df.columns:
        # Try JSON format
        import json
        try:
            df['embedding'] = df['embedding'].apply(json.loads)
        except:
            # Try comma-separated
            df['embedding'] = df['embedding'].apply(lambda x: [float(v) for v in x.split(',')])
    
    # Infer embedding dimension
    embedding_dim = len(df['embedding'].iloc[0])
    
    analyzer = DINOAnalyzer(embedding_dim=embedding_dim)
    analyzer.load_from_dataframe(df)
    
    print(f"✅ Loaded {len(analyzer.embeddings)} embeddings ({embedding_dim}D)")
    
    return analyzer


if __name__ == "__main__":
    # Demo: Generate synthetic embeddings
    print("DINO Analyzer - Demo Mode")
    
    analyzer = DINOAnalyzer(embedding_dim=384)
    
    # Add synthetic control embeddings
    for i in range(10):
        control_emb = np.random.randn(384)
        analyzer.add_embedding('NTC', f'NTC_{i}', control_emb)
    
    # Add synthetic gene knockouts
    for gene in ['TP53', 'KRAS', 'BRCA1', 'GAPDH']:
        for guide in range(4):
            # Simulate morphological shift
            shift = np.random.randn(384) * (2.0 if gene == 'TP53' else 0.5)
            emb = np.random.randn(384) + shift
            analyzer.add_embedding(gene, f'{gene}_g{guide}', emb)
    
    # Compute D_M
    gene_d_m = analyzer.compute_d_m()
    print("\nD_M Rankings:")
    print(gene_d_m.head(10))
    
    # Call hits
    hits = analyzer.call_hits(threshold=1.5)
    print(f"\nHits (z > 1.5): {hits['hit_status'].sum()}")
    print(hits[hits['hit_status']])
