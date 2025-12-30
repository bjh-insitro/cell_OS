"""
Smoke test: Contamination event generation sanity check.

This is a "fuse" test that catches if the contamination generator is dead.
Not a scientific test - just ensures we're in the right ballpark.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.run_context import RunContext


def test_contamination_event_count_fuse():
    """
    Fuse test: 128 vessels × 7 days with 0.5% rate should produce 5-35 events.

    NOT a rigorous statistical test - just a "your generator isn't dead" check.
    Catches catastrophic failures like RNG reuse or rate math bugs.
    """
    # Fixed setup
    n_vessels = 128
    duration_h = 7 * 24  # 7 days
    rate_per_vessel_day = 0.005  # 0.5%
    rate_multiplier = 1.0

    # Expected: lambda = 128 * 7 * 0.005 = 4.48
    # Wide bounds: [1, 15] catches most failures without false positives
    expected_lambda = n_vessels * (duration_h / 24.0) * rate_per_vessel_day * rate_multiplier

    # Create VM with contamination enabled
    vm = BiologicalVirtualMachine(seed=42)
    vm.run_context = RunContext.sample(seed=42)
    vm.contamination_config = {
        'enabled': True,
        'baseline_rate_per_vessel_day': rate_per_vessel_day,
        'rate_multiplier': rate_multiplier,
        'type_probs': {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3},
        'severity_lognormal_cv': 0.5,
        'min_severity': 0.25,
        'max_severity': 3.0,
        'morphology_signature_strength': 1.0,
        'phase_params': {
            'bacterial': {'latent_h': 6, 'arrest_h': 6, 'death_rate_per_h': 0.4},
            'fungal': {'latent_h': 12, 'arrest_h': 12, 'death_rate_per_h': 0.2},
            'mycoplasma': {'latent_h': 24, 'arrest_h': 48, 'death_rate_per_h': 0.05},
        },
        'growth_arrest_multiplier': 0.05,
    }

    # Seed vessels (using proper plate layout)
    rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    cols = range(1, 13)  # 8×12 = 96, use ~128 by adding overflow plate
    vessel_count = 0
    for plate_idx in range(2):  # 2 plates for 128 vessels
        for row in rows:
            for col in cols:
                if vessel_count >= n_vessels:
                    break
                vessel_id = f"Plate{plate_idx}_{row}{col:02d}"
                vm.seed_vessel(vessel_id, cell_line='A549', vessel_type="96-well", initial_count=5000)
                vessel_count += 1
            if vessel_count >= n_vessels:
                break

    # Run for 7 days in 12h steps
    n_steps = int(duration_h / 12.0)
    for _ in range(n_steps):
        vm.advance_time(12.0)

    # Count contamination events
    contaminated_vessels = [v for v in vm.vessel_states.values() if v.contaminated]
    n_events = len(contaminated_vessels)

    print(f"\nContamination event generation:")
    print(f"  Expected lambda: {expected_lambda:.2f}")
    print(f"  Observed events: {n_events}")
    print(f"  Vessels: {n_vessels}, Duration: {duration_h/24:.0f}d, Rate: {rate_per_vessel_day}")

    # Fuse bounds: [0.2 * lambda, 5 * lambda] catches most catastrophic failures
    # This is intentionally loose - not a statistical test
    lower_bound = max(1, int(0.2 * expected_lambda))
    upper_bound = int(5.0 * expected_lambda)

    assert lower_bound <= n_events <= upper_bound, (
        f"Contamination event generation likely broken!\n"
        f"  Expected lambda: {expected_lambda:.2f}\n"
        f"  Observed: {n_events}\n"
        f"  Fuse bounds: [{lower_bound}, {upper_bound}]\n"
        f"  This is a 'generator not dead' check, not a rigorous test."
    )


def test_contamination_event_rate_scaling():
    """
    Fuse test: 10× rate multiplier should produce ~10× more events.

    NOT a rigorous test - just checks that rate_multiplier has the right polarity.
    """
    n_vessels = 32
    duration_h = 168  # 7 days
    base_rate = 0.005

    def run_with_multiplier(multiplier, seed):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.run_context = RunContext.sample(seed=seed)
        vm.contamination_config = {
            'enabled': True,
            'baseline_rate_per_vessel_day': base_rate,
            'rate_multiplier': multiplier,
            'type_probs': {'bacterial': 1.0},
            'severity_lognormal_cv': 0.0,
            'min_severity': 1.0,
            'max_severity': 1.0,
            'morphology_signature_strength': 1.0,
            'phase_params': {
                'bacterial': {'latent_h': 6, 'arrest_h': 6, 'death_rate_per_h': 0.4},
            },
            'growth_arrest_multiplier': 0.05,
        }

        # Proper 96-well plate layout for 32 vessels
        rows = ['A', 'B', 'C', 'D']  # 4 rows × 8 cols = 32 wells
        cols = range(1, 9)
        vessel_count = 0
        for row in rows:
            for col in cols:
                vessel_id = f"Plate0_{row}{col:02d}"
                vm.seed_vessel(vessel_id, cell_line='A549', vessel_type="96-well", initial_count=5000)
                vessel_count += 1

        for _ in range(14):  # 14 × 12h steps = 168h
            vm.advance_time(12.0)

        return sum(1 for v in vm.vessel_states.values() if v.contaminated)

    events_1x = run_with_multiplier(1.0, seed=100)
    events_10x = run_with_multiplier(10.0, seed=200)

    print(f"\nRate multiplier scaling:")
    print(f"  1× multiplier: {events_1x} events")
    print(f"  10× multiplier: {events_10x} events")
    print(f"  Ratio: {events_10x / max(events_1x, 1):.1f}×")

    # Loose check: 10× rate should produce at least 3× more events
    # (accounting for Poisson variance and small sample size)
    assert events_10x >= 3 * events_1x, (
        f"Rate multiplier doesn't scale correctly!\n"
        f"  1× rate: {events_1x} events\n"
        f"  10× rate: {events_10x} events\n"
        f"  Expected ~10× increase, got {events_10x / max(events_1x, 1):.1f}×"
    )
