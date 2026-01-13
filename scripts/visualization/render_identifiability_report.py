#!/usr/bin/env python3
"""
Render identifiability report from inference results.

Usage:
    python scripts/render_identifiability_report.py \\
        --run artifacts/identifiability/dev_run
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def render_report(run_dir: Path) -> str:
    """
    Render markdown report from inference results.

    Args:
        run_dir: Directory with inference_results.json, truth.json, metadata.json

    Returns:
        Markdown report string
    """
    # Load results
    with open(run_dir / "inference_results.json", 'r') as f:
        results = json.load(f)

    with open(run_dir / "metadata.json", 'r') as f:
        metadata = json.load(f)

    # Load raw data for per-dose diagnostics
    import pandas as pd
    events_df = pd.read_csv(run_dir / "events.csv")
    observations_df = pd.read_csv(run_dir / "observations.csv")

    icc_result = results['icc']
    commitment_result = results['commitment_params']
    comparison_result = results['comparison']
    truth = results['truth']

    # Extract ground truth
    truth_phase1 = truth['phase1']
    truth_phase2a = truth['phase2a_er']

    # Compute errors
    threshold_truth = truth_phase2a['threshold']
    threshold_recovered = commitment_result['threshold']
    threshold_error = abs(threshold_recovered - threshold_truth) if threshold_recovered is not None else None

    lambda0_truth = truth_phase2a['baseline_hazard_per_h']
    lambda0_recovered = commitment_result['baseline_hazard_per_h']
    lambda0_log_ratio = (lambda0_recovered / lambda0_truth) if (lambda0_recovered and lambda0_truth) else None

    p_truth = truth_phase2a['sharpness_p']
    p_recovered = commitment_result['sharpness_p']
    p_error = abs(p_recovered - p_truth) if p_recovered is not None else None

    fraction_error = comparison_result['fraction_error']

    # Check acceptance criteria (load from truth if available, else hardcode)
    acceptance = results.get('truth', {}).get('acceptance', {})
    if not acceptance:
        # Fallback: load from config or use defaults
        acceptance = {
            'recovery': {
                'threshold_abs_error': 0.10,
                'sharpness_abs_error': 1.0,
                'baseline_hazard_log_factor': 3.0,
            },
            'prediction': {
                'commitment_fraction_abs_error': 0.15,
            },
        }

    # Compute per-dose diagnostics for Regime C
    regime_c_events = events_df[events_df['regime'] == 'high_stress_event_rich'].copy()
    regime_c_obs = observations_df[observations_df['regime'] == 'high_stress_event_rich'].copy()

    # Extract dose from well_id (format: PlateC1_A01)
    # Doses are applied in order, so group by plate row/col
    # Actually, we need to reconstruct dose from well position
    # For now, use a simpler approach: group by well_id and infer from data
    # Better: compute from first 12 wells = dose 1, next 12 = dose 2, etc.

    regime_c_events['well_index'] = regime_c_events.groupby('regime').cumcount()
    regime_c_events['dose_group'] = regime_c_events['well_index'] // 12  # 12 wells per dose

    per_dose_diagnostics = []
    for dose_idx in sorted(regime_c_events['dose_group'].unique()):
        dose_events = regime_c_events[regime_c_events['dose_group'] == dose_idx]
        dose_wells = dose_events['well_id'].unique()

        n_wells_dose = len(dose_wells)
        n_committed_dose = dose_events['committed'].sum()
        fraction_committed_dose = n_committed_dose / n_wells_dose if n_wells_dose > 0 else 0

        # Get ER stress for this dose (at t=12h, when most commitments happen)
        dose_stress = regime_c_obs[
            (regime_c_obs['well_id'].isin(dose_wells)) &
            (regime_c_obs['metric_name'] == 'er_stress') &
            (regime_c_obs['time_h'] == 12.0)
        ]
        mean_stress = dose_stress['value'].mean() if len(dose_stress) > 0 else 0

        per_dose_diagnostics.append({
            'dose_idx': dose_idx + 1,
            'n_wells': n_wells_dose,
            'n_committed': n_committed_dose,
            'fraction_committed': fraction_committed_dose,
            'mean_er_stress_12h': mean_stress,
        })

    per_dose_df = pd.DataFrame(per_dose_diagnostics)

    # Precondition checks (insufficient events)
    min_events_regime_c = 10  # Minimum events in Regime C for parameter fitting
    min_events_regime_b = 2   # Minimum events in Regime B for prediction
    n_events_c = commitment_result['n_events']
    n_wells_c = commitment_result['n_wells']
    n_events_b = comparison_result['n_events']
    n_wells_b = comparison_result['n_wells']

    insufficient_events_c = n_events_c < min_events_regime_c
    insufficient_events_b = n_events_b < min_events_regime_b or n_events_b >= n_wells_b  # All or none

    # Only evaluate pass/fail if preconditions are met
    if insufficient_events_c or insufficient_events_b:
        verdict = "INSUFFICIENT_EVENTS"
        verdict_emoji = "⚠️"
        verdict_text = "Insufficient events for identifiability test"
    else:
        threshold_pass = threshold_error <= acceptance['recovery']['threshold_abs_error'] if threshold_error is not None else False
        p_pass = p_error <= acceptance['recovery']['sharpness_abs_error'] if p_error is not None else False
        lambda0_pass = (lambda0_log_ratio <= acceptance['recovery']['baseline_hazard_log_factor'] and
                        lambda0_log_ratio >= 1.0/acceptance['recovery']['baseline_hazard_log_factor']) if lambda0_log_ratio else False
        prediction_pass = fraction_error <= acceptance['prediction']['commitment_fraction_abs_error']

        all_pass = threshold_pass and p_pass and lambda0_pass and prediction_pass

        verdict = "PASS" if all_pass else "FAIL"
        verdict_emoji = "✅" if all_pass else "❌"
        verdict_text = "All acceptance criteria met." if all_pass else "Some criteria not met."

    # Build report
    report = f"""# Identifiability Suite Report

