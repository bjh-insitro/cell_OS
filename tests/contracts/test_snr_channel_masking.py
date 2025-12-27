"""
Test SNR Channel Masking - Prevents Learning from Sub-Noise Channels

This test verifies that dim channels are actually MASKED (set to None) in
lenient mode, not just flagged with warnings. Without masking, the agent would
learn from "guilt-labeled poison" - dim channel values with warning labels.

Contract:
- Lenient mode + mask_dim_channels=True → dim channels set to None
- Agent cannot compute morphology deltas from masked channels
- usable_channels/masked_channels lists enable selective aggregation
"""

import json
import tempfile
from pathlib import Path

import pytest

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


def test_lenient_mode_masks_dim_channels(mock_profile):
    """
    CRITICAL: Lenient mode must MASK dim channels (set to None), not just warn.

    Without masking, agent learns from "guilt-labeled poison":
    - feature_means = {'er': 0.28, 'mito': 0.28, ...} ← poisoned data
    - warnings = ["er below threshold", ...] ← guilt label

    With masking, agent cannot use dim channels:
    - feature_means = {'er': None, 'mito': None, ...} ← unusable
    - usable_channels = [] ← explicit list of safe channels
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    # Observation with all dim channels (terrible SNR)
    obs = {
        "conditions": [
            {
                "compound": "DMSO",
                "dose_uM": 0.0,
                "time_h": 12.0,
                "feature_means": {
                    "er": 0.28,       # All below threshold (~0.30)
                    "mito": 0.28,
                    "nucleus": 0.28,
                    "actin": 0.28,
                    "rna": 0.28
                }
            }
        ]
    }

    # Filter with masking enabled
    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)

    cond = filtered["conditions"][0]
    snr = cond["snr_policy"]

    # Verify dim channels are MASKED (set to None)
    assert cond["feature_means"]["er"] is None, "Dim channel 'er' must be masked (None)"
    assert cond["feature_means"]["mito"] is None, "Dim channel 'mito' must be masked"
    assert cond["feature_means"]["nucleus"] is None, "Dim channel 'nucleus' must be masked"
    assert cond["feature_means"]["actin"] is None, "Dim channel 'actin' must be masked"
    assert cond["feature_means"]["rna"] is None, "Dim channel 'rna' must be masked"

    # Verify usable_channels is empty
    assert snr["usable_channels"] == [], "All channels dim, usable_channels should be empty"

    # Verify masked_channels lists all 5 channels
    assert set(snr["masked_channels"]) == {"er", "mito", "nucleus", "actin", "rna"}, \
        "All channels should be in masked_channels"

    # Verify quality score is 0.0 (no usable channels)
    assert snr["quality_score"] == 0.0, "Quality should be 0.0 with no usable channels"

    print("✓ Lenient mode masks dim channels (prevents learning from poison)")


def test_lenient_mode_preserves_bright_channels(mock_profile):
    """
    Verify that bright channels are NOT masked.

    Only dim channels should be set to None.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    # Mixed condition: 2 dim, 3 bright channels
    obs = {
        "conditions": [
            {
                "compound": "DrugA",
                "dose_uM": 1.0,
                "time_h": 12.0,
                "feature_means": {
                    "er": 0.28,       # Dim
                    "mito": 0.28,     # Dim
                    "nucleus": 0.60,  # Bright
                    "actin": 0.65,    # Bright
                    "rna": 0.68       # Bright
                }
            }
        ]
    }

    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)

    cond = filtered["conditions"][0]
    snr = cond["snr_policy"]

    # Verify dim channels are masked
    assert cond["feature_means"]["er"] is None, "Dim channel 'er' should be masked"
    assert cond["feature_means"]["mito"] is None, "Dim channel 'mito' should be masked"

    # Verify bright channels are preserved
    assert cond["feature_means"]["nucleus"] == 0.60, "Bright channel 'nucleus' should be preserved"
    assert cond["feature_means"]["actin"] == 0.65, "Bright channel 'actin' should be preserved"
    assert cond["feature_means"]["rna"] == 0.68, "Bright channel 'rna' should be preserved"

    # Verify lists
    assert set(snr["usable_channels"]) == {"nucleus", "actin", "rna"}
    assert set(snr["masked_channels"]) == {"er", "mito"}

    # Verify quality score
    assert snr["quality_score"] == 0.6, "Quality should be 3/5 = 0.6"

    print("✓ Bright channels preserved, only dim channels masked")


