"""
Agent 3 Test: Aggregation Cannot Silently Reduce Uncertainty

This test ensures that:
1. Aggregation transparently reports ALL wells (n_wells_total, n_wells_used, n_wells_dropped)
2. Drop reasons are explicitly tracked (drop_reasons dict)
3. Aggregation penalty is flagged when wells are dropped
4. Robust dispersion metrics (MAD, IQR) are computed alongside std

The test uses heavy-tailed noise to expose any silent CI tightening.
"""

import pytest
import numpy as np
from typing import List, Dict, Any

from cell_os.core.observation import RawWellResult, ConditionKey
from cell_os.core.experiment import SpatialLocation, Treatment
from cell_os.core.assay import AssayType
from cell_os.epistemic_agent.observation_aggregator import _summarize_condition


def make_raw_well(
    well_id: str,
    response: float,
    failed: bool = False
) -> Dict[str, Any]:
    """Create a raw well value dict for aggregation."""
    features = {
        'er': response * 0.2,
        'mito': response * 0.2,
        'nucleus': response * 0.2,
        'actin': response * 0.2,
        'rna': response * 0.2,
    }
    return {
        'response': response,
        'features': features,
        'well_id': well_id,
        'failed': failed,
    }


def test_aggregation_reports_all_wells_explicitly():
    """
    Test that n_wells_total, n_wells_used, n_wells_dropped are correctly reported.

    Agent 3 requirement: No silent information loss.
    """
    # Create canonical condition key directly
    from cell_os.core.canonicalize import canonical_condition_key

    canonical_key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    # 10 wells: 8 good, 2 failed
    values = []
    for i in range(8):
        values.append(make_raw_well(f"W{i}", response=1.0 + 0.1 * i, failed=False))
    for i in range(8, 10):
        values.append(make_raw_well(f"W{i}", response=0.0, failed=True))

    # Aggregate
    summary = _summarize_condition(canonical_key, values)

    # Agent 3: Verify transparency metadata
    assert summary.n_wells_total == 10, "Should count ALL wells"
    assert summary.n_wells_used == 8, "Should use only non-failed wells"
    assert summary.n_wells_dropped == 2, "Should report drops"
    assert 'qc_failed' in summary.drop_reasons, "Should explain WHY wells were dropped"
    assert summary.drop_reasons['qc_failed'] == 2, "Should count dropped wells by reason"


def test_aggregation_penalty_flag_set_when_drops_occur():
    """
    Test that aggregation_penalty_applied is True when wells are dropped.

    Agent 3 requirement: Flag when CI might be artificially tight.
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    # Case 1: No drops
    values_no_drops = [make_raw_well(f"W{i}", response=1.0, failed=False) for i in range(5)]
    summary_no_drops = _summarize_condition(key, values_no_drops)
    assert not summary_no_drops.aggregation_penalty_applied, "No penalty when no drops"

    # Case 2: With drops
    values_with_drops = [
        make_raw_well("W0", response=1.0, failed=False),
        make_raw_well("W1", response=1.0, failed=False),
        make_raw_well("W2", response=0.0, failed=True),  # Drop
    ]
    summary_with_drops = _summarize_condition(key, values_with_drops)
    assert summary_with_drops.aggregation_penalty_applied, "Penalty flag should be set when drops occur"


def test_robust_dispersion_metrics_computed():
    """
    Test that MAD and IQR are computed alongside std.

    Agent 3 requirement: Robust alternatives to std for heavy-tailed data.
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    # Heavy-tailed data: values with some spread plus outliers
    # Core values: 1.0, 1.1, 1.2, 1.3, 1.4, 1.5 (6 values with modest spread)
    # Outliers: 10.0, 10.0, 10.0, 10.0 (4 extreme outliers)
    values = []
    for i, response in enumerate([1.0, 1.1, 1.2, 1.3, 1.4, 1.5]):
        values.append(make_raw_well(f"W{i}", response=response, failed=False))
    for i in range(6, 10):
        values.append(make_raw_well(f"W{i}", response=10.0, failed=False))  # Outliers

    summary = _summarize_condition(key, values)

    # Agent 3: Verify robust metrics exist and detect dispersion
    assert summary.mad is not None, "MAD should be computed"
    assert summary.iqr is not None, "IQR should be computed"
    assert summary.mad > 0, "MAD should detect dispersion"
    assert summary.iqr > 0, "IQR should detect dispersion"
    assert summary.std > 0, "std should detect dispersion"

    # All three metrics should be positive, showing they detect the spread
    # Their relative magnitudes depend on the distribution shape
    # The key is that all are computed and reported honestly


