"""Tests for phenotype clustering."""

import pytest
import numpy as np
import pandas as pd

from cell_os.phenotype_clustering import (
    cluster_embeddings_kmeans,
    add_cluster_labels,
    summarize_clusters,
)
from cell_os.perturbation_goal import PerturbationPosterior


class TestClusterEmbeddingsKmeans:
    """Tests for cluster_embeddings_kmeans function."""
    
    def test_basic_clustering(self):
        """Test basic k-means clustering with obvious groups."""
        # Create 4 embeddings with 2 obvious clusters
        embeddings = {
            "A": np.array([0.0, 0.0]),
            "B": np.array([0.1, 0.1]),
            "C": np.array([10.0, 10.0]),
            "D": np.array([10.1, 10.1]),
        }
        
        clusters = cluster_embeddings_kmeans(embeddings, n_clusters=2)
        
        # Should have all genes
        assert set(clusters.keys()) == {"A", "B", "C", "D"}
        
        # A and B should be in same cluster, C and D in another
        assert clusters["A"] == clusters["B"]
        assert clusters["C"] == clusters["D"]
        assert clusters["A"] != clusters["C"]
    
    def test_deterministic(self):
        """Test that clustering is deterministic."""
        embeddings = {
            "G1": np.array([1.0, 0.0]),
            "G2": np.array([0.0, 1.0]),
            "G3": np.array([0.5, 0.5]),
        }
        
        clusters1 = cluster_embeddings_kmeans(embeddings, n_clusters=2)
        clusters2 = cluster_embeddings_kmeans(embeddings, n_clusters=2)
        
        assert clusters1 == clusters2
    
    def test_empty_embeddings(self):
        """Test that empty embeddings returns empty dict."""
        clusters = cluster_embeddings_kmeans({}, n_clusters=3)
        assert clusters == {}
    
    def test_n_clusters_exceeds_n_genes(self):
        """Test that n_clusters is reduced when it exceeds n_genes."""
        embeddings = {
            "A": np.array([1.0]),
            "B": np.array([2.0]),
        }
        
        # Request 5 clusters but only have 2 genes
        clusters = cluster_embeddings_kmeans(embeddings, n_clusters=5)
        
        # Should work without error
        assert len(clusters) == 2
        # Should have at most 2 unique cluster IDs
        assert len(set(clusters.values())) <= 2


class TestAddClusterLabels:
    """Tests for add_cluster_labels function."""
    
    def test_basic_merge(self):
        """Test basic merging of cluster labels."""
        phenotype_df = pd.DataFrame({
            "gene": ["A", "B", "C"],
            "phenotype_score": [0.5, 0.6, 0.7],
            "distance_to_centroid": [1.0, 2.0, 3.0],
        })
        
        cluster_assignments = {"A": 0, "B": 1, "C": 0}
        
        result = add_cluster_labels(phenotype_df, cluster_assignments)
        
        assert "cluster_id" in result.columns
        assert result.loc[result["gene"] == "A", "cluster_id"].iloc[0] == 0
        assert result.loc[result["gene"] == "B", "cluster_id"].iloc[0] == 1
        assert result.loc[result["gene"] == "C", "cluster_id"].iloc[0] == 0
    
    def test_missing_gene_gets_minus_one(self):
        """Test that genes not in cluster_assignments get cluster_id = -1."""
        phenotype_df = pd.DataFrame({
            "gene": ["A", "B", "C"],
            "phenotype_score": [0.5, 0.6, 0.7],
        })
        
        # Only cluster A and C
        cluster_assignments = {"A": 0, "C": 1}
        
        result = add_cluster_labels(phenotype_df, cluster_assignments)
        
        # B should get -1
        assert result.loc[result["gene"] == "B", "cluster_id"].iloc[0] == -1
    
    def test_does_not_modify_input(self):
        """Test that function returns a copy."""
        phenotype_df = pd.DataFrame({
            "gene": ["A"],
            "phenotype_score": [0.5],
        })
        
        result = add_cluster_labels(phenotype_df, {"A": 0})
        
        # Original should not have cluster_id
        assert "cluster_id" not in phenotype_df.columns
        # Result should have it
        assert "cluster_id" in result.columns


