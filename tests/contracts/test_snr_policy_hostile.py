"""
Hostile SNR Policy Tests - Physics Denial Prevention

These tests ensure SNR policy can't be gamed, bypassed, or accidentally
misconfigured in ways that let the agent hallucinate competence.

Checks:
1. No-peeking invariant: Policy uses only calibration + signal, never treatment metadata
2. Aggregation correctness: Rejected conditions don't leak into scalar aggregates
3. Quantization-aware threshold: Policy respects ADC limits, not just Gaussian sigma
4. Lenient mode loudness: Warnings are structured for agent decisions, not theater
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import numpy as np

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy


def create_calibration_report(
    floor_mean: float = 0.25,
    floor_unique_values: list = None,
    quant_step: float = 0.015,
    floor_observable: bool = True
) -> dict:
    """Create calibration report with specified floor/quantization params."""
    if floor_unique_values is None:
        # Default: sigma ~= 0.01 (range 0.06, divide by 6)
        floor_unique_values = [0.22, 0.24, 0.25, 0.26, 0.27, 0.28]

    report = {
        "schema_version": "bead_plate_calibration_report_v1",
        "created_utc": "2025-01-01T00:00:00Z",
        "channels": ["er", "mito", "nucleus", "actin", "rna"],
        "inputs": {
            "design_sha256": "mock",
            "detector_config_sha256": "mock"
        },
        "vignette": {
            "observable": True,
            "edge_multiplier": {"er": 0.85, "mito": 0.83, "nucleus": 0.88, "actin": 0.86, "rna": 0.84}
        },
        "saturation": {
            "observable": True,
            "per_channel": {ch: {"p99": 800.0, "confidence": "high"} for ch in ["er", "mito", "nucleus", "actin", "rna"]}
        },
        "quantization": {
            "observable": True,
            "per_channel": {ch: {"quant_step_estimate": quant_step} for ch in ["er", "mito", "nucleus", "actin", "rna"]}
        },
        "floor": {
            "observable": floor_observable,
            "reason": None if floor_observable else "Insufficient dark wells",
            "per_channel": {
                ch: {
                    "mean": floor_mean,
                    "std": 0.0,
                    "unique_values": floor_unique_values
                } for ch in ["er", "mito", "nucleus", "actin", "rna"]
            } if floor_observable else {}
        },
        "exposure_recommendations": {
            "observable": True,
            "global": {"warnings": []},
            "per_channel": {"er": {"recommended_exposure_multiplier": 0.9}}
        }
    }
    return report


@pytest.fixture
def mock_profile():
    """Standard mock profile."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(create_calibration_report(), f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    yield profile
    temp_path.unlink()


# =============================================================================
# 1. NO-PEEKING INVARIANT
# =============================================================================

def test_snr_policy_never_peeks_at_treatment_metadata(mock_profile):
    """
    HOSTILE CHECK 1: Ensure SNRPolicy uses ONLY calibration + signal values.

    If policy branches on compound, dose, time, cell_line, or any other
    treatment metadata, it's a clever censor, not physics.

    This test instruments check_measurement to verify it never receives
    anything except (signal: float, channel: str).
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0)

    # Spy on check_measurement calls
    calls = []
    original_check = policy.check_measurement

    def instrumented_check(signal, channel):
        # Record arguments
        calls.append({'signal': signal, 'channel': channel})
        # Verify types (physics data only)
        assert isinstance(signal, (int, float)), f"signal must be numeric, got {type(signal)}"
        assert isinstance(channel, str), f"channel must be string, got {type(channel)}"
        return original_check(signal, channel)

    policy.check_measurement = instrumented_check

    # Test with condition containing rich metadata
    condition = {
        "compound": "SuperDangerousDrug",
        "dose_uM": 666.0,
        "time_h": 666.0,
        "cell_line": "SuperSensitiveCells",
        "secret_metadata": "this_should_never_be_used",
        "feature_means": {
            "er": 0.30,
            "mito": 0.35,
            "nucleus": 0.40,
            "actin": 0.32,
            "rna": 0.38
        }
    }

    is_valid, warnings, _ = policy.check_condition_summary(condition)

    # Verify policy only saw (signal, channel) pairs
    assert len(calls) == 5, "Should check all 5 channels"
    for call in calls:
        # Only these keys allowed - no treatment metadata
        assert set(call.keys()) == {'signal', 'channel'}, \
            f"Policy peeked at non-physics data: {call.keys()}"

        # Signal must come from feature_means
        assert call['signal'] in condition['feature_means'].values(), \
            "Policy used signal not from feature_means"

        # Channel must be valid
        assert call['channel'] in ['er', 'mito', 'nucleus', 'actin', 'rna'], \
            f"Invalid channel: {call['channel']}"

    print("✓ SNR policy is physics-only (no peeking at treatment metadata)")


def test_snr_policy_deterministic_across_conditions(mock_profile):
    """
    HOSTILE CHECK 1b: Same signal + channel → same verdict, regardless of condition.

    If policy gives different answers for same (signal, channel) based on
    compound/dose/etc, it's condition-aware (bad).
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=True)

    signal = 0.35
    channel = "er"

    # Check same signal in different "dangerous" contexts
    contexts = [
        {"compound": "DMSO", "dose_uM": 0.0},
        {"compound": "CancerDrug", "dose_uM": 1000.0},
        {"compound": "Poison", "dose_uM": 0.001},
    ]

    verdicts = []
    for ctx in contexts:
        condition = {
            **ctx,
            "feature_means": {
                "er": signal,
                "mito": 0.50,
                "nucleus": 0.50,
                "actin": 0.50,
                "rna": 0.50
            }
        }
        is_valid, warnings, _ = policy.check_condition_summary(condition)
        verdicts.append((is_valid, len(warnings)))

    # All verdicts must be identical (policy is context-blind)
    assert len(set(verdicts)) == 1, \
        f"Policy gave different verdicts for same signal in different contexts: {verdicts}"

    print(f"✓ SNR policy is context-blind: signal={signal} → verdict={verdicts[0]}")


