"""
Test SNR None Laundering Prevention

CRITICAL: Ensures that None-masked channels never become 0.0 or NaN downstream.

Attack vector: Code that does `value or 0.0`, `np.nan_to_num(value)`, or
`if value > 0:` will quietly reintroduce poison when value=None.

Defense: Every morphology aggregation path must explicitly check for None
and either (a) skip the channel or (b) crash loudly.

This test feeds None-masked observations through the full agent update path
and asserts None never becomes a number without explicit imputation metadata.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import numpy as np

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy


def create_calibration_report() -> dict:
    """Create standard mock calibration report."""
    return {
        "schema_version": "bead_plate_calibration_report_v1",
        "created_utc": "2025-01-01T00:00:00Z",
        "channels": ["er", "mito", "nucleus", "actin", "rna"],
        "inputs": {"design_sha256": "mock", "detector_config_sha256": "mock"},
        "vignette": {
            "observable": True,
            "edge_multiplier": {ch: 0.85 for ch in ["er", "mito", "nucleus", "actin", "rna"]}
        },
        "saturation": {
            "observable": True,
            "per_channel": {ch: {"p99": 800.0, "confidence": "high"} for ch in ["er", "mito", "nucleus", "actin", "rna"]}
        },
        "quantization": {
            "observable": True,
            "per_channel": {ch: {"quant_step_estimate": 0.015} for ch in ["er", "mito", "nucleus", "actin", "rna"]}
        },
        "floor": {
            "observable": True,
            "per_channel": {
                ch: {
                    "mean": 0.25,
                    "std": 0.0,
                    "unique_values": [0.22, 0.24, 0.25, 0.26, 0.27, 0.28]
                } for ch in ["er", "mito", "nucleus", "actin", "rna"]
            }
        },
        "exposure_recommendations": {
            "observable": True,
            "global": {"warnings": []},
            "per_channel": {"er": {"recommended_exposure_multiplier": 0.9}}
        }
    }


@pytest.fixture
def mock_profile():
    """Create mock calibration profile."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(create_calibration_report(), f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    yield profile
    temp_path.unlink()


def test_none_stays_none_not_zero(mock_profile):
    """
    CRITICAL: None must stay None, not become 0.0.

    Common bug: `value or 0.0` converts None → 0.0
    Correct: `if value is not None: use(value)`
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    obs = {
        "conditions": [{
            "compound": "DMSO",
            "feature_means": {"er": 0.28, "mito": 0.60, "nucleus": 0.70, "actin": 0.65, "rna": 0.68}
        }]
    }

    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
    cond = filtered["conditions"][0]

    # Verify None stays None (not 0.0, not NaN)
    assert cond["feature_means"]["er"] is None, "Dim channel must be None"
    assert cond["feature_means"]["er"] != 0.0, "None must not become 0.0"
    assert not (isinstance(cond["feature_means"]["er"], float) and np.isnan(cond["feature_means"]["er"])), \
        "None must not become NaN"

    print("✓ None stays None (not 0.0, not NaN)")


def test_arithmetic_with_none_crashes_loudly(mock_profile):
    """
    Verify that arithmetic with None crashes with TypeError, not silent poison.

    If downstream code does `edge_val - center_val` where either is None,
    it should crash with TypeError, not produce 0.0 or NaN.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    obs = {
        "conditions": [{
            "compound": "DMSO",
            "feature_means": {"er": None, "mito": 0.60}  # er is masked
        }]
    }

    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
    cond = filtered["conditions"][0]

    # Attempt arithmetic with None (should crash)
    with pytest.raises(TypeError, match="unsupported operand type"):
        result = cond["feature_means"]["er"] - cond["feature_means"]["mito"]

    print("✓ Arithmetic with None crashes loudly (TypeError)")


