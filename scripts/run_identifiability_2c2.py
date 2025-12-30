#!/usr/bin/env python3
"""
Run Phase 2C.2: Multi-Mechanism Identifiability Suite.

Executes four-regime design to test whether ER and mito commitment mechanisms
are discriminable from observables alone (no mechanism labels in inference).

Workflow:
1. Run design (4 regimes: ER-dominant, mito-dominant, mixed, control)
2. Fit ER and mito parameters from dominant regimes
3. Attribute events in mixed regime using competing-risks model
4. Validate attribution accuracy against ground truth labels (post-hoc only)
5. Generate report with confusion matrices and stress correlation diagnostics
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_design import IdentifiabilityDesign
from cell_os.calibration.identifiability_runner import IdentifiabilityRunner
from cell_os.calibration.identifiability_inference import (
    fit_multi_mechanism_params,
    attribute_events_competing_risks,
    validate_attribution_accuracy,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run Phase 2C.2 multi-mechanism identifiability suite"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(project_root / "configs" / "calibration" / "identifiability_2c2.yaml"),
        help="Path to identifiability_2c2.yaml config"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(project_root / "data" / "identifiability_2c2"),
        help="Output directory for results"
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    output_dir = Path(args.out)

    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)

    # Load design
    print("Loading design...")
    design = IdentifiabilityDesign(str(config_path))

    # Create runner
    run_id = f"2c2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    runner = IdentifiabilityRunner(design, output_dir=output_dir, run_id=run_id)

    # Run all regimes
    print("\n▶ Running Phase 2C.2 suite (4 regimes)...")
    print("  - ER-dominant: Recover ER parameters")
    print("  - Mito-dominant: Recover mito parameters")
    print("  - Mixed: Test mechanism discrimination")
    print("  - Control: Phase 1 RE baseline")
    print()

    outputs = runner.run()

    # Load results
    events_df = pd.read_csv(outputs['events'])
    observations_df = pd.read_csv(outputs['observations'])

    print("\n▶ Running multi-mechanism inference...")

    # Fit ER and mito parameters from dominant regimes
    results = fit_multi_mechanism_params(
        events_df=events_df,
        observations_df=observations_df,
        er_dominant_regime="er_dominant",
        mito_dominant_regime="mito_dominant"
    )

    params_er = results['params_er']
    params_mito = results['params_mito']

    print("  ✓ ER parameters fitted")
    print(f"    - Threshold: {params_er['threshold']:.3f}")
    print(f"    - λ₀: {params_er['baseline_hazard_per_h']:.3f} per h")
    print(f"    - Sharpness p: {params_er['sharpness_p']:.2f}")

    print("  ✓ Mito parameters fitted")
    print(f"    - Threshold: {params_mito['threshold']:.3f}")
    print(f"    - λ₀: {params_mito['baseline_hazard_per_h']:.3f} per h")
    print(f"    - Sharpness p: {params_mito['sharpness_p']:.2f}")

    # Attribute events in all regimes
    print("\n▶ Attributing events using competing-risks model...")

    attribution_er_dominant = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=params_er,
        params_mito=params_mito,
        regime="er_dominant"
    )

    attribution_mito_dominant = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=params_er,
        params_mito=params_mito,
        regime="mito_dominant"
    )

    attribution_mixed = attribute_events_competing_risks(
        events_df=events_df,
        observations_df=observations_df,
        params_er=params_er,
        params_mito=params_mito,
        regime="mixed"
    )

    # Validate attribution accuracy (post-hoc only)
    print("\n▶ Validating attribution accuracy (using ground truth labels)...")

    validation_er = validate_attribution_accuracy(
        attributions=attribution_er_dominant['attributions'],
        events_df=events_df,
        regime="er_dominant"
    )

    validation_mito = validate_attribution_accuracy(
        attributions=attribution_mito_dominant['attributions'],
        events_df=events_df,
        regime="mito_dominant"
    )

    validation_mixed = validate_attribution_accuracy(
        attributions=attribution_mixed['attributions'],
        events_df=events_df,
        regime="mixed"
    )

    print(f"  ✓ ER-dominant accuracy: {validation_er['accuracy']:.1%} ({validation_er['n_events']} events)")
    print(f"  ✓ Mito-dominant accuracy: {validation_mito['accuracy']:.1%} ({validation_mito['n_events']} events)")
    print(f"  ✓ Mixed accuracy: {validation_mixed['accuracy']:.1%} ({validation_mixed['n_events']} events)")

    # Get ground truth and empirical fractions for mixed regime
    empirical_fraction_mixed = validation_mixed['n_events'] / attribution_mixed['n_wells'] if attribution_mixed['n_wells'] > 0 else 0.0

    # Compute per-mechanism empirical fractions in mixed regime
    events_mixed = events_df[events_df['regime'] == 'mixed']
    mechanism_col = 'death_commitment_mechanism' if 'death_commitment_mechanism' in events_mixed.columns else 'mechanism'
    n_er_events_mixed = ((events_mixed['committed'] == True) & (events_mixed[mechanism_col] == 'er_stress')).sum()
    n_mito_events_mixed = ((events_mixed['committed'] == True) & (events_mixed[mechanism_col] == 'mito')).sum()
    n_wells_mixed = len(events_mixed)

    empirical_er_fraction = n_er_events_mixed / n_wells_mixed if n_wells_mixed > 0 else 0.0
    empirical_mito_fraction = n_mito_events_mixed / n_wells_mixed if n_wells_mixed > 0 else 0.0

    validation_mixed['empirical_fraction'] = empirical_fraction_mixed
    validation_mixed['empirical_er_fraction'] = empirical_er_fraction
    validation_mixed['empirical_mito_fraction'] = empirical_mito_fraction

    # Save inference results
    print("\n▶ Saving inference results...")

    inference_results = {
        'params_er': params_er,
        'params_mito': params_mito,
        'attribution_results': attribution_mixed,
        'validation_er_dominant': validation_er,
        'validation_mito_dominant': validation_mito,
        'validation_mixed': validation_mixed,
        'truth': design.truth,
    }

    inference_path = runner.run_dir / "inference_results.json"
    with open(inference_path, 'w') as f:
        json.dump(inference_results, f, indent=2)

    print(f"  ✓ Saved: {inference_path}")

    # Generate report
    print("\n▶ Generating Phase 2C.2 report...")
    from scripts.render_identifiability_report_2c2 import render_2c2_report

    report = render_2c2_report(runner.run_dir)

    report_path = runner.run_dir / "report_2c2.md"
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"  ✓ Report saved: {report_path}\n")

    # Print verdict
    print("=" * 60)
    if "✅ **PASS**" in report:
        print("✅ PASS: Multi-mechanism discrimination successful")
    elif "❌ **FAIL**" in report:
        print("❌ FAIL: Multi-mechanism discrimination failed")
        print("   Check report for diagnostics")
    elif "⚠️ **INSUFFICIENT_EVENTS**" in report:
        print("⚠️ INSUFFICIENT_EVENTS: Not enough events to test discrimination")
        print("   Consider increasing hazard or extending observation window")
    print("=" * 60)

    print(f"\n📊 Full results: {runner.run_dir}")
    sys.exit(0)


if __name__ == "__main__":
    main()
