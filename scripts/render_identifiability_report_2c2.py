#!/usr/bin/env python3
"""
Render Phase 2C.2 Multi-Mechanism Identifiability Report.

Shows mechanism discrimination performance:
- Confusion matrices per regime
- Attribution accuracy
- Stress correlation warnings
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def render_2c2_report(run_dir: Path) -> str:
    """
    Render Phase 2C.2 multi-mechanism identifiability report.

    Args:
        run_dir: Directory with inference_results.json, observations.csv, events.csv

    Returns:
        Markdown report string
    """
    # Load results
    with open(run_dir / "inference_results.json", 'r') as f:
        results = json.load(f)

    with open(run_dir / "metadata.json", 'r') as f:
        metadata = json.load(f)

    # Load raw data for stress correlation analysis
    events_df = pd.read_csv(run_dir / "events.csv")
    observations_df = pd.read_csv(run_dir / "observations.csv")

    # Extract multi-mechanism results
    params_er = results.get('params_er', {})
    params_mito = results.get('params_mito', {})
    attribution_results = results.get('attribution_results', {})
    validation_er = results.get('validation_er_dominant', {})
    validation_mito = results.get('validation_mito_dominant', {})
    validation_mixed = results.get('validation_mixed', {})

    # Extract truth
    truth = results.get('truth', {})
    truth_er = truth.get('phase2a_er', {})
    truth_mito = truth.get('phase2a_mito', {})

    # Compute errors
    threshold_er_truth = truth_er.get('threshold', 0.60)
    threshold_er_recovered = params_er.get('threshold', 0.60)
    threshold_er_error = abs(threshold_er_recovered - threshold_er_truth)

    threshold_mito_truth = truth_mito.get('threshold', 0.60)
    threshold_mito_recovered = params_mito.get('threshold', 0.60)
    threshold_mito_error = abs(threshold_mito_recovered - threshold_mito_truth)

    lambda0_er_truth = truth_er.get('baseline_hazard_per_h', 0.20)
    lambda0_er_recovered = params_er.get('baseline_hazard_per_h', 0.20)
    lambda0_er_ratio = lambda0_er_recovered / lambda0_er_truth if lambda0_er_truth > 0 else 1.0

    lambda0_mito_truth = truth_mito.get('baseline_hazard_per_h', 0.15)
    lambda0_mito_recovered = params_mito.get('baseline_hazard_per_h', 0.15)
    lambda0_mito_ratio = lambda0_mito_recovered / lambda0_mito_truth if lambda0_mito_truth > 0 else 1.0

    p_er_truth = truth_er.get('sharpness_p', 2.0)
    p_er_recovered = params_er.get('sharpness_p', 2.0)
    p_er_error = abs(p_er_recovered - p_er_truth)

    p_mito_truth = truth_mito.get('sharpness_p', 2.5)
    p_mito_recovered = params_mito.get('sharpness_p', 2.5)
    p_mito_error = abs(p_mito_recovered - p_mito_truth)

    # Acceptance criteria
    acceptance = truth.get('acceptance', {
        'recovery': {
            'threshold_abs_error': 0.10,
            'sharpness_abs_error': 1.0,
            'baseline_hazard_log_factor': 3.0,
        },
        'attribution': {
            'min_accuracy_dominant_regimes': 0.80,
            'mechanism_split_abs_error': 0.20,
        },
        'prediction': {
            'commitment_fraction_abs_error': 0.15,
        },
    })

    # Check acceptance
    threshold_er_pass = threshold_er_error <= acceptance['recovery']['threshold_abs_error']
    lambda0_er_pass = (lambda0_er_ratio <= acceptance['recovery']['baseline_hazard_log_factor'] and
                       lambda0_er_ratio >= 1.0/acceptance['recovery']['baseline_hazard_log_factor'])
    p_er_pass = p_er_error <= acceptance['recovery']['sharpness_abs_error']

    threshold_mito_pass = threshold_mito_error <= acceptance['recovery']['threshold_abs_error']
    lambda0_mito_pass = (lambda0_mito_ratio <= acceptance['recovery']['baseline_hazard_log_factor'] and
                         lambda0_mito_ratio >= 1.0/acceptance['recovery']['baseline_hazard_log_factor'])
    p_mito_pass = p_mito_error <= acceptance['recovery']['sharpness_abs_error']

    # Attribution accuracy
    acc_er = validation_er.get('accuracy', 0.0)
    acc_mito = validation_mito.get('accuracy', 0.0)
    acc_mixed = validation_mixed.get('accuracy', 0.0)

    n_events_er = validation_er.get('n_events', 0)
    n_events_mito = validation_mito.get('n_events', 0)
    n_events_mixed = validation_mixed.get('n_events', 0)

    min_events = 10
    insufficient_events_er = n_events_er < min_events
    insufficient_events_mito = n_events_mito < min_events

    attribution_er_pass = acc_er >= acceptance['attribution']['min_accuracy_dominant_regimes']
    attribution_mito_pass = acc_mito >= acceptance['attribution']['min_accuracy_dominant_regimes']

    # Mixed regime metrics
    stress_corr = attribution_results.get('stress_correlation', 0.0)
    stress_corr_high = abs(stress_corr) > 0.7 if stress_corr is not None else False

    predicted_fraction_total = attribution_results.get('predicted_fraction_total', 0.0)
    empirical_fraction_mixed = validation_mixed.get('empirical_fraction', 0.0)
    fraction_error_mixed = abs(predicted_fraction_total - empirical_fraction_mixed)

    predicted_er_fraction = attribution_results.get('predicted_fraction_er', 0.0)
    empirical_er_fraction = validation_mixed.get('empirical_er_fraction', 0.0)
    split_error = abs(predicted_er_fraction - empirical_er_fraction)

    fraction_pass = fraction_error_mixed <= acceptance['prediction']['commitment_fraction_abs_error']
    split_pass = split_error <= acceptance['attribution']['mechanism_split_abs_error']

    # Overall verdict
    if insufficient_events_er or insufficient_events_mito:
        verdict = "INSUFFICIENT_EVENTS"
        verdict_emoji = "⚠️"
    elif (threshold_er_pass and lambda0_er_pass and p_er_pass and
          threshold_mito_pass and lambda0_mito_pass and p_mito_pass and
          attribution_er_pass and attribution_mito_pass and
          fraction_pass and split_pass):
        verdict = "PASS"
        verdict_emoji = "✅"
    else:
        verdict = "FAIL"
        verdict_emoji = "❌"

    # Build report
    report = f"""# Phase 2C.2: Multi-Mechanism Identifiability Report