# =============================================================================
# 2. AGGREGATION CORRECTNESS
# =============================================================================

def test_strict_mode_rejects_entire_condition_not_channels(mock_profile):
    """
    HOSTILE CHECK 2: In strict mode, ensure rejected conditions don't leak
    into downstream aggregates (e.g., scalar mean computed from mixed channels).

    Failure mode: Agent sees "morphology delta = 0.05" computed from 4 good
    channels and 1 sub-threshold channel.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=True)

    # Condition with 1 dim channel, 4 bright channels
    condition = {
        "compound": "TestDrug",
        "dose_uM": 1.0,
        "time_h": 12.0,
        "feature_means": {
            "er": 0.28,     # Below threshold (~0.30)
            "mito": 0.60,   # Above threshold
            "nucleus": 0.70,
            "actin": 0.65,
            "rna": 0.68
        }
    }

    is_valid, warnings, _ = policy.check_condition_summary(condition)

    # Strict mode: entire condition invalid (not just ER channel)
    assert is_valid is False, "Strict mode must reject entire condition if ANY channel dim"
    assert len(warnings) >= 1, "Must have warning for dim channel"
    assert any("er" in w for w in warnings), "Warning must mention dim ER channel"

    # Now verify filter_observation removes it
    obs = {"conditions": [condition]}
    filtered = policy.filter_observation(obs, annotate=True)

    assert len(filtered["conditions"]) == 0, \
        "Strict mode must REMOVE condition from observation, not just flag it"
    assert filtered["snr_policy_summary"]["n_conditions_rejected"] == 1

    print("✓ Strict mode rejects entire condition (no leakage into aggregates)")


def test_per_channel_warnings_machine_readable(mock_profile):
    """
    HOSTILE CHECK 2b: Verify warnings are structured for programmatic use,
    not just human-readable strings.

    Agent should be able to parse: which channels failed, by how much, etc.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    condition = {
        "feature_means": {
            "er": 0.28,     # Dim (below 0.30)
            "mito": 0.60,   # Bright
            "nucleus": 0.70,
            "actin": 0.28,  # Dim (below 0.30)
            "rna": 0.68
        }
    }

    is_valid, warnings, _ = policy.check_condition_summary(condition)

    # Warnings should be structured: channel name at start, threshold info present
    dim_channels = []
    for w in warnings:
        # Warning format: "channel: Signal X AU is below Y threshold ..."
        if w.startswith("er:") or w.startswith("actin:"):
            # Parse channel name
            channel = w.split(":")[0].strip()
            dim_channels.append(channel)

            # Verify it contains quantitative info
            assert "AU" in w, "Warning must include units (AU)"
            assert "threshold" in w, "Warning must state threshold"
            assert "floor" in w or "σ" in w or "sigma" in w, "Warning must reference floor stats"

    assert set(dim_channels) == {"er", "actin"}, \
        f"Should warn about ER and actin only, got {dim_channels}"

    print(f"✓ Warnings are machine-readable: {len(warnings)} warnings, {len(dim_channels)} dim channels identified")


# =============================================================================
# 3. QUANTIZATION-AWARE THRESHOLD (THE KILLER BUG)
# =============================================================================

