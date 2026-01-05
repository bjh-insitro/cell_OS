#!/usr/bin/env python3
"""
Debt-to-Completion Correlation Analysis

This script runs multiple epistemic agent episodes and measures:
1. Maximum debt accumulated during episode
2. Cycles to completion
3. Budget efficiency
4. Correlation between debt and outcomes

The "Honesty Tax" hypothesis: agents that accumulate more debt
(from overclaiming) will have worse outcomes.
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.epistemic_agent.loop import EpistemicLoop


@dataclass
class EpisodeMetrics:
    """Metrics from a single episode."""
    seed: int
    cycles_completed: int
    budget_used: int
    budget_remaining: int
    max_debt_bits: float
    total_refusals: int
    calibration_wells: int
    exploration_wells: int
    gates_earned: int
    aborted: bool
    abort_reason: Optional[str]


def run_episode(seed: int, budget: int = 384, max_cycles: int = 20) -> EpisodeMetrics:
    """Run single episode and extract metrics."""
    loop = EpistemicLoop(
        budget=budget,
        max_cycles=max_cycles,
        seed=seed,
        log_dir=Path(f"/tmp/debt_analysis/run_{seed}"),
        strict_quality=True,
        strict_provenance=False,  # Don't fail on provenance for batch runs
    )

    loop.run()

    # Extract metrics from episode summary
    summary = loop.episode_summary
    beliefs = loop.agent.beliefs

    # Count calibration vs exploration wells
    calibration_wells = 0
    exploration_wells = 0
    for h in loop.history:
        n_wells = h['proposal']['n_wells']
        design_id = h['proposal']['design_id'].lower()
        if any(cal in design_id for cal in ['baseline', 'calibrate', 'dmso']):
            calibration_wells += n_wells
        else:
            exploration_wells += n_wells

    # Count gates earned
    gates_earned = sum([
        beliefs.noise_sigma_stable,
        beliefs.ldh_sigma_stable,
        beliefs.cell_paint_sigma_stable,
        beliefs.scrna_sigma_stable,
        beliefs.edge_effect_confident,
    ])

    # Get max debt from diagnostics file
    max_debt = 0.0
    diagnostics_file = loop.diagnostics_file
    if diagnostics_file.exists():
        with open(diagnostics_file) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    if 'debt_bits' in event:
                        max_debt = max(max_debt, event['debt_bits'])
                except:
                    pass

    # Count refusals
    total_refusals = 0
    if loop.refusals_file.exists():
        with open(loop.refusals_file) as f:
            total_refusals = sum(1 for line in f if line.strip())

    return EpisodeMetrics(
        seed=seed,
        cycles_completed=len(loop.history),
        budget_used=budget - loop.world.budget_remaining,
        budget_remaining=loop.world.budget_remaining,
        max_debt_bits=max_debt,
        total_refusals=total_refusals,
        calibration_wells=calibration_wells,
        exploration_wells=exploration_wells,
        gates_earned=gates_earned,
        aborted=loop.abort_reason is not None,
        abort_reason=loop.abort_reason,
    )


def compute_correlations(metrics: List[EpisodeMetrics]) -> dict:
    """Compute correlation matrix between metrics."""
    n = len(metrics)

    # Extract arrays
    max_debt = np.array([m.max_debt_bits for m in metrics])
    cycles = np.array([m.cycles_completed for m in metrics])
    budget_eff = np.array([m.exploration_wells / max(1, m.budget_used) for m in metrics])
    refusals = np.array([m.total_refusals for m in metrics])
    gates = np.array([m.gates_earned for m in metrics])

    def safe_corr(x, y):
        if np.std(x) == 0 or np.std(y) == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    return {
        'debt_vs_cycles': safe_corr(max_debt, cycles),
        'debt_vs_budget_efficiency': safe_corr(max_debt, budget_eff),
        'debt_vs_refusals': safe_corr(max_debt, refusals),
        'debt_vs_gates': safe_corr(max_debt, gates),
        'refusals_vs_cycles': safe_corr(refusals, cycles),
    }


def main():
    """Run analysis across multiple seeds."""
    import argparse
    parser = argparse.ArgumentParser(description="Debt-completion correlation analysis")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to test")
    parser.add_argument("--budget", type=int, default=384, help="Budget per episode")
    parser.add_argument("--cycles", type=int, default=20, help="Max cycles per episode")
    parser.add_argument("--output", type=str, default="debt_correlation_results.json")
    args = parser.parse_args()

    print("=" * 60)
    print("DEBT-TO-COMPLETION CORRELATION ANALYSIS")
    print("=" * 60)
    print(f"Seeds: {args.seeds}")
    print(f"Budget: {args.budget} wells")
    print(f"Max cycles: {args.cycles}")
    print()

    metrics = []
    for i in range(args.seeds):
        seed = 42 + i
        print(f"Running seed {seed}...", end=" ", flush=True)
        try:
            m = run_episode(seed, args.budget, args.cycles)
            metrics.append(m)
            status = "ABORTED" if m.aborted else "OK"
            print(f"{status} (debt={m.max_debt_bits:.2f}, cycles={m.cycles_completed})")
        except Exception as e:
            print(f"ERROR: {e}")

    if len(metrics) < 2:
        print("\nNot enough successful runs for correlation analysis.")
        return

    # Summary stats
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    max_debts = [m.max_debt_bits for m in metrics]
    cycles = [m.cycles_completed for m in metrics]
    refusals = [m.total_refusals for m in metrics]

    print(f"Episodes: {len(metrics)}")
    print(f"Max debt: mean={np.mean(max_debts):.2f}, std={np.std(max_debts):.2f}")
    print(f"Cycles: mean={np.mean(cycles):.1f}, std={np.std(cycles):.1f}")
    print(f"Refusals: mean={np.mean(refusals):.1f}, std={np.std(refusals):.1f}")

    # Correlations
    corr = compute_correlations(metrics)
    print("\n" + "-" * 60)
    print("CORRELATIONS")
    print("-" * 60)
    for key, val in corr.items():
        print(f"  {key}: {val:+.3f}")

    # Save results
    results = {
        'config': {
            'seeds': args.seeds,
            'budget': args.budget,
            'max_cycles': args.cycles,
        },
        'episodes': [
            {
                'seed': m.seed,
                'cycles_completed': m.cycles_completed,
                'budget_used': m.budget_used,
                'max_debt_bits': m.max_debt_bits,
                'total_refusals': m.total_refusals,
                'calibration_wells': m.calibration_wells,
                'exploration_wells': m.exploration_wells,
                'gates_earned': m.gates_earned,
                'aborted': m.aborted,
            }
            for m in metrics
        ],
        'correlations': corr,
    }

    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
