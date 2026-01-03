#!/usr/bin/env python3
"""
Run SNR second-order leakage check and generate visual report.

Usage:
    python scripts/run_snr_leakage_check.py [--output-dir DIR]

Generates:
- AUC comparison plot (before/after QC stripping)
- QC feature embeddings
- Mask pattern distributions
- Summary report
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cell_os.calibration.profile import CalibrationProfile
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy
from src.cell_os.epistemic_agent.qc_gate import prepare_agent_observation
from src.cell_os.adversarial.snr_leakage_harness import (
    generate_hover_attack,
    generate_missingness_attack,
    generate_qc_proxy_attack,
    generate_spatial_confounding_attack,
    compute_leakage_auc
)
from src.cell_os.analysis.plot_snr_leakage import generate_leakage_report


def create_calibration_report() -> dict:
    """Create mock calibration report for testing."""
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
                    "std": 0.02,
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


def run_attack(attack_name, generator_func, profile, policy):
    """Run a single attack and return conditions before/after QC stripping."""
    print(f"  Running {attack_name}...", end=" ", flush=True)

    # Generate adversarial conditions
    adv_conditions = generator_func(profile, k=5.0)

    # Apply SNR policy (BEFORE: agent sees QC metadata)
    conditions_before = []
    for adv_cond in adv_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        conditions_before.extend(filtered["conditions"])

    # Strip QC metadata (AFTER: agent doesn't see QC metadata)
    conditions_after = []
    for adv_cond in adv_conditions:
        cond_dict = adv_cond.to_condition_summary()
        obs = {"conditions": [cond_dict]}
        filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
        agent_obs = prepare_agent_observation(filtered, apply_gate=False)
        conditions_after.extend(agent_obs["conditions"])

    # Compute AUC
    auc_before = compute_leakage_auc(conditions_before, qc_features_only=True)
    auc_after = compute_leakage_auc(conditions_after, qc_features_only=True)

    status = "✓" if auc_after < 0.6 else "✗"
    print(f"{status} (before: {auc_before:.3f}, after: {auc_after:.3f})")

    return auc_before, auc_after, conditions_before, conditions_after


def main():
    parser = argparse.ArgumentParser(description="Run SNR leakage check with visual report")
    parser.add_argument("--output-dir", default="snr_leakage_report",
                       help="Output directory for plots (default: snr_leakage_report)")
    parser.add_argument("--calibration", default=None,
                       help="Path to real calibration report (optional, uses mock if not provided)")
    args = parser.parse_args()

    print("="*80)
    print("SNR Second-Order Leakage Check")
    print("="*80)

    # Load calibration profile
    if args.calibration:
        print(f"\nUsing calibration: {args.calibration}")
        profile = CalibrationProfile(Path(args.calibration))
        temp_path = None
    else:
        print("\nUsing mock calibration profile")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(create_calibration_report(), f)
            temp_path = Path(f.name)
        profile = CalibrationProfile(temp_path)

    try:
        policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)

        print("\nRunning adversarial attacks...")

        results_before = {}
        results_after = {}
        conditions_before = {}
        conditions_after = {}

        # Run all 4 attacks
        attacks = [
            ("hover", "Hover (threshold-edge)", lambda p, k: generate_hover_attack(p, k=k, epsilon=0.01, n_treatments=4)),
            ("missingness", "Missingness (varying QC)", generate_missingness_attack),
            ("qc_proxy", "QC Proxy (varying margins)", generate_qc_proxy_attack),
            ("spatial", "Spatial (edge vs center)", generate_spatial_confounding_attack),
        ]

        for key, name, func in attacks:
            auc_b, auc_a, conds_b, conds_a = run_attack(name, func, profile, policy)
            results_before[key] = auc_b
            results_after[key] = auc_a
            conditions_before[key] = conds_b
            conditions_after[key] = conds_a

        # Generate visual report
        print(f"\nGenerating visual report...")
        generate_leakage_report(
            results_before,
            results_after,
            conditions_before,
            conditions_after,
            output_dir=args.output_dir
        )

        print(f"\n✓ Report saved to: {args.output_dir}/")

        # Check pass/fail
        strict_pass = all(auc < 0.6 for k, auc in results_after.items() if k != "spatial")
        spatial_pass = results_after["spatial"] < 0.75

        if strict_pass and spatial_pass:
            print("\n✓ All leakage checks PASSED")
            return 0
        else:
            print("\n✗ Some leakage checks FAILED")
            print("\nCountermeasures needed:")
            print("  1. Ensure QC metadata is stripped from agent-visible observations")
            print("  2. Use prepare_agent_observation() before passing to agent")
            print("  3. Check for additional leakage channels beyond QC metadata")
            return 1

    finally:
        if temp_path:
            temp_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