**Run ID:** {metadata['run_id']}
**Timestamp:** {metadata['timestamp']}
**Seed:** {metadata['seed']}
**Cell Line:** {metadata['cell_line']}

---

## Summary

{verdict_emoji} **{verdict}**: {verdict_text}

---

## 1. Phase 1 Random Effects (Plate A)

**Regime:** Low stress (DMSO control)
**Purpose:** Estimate persistent well-level variance (ICC)

| Metric | Value |
|--------|-------|
| ICC | {icc_result['icc']:.4f} |
| Between-well variance | {icc_result['var_well']:.2e} |
| Within-well variance | {icc_result['var_resid']:.2e} |
| N wells | {icc_result['n_wells']} |

**Ground Truth (Config):**
- Phase 1 enabled: {truth_phase1['enabled']}
- Growth CV: {truth_phase1['growth_cv']:.2f}
- Stress sensitivity CV: {truth_phase1['stress_sensitivity_cv']:.2f}
- Hazard scale CV: {truth_phase1['hazard_scale_cv']:.2f}

**Interpretation:**
ICC = {icc_result['icc']:.4f} indicates {_interpret_icc(icc_result['icc'])}

---

## 2. Phase 2A Commitment Parameters (Plate C)

**Regime:** High stress (tunicamycin, multiple doses)
**Purpose:** Recover commitment hazard parameters

| Parameter | Truth | Recovered | Error | Status |
|-----------|-------|-----------|-------|--------|
| Threshold | {threshold_truth:.2f} | {threshold_recovered:.2f} | {threshold_error:.3f} | {'✅' if threshold_pass else '❌'} |
| Baseline hazard λ₀ (per h) | {lambda0_truth:.3f} | {lambda0_recovered:.3f} | {lambda0_log_ratio:.2f}x | {'✅' if lambda0_pass else '❌'} |
| Sharpness p | {p_truth:.1f} | {p_recovered:.1f} | {p_error:.2f} | {'✅' if p_pass else '❌'} |

**Fit Quality:**
- Log-likelihood: {commitment_result['log_likelihood']:.2f}
- Events observed: {commitment_result['n_events']} / {commitment_result['n_wells']} wells

**Per-Dose Diagnostics (Regime C):**

| Dose | Wells | Committed | Fraction | ER Stress (t=12h) |
|------|-------|-----------|----------|-------------------|
"""

    for _, row in per_dose_df.iterrows():
        report += f"| C{row['dose_idx']} | {row['n_wells']} | {row['n_committed']} | {row['fraction_committed']:.3f} | {row['mean_er_stress_12h']:.3f} |\n"

    report += f"""
**Acceptance Criteria:**
- Threshold: |error| ≤ {acceptance['recovery']['threshold_abs_error']:.2f} {'✅' if threshold_pass else '❌'}
- Sharpness p: |error| ≤ {acceptance['recovery']['sharpness_abs_error']:.1f} {'✅' if p_pass else '❌'}
- Baseline hazard: within {acceptance['recovery']['baseline_hazard_log_factor']:.1f}x {'✅' if lambda0_pass else '❌'}

---

## 3. Held-Out Prediction (Plate B)

**Regime:** Mid stress (tunicamycin 1.0 µM)
**Purpose:** Validate joint model on unseen data