**Run ID:** {metadata['run_id']}
**Timestamp:** {metadata['timestamp']}
**Seed:** {metadata['seed']}
**Cell Line:** {metadata['cell_line']}

---

## Summary

{verdict_emoji} **{verdict}**

This suite tests whether **ER and mito commitment mechanisms are discriminable** from stress trajectories and event timing alone, without mechanism labels.

---

## 1. ER-Dominant Regime (Regime A)

**Purpose:** Recover ER parameters with mito negligible

### Recovered ER Parameters

| Parameter | Truth | Recovered | Error | Status |
|-----------|-------|-----------|-------|--------|
| Threshold | {threshold_er_truth:.2f} | {threshold_er_recovered:.2f} | {threshold_er_error:.3f} | {'✅' if threshold_er_pass else '❌'} |
| λ₀ (per h) | {lambda0_er_truth:.3f} | {lambda0_er_recovered:.3f} | {lambda0_er_ratio:.2f}x | {'✅' if lambda0_er_pass else '❌'} |
| Sharpness p | {p_er_truth:.1f} | {p_er_recovered:.1f} | {p_er_error:.2f} | {'✅' if p_er_pass else '❌'} |

**Fit Quality:**
- Events: {params_er.get('n_events', 0)} / {params_er.get('n_wells', 0)} wells
- Log-likelihood: {params_er.get('log_likelihood', 0):.2f}

**Cumulative Hazard Diagnostic:**
- Predicted commit prob: {params_er.get('predicted_commit_prob', 0):.1%}
- Observed commit frac: {params_er.get('observed_commit_frac', 0):.1%}
- Ratio (pred/obs): {'N/A' if params_er.get('observed_commit_frac', 0) == 0 else f"{(params_er.get('predicted_commit_prob', 0) / params_er.get('observed_commit_frac', 1)):.2f}x"}

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** {acc_er:.1%} ({n_events_er} events)
**Target:** ≥{acceptance['attribution']['min_accuracy_dominant_regimes']:.0%} {'✅' if attribution_er_pass else '❌'}

