"""
Unit tests: Death threshold heterogeneity with IC50 correlation (Phase 3.1).

Validates that death_threshold_shift_mult is:
- Sampled correctly (not always 1.0)
- Correlated with ic50_shift_mult (ρ ≈ 0.4-0.6)
- Has proper distribution (mean ~1.0, CV in band)
- Deterministic from lineage_id
- Has hierarchical structure (plate + vessel)
"""

import pytest
import numpy as np
from src.cell_os.hardware.stochastic_biology import StochasticBiologyHelper


def test_death_threshold_mult_is_sampled():
    """
    death_threshold_shift_mult should be sampled (not always 1.0).
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,  # 25% CV
        'ic50_cv': 0.20,
        'plate_level_fraction': 0.0,  # Disable plate variance for single-plate test
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    # Sample many vessels from same plate
    theta_mults = []
    for i in range(100):
        re = helper.sample_random_effects(
            lineage_id=f"lineage_{i}",
            plate_id="Plate1"
        )
        theta_mults.append(re['death_threshold_shift_mult'])

    theta_mults = np.array(theta_mults)

    # Assert: Not all 1.0 (sampling working)
    assert not np.allclose(theta_mults, 1.0), "death_threshold_shift_mult is always 1.0 (sampling broken)"

    # Assert: Mean close to 1.0 (lognormal correction working)
    mean_mult = np.mean(theta_mults)
    assert 0.95 <= mean_mult <= 1.05, f"Mean death_threshold_shift_mult {mean_mult:.3f} not close to 1.0"

    # Assert: CV in expected range (25% ± tolerance, wider at low sample size)
    cv_mult = np.std(theta_mults) / mean_mult
    assert 0.18 <= cv_mult <= 0.32, f"CV of death_threshold_shift_mult {cv_mult:.3f} outside [0.18, 0.32]"

    # Assert: Positive values only
    assert np.all(theta_mults > 0), "death_threshold_shift_mult has non-positive values"


def test_death_threshold_correlated_with_ic50():
    """
    death_threshold_shift_mult should be moderately correlated with ic50_shift_mult.

    Target: ρ ≈ 0.4-0.6 (moderate, not synonymous).
    Lower IC50 → more sensitive to induction → also more fragile (lower death threshold).
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.20,
        'sensitivity_correlation': 0.5,  # Target ρ = 0.5
        'growth_cv': 0.0,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    ic50_mults = []
    theta_mults = []

    for i in range(200):
        re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
        ic50_mults.append(re['ic50_shift_mult'])
        theta_mults.append(re['death_threshold_shift_mult'])

    ic50_mults = np.array(ic50_mults)
    theta_mults = np.array(theta_mults)

    # Compute correlation
    corr = np.corrcoef(ic50_mults, theta_mults)[0, 1]

    print(f"\nIC50 multipliers: mean={np.mean(ic50_mults):.3f}, std={np.std(ic50_mults):.3f}")
    print(f"Death threshold multipliers: mean={np.mean(theta_mults):.3f}, std={np.std(theta_mults):.3f}")
    print(f"Correlation (ic50_mult vs death_theta_mult): {corr:.3f}")

    # Assert: Moderate positive correlation (target ρ = 0.5, allow [0.35, 0.65])
    assert 0.35 <= corr <= 0.65, \
        f"Correlation {corr:.3f} outside target range [0.35, 0.65] (target ρ=0.5)"


def test_correlation_parameter_respected():
    """
    sensitivity_correlation parameter should control observed correlation.
    """
    for target_rho in [0.3, 0.5, 0.7]:
        config = {
            'enabled': True,
            'death_threshold_cv': 0.20,
            'ic50_cv': 0.20,
            'sensitivity_correlation': target_rho,
            'growth_cv': 0.0,
            'stress_sensitivity_cv': 0.0,
            'hazard_scale_cv': 0.0,
        }
        helper = StochasticBiologyHelper(config, run_seed=42)

        ic50_mults = []
        theta_mults = []
        for i in range(300):
            re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
            ic50_mults.append(re['ic50_shift_mult'])
            theta_mults.append(re['death_threshold_shift_mult'])

        corr = np.corrcoef(ic50_mults, theta_mults)[0, 1]

        # Allow ±0.15 tolerance (sampling variance)
        assert target_rho - 0.15 <= corr <= target_rho + 0.15, \
            f"Target ρ={target_rho:.2f}, observed {corr:.3f} outside tolerance"