def test_quantization_dominates_gaussian_noise():
    """
    HOSTILE CHECK 3: When quantization step >> floor_sigma, policy must respect
    ADC limits, not just declare "low sigma = high detectability".

    Scenario:
    - floor_mean = 0.25 AU
    - floor_unique_values = [0.25, 0.25, 0.25] → sigma ≈ 0 (stuck on same code!)
    - quant_step = 0.05 AU (coarse ADC)

    Bug: Policy computes threshold = 0.25 + 5*0.0 = 0.25 AU → everything "detectable"
    Reality: Signal at 0.26 AU is indistinguishable from 0.25 AU (both same ADC code)

    Fix: threshold = floor_mean + max(5*floor_sigma, 3*quant_step)
    """
    # Create profile with tiny sigma, coarse quantization
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report = create_calibration_report(
            floor_mean=0.25,
            floor_unique_values=[0.25, 0.25, 0.25],  # All same → sigma ≈ 0
            quant_step=0.05  # Coarse ADC (5 LSB)
        )
        json.dump(report, f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)

    # Check floor_sigma is tiny (near zero)
    floor_sigma = profile.floor_sigma("er")
    assert floor_sigma is not None
    assert floor_sigma < 0.01, f"floor_sigma should be near zero, got {floor_sigma}"

    # Current policy (before fix) would compute:
    # threshold = 0.25 + 5*~0.0 = 0.25 AU
    # This is WRONG - quantization dominates!

    # Proper threshold should account for quantization:
    # threshold ≥ floor_mean + 3*quant_step = 0.25 + 3*0.05 = 0.40 AU

    # Test signals
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    signal_just_above_floor = 0.26  # 1 LSB above floor
    signal_3lsb_above = 0.40        # 3 LSB above floor (meaningful)

    # BUG CHECK: Current implementation only uses floor_sigma
    is_above_tiny, reason_tiny = policy.check_measurement(signal_just_above_floor, "er")
    is_above_3lsb, reason_3lsb = policy.check_measurement(signal_3lsb_above, "er")

    # Current behavior (will fail until fixed):
    # is_above_tiny = True (WRONG - only 1 LSB above, stuck in quantization noise)
    # is_above_3lsb = True (CORRECT)

    # Expected behavior (after fix):
    # is_above_tiny = False (signal indistinguishable from floor due to quantization)
    # is_above_3lsb = True (signal clearly above quantization noise)

    print(f"Floor mean: {profile.floor_mean('er')} AU")
    print(f"Floor sigma: {floor_sigma:.6f} AU (near zero)")
    print(f"Quant step: {profile.effective_resolution('er')} AU")
    print(f"Signal {signal_just_above_floor} AU: is_above={is_above_tiny} (should be FALSE)")
    print(f"Signal {signal_3lsb_above} AU: is_above={is_above_3lsb} (should be TRUE)")

    # Quantization-aware threshold should reject tiny signal, accept 3lsb signal
    assert is_above_tiny is False, \
        f"Signal {signal_just_above_floor} AU should be rejected (only 1 LSB above floor, " \
        f"indistinguishable due to quantization)"
    assert is_above_3lsb is True, \
        f"Signal {signal_3lsb_above} AU should be accepted (3 LSB above floor, " \
        f"clearly distinguishable)"

    print("✓ Quantization-aware threshold prevents physics denial")

    temp_path.unlink()


