#!/usr/bin/env python3
"""
Phase 2D.1: Contamination Identifiability - Main Runner

Executes full suite: data generation → inference → scoring → verdict.

Usage:
    python scripts/run_identifiability_2d1.py [output_dir]

Outputs:
    - observations.npy, ground_truth.npy, metadata.yaml (from runner)
    - detections.npy, scores.yaml (from inference)
    - verdict: PASS / FAIL / INSUFFICIENT_EVENTS
"""

import sys
import numpy as np
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cell_os.calibration.identifiability_runner_2d1 import run_identifiability_suite
from cell_os.calibration.identifiability_inference_2d1 import (
    fit_clean_baseline,
    learn_type_prototypes,
    run_inference_on_regime,
    compute_sensitivity_specificity,
    compute_onset_mae,
    compute_type_accuracy,
)


def run_full_suite(output_dir: Path):
    """
    Run full identifiability suite: generate → infer → score → verdict.

    Args:
        output_dir: Output directory
    """
    output_dir = Path(output_dir)

    print("=" * 80)
    print("Phase 2D.1: Contamination Identifiability Suite")
    print("=" * 80)
    print()

    # ========================================================================
    # Step 1: Generate data
    # ========================================================================
    print("Step 1: Generating data...")
    print("-" * 80)

    result = run_identifiability_suite(output_dir)

    if result['status'] == 'INSUFFICIENT_EVENTS':
        print("\n❌ VERDICT: INSUFFICIENT_EVENTS")
        print("   Experiment design does not meet minimum event count preconditions.")
        print("   Increase n_vessels or duration_h.")
        return

    print()

    # ========================================================================
    # Step 2: Load data
    # ========================================================================
    print("Step 2: Loading data...")
    print("-" * 80)

    observations = np.load(output_dir / 'observations.npy')  # (regime, vessel, time, feature)
    ground_truth = np.load(output_dir / 'ground_truth.npy', allow_pickle=True).item()
    with open(output_dir / 'metadata.yaml', 'r') as f:
        metadata = yaml.safe_load(f)

    regime_labels = metadata['regime_order']
    times = np.array(metadata['regimes']['A_clean']['sampling_times'])

    print(f"  Observations shape: {observations.shape}")
    print(f"  Regimes: {regime_labels}")
    print(f"  Times: {len(times)} samples from {times[0]}h to {times[-1]}h")
    print()

    # ========================================================================
    # Step 3: Fit clean baseline (Regime A)
    # ========================================================================
    print("Step 3: Fitting clean baseline (Regime A)...")
    print("-" * 80)

    regime_A_obs = observations[0, :, :, :]  # First regime is A_clean
    clean_baseline = fit_clean_baseline(regime_A_obs)
    print(f"  Morphology baseline: mean={clean_baseline['morph_mean']}")
    print()

    # ========================================================================
    # Step 4: Learn type prototypes (Regime B)
    # ========================================================================
    print("Step 4: Learning type prototypes (Regime B)...")
    print("-" * 80)

    regime_B_obs = observations[1, :, :, :]  # Second regime is B_enriched
    regime_B_gt = ground_truth['B_enriched']
    type_prototypes = learn_type_prototypes(regime_B_obs, times, regime_B_gt)

    for ctype, prototype in type_prototypes.items():
        print(f"  {ctype:12s}: {prototype}")
    print()

    # ========================================================================
    # Step 5: Run inference on all regimes
    # ========================================================================
    print("Step 5: Running inference on all regimes...")
    print("-" * 80)

    all_detections = {}
    for i, regime_label in enumerate(regime_labels):
        print(f"  {regime_label}...")
        regime_obs = observations[i, :, :, :]
        detections = run_inference_on_regime(regime_obs, times, clean_baseline, type_prototypes)
        all_detections[regime_label] = detections

        n_flagged = sum(1 for d in detections if d['flagged'])
        print(f"    Flagged: {n_flagged}/{len(detections)} vessels")

    print()

    # ========================================================================
    # Step 6: Compute scores per regime
    # ========================================================================
    print("Step 6: Computing scores...")
    print("-" * 80)

    scores = {}

    for regime_label in regime_labels:
        detections = all_detections[regime_label]
        gt = ground_truth[regime_label]

        # Sensitivity/specificity
        perf = compute_sensitivity_specificity(detections, gt)

        # Onset MAE (on correctly detected true events)
        onset_mae, onset_errors = compute_onset_mae(detections, gt)

        # Type accuracy (on correctly detected true events)
        type_acc, type_confusion = compute_type_accuracy(detections, gt)

        # Estimated rate
        n_vessels = len(detections)
        duration_h = times[-1]
        detected_rate = perf['n_detected'] / (n_vessels * (duration_h / 24.0))

        # True rate (from metadata)
        true_rate = metadata['regimes'][regime_label]['contamination_config']
        if true_rate is not None:
            true_rate = true_rate['baseline_rate_per_vessel_day'] * true_rate.get('rate_multiplier', 1.0)
        else:
            true_rate = 0.0

        scores[regime_label] = {
            'performance': perf,
            'onset_mae': onset_mae,
            'onset_errors': onset_errors,
            'type_accuracy': type_acc,
            'type_confusion': type_confusion,
            'detected_rate': detected_rate,
            'true_rate': true_rate,
        }

        print(f"\n  {regime_label}:")
        print(f"    True events: {perf['n_true_events']}")
        print(f"    Detected: {perf['n_detected']} (TP={perf['TP']}, FP={perf['FP']}, FN={perf['FN']})")
        print(f"    Sensitivity: {perf['sensitivity']:.2%}")
        print(f"    FPR: {perf['fpr']:.2%}")
        print(f"    Onset MAE: {onset_mae:.1f}h ({len(onset_errors)} TP events)")
        print(f"    Type accuracy: {type_acc:.2%}")
        print(f"    Rate: true={true_rate:.5f}, detected={detected_rate:.5f}, ratio={detected_rate/true_rate if true_rate > 0 else np.nan:.2f}")

    print()

    # ========================================================================
    # Step 7: Verdict
    # ========================================================================
    print("Step 7: Verdict...")
    print("-" * 80)

    failures = []

    # Check 1: Regime A (clean) - FPR ≤ 1%
    fpr_A = scores['A_clean']['performance']['fpr']
    if fpr_A > 0.01:
        failures.append(f"Regime A FPR={fpr_A:.2%} > 1% (hallucination)")

    # Check 2: Regime D (disabled) - FPR ≤ 1%
    fpr_D = scores['D_disabled']['performance']['fpr']
    if fpr_D > 0.01:
        failures.append(f"Regime D FPR={fpr_D:.2%} > 1% (hallucination when disabled)")

    # Check 3: Regime B rate recovery within 2×
    rate_ratio_B = scores['B_enriched']['detected_rate'] / scores['B_enriched']['true_rate'] if scores['B_enriched']['true_rate'] > 0 else np.nan
    if not (0.5 <= rate_ratio_B <= 2.0):
        failures.append(f"Regime B rate ratio={rate_ratio_B:.2f} outside [0.5, 2.0]")

    # Check 4: Regime C rate recovery within 2×
    rate_ratio_C = scores['C_held_out']['detected_rate'] / scores['C_held_out']['true_rate'] if scores['C_held_out']['true_rate'] > 0 else np.nan
    if not (0.5 <= rate_ratio_C <= 2.0):
        failures.append(f"Regime C rate ratio={rate_ratio_C:.2f} outside [0.5, 2.0]")

    # Check 5: Onset MAE ≤ 24h (Regime B)
    onset_mae_B = scores['B_enriched']['onset_mae']
    if not np.isnan(onset_mae_B) and onset_mae_B > 24.0:
        failures.append(f"Regime B onset MAE={onset_mae_B:.1f}h > 24h")

    # Check 6: Type accuracy ≥ 70% (Regime B)
    type_acc_B = scores['B_enriched']['type_accuracy']
    if not np.isnan(type_acc_B) and type_acc_B < 0.70:
        failures.append(f"Regime B type accuracy={type_acc_B:.2%} < 70%")

    # Check 7: Type accuracy ≥ 60% (Regime C, looser threshold)
    type_acc_C = scores['C_held_out']['type_accuracy']
    if not np.isnan(type_acc_C) and type_acc_C < 0.60:
        failures.append(f"Regime C type accuracy={type_acc_C:.2%} < 60%")

    # Final verdict
    if len(failures) == 0:
        verdict = "PASS"
        print("✅ VERDICT: PASS")
        print("   All acceptance criteria satisfied.")
    else:
        verdict = "FAIL"
        print("❌ VERDICT: FAIL")
        print(f"   {len(failures)} acceptance criteria violated:")
        for failure in failures:
            print(f"   - {failure}")

    print()

    # ========================================================================
    # Step 8: Save results
    # ========================================================================
    print("Step 8: Saving results...")
    print("-" * 80)

    # Save detections
    np.save(output_dir / 'detections.npy', all_detections, allow_pickle=True)
    print(f"  Saved detections.npy")

    # Save scores and verdict
    results = {
        'verdict': verdict,
        'failures': failures,
        'scores': {
            regime: {
                'TP': s['performance']['TP'],
                'FP': s['performance']['FP'],
                'FN': s['performance']['FN'],
                'sensitivity': float(s['performance']['sensitivity']),
                'fpr': float(s['performance']['fpr']),
                'onset_mae': float(s['onset_mae']) if not np.isnan(s['onset_mae']) else None,
                'type_accuracy': float(s['type_accuracy']) if not np.isnan(s['type_accuracy']) else None,
                'detected_rate': float(s['detected_rate']),
                'true_rate': float(s['true_rate']),
                'rate_ratio': float(s['detected_rate'] / s['true_rate']) if s['true_rate'] > 0 else None,
            }
            for regime, s in scores.items()
        }
    }

    with open(output_dir / 'results.yaml', 'w') as f:
        yaml.dump(results, f)
    print(f"  Saved results.yaml")

    print()
    print("=" * 80)
    print(f"Suite complete. Verdict: {verdict}")
    print("=" * 80)


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output/identifiability_2d1"
    run_full_suite(Path(output_dir))