**Confusion Matrix:**

| True \\ Pred | ER | Mito |
|--------------|----|----|
| **ER** | {validation_er.get('confusion_matrix', {}).get('er_er', 0)} | {validation_er.get('confusion_matrix', {}).get('er_mito', 0)} |
| **Mito** | {validation_er.get('confusion_matrix', {}).get('mito_er', 0)} | {validation_er.get('confusion_matrix', {}).get('mito_mito', 0)} |

---

## 2. Mito-Dominant Regime (Regime B)

**Purpose:** Recover mito parameters with ER negligible

### Recovered Mito Parameters

| Parameter | Truth | Recovered | Error | Status |
|-----------|-------|-----------|-------|--------|
| Threshold | {threshold_mito_truth:.2f} | {threshold_mito_recovered:.2f} | {threshold_mito_error:.3f} | {'✅' if threshold_mito_pass else '❌'} |
| λ₀ (per h) | {lambda0_mito_truth:.3f} | {lambda0_mito_recovered:.3f} | {lambda0_mito_ratio:.2f}x | {'✅' if lambda0_mito_pass else '❌'} |
| Sharpness p | {p_mito_truth:.1f} | {p_mito_recovered:.1f} | {p_mito_error:.2f} | {'✅' if p_mito_pass else '❌'} |

**Fit Quality:**
- Events: {params_mito.get('n_events', 0)} / {params_mito.get('n_wells', 0)} wells
- Log-likelihood: {params_mito.get('log_likelihood', 0):.2f}

**Cumulative Hazard Diagnostic:**
- Predicted commit prob: {params_mito.get('predicted_commit_prob', 0):.1%}
- Observed commit frac: {params_mito.get('observed_commit_frac', 0):.1%}
- Ratio (pred/obs): {'N/A' if params_mito.get('observed_commit_frac', 0) == 0 else f"{(params_mito.get('predicted_commit_prob', 0) / params_mito.get('observed_commit_frac', 1)):.2f}x"}

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** {acc_mito:.1%} ({n_events_mito} events)
**Target:** ≥{acceptance['attribution']['min_accuracy_dominant_regimes']:.0%} {'✅' if attribution_mito_pass else '❌'}

**Confusion Matrix:**

| True \\ Pred | ER | Mito |
|--------------|----|----|
| **ER** | {validation_mito.get('confusion_matrix', {}).get('er_er', 0)} | {validation_mito.get('confusion_matrix', {}).get('er_mito', 0)} |
| **Mito** | {validation_mito.get('confusion_matrix', {}).get('mito_er', 0)} | {validation_mito.get('confusion_matrix', {}).get('mito_mito', 0)} |

---

## 3. Mixed Regime (Regime C)

**Purpose:** Test mechanism discrimination when both stresses compete

### Commitment Fraction Prediction

| Metric | Predicted | Observed | Error | Status |
|--------|-----------|----------|-------|--------|
| **Total fraction** | {predicted_fraction_total:.3f} | {empirical_fraction_mixed:.3f} | {fraction_error_mixed:.3f} | {'✅' if fraction_pass else '❌'} |
| ER fraction | {predicted_er_fraction:.3f} | {empirical_er_fraction:.3f} | {split_error:.3f} | {'✅' if split_pass else '❌'} |
| Mito fraction | {attribution_results.get('predicted_fraction_mito', 0):.3f} | {validation_mixed.get('empirical_mito_fraction', 0):.3f} | — | — |

**Events:** {n_events_mixed} / {attribution_results.get('n_wells', 0)} wells

### Attribution Accuracy (Post-Hoc Validation)

**Accuracy:** {acc_mixed:.1%} ({n_events_mixed} events)

**Confusion Matrix:**

| True \\ Pred | ER | Mito |
|--------------|----|----|
| **ER** | {validation_mixed.get('confusion_matrix', {}).get('er_er', 0)} | {validation_mixed.get('confusion_matrix', {}).get('er_mito', 0)} |
| **Mito** | {validation_mixed.get('confusion_matrix', {}).get('mito_er', 0)} | {validation_mixed.get('confusion_matrix', {}).get('mito_mito', 0)} |

