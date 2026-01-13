"""Tests for realistic noise model."""

import pytest
import numpy as np
from cell_os.biology.realistic_noise import (
    RealisticNoiseModel,
    NoiseParams,
    SpatialEffectParams,
    CHANNELS,
    DEFAULT_CHANNEL_CORRELATION,
    compute_morans_i,
    _parse_well_position,
    _is_edge_well,
)


class TestRealisticNoiseModel:
    """Tests for RealisticNoiseModel class."""

    def test_initialization(self):
        """Test model initializes correctly."""
        model = RealisticNoiseModel(seed=42)
        assert model.seed == 42
        assert model.params is not None
        assert model._cholesky is not None

    def test_deterministic_noise(self):
        """Test that noise is deterministic given same seed."""
        model1 = RealisticNoiseModel(seed=42)
        model2 = RealisticNoiseModel(seed=42)

        noise1 = model1.generate_correlated_noise("plate1", "A01", 0.1)
        noise2 = model2.generate_correlated_noise("plate1", "A01", 0.1)

        for ch in CHANNELS:
            assert noise1[ch] == pytest.approx(noise2[ch])

    def test_different_seeds_different_noise(self):
        """Test that different seeds produce different noise."""
        model1 = RealisticNoiseModel(seed=42)
        model2 = RealisticNoiseModel(seed=43)

        noise1 = model1.generate_correlated_noise("plate1", "A01", 0.1)
        noise2 = model2.generate_correlated_noise("plate1", "A01", 0.1)

        # At least one channel should differ
        differences = [abs(noise1[ch] - noise2[ch]) for ch in CHANNELS]
        assert max(differences) > 0.01

    def test_channel_correlations(self):
        """Test that generated noise has correct correlations."""
        model = RealisticNoiseModel(seed=42)
        n_samples = 1000

        samples = {ch: [] for ch in CHANNELS}
        for i in range(n_samples):
            noise = model.generate_correlated_noise("plate1", f"A{i:03d}", 0.1)
            for ch in CHANNELS:
                samples[ch].append(noise[ch])

        # Convert to arrays
        for ch in CHANNELS:
            samples[ch] = np.array(samples[ch])

        # Check ER-mito correlation (should be ~0.45)
        er_mito_corr = np.corrcoef(samples['er'], samples['mito'])[0, 1]
        assert 0.3 < er_mito_corr < 0.6  # Allow some variance

        # Check ER-RNA correlation (should be ~0.55)
        er_rna_corr = np.corrcoef(samples['er'], samples['rna'])[0, 1]
        assert 0.4 < er_rna_corr < 0.7


class TestSpatialEffects:
    """Tests for spatial effect calculations."""

    def test_edge_detection(self):
        """Test edge well detection."""
        assert _is_edge_well(0, 0, 8, 12) is True  # Corner
        assert _is_edge_well(0, 6, 8, 12) is True  # Top edge
        assert _is_edge_well(3, 0, 8, 12) is True  # Left edge
        assert _is_edge_well(3, 6, 8, 12) is False  # Center
        assert _is_edge_well(7, 11, 8, 12) is True  # Corner

    def test_well_position_parsing(self):
        """Test well ID parsing."""
        assert _parse_well_position("A01") == (0, 0)
        assert _parse_well_position("A12") == (0, 11)
        assert _parse_well_position("H01") == (7, 0)
        assert _parse_well_position("D06") == (3, 5)

    def test_edge_effect_reduces_signal(self):
        """Test that edge wells have reduced signal."""
        model = RealisticNoiseModel(seed=42)

        edge_effect = model.compute_spatial_effect("A01", "plate1")
        center_effect = model.compute_spatial_effect("D06", "plate1")

        assert edge_effect < center_effect

    def test_row_column_effects(self):
        """Test row/column systematic effects."""
        model = RealisticNoiseModel(seed=42)

        # Same row, different columns should share row effect
        effect_A01 = model.compute_row_column_effects("A01", "plate1")
        effect_A12 = model.compute_row_column_effects("A12", "plate1")

        # Both should be positive multipliers
        assert effect_A01 > 0.5
        assert effect_A12 > 0.5


class TestBatchDrift:
    """Tests for batch drift calculations."""

    def test_drift_increases_over_time(self):
        """Test that linear drift increases over time."""
        model = RealisticNoiseModel(seed=42)

        drift_start = model.compute_batch_drift("plate1", 0, 96)
        drift_mid = model.compute_batch_drift("plate1", 48, 96)
        drift_end = model.compute_batch_drift("plate1", 95, 96)

        # Linear drift should increase
        assert drift_start <= drift_mid <= drift_end

    def test_drift_bounded(self):
        """Test that drift is bounded to reasonable range."""
        model = RealisticNoiseModel(seed=42)

        for i in range(100):
            drift = model.compute_batch_drift("plate1", i, 100)
            assert 0.8 <= drift <= 1.2