def test_heavy_tailed_noise_transparency():
    """
    Test that heavy-tailed noise doesn't silently tighten CI.

    Agent 3 requirement: No silent uncertainty reduction.

    This is the core test: generate data from heavy-tailed distribution,
    verify that aggregation reports dispersion honestly (via MAD, IQR, and std).
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    # Generate heavy-tailed data: t-distribution with df=3 (heavier tails than normal)
    np.random.seed(42)
    n_wells = 20
    location = 1.0
    scale = 0.2
    responses = location + scale * np.random.standard_t(df=3, size=n_wells)

    values = [make_raw_well(f"W{i}", response=float(r), failed=False) for i, r in enumerate(responses)]

    summary = _summarize_condition(key, values)

    # Agent 3: Verify all wells are tracked
    assert summary.n_wells_total == n_wells
    assert summary.n_wells_used == n_wells
    assert summary.n_wells_dropped == 0

    # Verify dispersion metrics capture heavy tails
    # MAD should be robustly estimating scale
    # std should be larger (inflated by tails)
    # Both should be reported, no silent clipping

    empirical_mad = float(np.median(np.abs(responses - np.median(responses))))
    empirical_std = float(np.std(responses, ddof=1))

    # Check that computed metrics match empirical (no silent filtering)
    assert abs(summary.mad - empirical_mad) < 0.01, "MAD should match empirical (no silent filtering)"
    assert abs(summary.std - empirical_std) < 0.01, "std should match empirical (no silent filtering)"

    # Check that std > MAD for heavy-tailed data (sensitivity check)
    assert summary.std > summary.mad, "std should exceed MAD for heavy-tailed distribution"


def test_drop_reasons_are_explicit():
    """
    Test that drop reasons are explicitly enumerated.

    Agent 3 requirement: Never drop silently.
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    # Mix of good and failed wells
    values = [
        make_raw_well("W0", response=1.0, failed=False),
        make_raw_well("W1", response=1.0, failed=False),
        make_raw_well("W2", response=0.0, failed=True),
        make_raw_well("W3", response=0.0, failed=True),
        make_raw_well("W4", response=0.0, failed=True),
    ]

    summary = _summarize_condition(key, values)

    # Agent 3: Verify drop_reasons is a dict with explicit counts
    assert isinstance(summary.drop_reasons, dict), "drop_reasons should be a dict"
    assert 'qc_failed' in summary.drop_reasons, "Should have 'qc_failed' key"
    assert summary.drop_reasons['qc_failed'] == 3, "Should count each failure"

    # Verify it sums correctly
    total_drops = sum(summary.drop_reasons.values())
    assert total_drops == summary.n_wells_dropped, "drop_reasons should sum to n_wells_dropped"


def test_backward_compat_n_wells_is_total():
    """
    Test that n_wells (legacy field) equals n_wells_total for backward compatibility.

    Agent 3: Deprecated n_wells, but maintain compat.
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    values = [make_raw_well(f"W{i}", response=1.0, failed=False) for i in range(5)]
    summary = _summarize_condition(key, values)

    # Backward compat: n_wells should equal n_wells_total
    assert summary.n_wells == summary.n_wells_total, "n_wells should equal n_wells_total (backward compat)"


def test_aggregation_with_no_drops_has_zero_penalty():
    """
    Test that when no wells are dropped, penalty flag is False and drop_reasons is empty.
    """
    from cell_os.core.canonicalize import canonical_condition_key

    key = canonical_condition_key(
        cell_line='A549',
        compound_id='test',
        dose_uM=1.0,
        time_h=24.0,
        assay='cell_painting',
        position_class='center'
    )

    values = [make_raw_well(f"W{i}", response=1.0 + 0.1 * i, failed=False) for i in range(10)]
    summary = _summarize_condition(key, values)

    assert summary.n_wells_dropped == 0
    assert not summary.aggregation_penalty_applied
    assert len(summary.drop_reasons) == 0, "drop_reasons should be empty when no drops"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
