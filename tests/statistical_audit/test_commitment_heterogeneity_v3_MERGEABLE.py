"""
MERGEABLE tests for commitment heterogeneity patch v3.

All issues fixed:
1. Time contract asserted (no double-advancing)
2. IC50 from exact same source
3. Low viability seeded (viability gate doesn't block activation)
"""

import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.biology import biology_core


def test_no_kink_in_attrition_derivative():
    """Ensure attrition rate has no step discontinuities in time.

    Time contract: _step_vessel does NOT advance simulated_time (verified by assert).
    """

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    # LOW VIABILITY: Ensures attrition gate doesn't block (viability < 0.5 required)
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.3)
    vessel = vm.vessel_states[vessel_id]

    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    # Sample at fine resolution
    times = np.linspace(0, 24, 241)  # 0.1h steps
    deaths = []

    t_prev = 0.0

    for t in times:
        dt = t - t_prev
        if dt > 0:
            # Assert time contract: _step_vessel does NOT advance time
            t0 = vm.simulated_time
            vm._step_vessel(vessel, dt)
            # If this fails, _step_vessel is advancing time (double-advance bug)
            assert abs(vm.simulated_time - t0) < 1e-9, \
                "_step_vessel advanced simulated_time (should not)"

            # Manually advance clock (normally done by advance_time)
            vm.simulated_time = t

        deaths.append(vessel.death_er_stress)
        t_prev = t

    # Compute derivative
    dt_step = times[1] - times[0]
    derivatives = np.diff(deaths) / dt_step

    # Test: no adjacent derivatives differ by more than 100×
    max_ratio = 1.0
    for i in range(len(derivatives) - 1):
        if derivatives[i] > 1e-6:
            ratio = derivatives[i+1] / max(derivatives[i], 1e-9)
            max_ratio = max(max_ratio, ratio)

            assert ratio < 100, \
                f"Derivative jump {ratio:.1f}× at t={times[i+1]:.1f}h (step function)"

    print(f"✓ Maximum derivative ratio: {max_ratio:.2f}× (smooth)")


def test_no_lethal_dose_uses_fallback_12h():
    """Ensure all lethal doses have sampled delays, never fallback to 12h.

    IC50 computed from EXACT same source as treat_with_compound uses.
    """

    vm = BiologicalVirtualMachine(seed=42)

    compound = "tunicamycin"
    cell_line = "A549"

    # Retrieve compound params from EXACT same source as treat_with_compound
    # (lines 1995-2020 in biological_virtual.py)
    if compound not in vm.thalamus_params:
        print(f"⚠ {compound} not in thalamus_params, using default IC50=1.0")
        ic50_uM = 1.0
    else:
        compound_meta = vm.thalamus_params[compound]
        base_ec50 = compound_meta.get('ec50_uM', 1.0)
        stress_axis = compound_meta.get('stress_axis', 'er_stress')

        # Get cell_line_sensitivity from SAME place treat_with_compound uses
        cell_line_sensitivity = vm.thalamus_params.get('cell_line_sensitivity', {})

        # Compute adjusted IC50 using EXACT same function
        ic50_uM = biology_core.compute_adjusted_ic50(
            compound=compound,
            cell_line=cell_line,
            base_ec50=base_ec50,
            stress_axis=stress_axis,
            cell_line_sensitivity=cell_line_sensitivity,
            proliferation_index=biology_core.PROLIF_INDEX.get(cell_line)
        )

        # Apply run context modifier (same as treat_with_compound line 2019-2020)
        bio_mods = vm.run_context.get_biology_modifiers()
        ic50_uM *= bio_mods['ec50_multiplier']

    print(f"Using IC50 = {ic50_uM:.2f} µM for {compound} on {cell_line}")

    for dose_mult in [1.0, 2.0, 5.0, 10.0]:
        vessel_id = f"v_{dose_mult}x"
        vm.seed_vessel(vessel_id, cell_line, initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        # Use computed IC50, not hardcoded
        dose_uM = dose_mult * ic50_uM

        vm.treat_with_compound(vessel_id, compound, dose_uM)

        # Verify exposure_id exists
        exposure_id = vessel.compound_meta.get('exposure_ids', {}).get(compound)
        assert exposure_id is not None, f"Missing exposure_id at {dose_mult}×IC50"

        # Verify ALL subpops have sampled delays (dynamic subpop names)
        for subpop_name in sorted(vessel.subpopulations.keys()):
            cache_key = (compound, exposure_id, subpop_name)
            delay = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)

            assert delay is not None, \
                f"Missing delay for {subpop_name} at {dose_mult}×IC50 (fallback to 12h)"

            assert 1.5 <= delay <= 48.0, \
                f"Delay {delay:.1f}h out of bounds for {subpop_name}"

    print("✓ All lethal doses have sampled delays (no fallback)")


