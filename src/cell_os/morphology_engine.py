# -*- coding: utf-8 -*-
"""Morphology engine for extracting and processing cellular features.

This module provides interfaces and implementations for morphological
feature extraction from microscopy images.
"""

from __future__ import annotations
from typing import Protocol, List, Optional, Tuple
import numpy as np
import pandas as pd
from pathlib import Path


class MorphologyEngine(Protocol):
    """Protocol for morphology feature extraction engines.
    
    Implementations may use CellProfiler, DeepProfiler, or custom models.
    """
    
    def extract_features(self, image_paths: List[str]) -> np.ndarray:
        """Extract high-dimensional feature vectors from images.
        
        Parameters
        ----------
        image_paths : List[str]
            Paths to image files
        
        Returns
        -------
        features : np.ndarray
            Feature matrix (n_images × n_features)
        """
        ...
    
    def reduce_dimensionality(self, features: np.ndarray) -> np.ndarray:
        """Optionally reduce features to a lower dimension.
        
        Parameters
        ----------
        features : np.ndarray
            High-dimensional features
        
        Returns
        -------
        reduced : np.ndarray
            Reduced-dimension features
        """
        ...


class FakeMorphologyEngine:
    """Deterministic stand-in for a real morphology engine.
    
    Uses a hash of the image path to generate a stable high-dimensional vector.
    This allows testing and development without requiring actual image processing.
    
    Parameters
    ----------
    dim : int
        Dimensionality of feature vectors (default: 50)
    
    Examples
    --------
    >>> engine = FakeMorphologyEngine(dim=10)
    >>> paths = ["image_a.tif", "image_b.tif"]
    >>> features = engine.extract_features(paths)
    >>> features.shape
    (2, 10)
    >>> # Same paths always give same features
    >>> features2 = engine.extract_features(paths)
    >>> np.allclose(features, features2)
    True
    """
    
    def __init__(self, dim: int = 50):
        """Initialize fake morphology engine.
        
        Parameters
        ----------
        dim : int
            Dimensionality of feature vectors
        """
        self.dim = dim
    
    def extract_features(self, image_paths: List[str]) -> np.ndarray:
        """Generate deterministic fake features from image paths.
        
        Parameters
        ----------
        image_paths : List[str]
            Paths to image files (only used for hashing)
        
        Returns
        -------
        features : np.ndarray
            Fake feature matrix (n_images × dim)
        """
        if not image_paths:
            return np.zeros((0, self.dim))
        
        feats = []
        for p in image_paths:
            # Use hash of path to generate stable features
            seed = abs(hash(p)) % (2**32)
            rng = np.random.RandomState(seed)
            feats.append(rng.normal(loc=0.0, scale=1.0, size=self.dim))
        
        return np.vstack(feats)
    
    def reduce_dimensionality(self, features: np.ndarray) -> np.ndarray:
        """No-op dimensionality reduction for fake engine.
        
        Parameters
        ----------
        features : np.ndarray
            Input features
        
        Returns
        -------
        features : np.ndarray
            Same as input (no reduction)
        """
        # For now, no-op reduction
        return features


