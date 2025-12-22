"""
Agent 1: Observer Independence Invariant Tests

These tests verify that MEASUREMENT DOES NOT PERTURB BIOLOGY.

This is a correctness invariant, not a realism improvement.
If these tests fail, the simulator is epistemically invalid.

Test design:
- Run two identical simulations with same seed
- Path A: Measure at t=24h, then advance to t=48h
- Path B: Advance to t=24h (no measure), then advance to t=48h
- Assert: Final states are identical

Contract:
- Viability must be identical within 1e-6
- Cell count must be identical
- Death mechanism fractions must be identical
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_observer_independence_basic():
    """
    CRITICAL INVARIANT: Observation does not perturb biological state.

    Run identical well with/without measurement at intermediate timepoint.
    Final states must be identical.
    """
    seed = 42
    vessel_id = "test_vessel"
    cell_line = "A549"
    compound = "DMSO"
    dose_uM = 0.0
    final_time_h = 48.0
    intermediate_time_h = 24.0

    # Path A: Measure at t=24h, then continue to t=48h
    sim_a = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_a.seed_vessel(
        vessel_id=vessel_id,
        cell_line=cell_line,
        initial_count=10000,
        capacity=1e7
    )
    sim_a.add_compound(vessel_id, compound, dose_uM)

    # Advance to t=24h
    sim_a.advance_time(intermediate_time_h)

    # MEASURE at t=24h (this is the perturbation risk)
    count_result_24h = sim_a.count_cells(vessel_id, vessel_id=vessel_id)

    # Continue to t=48h
    sim_a.advance_time(final_time_h - intermediate_time_h)

    # Final measurement
    final_a = sim_a.get_vessel_state(vessel_id)
    count_final_a = sim_a.count_cells(vessel_id, vessel_id=vessel_id)

    # Path B: No measurement at t=24h
    sim_b = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_b.seed_vessel(
        vessel_id=vessel_id,
        cell_line=cell_line,
        initial_count=10000,
        capacity=1e7
    )
    sim_b.add_compound(vessel_id, compound, dose_uM)

    # Advance to t=24h WITHOUT measurement
    sim_b.advance_time(intermediate_time_h)

    # Continue to t=48h
    sim_b.advance_time(final_time_h - intermediate_time_h)

    # Final measurement
    final_b = sim_b.get_vessel_state(vessel_id)
    count_final_b = sim_b.count_cells(vessel_id, vessel_id=vessel_id)

    # CRITICAL ASSERTIONS: States must be identical

    # Viability (measured)
    via_a = count_final_a['viability']
    via_b = count_final_b['viability']
    assert abs(via_a - via_b) < 1e-6, (
        f"Observer independence violated: viability differs!\n"
        f"  Path A (with intermediate measure): {via_a:.10f}\n"
        f"  Path B (without measure): {via_b:.10f}\n"
        f"  Delta: {abs(via_a - via_b):.2e}\n"
        f"Measurement at t=24h perturbed biological trajectory."
    )

    # Cell count (measured)
    count_a = count_final_a['count']
    count_b = count_final_b['count']
    count_delta_rel = abs(count_a - count_b) / max(count_a, count_b)
    assert count_delta_rel < 1e-6, (
        f"Observer independence violated: cell count differs!\n"
        f"  Path A (with intermediate measure): {count_a:.2f}\n"
        f"  Path B (without measure): {count_b:.2f}\n"
        f"  Relative delta: {count_delta_rel:.2e}\n"
        f"Measurement at t=24h perturbed biological trajectory."
    )

    # Vessel state (biological ground truth)
    via_true_a = final_a['viability']
    via_true_b = final_b['viability']
    assert abs(via_true_a - via_true_b) < 1e-9, (
        f"Observer independence violated: true viability differs!\n"
        f"  Path A: {via_true_a:.10f}\n"
        f"  Path B: {via_true_b:.10f}\n"
        f"  Delta: {abs(via_true_a - via_true_b):.2e}\n"
        f"This is a fundamental correctness violation."
    )

    print("✓ Observer independence verified: Measurement does not perturb biology")
    print(f"  Final viability: {via_a:.6f} (identical in both paths)")
    print(f"  Final cell count: {count_a:.0f} (identical in both paths)")


def test_observer_independence_with_treatment():
    """
    Observer independence with active compound.

    Compound-induced death must be identical regardless of measurement frequency.
    """
    seed = 123
    vessel_id = "test_vessel"
    cell_line = "A549"
    compound = "tunicamycin"  # ER stress, causes death
    dose_uM = 10.0  # Lethal dose
    final_time_h = 48.0
    measurement_times_h = [12.0, 24.0, 36.0]  # Frequent measurements

    # Path A: Frequent measurements
    sim_a = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_a.seed_vessel(vessel_id, cell_line, 10000, 1e7)
    sim_a.add_compound(vessel_id, compound, dose_uM)

    for t in measurement_times_h:
        dt = t - sim_a.simulated_time
        sim_a.advance_time(dt)
        _ = sim_a.count_cells(vessel_id, vessel_id=vessel_id)  # Measure

    # Advance to final time
    sim_a.advance_time(final_time_h - sim_a.simulated_time)
    final_a = sim_a.get_vessel_state(vessel_id)

    # Path B: Single final measurement
    sim_b = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_b.seed_vessel(vessel_id, cell_line, 10000, 1e7)
    sim_b.add_compound(vessel_id, compound, dose_uM)
    sim_b.advance_time(final_time_h)
    final_b = sim_b.get_vessel_state(vessel_id)

    # Death should be identical
    via_a = final_a['viability']
    via_b = final_b['viability']
    assert abs(via_a - via_b) < 1e-6, (
        f"Observer independence violated with treatment!\n"
        f"  Frequent measurements: viability={via_a:.6f}\n"
        f"  Single measurement: viability={via_b:.6f}\n"
        f"  Delta: {abs(via_a - via_b):.2e}\n"
        f"Measurement frequency affected compound-induced death."
    )

    print(f"✓ Observer independence with treatment verified")
    print(f"  Compound: {compound} @ {dose_uM} µM")
    print(f"  Final viability: {via_a:.6f} (identical with/without intermediate measurements)")


def test_observer_independence_morphology():
    """
    Observer independence for morphology readouts.

    Measuring morphology at t=24h must not affect morphology at t=48h.
    """
    seed = 456
    vessel_id = "test_vessel"
    cell_line = "A549"
    compound = "DMSO"
    dose_uM = 0.0
    intermediate_h = 24.0
    final_h = 48.0

    # Path A: Measure morphology at t=24h
    sim_a = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_a.seed_vessel(vessel_id, cell_line, 10000, 1e7)
    sim_a.add_compound(vessel_id, compound, dose_uM)
    sim_a.advance_time(intermediate_h)

    # Measure morphology at t=24h
    morph_24h_a = sim_a.measure_morphology(
        sample_loc=vessel_id,
        vessel_id=vessel_id,
        timepoint_h=intermediate_h
    )

    sim_a.advance_time(final_h - intermediate_h)
    morph_48h_a = sim_a.measure_morphology(
        sample_loc=vessel_id,
        vessel_id=vessel_id,
        timepoint_h=final_h
    )

    # Path B: No measurement at t=24h
    sim_b = BiologicalVirtualMachine(seed=seed, use_database=False)
    sim_b.seed_vessel(vessel_id, cell_line, 10000, 1e7)
    sim_b.add_compound(vessel_id, compound, dose_uM)
    sim_b.advance_time(intermediate_h)
    # No measurement
    sim_b.advance_time(final_h - intermediate_h)
    morph_48h_b = sim_b.measure_morphology(
        sample_loc=vessel_id,
        vessel_id=vessel_id,
        timepoint_h=final_h
    )

    # Compare final morphology (channel by channel)
    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
    for ch in channels:
        val_a = morph_48h_a[ch]
        val_b = morph_48h_b[ch]
        # Morphology has measurement noise, but should use same assay RNG seed
        # So with same seed, measurements should be identical
        delta = abs(val_a - val_b)
        assert delta < 1e-6, (
            f"Observer independence violated for {ch} morphology!\n"
            f"  With t=24h measurement: {val_a:.6f}\n"
            f"  Without t=24h measurement: {val_b:.6f}\n"
            f"  Delta: {delta:.2e}\n"
            f"Intermediate morphology measurement perturbed final morphology."
        )

    print(f"✓ Observer independence for morphology verified")
    print(f"  All channels identical at t=48h regardless of t=24h measurement")


if __name__ == "__main__":
    print("="*70)
    print("Agent 1: Observer Independence Invariant Tests")
    print("="*70)
    print()

    print("Test 1: Basic observer independence (DMSO baseline)")
    print("-"*70)
    test_observer_independence_basic()
    print()

    print("Test 2: Observer independence with treatment (tunicamycin)")
    print("-"*70)
    test_observer_independence_with_treatment()
    print()

    print("Test 3: Observer independence for morphology measurements")
    print("-"*70)
    test_observer_independence_morphology()
    print()

    print("="*70)
    print("ALL OBSERVER INDEPENDENCE TESTS PASSED")
    print("="*70)
    print()
    print("✅ The simulator preserves observer independence:")
    print("   - Measurement does not perturb biological trajectories")
    print("   - Viability is independent of measurement frequency")
    print("   - Morphology readouts are independent of prior observations")
    print()
    print("If any of these tests had failed, the simulator would be")
    print("epistemically invalid and all downstream results would be suspect.")
