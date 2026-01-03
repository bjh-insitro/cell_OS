#!/usr/bin/env python3
"""
Phase 2D.1: Contamination Identifiability - Report Renderer

Generates human-readable markdown report from identifiability suite results.

Usage:
    python scripts/render_identifiability_report_2d1.py [output_dir]

Outputs:
    - identifiability_report_2d1.md
"""

import sys
import yaml
import numpy as np
from pathlib import Path
from datetime import datetime


def render_report(output_dir: Path):
    """
    Render markdown report from suite results.

    Args:
        output_dir: Directory containing results.yaml, metadata.yaml
    """
    output_dir = Path(output_dir)

    # Load results
    with open(output_dir / 'results.yaml', 'r') as f:
        results = yaml.safe_load(f)

    with open(output_dir / 'metadata.yaml', 'r') as f:
        metadata = yaml.safe_load(f)

    verdict = results['verdict']
    failures = results['failures']
    scores = results['scores']

    # Build markdown report
    lines = []
    lines.append("# Phase 2D.1: Contamination Identifiability Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Verdict:** {verdict}")
    lines.append("")

    if verdict == "PASS":
        lines.append("✅ **All acceptance criteria satisfied.**")
    elif verdict == "FAIL":
        lines.append(f"❌ **{len(failures)} acceptance criteria violated:**")
        for failure in failures:
            lines.append(f"- {failure}")
    else:
        lines.append(f"⚠️  **{verdict}**")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Experiment design
    lines.append("## Experiment Design")
    lines.append("")
    design = metadata['design']
    lines.append(f"- **Vessels per regime:** {design['n_vessels']}")
    lines.append(f"- **Duration:** {design['duration_h']:.1f}h ({design['duration_h']/24:.1f} days)")
    lines.append(f"- **Sampling interval:** {design['sampling_interval_h']:.1f}h")
    lines.append(f"- **Cell line:** {design['cell_line']}")
    lines.append(f"- **Base seed:** {design['base_seed']}")
    lines.append("")

    # Expected events
    lines.append("### Expected Events (Poisson λ)")
    lines.append("")
    lines.append("| Regime | Rate Multiplier | Expected Events | Observed Events |")
    lines.append("|--------|-----------------|-----------------|-----------------|")

    regime_labels = metadata['regime_order']
    for regime in regime_labels:
        expected = metadata['expected_counts'][regime]
        observed = scores[regime]['TP'] + scores[regime]['FN']  # True events
        rate_mult = metadata['regimes'][regime]['contamination_config']
        if rate_mult:
            rate_mult = rate_mult.get('rate_multiplier', 1.0)
        else:
            rate_mult = 0.0
        lines.append(f"| {regime:15s} | {rate_mult:6.1f}× | {expected:15.2f} | {observed:15d} |")

    lines.append("")

    # Per-regime performance
    lines.append("## Performance by Regime")
    lines.append("")

    for regime in regime_labels:
        s = scores[regime]
        lines.append(f"### {regime}")
        lines.append("")
        lines.append("**Detection Performance:**")
        lines.append("")
        lines.append(f"- True events: {s['TP'] + s['FN']}")
        lines.append(f"- Detected: {s['TP'] + s['FP']} (TP={s['TP']}, FP={s['FP']}, FN={s['FN']})")
        lines.append(f"- Sensitivity: {s['sensitivity']:.2%}")
        lines.append(f"- False positive rate: {s['fpr']:.2%}")
        lines.append("")

        lines.append("**Parameter Recovery:**")
        lines.append("")
        lines.append(f"- True rate: {s['true_rate']:.5f} events/vessel-day")
        lines.append(f"- Detected rate: {s['detected_rate']:.5f} events/vessel-day")
        if s['rate_ratio'] is not None:
            lines.append(f"- Rate ratio: {s['rate_ratio']:.2f}× (target: 0.5-2.0)")
        else:
            lines.append(f"- Rate ratio: N/A")

        if s['onset_mae'] is not None:
            lines.append(f"- Onset MAE: {s['onset_mae']:.1f}h (target: ≤24h)")
        else:
            lines.append(f"- Onset MAE: N/A (no TP events)")

        if s['type_accuracy'] is not None:
            target = "≥70%" if regime == "B_enriched" else "≥60%"
            lines.append(f"- Type accuracy: {s['type_accuracy']:.2%} (target: {target})")
        else:
            lines.append(f"- Type accuracy: N/A (no TP events)")

        lines.append("")

    # Acceptance criteria
    lines.append("## Acceptance Criteria")
    lines.append("")
    lines.append("| Criterion | Target | Actual | Status |")
    lines.append("|-----------|--------|--------|--------|")

    def check_mark(passed):
        return "✅" if passed else "❌"

    # FPR checks
    fpr_A_pass = scores['A_clean']['fpr'] <= 0.01
    lines.append(f"| Regime A FPR ≤ 1% | ≤1% | {scores['A_clean']['fpr']:.2%} | {check_mark(fpr_A_pass)} |")

    fpr_D_pass = scores['D_disabled']['fpr'] <= 0.01
    lines.append(f"| Regime D FPR ≤ 1% | ≤1% | {scores['D_disabled']['fpr']:.2%} | {check_mark(fpr_D_pass)} |")

    # Rate recovery
    rate_B = scores['B_enriched']['rate_ratio']
    rate_B_pass = rate_B is not None and 0.5 <= rate_B <= 2.0
    rate_B_str = f"{rate_B:.2f}×" if rate_B is not None else "N/A"
    lines.append(f"| Regime B rate ratio | 0.5-2.0× | {rate_B_str} | {check_mark(rate_B_pass)} |")

    rate_C = scores['C_held_out']['rate_ratio']
    rate_C_pass = rate_C is not None and 0.5 <= rate_C <= 2.0
    rate_C_str = f"{rate_C:.2f}×" if rate_C is not None else "N/A"
    lines.append(f"| Regime C rate ratio | 0.5-2.0× | {rate_C_str} | {check_mark(rate_C_pass)} |")

    # Onset MAE
    onset_B = scores['B_enriched']['onset_mae']
    onset_B_pass = onset_B is not None and onset_B <= 24.0
    onset_B_str = f"{onset_B:.1f}h" if onset_B is not None else "N/A"
    lines.append(f"| Regime B onset MAE | ≤24h | {onset_B_str} | {check_mark(onset_B_pass)} |")

    # Type accuracy
    type_B = scores['B_enriched']['type_accuracy']
    type_B_pass = type_B is not None and type_B >= 0.70
    type_B_str = f"{type_B:.2%}" if type_B is not None else "N/A"
    lines.append(f"| Regime B type accuracy | ≥70% | {type_B_str} | {check_mark(type_B_pass)} |")

    type_C = scores['C_held_out']['type_accuracy']
    type_C_pass = type_C is not None and type_C >= 0.60
    type_C_str = f"{type_C:.2%}" if type_C is not None else "N/A"
    lines.append(f"| Regime C type accuracy | ≥60% | {type_C_str} | {check_mark(type_C_pass)} |")

    lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    if verdict == "PASS":
        lines.append("✅ **Contamination events are identifiable from observables.**")
        lines.append("")
        lines.append("The detector can:")
        lines.append("- Detect events without labels (low FPR)")
        lines.append("- Recover event rate within 2× of truth")
        lines.append("- Estimate onset time within 24h")
        lines.append("- Classify contamination type at ≥70% accuracy")
    elif verdict == "FAIL":
        lines.append("❌ **Contamination events are NOT identifiable under current design.**")
        lines.append("")
        lines.append("Failures:")
        for failure in failures:
            lines.append(f"- {failure}")
        lines.append("")
        lines.append("**Possible causes:**")
        lines.append("- Detector thresholds need tuning")
        lines.append("- Morphology signature too weak")
        lines.append("- Growth arrest signal insufficient")
        lines.append("- Type signatures not sufficiently distinct")
    else:
        lines.append(f"⚠️  **{verdict}**")

    lines.append("")

    # Write report
    report_path = output_dir / 'identifiability_report_2d1.md'
    with open(report_path, 'w') as f:
        f.write("\n".join(lines))

    print(f"✅ Report saved: {report_path}")


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output/identifiability_2d1"
    render_report(Path(output_dir))