| Metric | Value |
|--------|-------|
| Predicted commitment fraction | {comparison_result['predicted_fraction']:.4f} |
| Observed commitment fraction | {comparison_result['empirical_fraction']:.4f} |
| Absolute error | {fraction_error:.4f} |
| N wells | {comparison_result['n_wells']} |
| N events observed | {comparison_result['n_events']} |

**Acceptance Criteria:**
- Fraction error ≤ {acceptance['prediction']['commitment_fraction_abs_error']:.2f}: {'✅' if verdict != "INSUFFICIENT_EVENTS" and prediction_pass else ('N/A' if verdict == "INSUFFICIENT_EVENTS" else '❌')}

---

## 4. Identifiability Verdict

"""

    if verdict == "INSUFFICIENT_EVENTS":
        report += f"""⚠️ **INSUFFICIENT_EVENTS**

**Precondition Failed:** Not enough commitment events to test identifiability.

**Event Counts:**
- Regime C (parameter fitting): {n_events_c} / {n_wells_c} events (minimum: {min_events_regime_c})
- Regime B (prediction): {n_events_b} / {n_wells_b} events (minimum: {min_events_regime_b}, maximum: {n_wells_b-1})

**Likely Causes:**
"""
        if insufficient_events_c:
            report += f"- **Regime C has too few events** ({n_events_c} < {min_events_regime_c}): Cannot fit hazard parameters with statistical power.\n"
        if insufficient_events_b:
            if n_events_b < min_events_regime_b:
                report += f"- **Regime B has too few events** ({n_events_b} < {min_events_regime_b}): Prediction test is non-informative.\n"
            else:
                report += f"- **Regime B has all events** ({n_events_b} = {n_wells_b}): Dose saturated, no variation for prediction.\n"

        report += """
**Next Steps:**
1. Run dose scout to find doses that produce meaningful event fractions:
   ```
   python scripts/run_identifiability_suite.py --scout --config ... --out ...
   ```
2. Update hazard parameters in truth block (increase baseline_hazard_per_h)
3. Extend observation window or increase replicate count
4. Rerun full suite after tuning
"""

    elif verdict == "PASS":
        report += """✅ **PASS**

All acceptance criteria met:
- Commitment parameters recovered within tolerance
- Held-out prediction accurate

**Conclusion:** Phase 2A (stochastic commitment) is identifiable from observations.
The generative parameters (λ₀, threshold, p) can be recovered and used to predict
unseen regimes with acceptable accuracy.
"""
    else:  # FAIL
        report += """❌ **FAIL**

One or more acceptance criteria not met. Likely causes:

"""
        if not threshold_pass:
            report += f"- **Threshold recovery failed** (error={threshold_error:.3f}): Stress proxy may not be informative enough, or hazard cap dominates.\n"
        if not p_pass:
            report += f"- **Sharpness recovery failed** (error={p_error:.2f}): Regime C doses may be too similar (need more stress variation).\n"
        if not lambda0_pass:
            report += f"- **Baseline hazard recovery failed** (ratio={lambda0_log_ratio:.2f}x): May indicate coupling between REs and stress dynamics.\n"
        if not prediction_pass:
            report += f"- **Prediction failed** (error={fraction_error:.4f}): Model does not generalize to held-out regime.\n"

        report += """
**Next steps:**
1. Check if stress trajectories have sufficient variation in Regime C
2. Increase number of replicates/timepoints for statistical power
3. Check for accidental coupling between Phase 1 REs and commitment timing
4. Verify that hazard cap is not dominating the fit
"""

    report += f"""
---

## 5. Reproducibility

**Seed:** {metadata['seed']}
**Config:** (see design config in run directory)
**Commit:** (git rev-parse HEAD)

---

*Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    return report


def _interpret_icc(icc: float) -> str:
    """Interpret ICC value."""
    if icc < 0.05:
        return "negligible persistent variance (wells are nearly exchangeable)"
    elif icc < 0.15:
        return "low persistent variance"
    elif icc < 0.35:
        return "moderate persistent variance"
    else:
        return "high persistent variance (strong well-level effects)"


def main():
    parser = argparse.ArgumentParser(
        description="Render identifiability report"
    )
    parser.add_argument(
        "--run",
        type=str,
        required=True,
        help="Run directory with inference_results.json"
    )

    args = parser.parse_args()

    run_dir = Path(args.run)
    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        sys.exit(1)

    try:
        report = render_report(run_dir)

        # Save report
        report_path = run_dir / "report.md"
        with open(report_path, 'w') as f:
            f.write(report)

        print(f"✓ Report saved: {report_path}\n")
        print(report)

        sys.exit(0)

    except Exception as e:
        print(f"❌ Report rendering failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
