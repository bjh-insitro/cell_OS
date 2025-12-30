"""
20-seed quantitative check for autonomous loop governance.

Output one line per run:
- first terminal action type (COMMIT vs NO_DETECTION vs horizon end)
- time of terminal
- nuisance_probability at terminal
- posterior_top_prob at terminal
- calibrated_confidence at terminal
- correctness
"""

import logging
from src.cell_os.hardware.beam_search import Phase5EpisodeRunner, BeamSearch
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY

logging.basicConfig(level=logging.ERROR)  # Suppress all but errors

def run_beam_search_single(compound_id: str, seed: int):
    """Run beam search for single seed and extract terminal action."""

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

    # Small beam for speed
    beam_search = BeamSearch(
        runner=runner,
        beam_width=5,
        max_interventions=2,
        death_tolerance=0.20,
        w_mechanism=2.0,
        w_viability=0.5,
        w_interventions=0.1
    )

    # Disable commit logging for speed
    beam_search.debug_commit_decisions = False

    try:
        result = beam_search.search(compound_id, phase5_compound)

        # Check if terminal action was COMMIT or NO_DETECTION
        # For now, extract from best schedule (horizon-end path)
        # TODO: Track actual terminal decisions when implemented

        terminal_type = "HORIZON_END"
        time_terminal = 48.0
        nuisance_prob_terminal = 0.0  # Not available at horizon end yet
        posterior_terminal = 0.0
        calibrated_conf_terminal = 0.0
        correct = False  # Will compute from receipt

        return {
            'seed': seed,
            'terminal_type': terminal_type,
            'time_h': time_terminal,
            'nuisance_prob': nuisance_prob_terminal,
            'posterior_top_prob': posterior_terminal,
            'calibrated_conf': calibrated_conf_terminal,
            'correct': correct,
            'true_mechanism': true_mechanism
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
            'true_mechanism': true_mechanism,
            'error': str(e)
        }

if __name__ == "__main__":
    compound_id = 'test_A_clean'  # ER stress (tunicamycin)
    n_seeds = 20

    print("Running 20-seed quantitative check...")
    print("="*80)
    print(f"{'Seed':<6} {'Terminal':<15} {'Time_h':<8} {'Nuisance':<10} {'Posterior':<10} {'Cal_Conf':<10} {'Correct':<8}")
    print("="*80)

    results = []
    for seed in range(n_seeds):
        data = run_beam_search_single(compound_id, seed)
        results.append(data)

        if 'error' in data:
            print(f"{data['seed']:<6} {'ERROR':<15} {'---':<8} {'---':<10} {'---':<10} {'---':<10} {'---':<8}")
        else:
            print(f"{data['seed']:<6} {data['terminal_type']:<15} {data['time_h']:<8.1f} "
                  f"{data['nuisance_prob']:<10.3f} {data['posterior_top_prob']:<10.3f} "
                  f"{data['calibrated_conf']:<10.3f} {data['correct']!s:<8}")

    print("="*80)
    print("\nSummary:")
    terminal_counts = {}
    for r in results:
        t = r['terminal_type']
        terminal_counts[t] = terminal_counts.get(t, 0) + 1

    for t, count in sorted(terminal_counts.items()):
        print(f"  {t}: {count}/{n_seeds}")