class TestSummarizeClusters:
    """Tests for summarize_clusters function."""
    
    def test_basic_summary(self):
        """Test basic cluster summarization."""
        df = pd.DataFrame({
            "gene": ["A", "B", "C", "D"],
            "cluster_id": [0, 0, 1, 1],
            "distance_to_centroid": [1.0, 2.0, 3.0, 4.0],
            "phenotype_score": [0.5, 0.6, 0.7, 0.8],
        })
        
        summary = summarize_clusters(df)
        
        assert len(summary) == 2
        assert set(summary["cluster_id"]) == {0, 1}
        
        # Check cluster 0 stats
        c0 = summary[summary["cluster_id"] == 0].iloc[0]
        assert c0["n_genes"] == 2
        assert c0["mean_distance_to_centroid"] == 1.5  # (1.0 + 2.0) / 2
        assert c0["mean_phenotype_score"] == 0.55  # (0.5 + 0.6) / 2
    
    def test_excludes_cluster_minus_one(self):
        """Test that cluster_id == -1 is excluded from summaries."""
        df = pd.DataFrame({
            "gene": ["A", "B", "C"],
            "cluster_id": [0, 0, -1],
            "distance_to_centroid": [1.0, 2.0, 999.0],
            "phenotype_score": [0.5, 0.6, 0.999],
        })
        
        summary = summarize_clusters(df)
        
        # Should only have cluster 0, not -1
        assert len(summary) == 1
        assert summary.iloc[0]["cluster_id"] == 0
        assert summary.iloc[0]["n_genes"] == 2
        # Should not include gene C's values
        assert summary.iloc[0]["mean_distance_to_centroid"] == 1.5


class TestPosteriorClusteringIntegration:
    """Integration tests with PerturbationPosterior."""
    
    def test_cluster_hits_basic(self):
        """Test cluster_hits method."""
        posterior = PerturbationPosterior()
        posterior.embeddings = {
            "TP53": np.array([1.0, 0.0]),
            "MDM2": np.array([0.9, 0.1]),
            "KRAS": np.array([0.0, 1.0]),
        }
        posterior.phenotype_scores = {
            "TP53": 0.5,
            "MDM2": 0.6,
            "KRAS": 0.7,
        }
        
        clustered_df = posterior.cluster_hits(n_clusters=2)
        
        # Should have cluster_id column
        assert "cluster_id" in clustered_df.columns
        
        # Should have all genes
        assert len(clustered_df) == 3
        
        # No NaNs in cluster_id
        assert not clustered_df["cluster_id"].isna().any()
        
        # TP53 and MDM2 should be in same cluster (close embeddings)
        tp53_cluster = clustered_df[clustered_df["gene"] == "TP53"]["cluster_id"].iloc[0]
        mdm2_cluster = clustered_df[clustered_df["gene"] == "MDM2"]["cluster_id"].iloc[0]
        assert tp53_cluster == mdm2_cluster
    
    def test_cluster_hits_empty_embeddings(self):
        """Test cluster_hits with no embeddings."""
        posterior = PerturbationPosterior()
        
        clustered_df = posterior.cluster_hits(n_clusters=3)
        
        # Should return empty table without cluster_id
        assert len(clustered_df) == 0
        assert "cluster_id" not in clustered_df.columns
    
    def test_cluster_summaries_basic(self):
        """Test cluster_summaries method."""
        posterior = PerturbationPosterior()
        posterior.embeddings = {
            "G1": np.array([0.0, 0.0]),
            "G2": np.array([0.1, 0.1]),
            "G3": np.array([10.0, 10.0]),
        }
        posterior.phenotype_scores = {
            "G1": 0.9,
            "G2": 0.95,
            "G3": 0.5,
        }
        
        summaries = posterior.cluster_summaries(n_clusters=2)
        
        # Should have 2 clusters
        assert len(summaries) == 2
        
        # Check columns
        assert set(summaries.columns) == {
            "cluster_id",
            "n_genes",
            "mean_distance_to_centroid",
            "mean_phenotype_score",
        }
    
    def test_cluster_summaries_empty_embeddings(self):
        """Test cluster_summaries with no embeddings."""
        posterior = PerturbationPosterior()
        
        summaries = posterior.cluster_summaries(n_clusters=3)
        
        # Should return empty DataFrame with correct columns
        assert len(summaries) == 0
        assert set(summaries.columns) == {
            "cluster_id",
            "n_genes",
            "mean_distance_to_centroid",
            "mean_phenotype_score",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
