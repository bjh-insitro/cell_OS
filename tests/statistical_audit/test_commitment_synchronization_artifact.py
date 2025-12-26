"""
Test that exposes the 12h commitment threshold as a falsifiable artifact.

Real biology: Commitment time is stochastic and dose-dependent.
Simulator: Hard step function at 12h creates synchronized death wave.

A hostile statistician would detect this via:
1. Time-derivative discontinuity at t=12h
2. Population-level synchronization (no cell-to-cell variation in commitment)
3. Dose-independence of commitment time (should be faster at high doses)
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.core.experiment import Treatment


def test_commitment_threshold_synchronization():
    """Prove that attrition death is synchronized at exactly 12h across all doses.

    Real biology violation:
    - High dose (10×IC50) should commit faster than low dose (1×IC50)
    - Commitment should be gradual (cell-to-cell variation), not step function
    - This test shows the step function artifact that would embarrass the simulator
    """

    # Setup
    vm = BiologicalVirtualMachine(seed=42)
    cell_line = "A549"
    compound = "tunicamycin"  # ER stress, strong attrition

    # Two doses: 1×IC50 and 10×IC50 (should have different commitment kinetics)
    ic50_uM = 1.0  # tunicamycin IC50 for A549
    doses = [ic50_uM, 10 * ic50_uM]

    results = {}

    for i, dose_uM in enumerate(doses):
        # Create vessel
        vessel_id = f"P1_A0{i+1}"
        vm.seed_vessel(vessel_id, cell_line, initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        # Treat immediately
        vm.treat_with_compound(vessel_id, compound, dose_uM)

        # Sample viability at fine temporal resolution around 12h threshold
        timepoints = [0, 6, 11, 11.5, 12.0, 12.5, 13, 18, 24]
        viabilities = []
        death_attrition = []

        for t in timepoints:
            # Step forward
            vm._step_vessel(vessel, t)
            viabilities.append(vessel.viability)
            # Track ATTRITION-specific death (not instant effect)
            # ER stress attrition is the gradual death from stress accumulation
            death_attrition.append(vessel.death_er_stress)

        results[dose_uM] = {
            'timepoints': timepoints,
            'viability': viabilities,
            'death_attrition': death_attrition
        }

    # ASSERTION 1: Massive acceleration at exactly 12h
    for dose_uM in doses:
        idx_11h = results[dose_uM]['timepoints'].index(11.5)
        idx_12h = results[dose_uM]['timepoints'].index(12.5)

        death_11h = results[dose_uM]['death_attrition'][idx_11h]
        death_12h = results[dose_uM]['death_attrition'][idx_12h]

        # Death should jump significantly right after 12h
        assert death_12h > death_11h, \
            f"No attrition increase after 12h at dose {dose_uM}×IC50"

    # ASSERTION 3 (THE KILLER): Commitment time is dose-INDEPENDENT
    # Real biology: 10×IC50 should commit much faster than 1×IC50
    # Simulator: Both commit at exactly 12h (synchronized artifact)

    # Find "commitment time" = when attrition death crosses 1% threshold
    def find_commitment_time(dose_uM):
        for i, t in enumerate(results[dose_uM]['timepoints']):
            if results[dose_uM]['death_attrition'][i] > 0.01:
                return t
        return None

    commit_low = find_commitment_time(doses[0])
    commit_high = find_commitment_time(doses[1])

    # Both doses commit at ~12h (within 1h window)
    assert commit_low is not None and commit_high is not None
    assert abs(commit_low - commit_high) < 1.0, \
        f"Commitment time varies by dose (low: {commit_low}h, high: {commit_high}h)"

    # Both should be close to 12h
    assert abs(commit_low - 12.0) < 1.0, \
        f"Low dose commits at {commit_low}h (expected ~12h)"
    assert abs(commit_high - 12.0) < 1.0, \
        f"High dose commits at {commit_high}h (expected ~12h)"

    # Print diagnostic for hostile reviewer
    print("\n=== COMMITMENT SYNCHRONIZATION ARTIFACT DETECTED ===")
    print(f"Low dose (1×IC50): Commitment at ~{commit_low:.1f}h")
    print(f"High dose (10×IC50): Commitment at ~{commit_high:.1f}h")
    print(f"Difference: {abs(commit_low - commit_high):.2f}h (should be >3h in real biology)")
    print("\nReal biology: High dose commits 2-6h faster than low dose.")
    print("This simulator: All doses commit at exactly 12h (hard threshold).")
    print("A flow cytometry time course would immediately reveal this artifact.")


def test_derivative_discontinuity_at_12h():
    """Prove that d(death)/dt has a step discontinuity at t=12h.

    This is a calculus-level proof that the model is non-smooth.
    Real biological processes don't have infinite derivatives.
    """

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # High dose to maximize attrition effect
    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    # Sample with very fine temporal resolution
    times = np.linspace(10, 14, 41)  # 0.1h resolution around 12h
    deaths = []

    for t in times:
        vm._step_vessel(vessel, t)
        deaths.append(vessel.death_er_stress)  # Attrition death only

    # Compute numerical derivative (forward difference)
    dt = times[1] - times[0]
    derivatives = np.diff(deaths) / dt

    # Find max derivative in pre-12h window vs post-12h window
    pre_12h_mask = times[:-1] < 12.0
    post_12h_mask = times[:-1] >= 12.0

    max_deriv_pre = np.max(derivatives[pre_12h_mask]) if np.any(pre_12h_mask) else 0
    max_deriv_post = np.max(derivatives[post_12h_mask]) if np.any(post_12h_mask) else 0

    # Post-12h derivative should be >>10× larger (step function)
    assert max_deriv_post > 10 * max_deriv_pre, \
        f"Derivative continuous at 12h (pre: {max_deriv_pre:.4f}, post: {max_deriv_post:.4f})"

    print(f"\n=== DERIVATIVE DISCONTINUITY ===")
    print(f"Max d(death)/dt before 12h: {max_deriv_pre:.6f}")
    print(f"Max d(death)/dt after 12h: {max_deriv_post:.6f}")
    print(f"Jump ratio: {max_deriv_post / max(max_deriv_pre, 1e-9):.1f}×")
    print("\nThis infinite derivative would be visible in high-resolution time courses.")


if __name__ == "__main__":
    test_commitment_threshold_synchronization()
    test_derivative_discontinuity_at_12h()
    print("\n✓ Commitment synchronization artifact proven.")
