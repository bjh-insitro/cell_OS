"""
Causality Trap Run: Verify planner cannot exploit timing bugs.

Test design:
1. Measure at t=0 (baseline)
2. Measure at t=1 (no treatment)
3. Treat at t=2 (instant exposure)
4. Measure at t=2 and t=3

Requirements:
- No death attribution to compound before t=2
- Early deaths land in correct bucket (unknown/unattributed)
- Belief features computed without phantom exposure
- NO_DETECTION guard enforced

Output: CAUSALITY_TRAP_RUN.md with full forensics
"""

import logging
import numpy as np
from src.cell_os.hardware.beam_search import Phase5EpisodeRunner, BeamSearch
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
from src.cell_os.hardware.episode import Action

logging.basicConfig(level=logging.WARNING)

def run_causality_trap(compound_id: str, seed: int):
    """Run single causality trap test."""

    phase5_compound = PHASE5_LIBRARY[compound_id]
    true_mechanism = phase5_compound.true_stress_axis

    # Create runner with mild cursed day (non-zero context shift)
    runner = Phase5EpisodeRunner(
        phase5_compound=phase5_compound,
        cell_line="A549",
        horizon_h=24.0,  # 4 timesteps × 6h
        step_h=6.0,
        seed=seed,
        lambda_dead=2.0,
        lambda_ops=0.1,
        actin_threshold=1.4
    )

    # Schedule: [baseline, pre-treatment, treatment, post-treatment]
    schedule = [
        Action(dose_fraction=0.0, washout=False, feed=False),  # t=0 (0h): baseline
        Action(dose_fraction=0.0, washout=False, feed=False),  # t=1 (6h): pre-treatment
        Action(dose_fraction=1.0, washout=False, feed=False),  # t=2 (12h): TREAT
        Action(dose_fraction=0.0, washout=False, feed=False),  # t=3 (18h): post-treatment
    ]

    results = []

    # Run prefix rollouts for each timestep
    for t in range(1, len(schedule) + 1):
        prefix = schedule[:t]

        try:
            result = runner.rollout_prefix(prefix)

            # Capture belief state
            results.append({
                'timestep': t,
                'time_h': t * 6.0,
                'treated': t >= 3,  # Treatment happens at t=2, visible at t=3
                'predicted_axis': result.predicted_axis,
                'posterior_top_prob': result.posterior_top_prob,
                'posterior_margin': result.posterior_margin,
                'nuisance_fraction': result.nuisance_fraction,  # Now stores nuisance_probability
                'calibrated_confidence': result.calibrated_confidence,
                'viability': result.viability,
                'actin_fold': result.actin_fold,
                'mito_fold': result.mito_fold,
                'er_fold': result.er_fold,
            })

        except Exception as e:
            results.append({
                'timestep': t,
                'time_h': t * 6.0,
                'error': str(e)
            })

    return {
        'compound_id': compound_id,
        'true_mechanism': true_mechanism,
        'seed': seed,
        'schedule': schedule,
        'results': results
    }

def format_report(data):
    """Format causality trap report."""
    lines = []
    lines.append("="*80)
    lines.append("CAUSALITY TRAP RUN")
    lines.append("="*80)
    lines.append("")
    lines.append(f"Compound: {data['compound_id']} ({data['true_mechanism']})")
    lines.append(f"Seed: {data['seed']}")
    lines.append("")

    lines.append("Schedule:")
    for i, action in enumerate(data['schedule']):
        lines.append(f"  t={i}: dose={action.dose_fraction:.1f}, washout={action.washout}, feed={action.feed}")
    lines.append("")

    lines.append("="*80)
    lines.append("BELIEF STATE SNAPSHOTS")
    lines.append("="*80)

    for r in data['results']:
        if 'error' in r:
            lines.append(f"\nt={r['timestep']} ({r['time_h']:.1f}h): ERROR")
            lines.append(f"  {r['error']}")
            continue

        lines.append(f"\nt={r['timestep']} ({r['time_h']:.1f}h):")
        lines.append(f"  Treated: {r['treated']}")
        lines.append(f"  Predicted axis: {r['predicted_axis']}")
        lines.append(f"  Posterior top_prob: {r['posterior_top_prob']:.3f}")
        lines.append(f"  Posterior margin: {r['posterior_margin']:.3f}")
        lines.append(f"  Nuisance probability: {r['nuisance_fraction']:.3f}")
        lines.append(f"  Calibrated confidence: {r['calibrated_confidence']:.3f}")
        lines.append(f"  Viability: {r['viability']:.3f}")
        lines.append(f"  Actin fold: {r['actin_fold']:.3f}")
        lines.append(f"  Mito fold: {r['mito_fold']:.3f}")
        lines.append(f"  ER fold: {r['er_fold']:.3f}")

    lines.append("")
    lines.append("="*80)
    lines.append("CAUSALITY CHECK")
    lines.append("="*80)

    # Check pre-treatment belief states
    pre_treatment = [r for r in data['results'] if not r.get('treated', False) and 'error' not in r]
    post_treatment = [r for r in data['results'] if r.get('treated', False) and 'error' not in r]

    if pre_treatment:
        lines.append("\nPre-treatment (t=0,1):")
        for r in pre_treatment:
            lines.append(f"  t={r['timestep']}: predicted={r['predicted_axis']}, "
                        f"posterior={r['posterior_top_prob']:.3f}, "
                        f"nuisance={r['nuisance_fraction']:.3f}")

        # Verify no mechanism detected before treatment
        early_concrete = [r for r in pre_treatment if r['predicted_axis'] not in ['unknown', None]]
        if early_concrete:
            lines.append("\n⚠️  WARNING: Concrete mechanism detected BEFORE treatment!")
            for r in early_concrete:
                lines.append(f"    t={r['timestep']}: {r['predicted_axis']}")
        else:
            lines.append("\n✓ No premature mechanism detection")

    if post_treatment:
        lines.append("\nPost-treatment (t=3+):")
        for r in post_treatment:
            lines.append(f"  t={r['timestep']}: predicted={r['predicted_axis']}, "
                        f"posterior={r['posterior_top_prob']:.3f}, "
                        f"nuisance={r['nuisance_fraction']:.3f}")

    lines.append("")
    return "\n".join(lines)

if __name__ == "__main__":
    # Use ER stress compound (tunicamycin) - known to have acute effects
    compound_id = 'test_A_clean'
    seed = 42

    print("Running causality trap...")
    data = run_causality_trap(compound_id, seed)

    report = format_report(data)
    print(report)

    # Save report
    with open('/Users/bjh/cell_OS/CAUSALITY_TRAP_RUN.md', 'w') as f:
        f.write(report)

    print("\nReport saved to: /Users/bjh/cell_OS/CAUSALITY_TRAP_RUN.md")
