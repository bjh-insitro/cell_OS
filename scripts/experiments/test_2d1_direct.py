#!/usr/bin/env python3
"""Direct test of Phase 2D.1 identifiability suite."""

import sys
from pathlib import Path
sys.path.insert(0, 'src')

from cell_os.calibration.identifiability_runner_2d1 import run_identifiability_suite
from cell_os.calibration.identifiability_inference_2d1 import (
    fit_clean_baseline,
    learn_type_prototypes,
    run_inference_on_regime,
    compute_sensitivity_specificity,
    compute_onset_mae,
    compute_type_accuracy,
)
import numpy as np
import yaml

print("=" * 80)
print("Phase 2D.1: Direct End-to-End Test")
print("=" * 80)
print()

output_dir = Path("output/identifiability_2d1_direct")
output_dir.mkdir(parents=True, exist_ok=True)

# Step 1: Generate data (32 vessels, 7 days, 12h sampling)
print("Step 1: Generating data (32 vessels, 7 days, 12h sampling)...")
result = run_identifiability_suite(
    output_dir=output_dir,
    n_vessels=32,
    duration_h=168.0,
    sampling_interval_h=12.0,
    cell_line="A549",
    initial_count=5000,
    base_seed=42,
)

if result['status'] == 'INSUFFICIENT_EVENTS':
    print("❌ INSUFFICIENT_EVENTS")
    sys.exit(1)

print(f"✅ Data generated: {result['status']}")
print()

# Step 2: Load data
print("Step 2: Loading data...")
observations = np.load(output_dir / 'observations.npy')
ground_truth = np.load(output_dir / 'ground_truth.npy', allow_pickle=True).item()
with open(output_dir / 'metadata.yaml', 'r') as f:
    metadata = yaml.safe_load(f)

regime_labels = metadata['regime_order']
times = np.array(metadata['regimes']['A_clean']['sampling_times'])
print(f"Observations shape: {observations.shape}")
print(f"Regimes: {regime_labels}")
print()

# Step 3: Fit clean baseline
print("Step 3: Fitting clean baseline...")
regime_A_obs = observations[0, :, :, :]
clean_baseline = fit_clean_baseline(regime_A_obs)
print("✅ Baseline fitted")
print()

# Step 4: Learn type prototypes
print("Step 4: Learning type prototypes...")
regime_B_obs = observations[1, :, :, :]
regime_B_gt = ground_truth['B_enriched']
type_prototypes = learn_type_prototypes(regime_B_obs, times, regime_B_gt)
print(f"✅ Prototypes learned ({len(type_prototypes)} types)")
print()

# Step 5: Run inference on all regimes
print("Step 5: Running inference...")
all_detections = {}
for i, regime_label in enumerate(regime_labels):
    regime_obs = observations[i, :, :, :]
    detections = run_inference_on_regime(regime_obs, times, clean_baseline, type_prototypes)
    all_detections[regime_label] = detections
    n_flagged = sum(1 for d in detections if d['flagged'])
    print(f"  {regime_label}: {n_flagged}/{len(detections)} flagged")

print()

# Step 6: Compute scores
print("Step 6: Computing scores...")
scores = {}
for regime_label in regime_labels:
    detections = all_detections[regime_label]
    gt = ground_truth[regime_label]
    perf = compute_sensitivity_specificity(detections, gt)
    onset_mae, _ = compute_onset_mae(detections, gt)
    type_acc, _ = compute_type_accuracy(detections, gt)

    scores[regime_label] = {
        'TP': perf['TP'],
        'FP': perf['FP'],
        'FN': perf['FN'],
        'sensitivity': perf['sensitivity'],
        'fpr': perf['fpr'],
        'onset_mae': onset_mae,
        'type_accuracy': type_acc,
    }

    print(f"  {regime_label}: TP={perf['TP']}, FP={perf['FP']}, FN={perf['FN']}, FPR={perf['fpr']:.2%}")

print()

# Step 7: Verdict
print("Step 7: Verdict...")
failures = []

if scores['A_clean']['fpr'] > 0.01:
    failures.append(f"Regime A FPR={scores['A_clean']['fpr']:.2%} > 1%")

if scores['D_disabled']['fpr'] > 0.01:
    failures.append(f"Regime D FPR={scores['D_disabled']['fpr']:.2%} > 1%")

if len(failures) == 0:
    verdict = "PASS"
    print("✅ VERDICT: PASS")
else:
    verdict = "FAIL"
    print("❌ VERDICT: FAIL")
    for failure in failures:
        print(f"   - {failure}")

print()
print("=" * 80)
print(f"Suite complete. Verdict: {verdict}")
print("=" * 80)
