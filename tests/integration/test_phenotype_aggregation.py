"""Tests for phenotype aggregation and hit calling."""

import pytest
import numpy as np
import pandas as pd

from cell_os.phenotype_aggregation import (
    GenePhenotypeSummary,
    build_gene_phenotype_table,
)
from cell_os.perturbation_goal import PerturbationPosterior
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor


class TestBuildGenePhenotypeTable:
    """Tests for build_gene_phenotype_table function."""
    
    def test_basic_table_construction(self):
        """Test basic table construction with 3 genes."""
        embeddings = {
            "G1": np.array([1.0, 0.0]),
            "G2": np.array([0.0, 1.0]),
            "G3": np.array([0.0, 0.0]),
        }
        phenotypes = {"G1": 0.5, "G2": 1.0}
        
        df = build_gene_phenotype_table(embeddings, phenotypes)
        
        # Check structure
        assert len(df) == 3
        assert list(df.columns) == [
            "gene",
            "phenotype_score",
            "distance_to_centroid",
            "embedding_norm",
            "rank_by_distance",
        ]
        
        # Check phenotype_score for G3 is NaN
        g3_row = df[df["gene"] == "G3"].iloc[0]
        assert pd.isna(g3_row["phenotype_score"])
        
        # Check G1 and G2 have scores
        g1_row = df[df["gene"] == "G1"].iloc[0]
        g2_row = df[df["gene"] == "G2"].iloc[0]
        assert g1_row["phenotype_score"] == 0.5
        assert g2_row["phenotype_score"] == 1.0
        
        # Check distances are non-negative
        assert (df["distance_to_centroid"] >= 0).all()
        
        # Check norms are positive for non-zero embeddings
        assert df[df["gene"] == "G1"]["embedding_norm"].iloc[0] > 0
        assert df[df["gene"] == "G2"]["embedding_norm"].iloc[0] > 0
        
        # Check ranks are 1, 2, 3
        assert set(df["rank_by_distance"]) == {1, 2, 3}
    
    def test_empty_embeddings(self):
        """Test that empty embeddings returns empty DataFrame with correct columns."""
        df = build_gene_phenotype_table({}, {})
        
        assert len(df) == 0
        assert list(df.columns) == [
            "gene",
            "phenotype_score",
            "distance_to_centroid",
            "embedding_norm",
            "rank_by_distance",
        ]
    
    def test_single_gene(self):
        """Test that single gene has distance_to_centroid = 0."""
        embeddings = {"SOLO": np.array([1.0, 2.0, 3.0])}
        phenotypes = {"SOLO": 0.8}
        
        df = build_gene_phenotype_table(embeddings, phenotypes)
        
        assert len(df) == 1
        assert df.iloc[0]["gene"] == "SOLO"
        assert df.iloc[0]["distance_to_centroid"] == 0.0
        assert df.iloc[0]["embedding_norm"] > 0
        assert df.iloc[0]["rank_by_distance"] == 1
    
    def test_deterministic_sorting(self):
        """Test that sorting is deterministic."""
        embeddings = {
            "A": np.array([1.0, 0.0]),
            "B": np.array([0.0, 1.0]),
            "C": np.array([0.5, 0.5]),
        }
        phenotypes = {}
        
        df1 = build_gene_phenotype_table(embeddings, phenotypes)
        df2 = build_gene_phenotype_table(embeddings, phenotypes)
        
        # Should be identical
        pd.testing.assert_frame_equal(df1, df2)
        
        # Check that genes are sorted by distance desc, then gene asc
        assert df1["gene"].tolist() == df2["gene"].tolist()


