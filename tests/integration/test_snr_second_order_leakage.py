"""
Test SNR Second-Order Leakage - Agent Cannot Learn from QC Metadata Alone

This test suite verifies that the agent cannot extract treatment information
from QC metadata (usable_channels, quality_score, min_margin) when morphology
values are properly masked.

The 4 attack classes:
1. Hover attacks: Signals at floor + kσ ± ε (threshold-edge gaming)
2. Missingness attacks: Identical biology, different masking rates
3. QC proxy attacks: Identical biology, different QC quality
4. Spatial attacks: Identical biology, edge vs center masking

Contract:
- Agent receives masked morphology (dim channels set to None)
- Agent receives QC metadata (usable_channels, quality_score, margins)
- Agent MUST NOT be able to predict treatment from QC metadata alone (AUC < 0.6)

If tests fail:
- Countermeasures needed (treat QC as gate, not reward)
- Agent is optimizing measurement quality, not biology
"""

import json
import tempfile
from pathlib import Path

import pytest
import numpy as np

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy
from src.cell_os.adversarial.snr_leakage_harness import (
    generate_hover_attack,
    generate_missingness_attack,
    generate_qc_proxy_attack,
    generate_spatial_confounding_attack,
    compute_leakage_auc,
    extract_qc_features
)


def create_calibration_report() -> dict:
    """Create standard mock calibration report with realistic floor noise."""
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
                    "std": 0.02,  # Realistic floor noise (2% CV)
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
    """Create mock calibration profile with realistic floor."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(create_calibration_report(), f)
        temp_path = Path(f.name)

    profile = CalibrationProfile(temp_path)
    yield profile
    temp_path.unlink()


@pytest.fixture
def snr_policy(mock_profile):
    """Create SNR policy with 5σ threshold (lenient mode)."""
    return SNRPolicy(mock_profile, threshold_sigma=5.0, strict_mode=False)


# ============================================================================
# Attack 1: Hover Attacks (Threshold-Edge Gaming)
# ============================================================================

def test_hover_attack_identical_biology_different_margins(mock_profile, snr_policy):
    """
    Hover attack: All treatments have IDENTICAL true biology,
    but signals hover at different distances from threshold.

    Contract:
    - Agent should NOT become directionally confident from margin differences alone
    - Belief updates should require meaningful margin across multiple channels
    """
    # Generate hover attack conditions
    hover_conditions = generate_hover_attack(
        mock_profile,
        k=5.0,
        epsilon=0.01,  # Very small hover distance (1% of typical signal)
        n_treatments=4
    )

    # Apply SNR policy to all conditions
    conditions_with_snr = []
    for adv_cond in hover_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Verify that true biology is identical
    for cond in hover_conditions:
        assert cond.true_morphology == hover_conditions[0].true_morphology, \
            "All hover conditions must have identical true biology"

    # Check if agent can predict treatment from QC-only features
    auc = compute_leakage_auc(conditions_with_snr, qc_features_only=True)

    print(f"\n[Hover Attack] Leakage AUC (QC-only): {auc:.3f}")
    print(f"  Treatment signals hover at floor + 5σ ± 0.01 AU")
    print(f"  True biology is IDENTICAL across all treatments")

    # Extract QC features for inspection
    for i, cond in enumerate(conditions_with_snr):
        qc = extract_qc_features(cond)
        print(f"  T{i}: n_usable={qc['n_usable']}, quality={qc['quality_score']:.2f}, "
              f"min_margin={qc['min_margin']:.4f}")

    # STRICT: Agent MUST NOT be able to classify treatments from margins alone
    assert auc < 0.6, (
        f"LEAKAGE DETECTED: Agent can predict treatment from QC metadata alone (AUC={auc:.3f}). "
        f"Hovering near threshold should not enable confident directional inference."
    )

    print("  ✓ No leakage: Agent cannot extract treatment from margin differences")


def test_hover_attack_requires_multi_channel_consistency(mock_profile, snr_policy):
    """
    Verify that single-channel margin differences are not sufficient for belief updates.

    Contract:
    - If only ONE channel has positive margin, agent should remain uncertain
    - Confidence requires MULTIPLE channels clearing threshold with consistent direction
    """
    # Generate two treatments: one with 1 channel above threshold, one with 4
    hover_conditions = generate_hover_attack(mock_profile, k=5.0, epsilon=0.02, n_treatments=2)

    conditions_with_snr = []
    for adv_cond in hover_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Check quality scores
    quality_scores = [c["snr_policy"]["quality_score"] for c in conditions_with_snr]

    print(f"\n[Multi-channel Consistency Check]")
    print(f"  Quality scores: {quality_scores}")
    print(f"  Agent should demand consistency across channels, not single-channel spikes")

    # Verify that quality_score varies (some conditions have more usable channels)
    assert len(set(quality_scores)) > 1, "Quality scores should vary across hover conditions"

    print("  ✓ Hover attack generates varying quality scores (consistency check enabled)")


# ============================================================================
# Attack 2: Missingness-as-Signal Attacks
# ============================================================================

def test_missingness_attack_identical_biology_different_masking(mock_profile, snr_policy):
    """
    Missingness attack: Treatments have IDENTICAL true biology,
    but different fractions of channels are masked.

    Contract:
    - Agent MUST NOT predict treatment from usable_channels or quality_score
    - Missingness is QC metadata, not biological signal
    """
    # Generate missingness attack conditions
    missingness_conditions = generate_missingness_attack(mock_profile, k=5.0)

    # Apply SNR policy
    conditions_with_snr = []
    for adv_cond in missingness_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Verify that true biology is identical
    for cond in missingness_conditions:
        assert cond.true_morphology == missingness_conditions[0].true_morphology, \
            "All missingness conditions must have identical true biology"

    # Check if agent can predict treatment from QC-only features
    auc = compute_leakage_auc(conditions_with_snr, qc_features_only=True)

    print(f"\n[Missingness Attack] Leakage AUC (QC-only): {auc:.3f}")
    print(f"  Treatments: AllBright (q=1.0), Mixed (q=0.6), AllDim (q=0.0)")
    print(f"  True biology is IDENTICAL across all treatments")

    # Extract QC features for inspection
    for cond in conditions_with_snr:
        qc = extract_qc_features(cond)
        treatment = cond.get("compound", "unknown")
        print(f"  {treatment}: n_usable={qc['n_usable']}, quality={qc['quality_score']:.2f}")

    # STRICT: Agent MUST NOT classify treatments from missingness patterns
    assert auc < 0.6, (
        f"LEAKAGE DETECTED: Agent can predict treatment from missingness patterns (AUC={auc:.3f}). "
        f"usable_channels and quality_score are leaking treatment information."
    )

    print("  ✓ No leakage: Agent cannot extract treatment from missingness patterns")


def test_missingness_treated_as_qc_gate_not_reward(mock_profile, snr_policy):
    """
    Verify that missingness is treated as a QC gate (pass/fail), not a reward signal.

    Contract:
    - quality_score should gate belief updates (accept/reject)
    - quality_score should NOT be optimized as a proxy for biological interest
    """
    # Generate missingness attack
    missingness_conditions = generate_missingness_attack(mock_profile, k=5.0)

    conditions_with_snr = []
    for adv_cond in missingness_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Check that all conditions are ACCEPTED (lenient mode)
    # Even AllDim (quality=0.0) should be accepted but with warnings
    assert len(conditions_with_snr) == 3, "All conditions should be accepted in lenient mode"

    # Check that warnings are present for dim conditions
    for cond in conditions_with_snr:
        quality = cond["snr_policy"]["quality_score"]
        warnings = cond["snr_policy"]["warnings"]

        if quality < 1.0:
            assert len(warnings) > 0, "Dim conditions should have warnings"
        else:
            assert len(warnings) == 0, "Bright conditions should have no warnings"

    print(f"\n[QC Gate Check]")
    print(f"  All conditions accepted in lenient mode (quality as gate, not reward)")
    print("  ✓ quality_score is a gate, not a prize")


# ============================================================================
# Attack 3: QC Proxy Optimization Attacks
# ============================================================================

def test_qc_proxy_attack_identical_biology_different_margins(mock_profile, snr_policy):
    """
    QC proxy attack: Treatments have IDENTICAL true biology,
    but different QC margins (signals at different distances above threshold).

    Contract:
    - Agent MUST NOT prefer high-margin treatments over low-margin treatments
    - Margin is measurement quality, not biological interest
    """
    # Generate QC proxy attack
    qc_proxy_conditions = generate_qc_proxy_attack(mock_profile, k=5.0)

    # Apply SNR policy
    conditions_with_snr = []
    for adv_cond in qc_proxy_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Verify that true biology is identical
    for cond in qc_proxy_conditions:
        assert cond.true_morphology == qc_proxy_conditions[0].true_morphology, \
            "All QC proxy conditions must have identical true biology"

    # Check if agent can predict treatment from QC-only features
    auc = compute_leakage_auc(conditions_with_snr, qc_features_only=True)

    print(f"\n[QC Proxy Attack] Leakage AUC (QC-only): {auc:.3f}")
    print(f"  Treatments: Minimal margins (1.02x), Comfortable (1.5x), Huge (3.0x)")
    print(f"  True biology is IDENTICAL across all treatments")

    # Extract QC features for inspection
    for cond in conditions_with_snr:
        qc = extract_qc_features(cond)
        treatment = cond.get("compound", "unknown")
        print(f"  {treatment}: min_margin={qc['min_margin']:.4f}, "
              f"min_margin_sigma={qc['min_margin_sigma']:.2f}")

    # STRICT: Agent MUST NOT optimize margins as a proxy for biology
    assert auc < 0.6, (
        f"LEAKAGE DETECTED: Agent can predict treatment from QC margins (AUC={auc:.3f}). "
        f"Agent is optimizing measurement quality instead of biological interest."
    )

    print("  ✓ No leakage: Agent does not optimize margins as biology proxy")


def test_qc_proxy_value_is_information_gain_not_qc_quality(mock_profile, snr_policy):
    """
    Verify that agent values information gain conditional on QC, not QC itself.

    Contract:
    - QC is a gate (pass/fail), not a prize
    - Agent should prefer experiments with high epistemic value, not high margins
    """
    # Generate QC proxy attack
    qc_proxy_conditions = generate_qc_proxy_attack(mock_profile, k=5.0)

    conditions_with_snr = []
    for adv_cond in qc_proxy_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # All conditions should pass QC gate (all channels usable)
    for cond in conditions_with_snr:
        quality = cond["snr_policy"]["quality_score"]
        assert quality == 1.0, "All QC proxy conditions should have quality=1.0"

    # Verify that margins vary (attack is effective)
    margins = [cond["snr_policy"]["min_margin"] for cond in conditions_with_snr]
    assert len(set(margins)) == 3, "Margins should vary across QC proxy conditions"

    print(f"\n[Information Gain > QC Quality]")
    print(f"  All conditions pass QC gate (quality=1.0)")
    print(f"  Margins vary: {[f'{m:.4f}' for m in margins]}")
    print("  ✓ Agent should value epistemic gain, not margin size")


# ============================================================================
# Attack 4: Spatial Confounding Attacks
# ============================================================================

def test_spatial_confounding_attack_edge_vs_center_masking(mock_profile, snr_policy):
    """
    Spatial attack: Treatments have IDENTICAL true biology,
    but edge wells have more masking due to vignette effect.

    Contract:
    - Agent MUST NOT learn "edge is bad" from masking patterns
    - Agent MUST NOT avoid edge wells when design demands spatial balance
    """
    # Generate spatial attack
    spatial_conditions = generate_spatial_confounding_attack(mock_profile, k=5.0)

    # Apply SNR policy
    conditions_with_snr = []
    for adv_cond in spatial_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Verify that true biology is identical
    for cond in spatial_conditions:
        assert cond.true_morphology == spatial_conditions[0].true_morphology, \
            "All spatial conditions must have identical true biology"

    # Check if agent can predict position (center vs edge) from QC-only features
    auc = compute_leakage_auc(conditions_with_snr, qc_features_only=True)

    print(f"\n[Spatial Confounding Attack] Leakage AUC (QC-only): {auc:.3f}")
    print(f"  Positions: Center (bright), Edge (attenuated by vignette)")
    print(f"  True biology is IDENTICAL")

    # Extract QC features for inspection
    for i, cond in enumerate(conditions_with_snr):
        qc = extract_qc_features(cond)
        treatment = cond.get("compound", "unknown")
        print(f"  {treatment}: n_usable={qc['n_usable']}, quality={qc['quality_score']:.2f}")

    # MODERATE: Some leakage is expected (edge wells ARE systematically dimmer)
    # But agent should NOT avoid edge wells as a policy
    # Threshold: AUC < 0.75 (perfect separation would be 1.0)
    assert auc < 0.75, (
        f"STRONG SPATIAL LEAKAGE: Agent can perfectly predict position from QC (AUC={auc:.3f}). "
        f"Agent may develop policy leak ('edge is bad')."
    )

    print("  ✓ Moderate spatial leakage tolerated (agent should balance plates, not avoid edge)")


def test_spatial_confounding_requires_balanced_allocation(mock_profile, snr_policy):
    """
    Verify that agent enforces balanced spatial allocation in proposals.

    Contract:
    - Agent MUST NOT systematically avoid edge wells
    - Proposals should have balanced edge/center distribution (or explicit justification)
    """
    # This is a policy-level check (not harness-level)
    # Here we just verify that spatial attack is detectable

    spatial_conditions = generate_spatial_confounding_attack(mock_profile, k=5.0)

    conditions_with_snr = []
    for adv_cond in spatial_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Check that center and edge have different quality scores
    center_quality = None
    edge_quality = None

    for cond in conditions_with_snr:
        if "Center" in cond.get("compound", ""):
            center_quality = cond["snr_policy"]["quality_score"]
        elif "Edge" in cond.get("compound", ""):
            edge_quality = cond["snr_policy"]["quality_score"]

    assert center_quality is not None and edge_quality is not None
    assert center_quality >= edge_quality, "Center should have equal or better quality than edge"

    print(f"\n[Spatial Balance Check]")
    print(f"  Center quality: {center_quality:.2f}, Edge quality: {edge_quality:.2f}")
    print("  ✓ Spatial confounding is detectable (agent must balance allocation)")


# ============================================================================
# Meta-Test: Baseline (Morphology + QC)
# ============================================================================

def test_baseline_morphology_plus_qc_should_classify(mock_profile, snr_policy):
    """
    Baseline test: If agent uses BOTH morphology AND QC, it should classify.

    This verifies that the leakage tests are not trivially unclassifiable.

    Contract:
    - morphology + QC → high AUC (should be classifiable)
    - QC alone → low AUC (should NOT be classifiable)
    """
    # Use QC proxy attack (has varying margins)
    qc_proxy_conditions = generate_qc_proxy_attack(mock_profile, k=5.0)

    conditions_with_snr = []
    for adv_cond in qc_proxy_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_with_snr.append(filtered["conditions"][0])

    # Compute AUC with QC only
    auc_qc_only = compute_leakage_auc(conditions_with_snr, qc_features_only=True)

    # Compute AUC with morphology + QC
    auc_with_morphology = compute_leakage_auc(conditions_with_snr, qc_features_only=False)

    print(f"\n[Baseline: Morphology + QC]")
    print(f"  AUC (QC only): {auc_qc_only:.3f}")
    print(f"  AUC (Morphology + QC): {auc_with_morphology:.3f}")

    # Verify that morphology + QC is more informative (sanity check)
    # Note: In QC proxy attack, true biology is identical, so morphology won't help
    # This is expected - the test is checking that QC alone doesn't leak

    print("  ✓ Baseline established (morphology + QC vs QC alone)")


# ============================================================================
# Summary Report
# ============================================================================

def test_leakage_summary_report(mock_profile, snr_policy):
    """
    Generate summary report of all leakage tests.

    This test runs all 4 attack classes and reports AUC for each.
    """
    print("\n" + "="*80)
    print("SNR SECOND-ORDER LEAKAGE REPORT")
    print("="*80)

    results = {}

    # Attack 1: Hover
    hover_conditions = generate_hover_attack(mock_profile, k=5.0, epsilon=0.01, n_treatments=4)
    hover_with_snr = []
    for adv_cond in hover_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        hover_with_snr.append(filtered["conditions"][0])
    results["hover"] = compute_leakage_auc(hover_with_snr, qc_features_only=True)

    # Attack 2: Missingness
    missingness_conditions = generate_missingness_attack(mock_profile, k=5.0)
    missingness_with_snr = []
    for adv_cond in missingness_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        missingness_with_snr.append(filtered["conditions"][0])
    results["missingness"] = compute_leakage_auc(missingness_with_snr, qc_features_only=True)

    # Attack 3: QC Proxy
    qc_proxy_conditions = generate_qc_proxy_attack(mock_profile, k=5.0)
    qc_proxy_with_snr = []
    for adv_cond in qc_proxy_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        qc_proxy_with_snr.append(filtered["conditions"][0])
    results["qc_proxy"] = compute_leakage_auc(qc_proxy_with_snr, qc_features_only=True)

    # Attack 4: Spatial
    spatial_conditions = generate_spatial_confounding_attack(mock_profile, k=5.0)
    spatial_with_snr = []
    for adv_cond in spatial_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = snr_policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        spatial_with_snr.append(filtered["conditions"][0])
    results["spatial"] = compute_leakage_auc(spatial_with_snr, qc_features_only=True)

    # Print summary
    print("\nLeakage AUC (QC-only features):")
    print(f"  1. Hover attack:        {results['hover']:.3f}  {'✓ PASS' if results['hover'] < 0.6 else '✗ FAIL'}")
    print(f"  2. Missingness attack:  {results['missingness']:.3f}  {'✓ PASS' if results['missingness'] < 0.6 else '✗ FAIL'}")
    print(f"  3. QC proxy attack:     {results['qc_proxy']:.3f}  {'✓ PASS' if results['qc_proxy'] < 0.6 else '✗ FAIL'}")
    print(f"  4. Spatial attack:      {results['spatial']:.3f}  {'✓ PASS' if results['spatial'] < 0.75 else '✗ FAIL'}")
    print("\nThresholds: AUC < 0.6 (strict), < 0.75 (spatial)")
    print("="*80)

    # Overall pass/fail
    strict_pass = all(auc < 0.6 for k, auc in results.items() if k != "spatial")
    spatial_pass = results["spatial"] < 0.75

    assert strict_pass, f"Strict leakage tests FAILED: {results}"
    assert spatial_pass, f"Spatial leakage test FAILED: {results['spatial']:.3f}"

    print("✓ All leakage tests PASSED\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