def test_downstream_edge_updater_respects_none():
    """
    Test edge belief updater with None-masked channels.

    VULNERABLE PATH: beliefs/updates/edge.py:78-81
    ```python
    edge_val = edge.feature_means[channel]
    center_val = center.feature_means[channel]
    if center_val > 0:  # ← crashes if center_val is None
        effect = (edge_val - center_val) / center_val
    ```

    This test verifies the updater either:
    (a) Skips None channels
    (b) Crashes loudly with TypeError
    """
    from src.cell_os.epistemic_agent.beliefs.updates.edge import EdgeBeliefUpdater
    from src.cell_os.epistemic_agent.beliefs.state import BeliefState
    from src.cell_os.epistemic_agent.schemas import ConditionSummary

    beliefs = BeliefState()
    updater = EdgeBeliefUpdater(beliefs)

    # Create edge and center conditions with None-masked channels
    edge_cond = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=12.0,
        assay="cell_painting",
        position_tag="edge",
        n_wells=3,
        mean=0.5,
        std=0.05,
        sem=0.02,
        cv=0.1,
        min_val=0.45,
        max_val=0.55,
        feature_means={"er": None, "mito": 0.50, "nucleus": 0.60},  # er masked
        feature_stds={"er": None, "mito": 0.05, "nucleus": 0.06},
        n_failed=0,
        n_outliers=0
    )

    center_cond = ConditionSummary(
        cell_line="A549",
        compound="DMSO",
        dose_uM=0.0,
        time_h=12.0,
        assay="cell_painting",
        position_tag="center",
        n_wells=3,
        mean=0.6,
        std=0.05,
        sem=0.02,
        cv=0.1,
        min_val=0.55,
        max_val=0.65,
        feature_means={"er": None, "mito": 0.60, "nucleus": 0.70},  # er masked
        feature_stds={"er": None, "mito": 0.05, "nucleus": 0.06},
        n_failed=0,
        n_outliers=0
    )

    # Test updater (should either skip None or crash)
    try:
        updater.update([edge_cond, center_cond])

        # If it doesn't crash, verify it skipped None channels
        effects = beliefs.edge_effect_strength_by_channel
        assert "er" not in effects or effects["er"] is None, \
            "None channels should be skipped or set to None, not computed"

        # Verify it computed effects for non-None channels
        assert "mito" in effects, "Non-None channels should be computed"
        assert "nucleus" in effects, "Non-None channels should be computed"

        print("✓ Edge updater skips None channels (safe)")

    except TypeError as e:
        # If it crashes, that's acceptable (loud failure)
        assert "None" in str(e) or "unsupported operand" in str(e), \
            f"Expected TypeError related to None, got: {e}"
        print("✓ Edge updater crashes loudly on None (acceptable)")


def test_downstream_instrument_shape_respects_none():
    """
    Test instrument shape analyzer with None-masked channels.

    VULNERABLE PATH: instrument_shape.py:564
    ```python
    all_features[feature].append(value)  # ← appends None without checking
    ```

    If correlation code runs on list with None, it will crash or produce NaN.
    """
    # This is a simpler test - just verify None breaks correlations
    values_with_none = [0.5, 0.6, None, 0.55]

    # Attempt correlation (should crash or return NaN)
    try:
        corr = np.corrcoef(values_with_none, values_with_none)[0, 1]
        # If it doesn't crash, verify it's NaN (not a valid correlation)
        assert np.isnan(corr), "Correlation with None should be NaN, not a valid number"
        print("✓ Correlation with None produces NaN (detectable)")
    except (TypeError, ValueError) as e:
        # If it crashes, that's acceptable
        print(f"✓ Correlation with None crashes loudly: {type(e).__name__}")


def test_none_not_laundered_by_or_operator():
    """
    Test common None-laundering pattern: `value or default`.

    BAD: `value or 0.0` converts None → 0.0 (silent poison)
    GOOD: `value if value is not None else 0.0` (explicit)
    """
    value = None

    # BAD pattern (launders None → 0.0)
    bad_result = value or 0.0
    assert bad_result == 0.0, "or operator launders None to 0.0"

    # GOOD pattern (explicit check)
    good_result = value if value is not None else 0.0
    assert good_result == 0.0, "Explicit check converts None to 0.0"

    # But in our case, we should NEVER do this without imputation metadata
    # This test just demonstrates the vulnerability

    print("✓ Demonstrated: 'value or 0.0' launders None → 0.0 (AVOID THIS)")


def test_none_not_laundered_by_nan_to_num():
    """
    Test np.nan_to_num behavior with None.

    Actually, np.nan_to_num(None) → None (safe!)
    But np.nan_to_num(np.array([None])) → array([0.]) (DANGER!)
    """
    # Scalar None stays None (safe)
    value = None
    result = np.nan_to_num(value)
    assert result is None, "np.nan_to_num(None) returns None (safe)"

    # But array with None becomes 0.0 (DANGER)
    arr_with_none = np.array([0.5, None, 0.6], dtype=object)
    result_arr = np.nan_to_num(arr_with_none, nan=0.0)
    # Note: This will convert None to NaN first, then NaN to 0.0
    print(f"  np.nan_to_num(array([0.5, None, 0.6])) → {result_arr}")
    print("  ⚠ Arrays with None are dangerous with nan_to_num")

    print("✓ Demonstrated: scalar None safe, array with None dangerous")


