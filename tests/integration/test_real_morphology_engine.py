"""Tests for RealMorphologyEngine."""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile

from cell_os.morphology_engine import (
    RealMorphologyEngine,
    FakeMorphologyEngine,
    create_morphology_engine,
)


class TestRealMorphologyEngine:
    """Tests for RealMorphologyEngine."""
    
    def test_load_embeddings_from_csv(self, tmp_path):
        """Test loading embeddings from CSV."""
        # Create test CSV
        data = {
            "cell_line": ["A549", "A549"],
            "compound": ["TBHP", "TBHP"],
            "dose_uM": [0.5, 1.0],
            "time_h": [24.0, 24.0],
            "plate_id": ["plate_1", "plate_1"],
            "well_id": ["A1", "A2"],
        }
        
        # Add feature columns
        for i in range(50):
            data[f"feat_{i+1:03d}"] = np.random.rand(2)
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test_embeddings.csv"
        df.to_csv(csv_path, index=False)
        
        # Load with engine
        engine = RealMorphologyEngine(csv_path, dim=50)
        
        # Should load successfully
        assert engine._data is not None
        assert len(engine._data) == 2
    
    def test_get_embedding_single_well(self, tmp_path):
        """Test getting embedding for single well."""
        # Create test data
        embedding_values = np.random.rand(50)
        data = {
            "cell_line": ["A549"],
            "compound": ["TBHP"],
            "dose_uM": [0.5],
            "time_h": [24.0],
            "plate_id": ["plate_1"],
            "well_id": ["A1"],
        }
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [embedding_values[i]]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = RealMorphologyEngine(csv_path)
        embedding = engine.get_embedding("A549", "TBHP", 0.5, 24.0)
        
        assert embedding.shape == (50,)
        np.testing.assert_allclose(embedding, embedding_values, rtol=1e-5)
    
    def test_get_embedding_multiple_wells_first(self, tmp_path):
        """Test aggregation='first' with multiple wells."""
        data = {
            "cell_line": ["A549", "A549", "A549"],
            "compound": ["TBHP", "TBHP", "TBHP"],
            "dose_uM": [0.5, 0.5, 0.5],
            "time_h": [24.0, 24.0, 24.0],
            "plate_id": ["plate_1", "plate_2", "plate_1"],
            "well_id": ["B1", "A1", "A1"],
        }
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [1.0, 2.0, 3.0]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = RealMorphologyEngine(csv_path)
        embedding = engine.get_embedding("A549", "TBHP", 0.5, 24.0, aggregation="first")
        
        # Should get first by (plate_id, well_id) sort: plate_1/A1
        assert embedding[0] == 3.0
    
    def test_get_embedding_multiple_wells_mean(self, tmp_path):
        """Test aggregation='mean' with multiple wells."""
        data = {
            "cell_line": ["A549", "A549"],
            "compound": ["TBHP", "TBHP"],
            "dose_uM": [0.5, 0.5],
            "time_h": [24.0, 24.0],
            "plate_id": ["plate_1", "plate_1"],
            "well_id": ["A1", "A2"],
        }
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [1.0, 3.0]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = RealMorphologyEngine(csv_path)
        embedding = engine.get_embedding("A549", "TBHP", 0.5, 24.0, aggregation="mean")
        
        # Should average: (1.0 + 3.0) / 2 = 2.0
        assert embedding[0] == 2.0
    
    def test_get_embedding_not_found(self, tmp_path):
        """Test error when embedding not found."""
        data = {
            "cell_line": ["A549"],
            "compound": ["TBHP"],
            "dose_uM": [0.5],
            "time_h": [24.0],
            "plate_id": ["plate_1"],
            "well_id": ["A1"],
        }
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [1.0]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = RealMorphologyEngine(csv_path)
        
        with pytest.raises(ValueError, match="No embedding found"):
            engine.get_embedding("HepG2", "TBHP", 0.5, 24.0)
    
    def test_extract_features_not_implemented(self, tmp_path):
        """Test that extract_features raises NotImplementedError."""
        data = {"cell_line": ["A549"], "compound": ["TBHP"], "dose_uM": [0.5],
                "time_h": [24.0], "plate_id": ["plate_1"], "well_id": ["A1"]}
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [1.0]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = RealMorphologyEngine(csv_path)
        
        with pytest.raises(NotImplementedError):
            engine.extract_features(["image.tif"])


class TestMorphologyEngineFactory:
    """Tests for create_morphology_engine factory."""
    
    def test_create_fake_engine(self):
        """Test creating fake engine."""
        engine = create_morphology_engine("fake", dim=10)
        
        assert isinstance(engine, FakeMorphologyEngine)
        assert engine.dim == 10
    
    def test_create_real_engine(self, tmp_path):
        """Test creating real engine."""
        # Create minimal CSV
        data = {"cell_line": ["A549"], "compound": ["TBHP"], "dose_uM": [0.5],
                "time_h": [24.0], "plate_id": ["plate_1"], "well_id": ["A1"]}
        for i in range(50):
            data[f"feat_{i+1:03d}"] = [1.0]
        
        df = pd.DataFrame(data)
        csv_path = tmp_path / "test.csv"
        df.to_csv(csv_path, index=False)
        
        engine = create_morphology_engine("real", csv_path=csv_path)
        
        assert isinstance(engine, RealMorphologyEngine)
    
    def test_create_real_engine_without_path_raises(self):
        """Test that creating real engine without path raises error."""
        with pytest.raises(ValueError, match="csv_path required"):
            create_morphology_engine("real")
    
    def test_create_unknown_engine_raises(self):
        """Test that unknown engine type raises error."""
        with pytest.raises(ValueError, match="Unknown engine type"):
            create_morphology_engine("unknown")


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
