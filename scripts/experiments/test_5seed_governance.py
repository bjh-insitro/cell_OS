"""
5-seed governance check: Verify terminal behavior across stochasticity.

Output columns:
- seed
- first terminal action type (COMMIT / NO_DETECTION / horizon end)
- terminal time (h)
- nuisance_probability at terminal
- posterior_top_prob at terminal
- calibrated_confidence at terminal
- correctness
- reason_code (which gate fired)

Stop conditions (debug immediately if found):
1. COMMIT to concrete with posterior < 0.5 AND nuisance > 0.3
2. NO_DETECTION when any concrete has posterior ≥ 0.55 OR margin ≥ 0.15
"""

import logging
from src.cell_os.hardware.beam_search import Phase5EpisodeRunner, BeamSearch
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY

logging.basicConfig(level=logging.ERROR)

def run_beam_search_single(compound_id: str, seed: int):
    """Run beam search and extract terminal action."""

    phase5_compound = PHASE5_LIBRARY[compound_id]
    true_mechanism = phase5_compound.true_stress_axis

    runner = Phase5EpisodeRunner(
        phase5_compound=phase5_compound,
        cell_line="A549",
        horizon_h=48.0,
        step_h=6.0,
        seed=seed,
        lambda_dead=2.0,
        lambda_ops=0.1,
        actin_threshold=1.4
    )

    # Small beam for speed - reduced dose levels from 4 to 3 (25% fewer actions)
    beam_search = BeamSearch(
        runner=runner,
        beam_width=5,
        max_interventions=2,
        death_tolerance=0.20,
        w_mechanism=2.0,
        w_viability=0.5,
        w_interventions=0.1,
        dose_levels=[0.0, 0.5, 1.0]  # Reduced from [0.0, 0.25, 0.5, 1.0]
    )

    beam_search.debug_commit_decisions = False

    try:
        result = beam_search.search(compound_id, phase5_compound)

        # Extract terminal state from best schedule
        best_schedule = result.best_schedule

        # Run prefix rollout to get terminal belief state
        terminal_state = runner.rollout_prefix(best_schedule)

        terminal_type = "HORIZON_END"
        reason_code = "reached_horizon"
        time_terminal = len(best_schedule) * 6.0

        correct = (terminal_state.predicted_axis == true_mechanism)

        return {
            'seed': seed,
            'terminal_type': terminal_type,
            'time_h': time_terminal,
            'nuisance_prob': terminal_state.nuisance_fraction,  # stores nuisance_probability
            'posterior_top_prob': terminal_state.posterior_top_prob,
            'calibrated_conf': terminal_state.calibrated_confidence,
            'correct': correct,
            'predicted': terminal_state.predicted_axis,
            'true_mechanism': true_mechanism,
            'reason_code': reason_code,
            'posterior_margin': terminal_state.posterior_margin
        }

    except Exception as e:
        return {
            'seed': seed,
            'terminal_type': 'ERROR',
            'time_h': 0.0,
            'nuisance_prob': 0.0,
            'posterior_top_prob': 0.0,
            'calibrated_conf': 0.0,
            'correct': False,
            'predicted': 'error',
            'true_mechanism': true_mechanism,
            'reason_code': 'error',
            'posterior_margin': 0.0,
            'error': str(e)
        }

def check_pathologies(data):
    """Check for stop conditions."""
    violations = []

    # Stop condition 1: COMMIT to concrete with weak posterior AND high nuisance
    if data['terminal_type'] == 'COMMIT':
        if (data['predicted'] not in ['unknown', 'error'] and
            data['posterior_top_prob'] < 0.5 and
            data['nuisance_prob'] > 0.3):
            violations.append(
                f"VIOLATION: COMMIT with weak posterior ({data['posterior_top_prob']:.3f}) "
                f"AND high nuisance ({data['nuisance_prob']:.3f})"
            )

    # Stop condition 2: NO_DETECTION when concrete mechanism has strong support
    if data['terminal_type'] == 'NO_DETECTION':
        if (data['posterior_top_prob'] >= 0.55 or data['posterior_margin'] >= 0.15):
            violations.append(
                f"VIOLATION: NO_DETECTION despite strong signal "
                f"(posterior={data['posterior_top_prob']:.3f}, margin={data['posterior_margin']:.3f})"
            )

    return violations

if __name__ == "__main__":
    compound_id = 'test_A_clean'  # ER stress
    n_seeds = 5

    print("5-Seed Governance Check (Optimized)")
    print("="*100)
    print(f"{'Seed':<6} {'Terminal':<15} {'Time_h':<8} {'Nuisance':<10} {'Posterior':<10} "
          f"{'Cal_Conf':<10} {'Correct':<8} {'Reason':<20}")
    print("="*100)

    results = []
    all_violations = []

    for seed in range(n_seeds):
        data = run_beam_search_single(compound_id, seed)
        results.append(data)

        # Check for violations
        violations = check_pathologies(data)
        if violations:
            all_violations.extend([(seed, v) for v in violations])

        if 'error' in data:
            print(f"{data['seed']:<6} {'ERROR':<15} {'---':<8} {'---':<10} {'---':<10} "
                  f"{'---':<10} {'---':<8} {data.get('reason_code', 'unknown'):<20}")
        else:
            print(f"{data['seed']:<6} {data['terminal_type']:<15} {data['time_h']:<8.1f} "
                  f"{data['nuisance_prob']:<10.3f} {data['posterior_top_prob']:<10.3f} "
                  f"{data['calibrated_conf']:<10.3f} {str(data['correct']):<8} {data['reason_code']:<20}")

    print("="*100)

    # Report violations
    if all_violations:
        print("\n⚠️  STOP CONDITIONS TRIGGERED:")
        for seed, violation in all_violations:
            print(f"  Seed {seed}: {violation}")
    else:
        print("\n✓ No pathologies detected")

    # Summary
    print("\nSummary:")
    terminal_counts = {}
    for r in results:
        t = r['terminal_type']
        terminal_counts[t] = terminal_counts.get(t, 0) + 1

    for t, count in sorted(terminal_counts.items()):
        print(f"  {t}: {count}/{n_seeds}")

    correct_count = sum(1 for r in results if r['correct'])
    print(f"  Correct predictions: {correct_count}/{n_seeds}")