def test_quantization_aware_minimum_detectable_signal():
    """
    HOSTILE CHECK 3b: Verify minimum_detectable_signal respects quantization.

    When quantization dominates (quant_step >> sigma), MDS should be:
    MDS = floor_mean + max(k*sigma, 3*quant_step)

    Not just k*sigma.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report = create_calibration_report(
            floor_mean=0.25,
            floor_unique_values=[0.24, 0.25, 0.26],  # sigma ~= 0.02/6 ≈ 0.003
            quant_step=0.05  # Much larger than sigma
        )
        json.dump(report, f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    policy = SNRPolicy(profile, threshold_sigma=5.0)

    mds = policy.minimum_detectable_signals()
    quant_step = profile.effective_resolution("er")
    floor_mean = profile.floor_mean("er")

    # Expected MDS = floor_mean + max(5*sigma, 3*quant_step)
    # With sigma ≈ 0.003, 5*sigma ≈ 0.015
    # With quant_step = 0.05, 3*quant_step = 0.15
    # So MDS should be ≈ 0.25 + 0.15 = 0.40 AU

    expected_mds_lower_bound = floor_mean + 3 * quant_step

    print(f"Floor mean: {floor_mean} AU")
    print(f"Quant step: {quant_step} AU")
    print(f"Expected MDS ≥ {expected_mds_lower_bound} AU")
    print(f"Actual MDS: {mds['er']} AU")

    # Verify MDS accounts for quantization
    assert mds["er"] >= expected_mds_lower_bound, \
        f"MDS should account for quantization: {mds['er']:.3f} < {expected_mds_lower_bound:.3f}"

    # Verify MDS is close to expected (floor + 3*quant_step)
    expected_mds = floor_mean + 3 * quant_step
    assert abs(mds["er"] - expected_mds) < 0.001, \
        f"MDS should be {expected_mds:.3f} AU (floor + 3*quant), got {mds['er']:.3f}"

    print(f"✓ Quantization-aware MDS: {mds['er']:.3f} AU (accounts for coarse ADC)")

    temp_path.unlink()


# =============================================================================
# 4. LENIENT MODE LOUDNESS
# =============================================================================

def test_lenient_mode_warnings_in_qc_struct(mock_profile):
    """
    HOSTILE CHECK 4: Lenient mode warnings must propagate to qc_struct
    in a way downstream selection can use.

    Not just log lines nobody reads.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    # Condition with all dim channels (terrible SNR)
    condition = {
        "compound": "DMSO",
        "dose_uM": 0.0,
        "time_h": 12.0,
        "feature_means": {
            "er": 0.28,
            "mito": 0.28,
            "nucleus": 0.28,
            "actin": 0.28,
            "rna": 0.28
        }
    }

    obs = {"conditions": [condition]}
    filtered = policy.filter_observation(obs, annotate=True)

    # Check condition-level metadata
    assert len(filtered["conditions"]) == 1, "Lenient mode keeps condition"
    cond_meta = filtered["conditions"][0]["snr_policy"]

    # Must have structured warnings, not just strings
    assert "warnings" in cond_meta, "Condition must have warnings field"
    assert isinstance(cond_meta["warnings"], list), "Warnings must be list"
    assert len(cond_meta["warnings"]) == 5, "Should warn about all 5 dim channels"

    # Must flag as "valid but questionable"
    assert cond_meta["is_valid"] is True, "Lenient mode: is_valid=True"
    assert len(cond_meta["warnings"]) > 0, "But must have warnings"

    # Check observation-level summary
    assert "snr_policy_summary" in filtered
    summary = filtered["snr_policy_summary"]
    assert summary["n_conditions_rejected"] == 0, "Lenient mode rejects nothing"
    assert summary["n_conditions_accepted"] == 1

    print("✓ Lenient mode warnings are loud and structured:")
    print(f"  - {len(cond_meta['warnings'])} channel warnings at condition level")
    print(f"  - is_valid={cond_meta['is_valid']} (agent must decide)")
    print(f"  - Summary in qc_struct for downstream selection")


def test_lenient_mode_can_penalize_dim_conditions():
    """
    HOSTILE CHECK 4b: Demonstrate how agent can use SNR metadata to penalize
    proposals that repeatedly land sub-threshold.

    This is a "show your work" test - prove the schema enables smart decisions.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(create_calibration_report(), f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)

    # Mock observation with mixed SNR
    obs = {
        "conditions": [
            {
                "compound": "DMSO",
                "feature_means": {"er": 0.28, "mito": 0.28, "nucleus": 0.28, "actin": 0.28, "rna": 0.28}
            },
            {
                "compound": "DrugA",
                "feature_means": {"er": 0.50, "mito": 0.60, "nucleus": 0.70, "actin": 0.65, "rna": 0.68}
            },
            {
                "compound": "DrugB",
                "feature_means": {"er": 0.30, "mito": 0.55, "nucleus": 0.65, "actin": 0.60, "rna": 0.62}
            }
        ]
    }

    filtered = policy.filter_observation(obs, annotate=True)

    # Agent can compute "SNR quality score" from warnings
    quality_scores = []
    for cond in filtered["conditions"]:
        n_dim_channels = len(cond["snr_policy"]["warnings"])
        n_total_channels = 5
        quality_score = 1.0 - (n_dim_channels / n_total_channels)
        quality_scores.append({
            "compound": cond["compound"],
            "quality_score": quality_score,
            "n_dim_channels": n_dim_channels
        })

    print("✓ Agent can compute SNR quality scores:")
    for score in quality_scores:
        print(f"  {score['compound']}: quality={score['quality_score']:.2f} "
              f"({score['n_dim_channels']}/5 dim channels)")

    # Verify scores make sense
    dmso_score = [s for s in quality_scores if s["compound"] == "DMSO"][0]
    druga_score = [s for s in quality_scores if s["compound"] == "DrugA"][0]

    assert dmso_score["quality_score"] < druga_score["quality_score"], \
        "Dim condition should have lower quality score than bright condition"

    # Agent could penalize proposals that produce low-quality observations
    # Example: "If expected_quality < 0.5, increase exposure or reject proposal"

    temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
