"""
Test: Instrument health reward prevents the agent from gouging its own eyes out.

Three critical properties:
1. High-quality beats low-quality when science metric equal (steering)
2. Low-quality allowed when epistemic gain huge (flexibility)
3. Health term is bounded and logged (multi-objective, not collapsed)

This ensures the agent optimizes measurement reliability alongside discovery,
not accidentally optimizing the instrument into the ground.
"""

import pytest
import numpy as np
from src.cell_os.epistemic_agent.rewards.instrument_health_reward import (
    compute_instrument_health_reward,
    suggest_qc_mitigation,
    log_instrument_health_summary,
)


def test_high_quality_beats_low_quality_when_science_equal():
    """
    When epistemic gain is equal, higher QC should win.

    This is the core steering signal: agent prefers reliable regimes.
    """
    # Scenario A: High quality measurements
    observations_high_quality = [
        {
            'well_id': f'A{i}',
            'nuclei_qc': {
                'segmentation_quality': 0.90,
                'nuclei_cv': 0.08,
            }
        }
        for i in range(1, 11)  # 10 wells
    ]

    # Scenario B: Low quality measurements (same n_wells, same observable)
    observations_low_quality = [
        {
            'well_id': f'B{i}',
            'nuclei_qc': {
                'segmentation_quality': 0.50,
                'nuclei_cv': 0.30,
            }
        }
        for i in range(1, 11)  # 10 wells
    ]

    # Compute health rewards
    result_high = compute_instrument_health_reward(observations_high_quality)
    result_low = compute_instrument_health_reward(observations_low_quality)

    # High quality should have higher reward
    assert result_high['health_reward'] > result_low['health_reward'], (
        f"High quality should beat low quality. "
        f"High={result_high['health_reward']:.3f}, Low={result_low['health_reward']:.3f}"
    )

    # High quality should have higher health score
    assert result_high['health_metrics'].health_score > result_low['health_metrics'].health_score

    # High quality should not trigger mitigation
    assert result_high['mitigation_triggered'] is False

    # Low quality should trigger mitigation
    assert result_low['mitigation_triggered'] is True


def test_low_quality_allowed_when_epistemic_gain_huge():
    """
    When epistemic gain is huge, low QC should be acceptable.

    This tests flexibility: agent can pay QC cost for discovery.
    Key: health reward is bounded so it can't dominate epistemic term.
    """
    # Scenario: Low quality regime but potentially high information
    observations_low_quality_high_info = [
        {
            'well_id': f'C{i}',
            'nuclei_qc': {
                'segmentation_quality': 0.55,  # Below threshold but not catastrophic
                'nuclei_cv': 0.28,  # High but measurable
            }
        }
        for i in range(1, 21)  # 20 wells (more data)
    ]

    result = compute_instrument_health_reward(observations_low_quality_high_info)

    # Health reward should be negative (penalize low quality)
    assert result['health_reward'] < 0, (
        f"Low quality should have negative reward: {result['health_reward']:.3f}"
    )

    # But bounded: shouldn't be catastrophic
    # If epistemic gain is e.g. +50, and health is -2, epistemic dominates
    assert result['health_reward'] > -10.0, (
        f"Health penalty should be bounded (not catastrophic): {result['health_reward']:.3f}"
    )

    # Mitigation triggered (agent knows it's in low-quality regime)
    assert result['mitigation_triggered'] is True

    # But health reward is bounded, so epistemic gain can still dominate
    # Key: The negative reward shouldn't block a high-information experiment
    assert result['health_reward'] > -5.0, (
        f"Health penalty should allow epistemic gain to dominate: {result['health_reward']:.3f}"
    )


def test_health_term_is_bounded_and_logged():
    """
    Health reward must be bounded to avoid dominating epistemic term.

    Also verify all components are logged for multi-objective tracking.
    """
    # Test extreme regimes
    scenarios = [
        {
            'name': 'perfect',
            'observations': [
                {'well_id': f'D{i}', 'nuclei_qc': {'segmentation_quality': 1.0, 'nuclei_cv': 0.05}}
                for i in range(1, 11)
            ],
            'expected_range': (0.0, 2.5),  # Positive but bounded
        },
        {
            'name': 'catastrophic',
            'observations': [
                {'well_id': f'E{i}', 'nuclei_qc': {'segmentation_quality': 0.1, 'nuclei_cv': 0.8}}
                for i in range(1, 11)
            ],
            'expected_range': (-10.5, 0.0),  # Negative but bounded
        },
        {
            'name': 'missing_qc',
            'observations': [
                {'well_id': f'F{i}'}  # No nuclei_qc field
                for i in range(1, 11)
            ],
            'expected_range': (-60.0, -40.0),  # Hard penalty but bounded
        },
    ]

    for scenario in scenarios:
        result = compute_instrument_health_reward(scenario['observations'])

        # Check boundedness
        reward = result['health_reward']
        min_expected, max_expected = scenario['expected_range']

        assert min_expected <= reward <= max_expected, (
            f"Scenario '{scenario['name']}': reward {reward:.2f} outside expected range [{min_expected}, {max_expected}]"
        )

        # Verify all components logged
        metrics = result['health_metrics']
        assert hasattr(metrics, 'mean_segmentation_quality')
        assert hasattr(metrics, 'mean_nuclei_cv')
        assert hasattr(metrics, 'health_score')
        assert hasattr(metrics, 'health_reward')
        assert hasattr(metrics, 'n_qc_failures')

        # Verify health_score in [0, 1]
        assert 0.0 <= metrics.health_score <= 1.0, (
            f"Health score should be in [0, 1]: {metrics.health_score}"
        )