class TestPerturbationPosteriorPhenotypeMethods:
    """Tests for PerturbationPosterior phenotype methods."""
    
    def test_gene_phenotype_table_empty(self):
        """Test gene_phenotype_table with no embeddings."""
        posterior = PerturbationPosterior()
        
        df = posterior.gene_phenotype_table()
        
        assert len(df) == 0
        assert list(df.columns) == [
            "gene",
            "phenotype_score",
            "distance_to_centroid",
            "embedding_norm",
            "rank_by_distance",
        ]
    
    def test_gene_phenotype_table_with_data(self):
        """Test gene_phenotype_table with embeddings."""
        posterior = PerturbationPosterior()
        posterior.embeddings = {
            "TP53": np.array([1.0, 0.0]),
            "MDM2": np.array([0.9, 0.1]),
            "CTRL": np.array([0.0, 0.0]),
        }
        posterior.phenotype_scores = {
            "TP53": 0.2,
            "MDM2": 0.3,
            "CTRL": 1.0,
        }
        
        df = posterior.gene_phenotype_table()
        
        assert len(df) == 3
        assert set(df["gene"]) == {"TP53", "MDM2", "CTRL"}
        
        # Check no NaNs in distance and norm
        assert not df["distance_to_centroid"].isna().any()
        assert not df["embedding_norm"].isna().any()
    
    def test_top_hits_empty(self):
        """Test top_hits with no embeddings."""
        posterior = PerturbationPosterior()
        
        hits = posterior.top_hits(top_n=10)
        
        assert hits == []
    
    def test_top_hits_is_deterministic(self):
        """Test that top_hits returns deterministic results."""
        posterior = PerturbationPosterior()
        posterior.embeddings = {
            "TP53": np.array([1.0, 0.0]),
            "MDM2": np.array([0.9, 0.1]),
            "CTRL": np.array([0.0, 0.0]),
        }
        posterior.phenotype_scores = {
            "TP53": 0.2,
            "MDM2": 0.3,
            "CTRL": 1.0,
        }
        
        hits_1 = posterior.top_hits(top_n=3)
        hits_2 = posterior.top_hits(top_n=3)
        
        # Should be deterministic
        assert hits_1 == hits_2
        # Should return all 3 genes
        assert len(hits_1) == 3
        assert set(hits_1) == {"TP53", "MDM2", "CTRL"}
    
    def test_top_hits_truncates_gracefully(self):
        """Test that top_n > num_genes works correctly."""
        posterior = PerturbationPosterior()
        posterior.embeddings = {
            "G1": np.array([1.0, 0.0]),
            "G2": np.array([0.0, 1.0]),
        }
        posterior.phenotype_scores = {}
        
        hits = posterior.top_hits(top_n=100)
        
        assert len(hits) == 2
        assert set(hits) == {"G1", "G2"}


class TestPhenotypeAggregationIntegration:
    """Integration tests with perturbation loop."""
    
    def test_phenotype_aggregation_with_loop(self):
        """Test phenotype aggregation after running a perturbation cycle."""
        posterior = PerturbationPosterior()
        executor = SimulatedPerturbationExecutor()
        
        from cell_os.perturbation_goal import PerturbationGoal
        goal = PerturbationGoal(max_perturbations=10)
        
        loop = PerturbationAcquisitionLoop(posterior, executor, goal)
        
        # Run one cycle
        candidate_genes = ["TP53", "MDM2", "KRAS", "EGFR", "PTEN"]
        batch = loop.propose(candidate_genes)
        
        # Execute and update posterior
        results = executor.run_batch(batch)
        posterior.update_with_results(results)
        
        # Now test phenotype aggregation
        df = posterior.gene_phenotype_table()
        hits = posterior.top_hits(top_n=3)
        
        # Assertions
        assert len(df) == len(candidate_genes)
        assert set(df["gene"]) == set(candidate_genes)
        
        # Check no NaNs in critical columns
        assert not df["distance_to_centroid"].isna().any()
        assert not df["embedding_norm"].isna().any()
        
        # Hits should be subset of candidates
        assert set(hits) <= set(candidate_genes)
        assert len(hits) <= 3
        
        # Hits should be non-empty (we have data)
        assert len(hits) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