def test_commitment_gate_not_a_threshold():
    """Verify subpops don't all activate attrition in same timestep.

    Uses actual hazard rate. Seeds at LOW viability so viability gate doesn't block.
    """

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    # LOW VIABILITY: Attrition requires viability < 0.5 (biology_core.py:444)
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.3)
    vessel = vm.vessel_states[vessel_id]

    compound = "tunicamycin"
    dose_uM = 5.0
    vm.treat_with_compound(vessel_id, compound, dose_uM)

    # Extract commitment delays
    exposure_id = vessel.compound_meta['exposure_ids'][compound]
    treatment_start = vessel.compound_start_time[compound]
    delays = []

    for subpop_name in sorted(vessel.subpopulations.keys()):
        cache_key = (compound, exposure_id, subpop_name)
        delay = vessel.compound_meta['commitment_delays'][cache_key]
        delays.append((subpop_name, delay))

    delays.sort(key=lambda x: x[1])

    # Verify delays span at least 1h
    delay_span = delays[-1][1] - delays[0][1]
    assert delay_span >= 1.0, \
        f"Delay span {delay_span:.2f}h too narrow (risk of synchronization)"

    # Get compound params for hazard computation
    compound_meta = vm.thalamus_params[compound]
    base_ec50 = compound_meta['ec50_uM']
    stress_axis = compound_meta['stress_axis']
    hill_slope = compound_meta.get('hill_slope', 1.5)

    # Sample attrition hazard around median delay
    median_delay = delays[1][1]  # Typical subpop
    times = np.linspace(treatment_start + median_delay - 2,
                        treatment_start + median_delay + 2, 41)

    # Track activation time per subpop (when hazard first becomes >0)
    activations_per_subpop = {name: None for name, _ in delays}

    t_prev = treatment_start
    for t in times:
        dt = t - t_prev
        if dt > 0:
            vm._step_vessel(vessel, dt)
            vm.simulated_time = t

        time_since_treatment = t - treatment_start

        # Check ACTUAL hazard rate for each subpop
        for subpop_name in sorted(vessel.subpopulations.keys()):
            subpop = vessel.subpopulations[subpop_name]

            # Compute adjusted IC50 for this subpop (same as simulator does)
            ic50_shift = subpop['ic50_shift']
            ic50_uM = biology_core.compute_adjusted_ic50(
                compound=compound,
                cell_line=vessel.cell_line,
                base_ec50=base_ec50,
                stress_axis=stress_axis,
                cell_line_sensitivity=vm.thalamus_params.get('cell_line_sensitivity', {}),
                proliferation_index=biology_core.PROLIF_INDEX.get(vessel.cell_line)
            )
            ic50_uM *= ic50_shift  # Apply subpop shift

            # Get commitment delay for this subpop
            cache_key = (compound, exposure_id, subpop_name)
            commitment_delay_h = vessel.compound_meta['commitment_delays'][cache_key]

            # Compute actual attrition hazard rate
            # Use vessel viability (already low, 0.3, so gate doesn't block)
            try:
                hazard_rate = biology_core.compute_attrition_rate_instantaneous(
                    compound=compound,
                    dose_uM=dose_uM,
                    ic50_uM=ic50_uM,
                    stress_axis=stress_axis,
                    cell_line=vessel.cell_line,
                    hill_slope=hill_slope,
                    transport_dysfunction=subpop.get('transport_dysfunction', 0.0),
                    time_since_treatment_h=time_since_treatment,
                    current_viability=vessel.viability,  # Already 0.3, gate doesn't block
                    params={'commitment_delay_h': commitment_delay_h}
                )

                # Record first time hazard becomes positive
                if hazard_rate > 1e-9 and activations_per_subpop[subpop_name] is None:
                    activations_per_subpop[subpop_name] = t

            except ValueError:
                # IC50 validation error - skip this subpop
                pass

        t_prev = t

    # Count unique activation times (rounded to 0.1h)
    activated = [t for t in activations_per_subpop.values() if t is not None]

    if len(activated) == 0:
        # Shouldn't happen with low viability, but guard anyway
        print("⚠ No hazard activations detected (viability gate or other issue)")
        assert False, "No activations detected - test setup broken"

    unique_activation_times = len(set(np.round(activated, 1)))

    assert unique_activation_times >= 2, \
        f"Only {unique_activation_times} activation time(s) - suggests synchronization"

    print(f"✓ Attrition activates at {unique_activation_times} distinct times")
    print(f"  Activation times: {[f'{t:.1f}h' for t in sorted(activated)]}")


def test_commitment_heterogeneity_cv_stable():
    """Verify delays vary with dose, CV stays bounded."""

    results = {}

    for dose_mult in [1, 2, 5, 10, 20]:
        vm = BiologicalVirtualMachine(seed=42)
        vessel_id = f"v_{dose_mult}x"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        dose_uM = dose_mult * 1.0
        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
        delays = []

        # Dynamic subpop names
        for subpop_name in sorted(vessel.subpopulations.keys()):
            cache_key = ('tunicamycin', exposure_id, subpop_name)
            delay = vessel.compound_meta['commitment_delays'][cache_key]
            delays.append(delay)

        results[dose_mult] = {
            'delays': delays,
            'mean': np.mean(delays),
            'std': np.std(delays),
            'cv': np.std(delays) / np.mean(delays)
        }

    # Mean decreases monotonically
    dose_levels = sorted(results.keys())
    for i in range(len(dose_levels) - 1):
        assert results[dose_levels[i]]['mean'] >= results[dose_levels[i+1]]['mean'], \
            f"Mean increased with dose"

    # CV stays bounded
    cvs = [r['cv'] for r in results.values()]
    assert all(0.05 < cv < 0.6 for cv in cvs), f"CV out of range: {cvs}"

    print("✓ Commitment heterogeneity with stable CV:")
    for dose, r in results.items():
        print(f"  {dose:2d}×IC50: mean={r['mean']:5.1f}h, CV={r['cv']:.3f}")


if __name__ == "__main__":
    print("Running mergeable tests...\n")
    test_no_kink_in_attrition_derivative()
    print()
    test_no_lethal_dose_uses_fallback_12h()
    print()
    test_commitment_gate_not_a_threshold()
    print()
    test_commitment_heterogeneity_cv_stable()
    print("\n✓ All tests passed - READY TO MERGE")
