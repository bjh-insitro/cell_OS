#!/usr/bin/env python3
"""
Fit inference models on identifiability suite outputs.

Usage:
    python scripts/fit_identifiability_suite.py \\
        --in artifacts/identifiability/dev_run \\
        --out artifacts/identifiability/dev_run
"""

import argparse
import sys
import json
from pathlib import Path
import pandas as pd

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_inference import (
    fit_re_icc,
    fit_commitment_params,
    predict_commitment_fraction,
    compare_prediction_to_empirical,
)


def main():
    parser = argparse.ArgumentParser(
        description="Fit inference models on identifiability suite outputs"
    )
    parser.add_argument(
        "--in",
        dest="input_dir",
        type=str,
        required=True,
        help="Input directory with observations.csv and events.csv"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output directory for results (same as input is fine)"
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Load data
        print("Loading data...")
        observations_df = pd.read_csv(input_dir / "observations.csv")
        events_df = pd.read_csv(input_dir / "events.csv")
        with open(input_dir / "truth.json", 'r') as f:
            truth = json.load(f)

        print(f"  Observations: {len(observations_df)} rows")
        print(f"  Events: {len(events_df)} rows")

        # Step 1: Fit RE ICC (Plate A)
        print("\n1. Fitting RE ICC (Plate A)...")
        icc_result = fit_re_icc(
            observations_df=observations_df,
            metric="cell_count",
            regime="low_stress_re_only"
        )
        print(f"  ICC = {icc_result['icc']:.4f}")
        print(f"  var_well = {icc_result['var_well']:.2e}")
        print(f"  var_resid = {icc_result['var_resid']:.2e}")
        print(f"  n_wells = {icc_result['n_wells']}")

        # Step 2: Fit commitment params (Plate C)
        print("\n2. Fitting commitment params (Plate C)...")
        commitment_result = fit_commitment_params(
            events_df=events_df,
            observations_df=observations_df,
            regime="high_stress_event_rich",
            mechanism="er_stress",
            stress_metric="er_stress"
        )
        print(f"  threshold = {commitment_result['threshold']}")
        print(f"  baseline_hazard_per_h = {commitment_result['baseline_hazard_per_h']}")
        print(f"  sharpness_p = {commitment_result['sharpness_p']}")
        print(f"  log_likelihood = {commitment_result['log_likelihood']:.2f}")
        print(f"  n_events = {commitment_result['n_events']}/{commitment_result['n_wells']}")

        # Step 3: Predict on held-out (Plate B)
        print("\n3. Predicting on held-out regime (Plate B)...")
        prediction_result = predict_commitment_fraction(
            observations_df=observations_df,
            recovered_params=commitment_result,
            regime="mid_stress_mixed",
            stress_metric="er_stress"
        )
        print(f"  predicted_fraction = {prediction_result['predicted_fraction']:.4f}")

        # Compare to empirical
        comparison_result = compare_prediction_to_empirical(
            events_df=events_df,
            predicted_fraction=prediction_result['predicted_fraction'],
            regime="mid_stress_mixed"
        )
        print(f"  empirical_fraction = {comparison_result['empirical_fraction']:.4f}")
        print(f"  fraction_error = {comparison_result['fraction_error']:.4f}")

        # Save results
        results = {
            'icc': icc_result,
            'commitment_params': commitment_result,
            'prediction': prediction_result,
            'comparison': comparison_result,
            'truth': truth,
        }

        results_path = output_dir / "inference_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved: {results_path}")

        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
