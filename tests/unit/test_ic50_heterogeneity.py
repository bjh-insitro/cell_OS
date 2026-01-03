"""
Unit tests: IC50 heterogeneity (Phase 3.0).

Validates that ic50_shift_mult is sampled correctly and affects induction.

This is a bugfix test - prior to Phase 3.0, ic50_shift_mult was always 1.0
despite code reading it.
"""

import pytest
import numpy as np
from src.cell_os.hardware.stochastic_biology import StochasticBiologyHelper


def test_ic50_shift_mult_is_sampled():
    """
    ic50_shift_mult should be sampled (not always 1.0).

    Prior bug: ic50_shift_mult was always 1.0 because it wasn't in KEYMAP.
    """
    config = {
        'enabled': True,
        'ic50_cv': 0.20,  # 20% CV
        'plate_level_fraction': 0.0,  # Disable plate variance for single-plate test
        'growth_cv': 0.0,  # Disable others for isolation
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    # Sample many vessels
    ic50_mults = []
    for i in range(100):
        re = helper.sample_random_effects(
            lineage_id=f"lineage_{i}",
            plate_id="Plate1"
        )
        ic50_mults.append(re['ic50_shift_mult'])

    ic50_mults = np.array(ic50_mults)

    # Assert: Not all 1.0 (bugfix verification)
    assert not np.allclose(ic50_mults, 1.0), "ic50_shift_mult is always 1.0 (sampling broken)"

    # Assert: Mean close to 1.0 (lognormal correction working)
    mean_mult = np.mean(ic50_mults)
    assert 0.95 <= mean_mult <= 1.05, f"Mean ic50_shift_mult {mean_mult:.3f} not close to 1.0"

    # Assert: CV in expected range (20% ± some tolerance)
    cv_mult = np.std(ic50_mults) / mean_mult
    assert 0.15 <= cv_mult <= 0.25, f"CV of ic50_shift_mult {cv_mult:.3f} outside [0.15, 0.25]"

    # Assert: Positive values only
    assert np.all(ic50_mults > 0), "ic50_shift_mult has non-positive values"


def test_ic50_mult_hierarchical_structure():
    """
    ic50_shift_mult should have plate-level and vessel-level components.

    Vessels on same plate should be more correlated than vessels on different plates.
    """
    config = {
        'enabled': True,
        'ic50_cv': 0.20,
        'plate_level_fraction': 0.3,  # 30% variance at plate level
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    # Sample vessels from two plates
    plate1_mults = []
    plate2_mults = []
    for i in range(50):
        re1 = helper.sample_random_effects(f"lineage_p1_{i}", "Plate1")
        re2 = helper.sample_random_effects(f"lineage_p2_{i}", "Plate2")
        plate1_mults.append(re1['ic50_shift_mult'])
        plate2_mults.append(re2['ic50_shift_mult'])

    plate1_mults = np.array(plate1_mults)
    plate2_mults = np.array(plate2_mults)

    # Compute plate means
    mean_p1 = np.mean(plate1_mults)
    mean_p2 = np.mean(plate2_mults)

    # Assert: Plate means differ (plate-level variance exists)
    # With 30% variance at plate level, plate means should differ by ~sqrt(0.3) * sigma ~ 0.1
    assert abs(mean_p1 - mean_p2) > 0.05, \
        f"Plate means too similar ({mean_p1:.3f} vs {mean_p2:.3f}), plate-level variance missing"


def test_ic50_disabled_returns_one():
    """
    When disabled or CV=0, ic50_shift_mult should be 1.0.
    """
    config_disabled = {
        'enabled': False,
        'ic50_cv': 0.20,
    }
    helper_disabled = StochasticBiologyHelper(config_disabled, run_seed=42)

    re = helper_disabled.sample_random_effects("lineage_1", "Plate1")
    assert re['ic50_shift_mult'] == 1.0, "Disabled should return 1.0"

    config_cv_zero = {
        'enabled': True,
        'ic50_cv': 0.0,
    }
    helper_cv_zero = StochasticBiologyHelper(config_cv_zero, run_seed=42)

    re = helper_cv_zero.sample_random_effects("lineage_2", "Plate1")
    assert re['ic50_shift_mult'] == 1.0, "CV=0 should return 1.0"


def test_ic50_mult_deterministic_from_lineage():
    """
    ic50_shift_mult should be deterministic from lineage_id (stable under resampling).
    """
    config = {
        'enabled': True,
        'ic50_cv': 0.20,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    # Sample same lineage twice
    re1 = helper.sample_random_effects("lineage_stable", "Plate1")
    re2 = helper.sample_random_effects("lineage_stable", "Plate1")

    assert re1['ic50_shift_mult'] == re2['ic50_shift_mult'], \
        "ic50_shift_mult not deterministic from lineage_id"


def test_ic50_mult_independent_of_other_axes():
    """
    ic50_shift_mult should be sampled independently from growth/stress/hazard.

    Correlation should be low (not perfectly independent due to shared RNG, but <0.3).
    """
    config = {
        'enabled': True,
        'ic50_cv': 0.20,
        'growth_cv': 0.15,
        'stress_sensitivity_cv': 0.20,
        'hazard_scale_cv': 0.12,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    ic50_mults = []
    growth_mults = []
    for i in range(100):
        re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
        ic50_mults.append(re['ic50_shift_mult'])
        growth_mults.append(re['growth_rate_mult'])

    # Compute correlation
    corr = np.corrcoef(ic50_mults, growth_mults)[0, 1]

    # Assert: Low correlation (independent sampling)
    assert abs(corr) < 0.3, f"IC50 and growth too correlated ({corr:.3f}), should be independent"


def test_ic50_cv_parameter_range():
    """
    ic50_cv parameter should produce expected CV across reasonable ranges.
    """
    for target_cv in [0.10, 0.20, 0.30]:
        config = {
            'enabled': True,
            'ic50_cv': target_cv,
            'growth_cv': 0.0,
            'stress_sensitivity_cv': 0.0,
            'hazard_scale_cv': 0.0,
        }
        helper = StochasticBiologyHelper(config, run_seed=42)

        mults = []
        for i in range(200):
            re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
            mults.append(re['ic50_shift_mult'])

        mults = np.array(mults)
        observed_cv = np.std(mults) / np.mean(mults)

        # Allow 20% tolerance on CV (sampling variance, wider at low CV)
        assert target_cv * 0.80 <= observed_cv <= target_cv * 1.20, \
            f"Target CV {target_cv:.2f}, observed {observed_cv:.3f} outside tolerance"