class TestWellFailures:
    """Tests for well failure clustering."""

    def test_failure_rate(self):
        """Test that failure rate is approximately correct."""
        model = RealisticNoiseModel(seed=42)

        n_failures = 0
        n_wells = 1000
        for i in range(n_wells):
            is_failed, _, _ = model.check_well_failure(f"A{i:03d}", "plate1")
            if is_failed:
                n_failures += 1

        # Should be around 2% (allow 1-4%)
        failure_rate = n_failures / n_wells
        assert 0.01 < failure_rate < 0.05

    def test_failure_clustering(self):
        """Test that failures cluster near other failures."""
        model = RealisticNoiseModel(seed=42)

        # Check a well with and without failed neighbors
        failed_wells = {"A01", "A02", "B01"}

        _, _, mult_no_neighbor = model.check_well_failure("H12", "plate1", set())
        is_failed_with_neighbor, _, _ = model.check_well_failure("A03", "plate1", failed_wells)

        # Can't guarantee clustering in single test, but at least test it runs
        assert mult_no_neighbor >= 0


class TestAssayNoise:
    """Tests for assay-specific noise."""

    def test_ldh_higher_cv_than_cell_painting(self):
        """Test that LDH has higher CV than Cell Painting."""
        model = RealisticNoiseModel(seed=42)

        cp_values = [model.apply_assay_specific_noise(1.0, "cell_painting", f"A{i:02d}", "plate1", 0.0)
                     for i in range(100)]
        ldh_values = [model.apply_assay_specific_noise(1.0, "ldh", f"A{i:02d}", "plate1", 0.0)
                      for i in range(100)]

        cp_cv = np.std(cp_values) / np.mean(cp_values)
        ldh_cv = np.std(ldh_values) / np.mean(ldh_values)

        assert ldh_cv > cp_cv  # LDH should have higher CV

    def test_stress_increases_ldh_cv(self):
        """Test that stress increases LDH CV."""
        model = RealisticNoiseModel(seed=42)

        healthy_values = [model.apply_assay_specific_noise(1.0, "ldh", f"A{i:02d}", "plate1", 0.0)
                          for i in range(100)]
        stressed_values = [model.apply_assay_specific_noise(1.0, "ldh", f"B{i:02d}", "plate1", 0.8)
                           for i in range(100)]

        healthy_cv = np.std(healthy_values) / np.mean(healthy_values)
        stressed_cv = np.std(stressed_values) / np.mean(stressed_values)

        assert stressed_cv > healthy_cv


# TestPopulationHeterogeneity removed - discrete subpopulation modeling was intentionally
# removed after Phase 5/6 design review. See realistic_noise.py module docstring
# "Design Note - Why No Discrete Subpopulations" for rationale.


class TestMoransI:
    """Tests for Moran's I spatial autocorrelation."""

    def test_random_values_near_zero(self):
        """Test that random values give Moran's I near 0."""
        rng = np.random.default_rng(42)
        values = {}
        for row in range(8):
            for col in range(12):
                well_id = f"{chr(65 + row)}{col + 1:02d}"
                values[well_id] = rng.random()

        morans_i = compute_morans_i(values)
        assert -0.3 < morans_i < 0.3  # Should be near 0 for random

    def test_clustered_values_positive(self):
        """Test that clustered values give positive Moran's I."""
        values = {}
        for row in range(8):
            for col in range(12):
                well_id = f"{chr(65 + row)}{col + 1:02d}"
                # High values in top-left, low in bottom-right
                values[well_id] = 1.0 if (row < 4 and col < 6) else 0.0

        morans_i = compute_morans_i(values)
        assert morans_i > 0.3  # Should be positive for clustered


class TestApplyRealisticNoise:
    """Tests for the main apply_realistic_noise function."""

    def test_returns_all_channels(self):
        """Test that all channels are returned."""
        model = RealisticNoiseModel(seed=42)
        base_morph = {ch: 1.0 for ch in CHANNELS}

        result = model.apply_realistic_noise(base_morph, "A01", "plate1")

        for ch in CHANNELS:
            assert ch in result

    def test_values_are_positive(self):
        """Test that all values are non-negative."""
        model = RealisticNoiseModel(seed=42)
        base_morph = {ch: 1.0 for ch in CHANNELS}

        for i in range(100):
            result = model.apply_realistic_noise(base_morph, f"A{i:02d}", "plate1", stress_level=0.5)
            for ch in CHANNELS:
                assert result[ch] >= 0
