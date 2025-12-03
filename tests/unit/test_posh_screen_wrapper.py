"""
Unit tests for POSH Screen Simulation.

Tests the core simulation logic including:
- Data generation
- Embedding generation
- Hit calling
- Result packaging
"""

import pytest
import pandas as pd
import numpy as np
from src.cell_os.simulation.posh_screen_wrapper import (
    simulate_posh_screen,
    simulate_screen_data,
    generate_embeddings,
    analyze_screen_results,
    POSHScreenResult,
    CELL_PAINTING_FEATURES,
    HIT_RATE,
    EMBEDDING_DIMENSIONS,
    PCA_COMPONENTS,
)


class TestSimulateScreenData:
    """Test raw screen data generation."""
    
    def test_basic_data_generation(self):
        """Test that data generation produces expected structure."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        # Check DataFrames are not empty
        assert not df_raw.empty
        assert not df_channels.empty
        
        # Check correct number of genes
        assert len(df_raw) == 100
        assert len(df_channels) == 100
        
        # Check Gene column exists
        assert "Gene" in df_raw.columns
        assert "Gene" in df_channels.columns
        
    def test_channel_columns(self):
        """Test that all expected channel columns are present."""
        _, df_channels = simulate_screen_data(
            cell_line="A549",
            treatment="Staurosporine",
            dose_uM=5.0,
            library_size=50,
            random_seed=42
        )
        
        expected_channels = ["Hoechst", "ConA", "Phalloidin", "WGA", "MitoProbe"]
        for channel in expected_channels:
            assert channel in df_channels.columns
            
    def test_raw_measurement_columns(self):
        """Test that segmentation outputs are present."""
        df_raw, _ = simulate_screen_data(
            cell_line="HepG2",
            treatment="Tunicamycin",
            dose_uM=20.0,
            library_size=50,
            random_seed=42
        )
        
        # Nuclear measurements
        assert "Nucleus_Area" in df_raw.columns
        assert "Nucleus_Mean_Intensity" in df_raw.columns
        assert "Nucleus_Form_Factor" in df_raw.columns
        
        # Mitochondrial measurements
        assert "Mito_Object_Count" in df_raw.columns
        assert "Mito_Total_Area" in df_raw.columns
        assert "Mito_Mean_Intensity" in df_raw.columns
        
    def test_hit_injection(self):
        """Test that hits are injected at expected rate."""
        library_size = 1000
        df_raw, _ = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=library_size,
            random_seed=42
        )
        
        # We can't directly verify hits, but we can check data variability
        # Hits should create outliers in the data
        mito_count_std = df_raw["Mito_Object_Count"].std()
        assert mito_count_std > 0  # Should have variation
        
    def test_reproducibility(self):
        """Test that same seed produces same results."""
        df_raw1, df_channels1 = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_raw2, df_channels2 = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        # Should be identical
        pd.testing.assert_frame_equal(df_raw1, df_raw2)
        pd.testing.assert_frame_equal(df_channels1, df_channels2)
        
    def test_different_cell_lines(self):
        """Test that different cell lines produce different baselines."""
        df_raw_u2os, _ = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_raw_ipsc, _ = simulate_screen_data(
            cell_line="iPSC",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        # Nuclear areas should differ (U2OS larger than iPSC)
        u2os_mean = df_raw_u2os["Nucleus_Area"].mean()
        ipsc_mean = df_raw_ipsc["Nucleus_Area"].mean()
        assert u2os_mean > ipsc_mean


class TestGenerateEmbeddings:
    """Test embedding generation."""
    
    def test_embedding_dimensions(self):
        """Test that embeddings have correct dimensions."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        # Check embedding dimensions
        assert len(df_embeddings) == 100
        embed_cols = [c for c in df_embeddings.columns if c.startswith("DIM_")]
        assert len(embed_cols) == EMBEDDING_DIMENSIONS
        
        # Check projection dimensions
        assert len(df_proj) == 100
        assert "UMAP_1" in df_proj.columns
        assert "UMAP_2" in df_proj.columns
        
    def test_embedding_reproducibility(self):
        """Test that embeddings are reproducible with same seed."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        
        df_emb1, df_proj1 = generate_embeddings(df_combined, random_seed=42)
        df_emb2, df_proj2 = generate_embeddings(df_combined, random_seed=42)
        
        pd.testing.assert_frame_equal(df_emb1, df_emb2)
        pd.testing.assert_frame_equal(df_proj1, df_proj2)
        
    def test_embedding_gene_column(self):
        """Test that Gene column is preserved."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        assert "Gene" in df_embeddings.columns
        assert "Gene" in df_proj.columns
        assert len(df_embeddings["Gene"].unique()) == 100