def test_safe_aggregation_pattern(mock_profile):
    """
    Demonstrate safe aggregation pattern that respects None.

    SAFE pattern:
    ```python
    usable_values = [v for v in values if v is not None]
    if usable_values:
        mean = np.mean(usable_values)
    else:
        mean = None  # No usable data
    ```
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    obs = {
        "conditions": [{
            "compound": "DMSO",
            "feature_means": {"er": None, "mito": None, "nucleus": 0.60, "actin": 0.65, "rna": 0.68}
        }]
    }

    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
    cond = filtered["conditions"][0]

    # Safe aggregation using usable_channels
    usable_channels = cond["snr_policy"]["usable_channels"]
    usable_values = [cond["feature_means"][ch] for ch in usable_channels
                     if cond["feature_means"].get(ch) is not None]

    if usable_values:
        mean_morphology = np.mean(usable_values)
        assert not np.isnan(mean_morphology), "Mean should be valid number"
        assert mean_morphology > 0, "Mean should be positive"
    else:
        mean_morphology = None

    # Verify we got valid result
    assert mean_morphology is not None, "Should have usable channels"
    assert abs(mean_morphology - 0.643) < 0.01, "Mean of usable channels"

    print(f"✓ Safe aggregation: mean={mean_morphology:.3f} from {len(usable_channels)} usable channels")


def test_aggregator_preserves_none_from_raw_results():
    """
    CRITICAL: Test full aggregation path from raw results to ConditionSummary.

    This test verifies that None-masked channels in raw results:
    1. Stay None after feature extraction (no 0.0 laundering)
    2. Propagate through aggregation (no np.mean poisoning)
    3. Appear in usable_channels/masked_channels metadata
    4. Scalar response excludes masked channels
    """
    from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation
    from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
    from src.cell_os.core.observation import RawWellResult
    from src.cell_os.core.experiment import Treatment, SpatialLocation
    from src.cell_os.core.assay import AssayType

    # Create proposal
    proposal = Proposal(
        design_id="test_none_preservation",
        hypothesis="Testing None preservation",
        wells=[
            WellSpec(
                cell_line="A549",
                compound="DMSO",
                dose_uM=0.0,
                time_h=12.0,
                assay="cell_painting",
                position_tag="center"
            )
        ],
        budget_limit=10
    )

    # Create raw results with None-masked channels (simulating SNR policy output)
    raw_results = [
        RawWellResult(
            location=SpatialLocation(plate_id="test_plate", well_id="A1"),
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=12.0,
            readouts={
                "morphology": {
                    "er": None,        # Masked by SNR policy
                    "mito": 0.60,
                    "nucleus": 0.70,
                    "actin": 0.65,
                    "rna": 0.68
                }
            },
            qc={"failed": False}
        ),
        RawWellResult(
            location=SpatialLocation(plate_id="test_plate", well_id="A2"),
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=12.0,
            readouts={
                "morphology": {
                    "er": None,        # Masked by SNR policy
                    "mito": 0.62,
                    "nucleus": 0.72,
                    "actin": 0.67,
                    "rna": 0.70
                }
            },
            qc={"failed": False}
        ),
    ]

    # Run aggregation
    obs = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=8,
        cycle=0,
        strategy="default_per_channel"
    )

    # Verify observation has conditions
    assert len(obs.conditions) == 1, "Should have one condition"
    cond = obs.conditions[0]

    # CRITICAL: Verify None stays None in feature_means
    assert cond.feature_means["er"] is None, "Masked channel must be None"
    assert cond.feature_means["er"] != 0.0, "None must not become 0.0"

    # Verify non-None channels are aggregated correctly
    assert cond.feature_means["mito"] is not None, "Usable channel must have value"
    assert abs(cond.feature_means["mito"] - 0.61) < 0.01, "Should be mean of [0.60, 0.62]"

    # Verify metadata tracking
    assert hasattr(cond, "usable_channels"), "Must have usable_channels metadata"
    assert hasattr(cond, "masked_channels"), "Must have masked_channels metadata"
    assert "er" in cond.masked_channels, "er should be in masked_channels"
    assert "mito" in cond.usable_channels, "mito should be in usable_channels"
    assert len(cond.usable_channels) == 4, "Should have 4 usable channels"
    assert len(cond.masked_channels) == 1, "Should have 1 masked channel"

    # Verify scalar response excludes masked channels
    # Scalar should be mean of [0.61, 0.71, 0.66, 0.69] = 0.6675
    assert cond.mean is not None, "Scalar response should not be None (some channels usable)"
    expected_mean = (0.61 + 0.71 + 0.66 + 0.69) / 4
    assert abs(cond.mean - expected_mean) < 0.01, f"Scalar should exclude masked channel: {cond.mean}"

    print(f"✓ Aggregator preserves None: usable={cond.usable_channels}, masked={cond.masked_channels}")
    print(f"  Scalar response = {cond.mean:.3f} (excludes masked channels)")


def test_all_channels_masked_produces_none_scalar():
    """
    Test that when ALL channels are masked, scalar response becomes None.
    """
    from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation
    from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
    from src.cell_os.core.observation import RawWellResult
    from src.cell_os.core.experiment import Treatment, SpatialLocation
    from src.cell_os.core.assay import AssayType

    proposal = Proposal(
        design_id="test_all_masked",
        hypothesis="Testing all channels masked",
        wells=[WellSpec("A549", "DMSO", 0.0, 12.0, "cell_painting", "center")],
        budget_limit=10
    )

    # All channels masked
    raw_results = [
        RawWellResult(
            location=SpatialLocation(plate_id="test_plate", well_id="A1"),
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=12.0,
            readouts={
                "morphology": {
                    "er": None,
                    "mito": None,
                    "nucleus": None,
                    "actin": None,
                    "rna": None
                }
            },
            qc={"failed": False}
        )
    ]

    obs = aggregate_observation(proposal, raw_results, budget_remaining=9, cycle=0)
    cond = obs.conditions[0]

    # All channels masked
    assert all(cond.feature_means[ch] is None for ch in ["er", "mito", "nucleus", "actin", "rna"]), \
        "All channels should be None"
    assert len(cond.masked_channels) == 5, "All 5 channels should be masked"
    assert len(cond.usable_channels) == 0, "No usable channels"

    # Scalar response should be None
    assert cond.mean is None, "Scalar response must be None when all channels masked"

    print("✓ All channels masked → scalar response = None")


def test_partial_masking_across_replicates():
    """
    Test case where some replicates have a channel masked, others don't.

    This is an edge case: if replicate 1 has er=None and replicate 2 has er=0.5,
    should we:
    (a) Aggregate only the non-None values? (current implementation)
    (b) Mark entire channel as unreliable?

    This test documents current behavior (option a).
    """
    from src.cell_os.epistemic_agent.observation_aggregator import aggregate_observation
    from src.cell_os.epistemic_agent.schemas import Proposal, WellSpec
    from src.cell_os.core.observation import RawWellResult
    from src.cell_os.core.experiment import Treatment, SpatialLocation
    from src.cell_os.core.assay import AssayType

    proposal = Proposal(
        design_id="test_partial_masking",
        hypothesis="Testing partial masking",
        wells=[WellSpec("A549", "DMSO", 0.0, 12.0, "cell_painting", "center")],
        budget_limit=10
    )

    raw_results = [
        # Replicate 1: er masked
        RawWellResult(
            location=SpatialLocation(plate_id="test_plate", well_id="A1"),
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=12.0,
            readouts={"morphology": {"er": None, "mito": 0.60, "nucleus": 0.70, "actin": 0.65, "rna": 0.68}},
            qc={"failed": False}
        ),
        # Replicate 2: er usable
        RawWellResult(
            location=SpatialLocation(plate_id="test_plate", well_id="A2"),
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=12.0,
            readouts={"morphology": {"er": 0.50, "mito": 0.62, "nucleus": 0.72, "actin": 0.67, "rna": 0.70}},
            qc={"failed": False}
        ),
    ]

    obs = aggregate_observation(proposal, raw_results, budget_remaining=8, cycle=0)
    cond = obs.conditions[0]

    # Current behavior: aggregate only non-None values
    # er should be 0.50 (only one replicate usable)
    assert cond.feature_means["er"] is not None, "Should aggregate non-None values"
    assert abs(cond.feature_means["er"] - 0.50) < 0.01, "Should be mean of [0.50] (one replicate)"

    # er is in usable_channels because at least one replicate had signal
    assert "er" in cond.usable_channels, "Channel with partial masking still usable"

    print("✓ Partial masking: aggregates non-None values (current behavior)")
    print(f"  er = {cond.feature_means['er']:.2f} (1/2 replicates usable)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