class RealMorphologyEngine:
    """Real morphology engine that loads embeddings from disk.
    
    Loads pre-computed morphological embeddings from CSV files.
    
    CSV Schema:
        Index columns: cell_line, compound, dose_uM, time_h, plate_id, well_id
        Feature columns: feat_001, feat_002, ..., feat_050
    
    Parameters
    ----------
    csv_path : str or Path
        Path to CSV file containing embeddings
    dim : int
        Expected dimensionality of embeddings (default: 50)
    
    Examples
    --------
    >>> engine = RealMorphologyEngine("data/morphology/embeddings.csv")
    >>> embedding = engine.get_embedding("A549", "TBHP", 0.5, 24.0)
    >>> embedding.shape
    (50,)
    """
    
    def __init__(self, csv_path: str | Path, dim: int = 50):
        """Initialize real morphology engine.
        
        Parameters
        ----------
        csv_path : str or Path
            Path to CSV file with embeddings
        dim : int
            Expected dimensionality of embeddings
        """
        self.csv_path = Path(csv_path)
        self.dim = dim
        self._data: Optional[pd.DataFrame] = None
        self._load_embeddings()
    
    def _load_embeddings(self):
        """Load embeddings from CSV."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Embedding file not found: {self.csv_path}")
        
        self._data = pd.read_csv(self.csv_path)
        
        # Validate schema
        required_cols = ["cell_line", "compound", "dose_uM", "time_h", "plate_id", "well_id"]
        for col in required_cols:
            if col not in self._data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Check feature columns
        feat_cols = [c for c in self._data.columns if c.startswith("feat_")]
        if len(feat_cols) != self.dim:
            raise ValueError(f"Expected {self.dim} feature columns, found {len(feat_cols)}")
    
    def get_embedding(
        self,
        cell_line: str,
        compound: str,
        dose_uM: float,
        time_h: float,
        aggregation: str = "first",
    ) -> np.ndarray:
        """Get embedding for specific experimental condition.
        
        Parameters
        ----------
        cell_line : str
            Cell line name
        compound : str
            Compound name
        dose_uM : float
            Dose in micromolar
        time_h : float
            Time in hours
        aggregation : str
            How to handle multiple wells: "first", "mean", "median" (default: "first")
        
        Returns
        -------
        embedding : np.ndarray
            Feature vector (dim,)
        
        Raises
        ------
        ValueError
            If no matching data found
        """
        # Query data
        mask = (
            (self._data["cell_line"] == cell_line) &
            (self._data["compound"] == compound) &
            (np.abs(self._data["dose_uM"] - dose_uM) < 1e-6) &
            (np.abs(self._data["time_h"] - time_h) < 1e-6)
        )
        
        matches = self._data[mask]
        
        if len(matches) == 0:
            raise ValueError(
                f"No embedding found for {cell_line}/{compound}/{dose_uM}µM/{time_h}h"
            )
        
        # Extract feature columns
        feat_cols = [c for c in self._data.columns if c.startswith("feat_")]
        features = matches[feat_cols].values
        
        # Aggregate if multiple wells
        if aggregation == "first":
            # Sort by plate_id, well_id for determinism
            matches_sorted = matches.sort_values(["plate_id", "well_id"])
            return matches_sorted[feat_cols].iloc[0].values.astype(np.float64)
        elif aggregation == "mean":
            return features.mean(axis=0).astype(np.float64)
        elif aggregation == "median":
            return np.median(features, axis=0).astype(np.float64)
        else:
            raise ValueError(f"Unknown aggregation: {aggregation}")
    
    def extract_features(self, image_paths: List[str]) -> np.ndarray:
        """Extract features (not implemented for real engine).
        
        RealMorphologyEngine loads pre-computed features, so this method
        is not applicable. Use get_embedding() instead.
        """
        raise NotImplementedError(
            "RealMorphologyEngine loads pre-computed embeddings. "
            "Use get_embedding() instead of extract_features()."
        )
    
    def reduce_dimensionality(self, features: np.ndarray) -> np.ndarray:
        """No-op dimensionality reduction.
        
        Parameters
        ----------
        features : np.ndarray
            Input features
        
        Returns
        -------
        features : np.ndarray
            Same as input (no reduction)
        """
        return features


def create_morphology_engine(
    engine_type: str = "fake",
    csv_path: Optional[str | Path] = None,
    dim: int = 50,
) -> FakeMorphologyEngine | RealMorphologyEngine:
    """Factory function to create morphology engines.
    
    Parameters
    ----------
    engine_type : str
        Type of engine: "fake" or "real" (default: "fake")
    csv_path : str or Path, optional
        Path to CSV file (required for "real" engine)
    dim : int
        Dimensionality of embeddings (default: 50)
    
    Returns
    -------
    engine : FakeMorphologyEngine or RealMorphologyEngine
        Configured morphology engine
    
    Examples
    --------
    >>> # Use fake engine for testing
    >>> engine = create_morphology_engine("fake", dim=10)
    
    >>> # Use real engine with data
    >>> engine = create_morphology_engine("real", csv_path="data/morphology/embeddings.csv")
    """
    if engine_type == "fake":
        return FakeMorphologyEngine(dim=dim)
    elif engine_type == "real":
        if csv_path is None:
            raise ValueError("csv_path required for real morphology engine")
        return RealMorphologyEngine(csv_path=csv_path, dim=dim)
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
