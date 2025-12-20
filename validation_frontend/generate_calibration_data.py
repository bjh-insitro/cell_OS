#!/usr/bin/env python3
"""
Generate realistic calibration data for the epistemic agent tutorial.
Uses realistic pharmacology parameters for Staurosporine in A549 cells.
"""

import json
import numpy as np
from pathlib import Path

def hill_equation(dose, ec50, hill_slope=2.0, baseline=1.0, max_effect=0.0):
    """Standard dose-response curve (Hill equation)."""
    return max_effect + (baseline - max_effect) / (1 + (dose / ec50) ** hill_slope)

def run_calibration_cycle(cycle_num, day, batch, seed_offset=0):
    """Generate realistic calibration data for one cycle."""

    # Dose levels: 1.56 to 800 nM (12 levels, 2x dilution series)
    doses_nM = [1.56 * (2**i) for i in range(12)]
    replicates = 13

    results = {
        'cycle': cycle_num,
        'day': day,
        'batch': batch,
        'doses_nM': doses_nM,
        'replicates': replicates,
        'well_data': []
    }

    # Pharmacology parameters for Staurosporine in A549
    # EC50 varies slightly between batches and days
    base_ec50 = 75.0  # nM
    if batch == 'B':
        ec50 = base_ec50 * 0.92  # Batch B slightly more sensitive
    else:
        ec50 = base_ec50

    # Day-to-day drift
    ec50 *= (1.0 + 0.02 * (day - 1))  # 2% drift per day

    # RNG for this cycle
    rng = np.random.RandomState(seed=42 + seed_offset + cycle_num * 1000)

    # Run simulation for each dose
    for dose_idx, dose_nM in enumerate(doses_nM):
        dose_measurements = []

        for rep in range(replicates):
            # True biological response (Hill equation)
            true_viability = hill_equation(dose_nM, ec50, hill_slope=2.5, baseline=1.0, max_effect=0.05)

            # Add realistic technical noise (within-run variability)
            # CV ~ 10-12% for morphology-based viability
            cv = 0.11
            noise = rng.normal(0, cv * true_viability)
            measured_viability = np.clip(true_viability + noise, 0.01, 1.0)

            dose_measurements.append(measured_viability)

        # Store dose-level stats
        mean_viability = np.mean(dose_measurements)
        std_viability = np.std(dose_measurements, ddof=1)

        results['well_data'].append({
            'dose_nM': dose_nM,
            'measurements': dose_measurements,
            'mean': float(mean_viability),
            'std': float(std_viability),
            'n': replicates
        })

    # Compute per-cycle metrics
    # Pool within-dose standard deviations (weighted by signal)
    pooled_variance = np.mean([d['std']**2 for d in results['well_data']])
    sigma_within = np.sqrt(pooled_variance)

    # Compute overall signal (mean across mid-range doses for best SNR)
    mid_dose_means = [d['mean'] for d in results['well_data'][4:8]]  # Doses 5-8
    mean_signal = np.mean(mid_dose_means)

    # Compute rel_width
    # Standard error = sigma_within / sqrt(n)
    se = sigma_within / np.sqrt(replicates)
    rel_width = (2 * se) / mean_signal if mean_signal > 0 else 999

    results['metrics'] = {
        'sigma_within': float(sigma_within),
        'mean_signal': float(mean_signal),
        'rel_width': float(rel_width),
        'df': (replicates - 1) * len(doses_nM)
    }

    return results


def main():
    print("Generating 4-cycle calibration data...")

    all_cycles = []

    # Cycle 1: Day 1, Batch A
    print("  Cycle 1: Day 1, Batch A")
    cycle1 = run_calibration_cycle(1, 1, 'A', seed_offset=0)
    all_cycles.append(cycle1)

    # Cycle 2: Day 2, Batch A (same batch, day-to-day variability)
    print("  Cycle 2: Day 2, Batch A")
    cycle2 = run_calibration_cycle(2, 2, 'A', seed_offset=10000)
    all_cycles.append(cycle2)

    # Cycle 3: Day 3, Batch B (new batch, batch variability)
    print("  Cycle 3: Day 3, Batch B")
    cycle3 = run_calibration_cycle(3, 3, 'B', seed_offset=20000)
    all_cycles.append(cycle3)

    # Cycle 4: Day 7, Batch A (temporal drift)
    print("  Cycle 4: Day 7, Batch A")
    cycle4 = run_calibration_cycle(4, 7, 'A', seed_offset=30000)
    all_cycles.append(cycle4)

    # Compute aggregate statistics
    sigma_withins = [c['metrics']['sigma_within'] for c in all_cycles]
    mean_signals = [c['metrics']['mean_signal'] for c in all_cycles]

    # Pooled within-run noise
    sigma_within_pooled = np.sqrt(np.mean([s**2 for s in sigma_withins]))

    # Between-run noise (standard deviation of mean signals)
    sigma_between = np.std(mean_signals, ddof=1)

    # Total noise
    sigma_total = np.sqrt(sigma_within_pooled**2 + sigma_between**2)

    # Overall rel_width
    mean_signal_overall = np.mean(mean_signals)
    se_total = sigma_total / np.sqrt(13)  # Using replicate count
    rel_width_total = (2 * se_total) / mean_signal_overall

    summary = {
        'cycles': all_cycles,
        'aggregate': {
            'sigma_within_pooled': float(sigma_within_pooled),
            'sigma_between': float(sigma_between),
            'sigma_total': float(sigma_total),
            'mean_signal_overall': float(mean_signal_overall),
            'rel_width_total': float(rel_width_total),
            'gate_threshold': 0.25,
            'gate_earned': bool(rel_width_total < 0.25)
        }
    }

    # Save to JSON
    output_path = Path(__file__).parent / 'src' / 'data' / 'calibration_results.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n✓ Calibration data generated: {output_path}")
    print(f"  σ_within_pooled = {sigma_within_pooled:.3f}")
    print(f"  σ_between = {sigma_between:.3f}")
    print(f"  σ_total = {sigma_total:.3f}")
    print(f"  rel_width_total = {rel_width_total:.3f}")
    print(f"  Gate earned: {rel_width_total < 0.25}")


if __name__ == '__main__':
    main()