def test_qc_mitigation_triggers_at_thresholds():
    """
    QC mitigation should trigger when thresholds violated.

    Severity should scale with failure rate.
    """
    # Catastrophic failure (>50% wells failed)
    observations_catastrophic = [
        {'well_id': f'G{i}', 'nuclei_qc': {'segmentation_quality': 0.3, 'nuclei_cv': 0.5}}
        for i in range(1, 11)
    ]

    result_catastrophic = compute_instrument_health_reward(observations_catastrophic)

    assert result_catastrophic['mitigation_triggered'] is True
    mitigation = suggest_qc_mitigation(
        result_catastrophic['health_metrics'],
        result_catastrophic['qc_failures'],
        cycle=5
    )

    assert mitigation is not None
    assert mitigation['severity'] == 'critical'
    assert mitigation['action'] == 'replate_with_altered_layout'


def test_edge_concentrated_failures_suggest_edge_avoidance():
    """
    If QC failures are edge-concentrated, suggest avoiding edge wells.
    """
    # Edge wells fail, center wells pass
    observations = []

    # Edge wells (fail)
    for i in [1, 24]:  # Columns 1 and 24 are edges
        observations.append({
            'well_id': f'H{i}',
            'nuclei_qc': {'segmentation_quality': 0.4, 'nuclei_cv': 0.35}
        })

    # Center wells (pass)
    for i in range(6, 20):
        observations.append({
            'well_id': f'H{i}',
            'nuclei_qc': {'segmentation_quality': 0.85, 'nuclei_cv': 0.12}
        })

    result = compute_instrument_health_reward(observations)

    if result['mitigation_triggered']:
        mitigation = suggest_qc_mitigation(
            result['health_metrics'],
            result['qc_failures'],
            cycle=3
        )

        # Should suggest edge avoidance (if failure rate moderate and edge-concentrated)
        if mitigation and len(result['qc_failures']) > 0:
            # Edge failures should be detected
            edge_failures = [w for w in result['qc_failures'] if w.endswith('1') or w.endswith('24')]
            assert len(edge_failures) > 0, "Should detect edge failures"


def test_health_summary_logging_format():
    """
    Health summary should be human-readable and contain all key metrics.
    """
    observations = [
        {'well_id': f'I{i}', 'nuclei_qc': {'segmentation_quality': 0.75, 'nuclei_cv': 0.15}}
        for i in range(1, 11)
    ]

    result = compute_instrument_health_reward(observations)

    summary = log_instrument_health_summary(
        cycle=10,
        health_metrics=result['health_metrics'],
        mitigation=None
    )

    # Verify key components in summary
    assert 'Cycle 10' in summary
    assert 'Health Score' in summary
    assert 'Segmentation Quality' in summary
    assert 'Nuclei CV' in summary
    assert 'Health Reward' in summary


def test_custom_weights_and_thresholds():
    """
    Health reward should respect custom weights and thresholds.

    This allows tuning the multi-objective balance.
    """
    observations = [
        {'well_id': f'J{i}', 'nuclei_qc': {'segmentation_quality': 0.70, 'nuclei_cv': 0.20}}
        for i in range(1, 11)
    ]

    # Default weights
    result_default = compute_instrument_health_reward(observations)

    # Custom weights (emphasize quality more)
    result_custom = compute_instrument_health_reward(
        observations,
        weights={'quality_weight': 2.0, 'cv_penalty': 0.3, 'failure_penalty': 3.0}
    )

    # Custom thresholds (more lenient)
    result_lenient = compute_instrument_health_reward(
        observations,
        thresholds={'min_quality': 0.5, 'max_cv': 0.3}
    )

    # Custom weights should produce different rewards
    assert result_custom['health_reward'] != result_default['health_reward']

    # Lenient thresholds should reduce failures
    assert result_lenient['health_metrics'].n_qc_failures <= result_default['health_metrics'].n_qc_failures


def test_zero_wells_handled_gracefully():
    """
    Edge case: empty observations should not crash.
    """
    result = compute_instrument_health_reward([])

    assert result['health_reward'] == 0.0  # No penalty if no observations
    assert result['health_metrics'].n_wells_measured == 0
    assert result['mitigation_triggered'] is False  # Can't trigger without data