def test_death_threshold_hierarchical_structure():
    """
    death_threshold_shift_mult should have plate-level and vessel-level components.

    Vessels on same plate should be more correlated than vessels on different plates.
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
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
        plate1_mults.append(re1['death_threshold_shift_mult'])
        plate2_mults.append(re2['death_threshold_shift_mult'])

    plate1_mults = np.array(plate1_mults)
    plate2_mults = np.array(plate2_mults)

    # Compute plate means
    mean_p1 = np.mean(plate1_mults)
    mean_p2 = np.mean(plate2_mults)

    # Assert: Plate means differ (plate-level variance exists)
    # With 30% variance at plate level and CV=0.25, expect ~0.1 difference
    assert abs(mean_p1 - mean_p2) > 0.05, \
        f"Plate means too similar ({mean_p1:.3f} vs {mean_p2:.3f}), plate-level variance missing"


def test_death_threshold_disabled_returns_one():
    """
    When disabled or CV=0, death_threshold_shift_mult should be 1.0.
    """
    config_disabled = {
        'enabled': False,
        'death_threshold_cv': 0.25,
    }
    helper_disabled = StochasticBiologyHelper(config_disabled, run_seed=42)

    re = helper_disabled.sample_random_effects("lineage_1", "Plate1")
    assert re['death_threshold_shift_mult'] == 1.0, "Disabled should return 1.0"

    config_cv_zero = {
        'enabled': True,
        'death_threshold_cv': 0.0,
    }
    helper_cv_zero = StochasticBiologyHelper(config_cv_zero, run_seed=42)

    re = helper_cv_zero.sample_random_effects("lineage_2", "Plate1")
    assert re['death_threshold_shift_mult'] == 1.0, "CV=0 should return 1.0"


def test_death_threshold_deterministic_from_lineage():
    """
    death_threshold_shift_mult should be deterministic from lineage_id.
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    # Sample same lineage twice
    re1 = helper.sample_random_effects("lineage_stable", "Plate1")
    re2 = helper.sample_random_effects("lineage_stable", "Plate1")

    assert re1['death_threshold_shift_mult'] == re2['death_threshold_shift_mult'], \
        "death_threshold_shift_mult not deterministic from lineage_id"


def test_death_threshold_independent_of_growth():
    """
    death_threshold_shift_mult should be independent of growth_rate_mult.

    Correlation should be low (<0.3).
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'growth_cv': 0.15,
        'ic50_cv': 0.20,
        'stress_sensitivity_cv': 0.0,
        'hazard_scale_cv': 0.0,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    theta_mults = []
    growth_mults = []
    for i in range(150):
        re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
        theta_mults.append(re['death_threshold_shift_mult'])
        growth_mults.append(re['growth_rate_mult'])

    # Compute correlation
    corr = np.corrcoef(theta_mults, growth_mults)[0, 1]

    # Assert: Low correlation (independent sampling, except for shared RNG effects)
    assert abs(corr) < 0.3, f"Death threshold and growth too correlated ({corr:.3f}), should be independent"


def test_death_threshold_cv_parameter_range():
    """
    death_threshold_cv parameter should produce expected CV across reasonable ranges.
    """
    for target_cv in [0.15, 0.25, 0.35]:
        config = {
            'enabled': True,
            'death_threshold_cv': target_cv,
            'plate_level_fraction': 0.0,  # Disable plate variance for single-plate test
            'ic50_cv': 0.0,  # Disable others for isolation
            'growth_cv': 0.0,
            'stress_sensitivity_cv': 0.0,
            'hazard_scale_cv': 0.0,
        }
        helper = StochasticBiologyHelper(config, run_seed=42)

        mults = []
        for i in range(200):
            re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
            mults.append(re['death_threshold_shift_mult'])

        mults = np.array(mults)
        observed_cv = np.std(mults) / np.mean(mults)

        # Allow 25% tolerance on CV (wider for low CV due to sampling variance)
        assert target_cv * 0.75 <= observed_cv <= target_cv * 1.25, \
            f"Target CV {target_cv:.2f}, observed {observed_cv:.3f} outside tolerance"


def test_ic50_and_death_threshold_not_synonymous():
    """
    Even with correlation, IC50 and death threshold should not be identical.

    With ρ = 0.5, R² ≈ 0.25 (75% independent variance).
    """
    config = {
        'enabled': True,
        'death_threshold_cv': 0.25,
        'ic50_cv': 0.20,
        'sensitivity_correlation': 0.5,
    }
    helper = StochasticBiologyHelper(config, run_seed=42)

    ic50_mults = []
    theta_mults = []
    for i in range(100):
        re = helper.sample_random_effects(f"lineage_{i}", "Plate1")
        ic50_mults.append(re['ic50_shift_mult'])
        theta_mults.append(re['death_threshold_shift_mult'])

    ic50_mults = np.array(ic50_mults)
    theta_mults = np.array(theta_mults)

    # Assert: Not identical
    assert not np.allclose(ic50_mults, theta_mults), \
        "IC50 and death threshold are identical (should be correlated but distinct)"

    # Assert: Correlation exists but not perfect
    corr = np.corrcoef(ic50_mults, theta_mults)[0, 1]
    assert corr < 0.95, f"Correlation too high ({corr:.3f}), should be moderate (~0.5)"
