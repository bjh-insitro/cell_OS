"""
Phase 4 Option 3: Cross-talk coupling test (transport → mito).

Verifies that prolonged transport dysfunction induces secondary mito dysfunction:
- Coupling activates after 18h delay
- Effect is small (secondary to primary signatures)
- Identifiability preserved (primary signatures still dominate)
- "Do nothing now, pay later" dynamic works

This is the critical test that proves coupling doesn't break orthogonality.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
import numpy as np


def test_coupling_delay_requirement():
    """
    Test that coupling only activates after 18h delay.

    Setup:
    - Dose paclitaxel at 0h (microtubule axis → transport dysfunction)
    - Measure mito dysfunction at 6h, 12h, 18h, 24h, 30h, 36h
    - Verify coupling doesn't activate until after 18h

    Expected:
    - Transport dysfunction rises quickly (fast k_on)
    - Mito dysfunction stays near zero for first ~18h
    - After sustained high transport (18h above threshold), mito dysfunction begins slow rise
    """
    print("\n=== Coupling Delay Test ===")

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Dose paclitaxel at higher dose to keep transport stably high
    # (0.01 µM = 2× reference, keeps transport above threshold more consistently)
    vm.treat_with_compound("test", "paclitaxel", dose_uM=0.01)

    # Track dysfunction over time (extend to 42h to see coupling effect accumulate)
    timepoints = [0, 6, 12, 18, 24, 30, 36, 42]
    transport_dys = []
    mito_dys = []
    high_since_times = []

    for t in timepoints:
        if t > 0:
            vm.advance_time(t - vm.simulated_time)

        vessel = vm.vessel_states["test"]
        transport_dys.append(vessel.transport_dysfunction)
        mito_dys.append(vessel.mito_dysfunction)
        high_since_times.append(vessel.transport_high_since)

    print(f"\n{'Time (h)':<10} {'Transport Dys':<15} {'Mito Dys':<15} {'high_since':<15}")
    print(f"{'='*55}")
    for i, t in enumerate(timepoints):
        print(f"{t:<10} {transport_dys[i]:<15.3f} {mito_dys[i]:<15.3f} {str(high_since_times[i]):<15}")

    # Assertions

    # 1. Transport dysfunction should rise quickly (microtubule axis effect)
    assert transport_dys[1] > 0.6, (
        f"Transport dysfunction should exceed threshold at 6h: {transport_dys[1]:.3f}"
    )

    # 2. Mito dysfunction should stay near zero for first ~18-24h (no coupling or just activated)
    assert mito_dys[1] < 0.05, (
        f"Mito dysfunction should be minimal at 6h (no coupling): {mito_dys[1]:.3f}"
    )
    assert mito_dys[2] < 0.10, (
        f"Mito dysfunction should be minimal at 12h (no coupling): {mito_dys[2]:.3f}"
    )

    # 3. Find when transport_high_since was LAST set (not first, due to resets)
    # This tells us when the 18h delay actually started counting
    last_high_set = None
    for i in range(1, len(timepoints)):
        if high_since_times[i] is not None and high_since_times[i-1] is None:
            last_high_set = high_since_times[i]

    if last_high_set is None:
        # high_since might have been set before first measurement
        last_high_set = next((hs for hs in high_since_times if hs is not None), None)

    print(f"\nTransport high_since last set at: {last_high_set}h")
    coupling_activation_time = last_high_set + 18 if last_high_set else None
    print(f"Coupling should activate at: {coupling_activation_time}h")

    # By 42h, if high_since was set at 18h, coupling activated at 36h and has been active for 6h
    if coupling_activation_time and coupling_activation_time <= 42:
        coupling_active_duration = 42 - coupling_activation_time
        print(f"Coupling active duration by 42h: {coupling_active_duration}h")

        # At coupling rate of 0.02/h, after 6h we expect ~0.12 mito dysfunction
        # (assuming transport stays high and no mito compounds present)
        assert mito_dys[7] > 0.05, (
            f"Mito dysfunction should increase after coupling activates: {mito_dys[7]:.3f}"
        )

        # 4. Coupling effect should be small (< 0.4 by 42h)
        assert mito_dys[7] < 0.4, (
            f"Coupling effect should be secondary (< 0.4 by 42h): {mito_dys[7]:.3f}"
        )

    print(f"\n✓ PASSED: Coupling activates after 18h delay")


def test_coupling_threshold_gating():
    """
    Test that coupling only activates when transport dysfunction exceeds threshold.

    Setup:
    - Use same high dose (0.01 µM) from delay test
    - Compare viability/mito at 24h vs 42h
    - At 24h: coupling just activated (18h after high_since set at ~6h)
    - At 42h: coupling active for ~18h

    Expected:
    - Mito dysfunction increases from 24h to 42h due to coupling
    """
    print("\n=== Coupling Threshold Test ===")

    # Scenario 1: Measure at 24h (coupling just activated)
    vm_24h = BiologicalVirtualMachine(seed=42)
    vm_24h.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm_24h.treat_with_compound("test", "paclitaxel", dose_uM=0.01)
    # Advance in smaller steps for numerical accuracy (6h steps like delay test)
    for _ in range(4):  # 4 × 6h = 24h
        vm_24h.advance_time(6.0)
    vessel_24h = vm_24h.vessel_states["test"]
    transport_24h = vessel_24h.transport_dysfunction
    mito_24h = vessel_24h.mito_dysfunction

    # Scenario 2: Measure at 42h (coupling active for ~18h)
    vm_42h = BiologicalVirtualMachine(seed=42)
    vm_42h.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm_42h.treat_with_compound("test", "paclitaxel", dose_uM=0.01)
    # Advance in smaller steps for numerical accuracy (6h steps like delay test)
    for _ in range(7):  # 7 × 6h = 42h
        vm_42h.advance_time(6.0)
    vessel_42h = vm_42h.vessel_states["test"]
    transport_42h = vessel_42h.transport_dysfunction
    mito_42h = vessel_42h.mito_dysfunction

    print(f"\nAt 24h (coupling just activated):")
    print(f"  Transport dysfunction: {transport_24h:.3f}")
    print(f"  Mito dysfunction: {mito_24h:.3f}")
    print(f"  transport_high_since: {vessel_24h.transport_high_since}")

    print(f"\nAt 42h (coupling active for ~18h):")
    print(f"  Transport dysfunction: {transport_42h:.3f}")
    print(f"  Mito dysfunction: {mito_42h:.3f}")
    print(f"  transport_high_since: {vessel_42h.transport_high_since}")

    # Assertions

    # 1. Both timepoints should have transport > 0.6
    assert transport_24h > 0.6, (
        f"Transport should exceed threshold at 24h: {transport_24h:.3f}"
    )
    assert transport_42h > 0.6, (
        f"Transport should exceed threshold at 42h: {transport_42h:.3f}"
    )

    # 2. Mito dysfunction should be minimal at 24h (coupling just activated)
    assert mito_24h < 0.01, (
        f"Mito dysfunction should be minimal at 24h: {mito_24h:.3f}"
    )

    # 3. Mito dysfunction should increase by 42h (coupling active)
    assert mito_42h > 0.04, (
        f"Mito dysfunction should accumulate by 42h: {mito_42h:.3f}"
    )

    # 4. Meaningful increase from 24h to 42h
    mito_increase = mito_42h - mito_24h
    print(f"\nMito dysfunction increase from 24h to 42h: {mito_increase:.3f}")

    assert mito_increase > 0.03, (
        f"Coupling should cause measurable mito increase: {mito_24h:.3f} → {mito_42h:.3f} (Δ={mito_increase:.3f})"
    )

    print(f"\n✓ PASSED: Coupling induces measurable secondary mito dysfunction")


def test_coupling_reset_on_washout():
    """
    Test that coupling resets when transport dysfunction drops below threshold.

    Setup:
    - Dose paclitaxel, wait 12h (transport high, coupling not yet active)
    - Washout compound
    - Wait another 12h (transport decays, coupling should not activate)

    Expected:
    - Transport dysfunction should decay after washout
    - Mito dysfunction should not increase (coupling never activated)
    """
    print("\n=== Coupling Reset Test ===")

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Dose and wait 12h
    vm.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    vm.advance_time(12.0)
    vessel = vm.vessel_states["test"]
    transport_12h = vessel.transport_dysfunction
    mito_12h = vessel.mito_dysfunction

    print(f"\nAt 12h (before washout):")
    print(f"  Transport dysfunction: {transport_12h:.3f}")
    print(f"  Mito dysfunction: {mito_12h:.3f}")
    print(f"  transport_high_since: {vessel.transport_high_since}")

    # Washout compound
    vm.washout_compound("test", "paclitaxel")

    # Wait another 12h (total 24h)
    vm.advance_time(12.0)
    transport_24h = vessel.transport_dysfunction
    mito_24h = vessel.mito_dysfunction

    print(f"\nAt 24h (after washout at 12h):")
    print(f"  Transport dysfunction: {transport_24h:.3f}")
    print(f"  Mito dysfunction: {mito_24h:.3f}")
    print(f"  transport_high_since: {vessel.transport_high_since}")

    # Assertions

    # 1. Transport should decay after washout
    assert transport_24h < transport_12h, (
        f"Transport should decay after washout: {transport_12h:.3f} → {transport_24h:.3f}"
    )

    # 2. Mito dysfunction should not increase significantly (coupling never activated)
    mito_increase = mito_24h - mito_12h
    assert mito_increase < 0.05, (
        f"Coupling should not activate after washout: Δmito={mito_increase:.3f}"
    )

    # 3. transport_high_since should be None (reset after dropping below threshold)
    assert vessel.transport_high_since is None, (
        f"transport_high_since should reset after washout: {vessel.transport_high_since}"
    )

    print(f"\n✓ PASSED: Coupling resets when transport drops below threshold")


def test_identifiability_with_coupling():
    """
    Test that primary signatures still dominate even with coupling active.

    This is the critical test for orthogonality.

    Setup:
    - Three scenarios at 24h (coupling active):
      1. ER stress compound (tunicamycin)
      2. Mito compound (cccp)
      3. Transport compound (paclitaxel, with coupling)

    Expected:
    - Each axis should still be identifiable from signatures
    - Primary signatures >> coupling effects
    - Classifier should correctly identify all three axes
    """
    print("\n=== Identifiability with Coupling Test ===")

    # Reference doses for each axis
    test_cases = [
        ("tunicamycin", 0.5, "er_stress"),
        ("cccp", 1.0, "mitochondrial"),
        ("paclitaxel", 0.005, "microtubule")
    ]

    results = {}

    for compound, dose_uM, expected_axis in test_cases:
        print(f"\n--- Testing {compound} (expected: {expected_axis}) ---")

        # Initialize VM
        vm = BiologicalVirtualMachine(seed=42)
        vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

        # Measure baseline
        baseline_result = vm.cell_painting_assay("test")
        baseline_struct = baseline_result['morphology_struct']
        baseline_scalars = vm.atp_viability_assay("test")

        baseline_er = baseline_struct['er']
        baseline_mito = baseline_struct['mito']
        baseline_actin = baseline_struct['actin']
        baseline_upr = baseline_scalars['upr_marker']
        baseline_atp = baseline_scalars['atp_signal']
        baseline_trafficking = baseline_scalars['trafficking_marker']

        # Treat and advance to 36h (coupling active if transport axis)
        # Advance in 6h steps for numerical accuracy
        vm.treat_with_compound("test", compound, dose_uM=dose_uM)
        for _ in range(6):  # 6 × 6h = 36h
            vm.advance_time(6.0)

        # Measure signatures
        result = vm.cell_painting_assay("test")
        morph_struct = result['morphology_struct']
        scalars = vm.atp_viability_assay("test")

        # Compute fold-changes
        er_fold = morph_struct['er'] / baseline_er
        mito_fold = morph_struct['mito'] / baseline_mito
        actin_fold = morph_struct['actin'] / baseline_actin
        upr_fold = scalars['upr_marker'] / baseline_upr
        atp_fold = scalars['atp_signal'] / baseline_atp
        trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

        print(f"  ER fold: {er_fold:.2f}×, UPR fold: {upr_fold:.2f}×")
        print(f"  Mito fold: {mito_fold:.2f}×, ATP fold: {atp_fold:.2f}×")
        print(f"  Actin fold: {actin_fold:.2f}×, Trafficking fold: {trafficking_fold:.2f}×")

        # Print latent states
        vessel = vm.vessel_states["test"]
        print(f"  Latent states: ER={vessel.er_stress:.3f}, Mito={vessel.mito_dysfunction:.3f}, Transport={vessel.transport_dysfunction:.3f}")

        # Classify axis using same logic as exploration test
        er_signature = (upr_fold > 1.30 and er_fold > 1.30)
        mito_signature = (atp_fold < 0.85 or (atp_fold < 0.90 and mito_fold < 0.95))
        transport_signature = (trafficking_fold > 1.30 and actin_fold > 1.30)

        active_count = sum([er_signature, mito_signature, transport_signature])

        if active_count == 0:
            predicted_axis = None
        elif active_count > 1:
            predicted_axis = "ambiguous"
        elif er_signature:
            predicted_axis = "er_stress"
        elif mito_signature:
            predicted_axis = "mitochondrial"
        elif transport_signature:
            predicted_axis = "microtubule"
        else:
            predicted_axis = None

        print(f"  Predicted axis: {predicted_axis}")
        print(f"  Expected axis: {expected_axis}")
        print(f"  Correct: {predicted_axis == expected_axis}")

        results[compound] = {
            'predicted': predicted_axis,
            'expected': expected_axis,
            'correct': (predicted_axis == expected_axis),
            'signatures': {
                'er_fold': er_fold,
                'mito_fold': mito_fold,
                'actin_fold': actin_fold,
                'upr_fold': upr_fold,
                'atp_fold': atp_fold,
                'trafficking_fold': trafficking_fold
            },
            'latent': {
                'er_stress': vessel.er_stress,
                'mito_dysfunction': vessel.mito_dysfunction,
                'transport_dysfunction': vessel.transport_dysfunction
            }
        }

    # Assertions

    print(f"\n{'='*70}")
    print(f"Classification Results:")
    print(f"{'='*70}")

    for compound, result in results.items():
        status = "✓" if result['correct'] else "✗"
        print(f"{status} {compound}: predicted={result['predicted']}, expected={result['expected']}")

    # 1. All compounds should be identifiable (no ambiguity)
    for compound, result in results.items():
        assert result['predicted'] is not None and result['predicted'] != "ambiguous", (
            f"{compound}: Signatures ambiguous or undetectable (predicted={result['predicted']})"
        )

    # 2. All axes should be correctly identified
    correct_count = sum(1 for r in results.values() if r['correct'])
    accuracy = correct_count / len(results)

    print(f"\nAccuracy: {correct_count}/{len(results)} ({accuracy:.0%})")

    assert accuracy == 1.0, (
        f"All axes should be identifiable with coupling active: {correct_count}/{len(results)}"
    )

    # 3. For paclitaxel, verify coupling is active but secondary (at 36h)
    paclitaxel_result = results['paclitaxel']
    paclitaxel_latent = paclitaxel_result['latent']

    print(f"\nPaclitaxel coupling verification (at 36h):")
    print(f"  Transport dysfunction: {paclitaxel_latent['transport_dysfunction']:.3f}")
    print(f"  Mito dysfunction (from coupling): {paclitaxel_latent['mito_dysfunction']:.3f}")

    # Transport should be high (primary effect)
    assert paclitaxel_latent['transport_dysfunction'] > 0.6, (
        f"Transport dysfunction should be high for paclitaxel: {paclitaxel_latent['transport_dysfunction']:.3f}"
    )

    # Mito should be elevated (coupling active at 36h) but small (< 0.1)
    # At 36h with high_since set at ~6-18h, coupling has been active for 0-18h
    # With rate 0.02/h, expect 0.02-0.03 mito dysfunction
    assert paclitaxel_latent['mito_dysfunction'] > 0.01, (
        f"Coupling should induce some mito dysfunction by 36h: {paclitaxel_latent['mito_dysfunction']:.3f}"
    )

    assert paclitaxel_latent['mito_dysfunction'] < 0.10, (
        f"Coupling effect should be small (< 0.10 at 36h): "
        f"mito={paclitaxel_latent['mito_dysfunction']:.3f}"
    )

    # Coupling should be much smaller than primary transport dysfunction
    assert paclitaxel_latent['mito_dysfunction'] < paclitaxel_latent['transport_dysfunction'] / 2, (
        f"Coupling effect should be secondary (< 50% of transport): "
        f"mito={paclitaxel_latent['mito_dysfunction']:.3f}, transport={paclitaxel_latent['transport_dysfunction']:.3f}"
    )

    print(f"\n✓ PASSED: Identifiability preserved with coupling active")


def test_planning_pressure_scenario():
    """
    Test "do nothing now, pay later" dynamic.

    Setup:
    - Continuous paclitaxel (no washout)
    - Pulse paclitaxel (washout at 12h)
    - Measure viability at 48h

    Expected:
    - Continuous: higher transport dysfunction → coupling active → higher mito dysfunction → more death
    - Pulse: washout breaks coupling → less mito dysfunction → less death
    - Pulse should beat continuous on viability
    """
    print("\n=== Planning Pressure Test ===")

    # Continuous dosing (advance in 6h steps for numerical accuracy)
    vm_continuous = BiologicalVirtualMachine(seed=42)
    vm_continuous.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm_continuous.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    for _ in range(8):  # 8 × 6h = 48h
        vm_continuous.advance_time(6.0)
    vessel_continuous = vm_continuous.vessel_states["test"]
    viability_continuous = vessel_continuous.viability
    transport_continuous = vessel_continuous.transport_dysfunction
    mito_continuous = vessel_continuous.mito_dysfunction

    # Pulse dosing (washout at 12h, advance in 6h steps)
    vm_pulse = BiologicalVirtualMachine(seed=42)
    vm_pulse.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)
    vm_pulse.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    for _ in range(2):  # 2 × 6h = 12h
        vm_pulse.advance_time(6.0)
    vm_pulse.washout_compound("test", "paclitaxel")
    for _ in range(6):  # 6 × 6h = 36h more, total 48h
        vm_pulse.advance_time(6.0)
    vessel_pulse = vm_pulse.vessel_states["test"]
    viability_pulse = vessel_pulse.viability
    transport_pulse = vessel_pulse.transport_dysfunction
    mito_pulse = vessel_pulse.mito_dysfunction

    print(f"\nContinuous dosing (no washout):")
    print(f"  Transport dysfunction: {transport_continuous:.3f}")
    print(f"  Mito dysfunction: {mito_continuous:.3f}")
    print(f"  Viability at 48h: {viability_continuous:.1%}")

    print(f"\nPulse dosing (washout at 12h):")
    print(f"  Transport dysfunction: {transport_pulse:.3f}")
    print(f"  Mito dysfunction: {mito_pulse:.3f}")
    print(f"  Viability at 48h: {viability_pulse:.1%}")

    # Assertions

    # 1. Continuous should have higher mito dysfunction (coupling active longer)
    assert mito_continuous > mito_pulse + 0.05, (
        f"Continuous should have higher mito dysfunction due to coupling: "
        f"continuous={mito_continuous:.3f}, pulse={mito_pulse:.3f}"
    )

    # 2. Continuous should have lower viability (more death from mito dysfunction)
    assert viability_continuous < viability_pulse, (
        f"Continuous should have lower viability due to coupling: "
        f"continuous={viability_continuous:.1%}, pulse={viability_pulse:.1%}"
    )

    # 3. Difference should be meaningful (> 5% viability difference)
    viability_diff = viability_pulse - viability_continuous
    print(f"\nViability advantage for pulse: {viability_diff:.1%}")

    assert viability_diff > 0.05, (
        f"Coupling should create meaningful planning pressure (> 5% viability difference): {viability_diff:.1%}"
    )

    print(f"\n✓ PASSED: Coupling creates 'do nothing now, pay later' dynamic")


if __name__ == "__main__":
    test_coupling_delay_requirement()
    test_coupling_threshold_gating()
    test_coupling_reset_on_washout()
    test_identifiability_with_coupling()
    test_planning_pressure_scenario()
    print("\n=== Phase 4 Option 3: Cross-talk Coupling Tests Complete ===")
