"""
Tests for parameterized classifier thresholds (Issue #5) and stability (Issue #6).
"""

import pytest
from cell_os.hardware.masked_compound_phase5 import (
    ClassifierThresholds,
    DEFAULT_CLASSIFIER_THRESHOLDS,
    infer_stress_axis_with_confidence,
)


class TestClassifierThresholds:
    """Test ClassifierThresholds dataclass (Issue #5)."""

    def test_default_thresholds_exist(self):
        """Default thresholds should be defined."""
        assert DEFAULT_CLASSIFIER_THRESHOLDS is not None
        assert isinstance(DEFAULT_CLASSIFIER_THRESHOLDS, ClassifierThresholds)

    def test_default_values_match_original(self):
        """Default values should match original hardcoded values."""
        t = DEFAULT_CLASSIFIER_THRESHOLDS
        assert t.er_upr_min == 1.30
        assert t.er_struct_min == 1.15
        assert t.mito_atp_strong_max == 0.95
        assert t.transport_trafficking_min == 1.30
        assert t.min_winner_score == 0.05

    def test_thresholds_immutable(self):
        """Thresholds should be frozen (immutable)."""
        t = DEFAULT_CLASSIFIER_THRESHOLDS
        with pytest.raises(AttributeError):
            t.er_upr_min = 2.0

    def test_custom_thresholds(self):
        """Can create custom thresholds."""
        custom = ClassifierThresholds(er_upr_min=1.50, mito_atp_strong_max=0.90)
        assert custom.er_upr_min == 1.50
        assert custom.mito_atp_strong_max == 0.90

    def test_to_dict_serialization(self):
        """Thresholds serialize to dict."""
        d = DEFAULT_CLASSIFIER_THRESHOLDS.to_dict()
        assert "er_upr_min" in d
        assert d["er_upr_min"] == 1.30


class TestClassifierBackwardsCompatibility:
    """Test that classifier works without explicit thresholds."""

    def test_no_thresholds_uses_default(self):
        """Calling without thresholds uses defaults."""
        axis, conf = infer_stress_axis_with_confidence(
            er_fold=1.3, mito_fold=1.0, actin_fold=1.0,
            upr_fold=1.5, atp_fold=1.0, trafficking_fold=1.0
        )
        assert axis == "er_stress"

    def test_explicit_default_same_result(self):
        """Explicit default thresholds give same result."""
        args = dict(er_fold=1.3, mito_fold=1.0, actin_fold=1.0,
                   upr_fold=1.5, atp_fold=1.0, trafficking_fold=1.0)

        axis1, conf1 = infer_stress_axis_with_confidence(**args)
        axis2, conf2 = infer_stress_axis_with_confidence(**args, thresholds=DEFAULT_CLASSIFIER_THRESHOLDS)

        assert axis1 == axis2
        assert conf1 == conf2


class TestClassifierStability:
    """Test classifier stability under threshold perturbation (Issue #6)."""

    def test_small_perturbation_preserves_clear_calls(self):
        """Small threshold changes shouldn't flip clear predictions."""
        # Strong ER signal
        args = dict(er_fold=1.4, mito_fold=1.0, actin_fold=1.0,
                   upr_fold=1.8, atp_fold=1.0, trafficking_fold=1.0)

        # Test with ±5% threshold perturbation
        for delta in [-0.05, 0.0, 0.05]:
            perturbed = ClassifierThresholds(
                er_upr_min=1.30 * (1 + delta),
                er_struct_min=1.15 * (1 + delta),
            )
            axis, conf = infer_stress_axis_with_confidence(**args, thresholds=perturbed)
            assert axis == "er_stress", f"Failed at delta={delta}"

    def test_boundary_cases_sensitive_to_thresholds(self):
        """Near-boundary cases should be sensitive to thresholds."""
        # Moderate ER signal - above default thresholds
        args = dict(er_fold=1.25, mito_fold=1.0, actin_fold=1.0,
                   upr_fold=1.45, atp_fold=1.0, trafficking_fold=1.0)

        # Default: should detect ER
        axis1, _ = infer_stress_axis_with_confidence(**args)

        # Raised threshold: should NOT detect ER (values below new thresholds)
        strict = ClassifierThresholds(er_upr_min=1.50, er_struct_min=1.30)
        axis2, _ = infer_stress_axis_with_confidence(**args, thresholds=strict)

        assert axis1 == "er_stress"
        assert axis2 is None  # No clear signal with stricter thresholds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