def test_masking_disabled_preserves_all_channels(mock_profile):
    """
    Verify that mask_dim_channels=False preserves original feature_means.

    This is for debugging or when agent explicitly wants to see all data.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    obs = {
        "conditions": [
            {
                "compound": "DMSO",
                "feature_means": {"er": 0.28, "mito": 0.28, "nucleus": 0.28, "actin": 0.28, "rna": 0.28}
            }
        ]
    }

    # Filter WITHOUT masking
    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=False)

    cond = filtered["conditions"][0]

    # All channels should be PRESERVED (original values)
    assert cond["feature_means"]["er"] == 0.28, "Channel preserved when masking disabled"
    assert cond["feature_means"]["mito"] == 0.28
    assert cond["feature_means"]["nucleus"] == 0.28

    # But metadata should still show they're dim
    assert len(cond["snr_policy"]["masked_channels"]) == 5
    assert cond["snr_policy"]["quality_score"] == 0.0

    print("✓ Masking disabled: all channels preserved (for debugging)")


def test_agent_can_compute_usable_morphology_delta(mock_profile):
    """
    Demonstrate how agent uses usable_channels to compute safe morphology deltas.

    Without usable_channels list, agent would mix safe and unsafe channels.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    # Baseline condition (all bright)
    baseline_obs = {
        "conditions": [{
            "compound": "DMSO",
            "feature_means": {"er": 0.50, "mito": 0.55, "nucleus": 0.60, "actin": 0.52, "rna": 0.58}
        }]
    }

    # Treatment condition (2 dim, 3 bright)
    treatment_obs = {
        "conditions": [{
            "compound": "DrugA",
            "feature_means": {"er": 0.28, "mito": 0.28, "nucleus": 0.70, "actin": 0.68, "rna": 0.72}
        }]
    }

    baseline_filtered = policy.filter_observation(baseline_obs, annotate=True, mask_dim_channels=True)
    treatment_filtered = policy.filter_observation(treatment_obs, annotate=True, mask_dim_channels=True)

    baseline_cond = baseline_filtered["conditions"][0]
    treatment_cond = treatment_filtered["conditions"][0]

    # Agent computes delta ONLY from usable channels (both conditions)
    baseline_usable = set(baseline_cond["snr_policy"]["usable_channels"])
    treatment_usable = set(treatment_cond["snr_policy"]["usable_channels"])
    safe_channels = baseline_usable & treatment_usable  # Intersection

    assert safe_channels == {"nucleus", "actin", "rna"}, \
        "Only channels usable in BOTH conditions are safe for comparison"

    # Compute morphology delta from safe channels only
    deltas = {}
    for ch in safe_channels:
        baseline_val = baseline_cond["feature_means"][ch]
        treatment_val = treatment_cond["feature_means"][ch]
        if baseline_val is not None and treatment_val is not None:
            deltas[ch] = treatment_val - baseline_val

    # Verify deltas computed only from safe channels (approximate comparison for floats)
    assert abs(deltas["nucleus"] - 0.10) < 0.001, "Nucleus delta should be ~0.10"
    assert abs(deltas["actin"] - 0.16) < 0.001, "Actin delta should be ~0.16"
    assert abs(deltas["rna"] - 0.14) < 0.001, "RNA delta should be ~0.14"

    # Compute mean delta (safe scalar summary)
    mean_delta = sum(deltas.values()) / len(deltas)
    assert abs(mean_delta - 0.133) < 0.01, "Mean delta from safe channels only"

    print("✓ Agent computes morphology delta from usable channels only (safe)")


def test_machine_readable_schema_enables_analytics(mock_profile):
    """
    Demonstrate that per_channel numeric fields enable cross-cycle analytics.

    This is why we need machine-readable data, not just warning strings.
    """
    policy = SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)

    obs = {
        "conditions": [{
            "compound": "DMSO",
            "feature_means": {"er": 0.28, "mito": 0.60, "nucleus": 0.70, "actin": 0.65, "rna": 0.68}
        }]
    }

    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
    snr = filtered["conditions"][0]["snr_policy"]

    # Extract per-channel margins (numeric, not strings)
    margins = {ch: detail["margin"] for ch, detail in snr["per_channel"].items()}

    # Agent can track margins across cycles (detector degradation)
    er_margin = margins["er"]
    assert er_margin < 0, "ER channel below threshold (negative margin)"
    assert margins["mito"] > 0, "Mito channel above threshold (positive margin)"

    # Agent can identify most conservative channel (minimum margin)
    min_margin_channel = min(margins.items(), key=lambda x: x[1])
    assert min_margin_channel[0] == "er", "ER has most negative margin"
    assert snr["min_margin"] == min_margin_channel[1], "min_margin matches min across channels"

    # Agent can compute "safety buffer" per channel
    safety_buffers = {ch: detail["margin"] / detail["threshold"] for ch, detail in snr["per_channel"].items() if detail["threshold"]}

    er_buffer = safety_buffers["er"]
    assert er_buffer < 0, "ER has negative safety buffer (below threshold)"

    print("✓ Machine-readable schema enables cross-cycle analytics")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