### Stress Correlation (Confounding Check)

**Correlation at event times:** {'N/A' if stress_corr is None else f'{stress_corr:.3f}'}
"""

    if stress_corr is not None and stress_corr_high:
        report += f"""
⚠️ **LIKELY CONFOUNDED**: ER and mito stresses are highly correlated (|r| = {abs(stress_corr):.2f} > 0.7).

Attribution becomes ambiguous when both stresses move together. Consider:
- Checking if both compounds affect shared upstream state
- Using more orthogonal stressors
- Examining per-well stress trajectories for hidden coupling
"""
    else:
        report += "\n✅ Stresses are reasonably separated (no high correlation detected)\n"

    report += """
---

## 4. Identifiability Verdict

"""

    if verdict == "INSUFFICIENT_EVENTS":
        report += f"""⚠️ **INSUFFICIENT_EVENTS**

Not enough events in dominant regimes to test mechanism discrimination.

**Event counts:**
- ER-dominant: {n_events_er} (need ≥{min_events})
- Mito-dominant: {n_events_mito} (need ≥{min_events})

**Next steps:**
1. Scout doses for both ER and mito stressors
2. Increase baseline hazard or extend observation window
3. Ensure dominant regimes actually produce events before testing discrimination
"""

    elif verdict == "PASS":
        report += """✅ **PASS**

**Mechanism discrimination successful:**
- Both ER and mito parameters recovered within tolerance
- Attribution accuracy ≥80% in dominant regimes
- Mixed regime predictions accurate

**Conclusion:** ER and mito commitment mechanisms are **independently identifiable** from stress trajectories and event timing alone. The simulator can discriminate between mechanisms without access to ground truth labels.

**This proves:**
1. Parameters are recoverable per-mechanism
2. Events can be attributed to mechanisms using only observables
3. The model is not accidentally confounding ER and mito dynamics
"""

    else:  # FAIL
        report += """❌ **FAIL**

One or more discrimination criteria not met:

"""
        if not attribution_er_pass and not insufficient_events_er:
            report += f"- **ER attribution failed** ({acc_er:.1%} < 80%): Cannot discriminate ER events from mito in ER-dominant regime\n"
        if not attribution_mito_pass and not insufficient_events_mito:
            report += f"- **Mito attribution failed** ({acc_mito:.1%} < 80%): Cannot discriminate mito events from ER in mito-dominant regime\n"
        if not (threshold_er_pass and lambda0_er_pass and p_er_pass):
            report += f"- **ER parameter recovery failed**: Check if ER-dominant regime has sufficient ER stress variation\n"
        if not (threshold_mito_pass and lambda0_mito_pass and p_mito_pass):
            report += f"- **Mito parameter recovery failed**: Check if mito-dominant regime has sufficient mito stress variation\n"
        if not fraction_pass:
            report += f"- **Mixed regime total prediction failed** (error={fraction_error_mixed:.3f}): Combined hazard model doesn't generalize\n"
        if not split_pass:
            report += f"- **Mechanism split prediction failed** (error={split_error:.3f}): Cannot predict which mechanism dominates\n"

        report += """
**Likely causes:**
1. **Stress separation insufficient** - ER and mito stresses may be correlated even in "dominant" regimes
2. **Parameters structurally confounded** - ER and mito thresholds/hazards may be too similar
3. **Design doesn't bracket thresholds** - Stresses may saturate above both thresholds
4. **Hidden coupling** - Phase 1 REs or shared upstream state creates per-well correlation

**Next steps:**
1. Check per-dose stress levels (should be ER-high/mito-low in A, ER-low/mito-high in B)
2. Run ablation tests (scramble labels, disable one mechanism) to diagnose
3. Scout doses more carefully to ensure orthogonal stress regimes
4. Check if ER and mito stress models share hidden state that creates correlation
"""

    report += f"""
---

## 5. Reproducibility

**Seed:** {metadata['seed']}
**Config:** See run directory
**Inference:** NO mechanism labels used (post-hoc validation only)

---

*Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Render Phase 2C.2 multi-mechanism identifiability report"
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
        report = render_2c2_report(run_dir)

        # Save report
        report_path = run_dir / "report_2c2.md"
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