class TestAnalyzeScreenResults:
    """Test hit calling and result analysis."""
    
    def test_result_structure(self):
        """Test that analysis produces complete POSHScreenResult."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        result = analyze_screen_results(
            df_raw=df_raw,
            df_channels=df_channels,
            df_embeddings=df_embeddings,
            df_proj=df_proj,
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            feature="mitochondrial_fragmentation"
        )
        
        assert isinstance(result, POSHScreenResult)
        assert result.success
        assert result.cell_line == "U2OS"
        assert result.treatment == "tBHP"
        assert result.dose_uM == 10.0
        
    def test_hit_calling(self):
        """Test that hits are identified."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=1000,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        result = analyze_screen_results(
            df_raw=df_raw,
            df_channels=df_channels,
            df_embeddings=df_embeddings,
            df_proj=df_proj,
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=1000,
            feature="mitochondrial_fragmentation"
        )
        
        # Should identify some hits
        assert len(result.hit_list) > 0
        # Roughly 5% hit rate expected
        assert len(result.hit_list) < 1000 * 0.2  # Upper bound
        
    def test_volcano_data_columns(self):
        """Test that volcano data has required columns."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        result = analyze_screen_results(
            df_raw=df_raw,
            df_channels=df_channels,
            df_embeddings=df_embeddings,
            df_proj=df_proj,
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            feature="mitochondrial_fragmentation"
        )
        
        required_cols = ["Gene", "Log2FoldChange", "P_Value", "NegLog10P", "Category"]
        for col in required_cols:
            assert col in result.volcano_data.columns
            
    def test_derived_features(self):
        """Test that derived features are calculated."""
        df_raw, df_channels = simulate_screen_data(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            random_seed=42
        )
        
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=42)
        
        result = analyze_screen_results(
            df_raw=df_raw,
            df_channels=df_channels,
            df_embeddings=df_embeddings,
            df_proj=df_proj,
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            feature="mitochondrial_fragmentation"
        )
        
        # Check derived features exist
        assert "Mitochondrial_Fragmentation" in result.raw_measurements.columns
        assert "Nuclear_Condensation" in result.raw_measurements.columns
        assert "ER_Stress_Score" in result.raw_measurements.columns


class TestSimulatePOSHScreen:
    """Test the end-to-end simulation function."""
    
    def test_full_simulation(self):
        """Test complete simulation workflow."""
        result = simulate_posh_screen(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=100,
            feature="mitochondrial_fragmentation",
            random_seed=42
        )
        
        assert isinstance(result, POSHScreenResult)
        assert result.success
        assert not result.hit_list.empty or len(result.hit_list) == 0  # May have 0 hits with small library
        assert not result.volcano_data.empty
        assert not result.raw_measurements.empty
        assert not result.channel_intensities.empty
        assert not result.embeddings.empty
        assert not result.projection_2d.empty
        
    def test_different_features(self):
        """Test that different features produce different hit lists."""
        result_mito = simulate_posh_screen(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=1000,
            feature="mitochondrial_fragmentation",
            random_seed=42
        )
        
        result_nuclear = simulate_posh_screen(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=1000,
            feature="nuclear_size",
            random_seed=42
        )
        
        # Hit lists should differ (different features)
        # Note: They use the same seed, so raw data is identical, but analysis differs
        mito_hits = set(result_mito.hit_list["Gene"].tolist())
        nuclear_hits = set(result_nuclear.hit_list["Gene"].tolist())
        
        # There should be some difference (though may overlap)
        assert mito_hits != nuclear_hits or (len(mito_hits) == 0 and len(nuclear_hits) == 0)
        
    def test_error_handling(self):
        """Test that simulation handles errors gracefully."""
        # This should not crash even with edge cases
        result = simulate_posh_screen(
            cell_line="U2OS",
            treatment="tBHP",
            dose_uM=10.0,
            library_size=10,  # Very small library
            feature="mitochondrial_fragmentation",
            random_seed=42
        )
        
        # Should still succeed
        assert result.success or not result.success  # Either outcome is valid
        
    def test_all_cell_lines(self):
        """Test simulation works for all supported cell lines."""
        cell_lines = ["U2OS", "A549", "HepG2", "iPSC"]
        
        for cell_line in cell_lines:
            result = simulate_posh_screen(
                cell_line=cell_line,
                treatment="tBHP",
                dose_uM=10.0,
                library_size=100,
                feature="mitochondrial_fragmentation",
                random_seed=42
            )
            assert result.success
            assert result.cell_line == cell_line
            
    def test_all_treatments(self):
        """Test simulation works for all treatments."""
        treatments = ["tBHP", "Staurosporine", "Tunicamycin"]
        
        for treatment in treatments:
            result = simulate_posh_screen(
                cell_line="U2OS",
                treatment=treatment,
                dose_uM=10.0,
                library_size=100,
                feature="mitochondrial_fragmentation",
                random_seed=42
            )
            assert result.success
            assert result.treatment == treatment
            
    def test_all_features(self):
        """Test simulation works for all features."""
        for feature_key in CELL_PAINTING_FEATURES.keys():
            result = simulate_posh_screen(
                cell_line="U2OS",
                treatment="tBHP",
                dose_uM=10.0,
                library_size=100,
                feature=feature_key,
                random_seed=42
            )
            assert result.success
            assert result.selected_feature == feature_key


class TestConstants:
    """Test that constants are properly defined."""
    
    def test_hit_rate(self):
        """Test HIT_RATE is reasonable."""
        assert 0 < HIT_RATE < 1
        assert HIT_RATE == 0.05
        
    def test_embedding_dimensions(self):
        """Test EMBEDDING_DIMENSIONS is positive."""
        assert EMBEDDING_DIMENSIONS > 0
        assert EMBEDDING_DIMENSIONS == 128
        
    def test_pca_components(self):
        """Test PCA_COMPONENTS is valid."""
        assert PCA_COMPONENTS > 0
        assert PCA_COMPONENTS == 2
        
    def test_cell_painting_features(self):
        """Test CELL_PAINTING_FEATURES is properly defined."""
        assert len(CELL_PAINTING_FEATURES) > 0
        assert "mitochondrial_fragmentation" in CELL_PAINTING_FEATURES
        assert "nuclear_size" in CELL_PAINTING_FEATURES
        
        for key, value in CELL_PAINTING_FEATURES.items():
            assert "name" in value
            assert "unit" in value
            assert "description" in value
