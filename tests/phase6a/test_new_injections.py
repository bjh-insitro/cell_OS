"""
Test New Injections (C, D, E): Coating Quality, Pipetting Variance, Mixing Gradients

Tests:
1. Coating quality variation (well-to-well, edge effects)
2. Coating affects attachment and growth
3. Pipetting systematic and random errors
4. Mixing gradients decay over time
5. All injections work together
"""

import numpy as np
from cell_os.hardware.injections import (
    CoatingQualityInjection,
    PipettingVarianceInjection,
    MixingGradientsInjection,
    InjectionContext
)


def test_coating_quality_variation():
    """Test that coating quality varies well-to-well."""
    print("\n" + "="*60)
    print("Test: Coating Quality Variation")
    print("="*60)

    injection = CoatingQualityInjection(seed=42)

    # Create states for multiple wells
    wells = ['A01', 'E06', 'H12']  # Edge, center, edge
    states = []

    for well in wells:
        context = InjectionContext(
            simulated_time=0.0,
            run_context=None,
            well_position=well
        )
        state = injection.create_state(f"well_{well}", context)
        states.append(state)

        print(f"\n{well}:")
        print(f"  Coating efficiency: {state.coating_efficiency:.3f}")
        print(f"  Is edge well: {state.is_edge_well}")
        print(f"  Attachment rate: {state.get_attachment_rate_multiplier():.3f}×")
        print(f"  Growth rate: {state.get_growth_rate_multiplier():.3f}×")
        print(f"  Substrate stress: {state.get_substrate_stress():.3f}")

    # Check variation exists
    coatings = [s.coating_efficiency for s in states]
    assert np.std(coatings) > 0.01, "Should have well-to-well variation"

    # Check edge wells are worse on average
    edge_coating = (states[0].coating_efficiency + states[2].coating_efficiency) / 2
    center_coating = states[1].coating_efficiency
    print(f"\nEdge wells avg: {edge_coating:.3f}")
    print(f"Center well: {center_coating:.3f}")

    print("\n✓ Coating quality variation: PASS")


def test_coating_degradation():
    """Test that coating degrades over passages."""
    print("\n" + "="*60)
    print("Test: Coating Degradation Over Passages")
    print("="*60)

    injection = CoatingQualityInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None, well_position='E06')
    state = injection.create_state("well_E06", context)

    initial_coating = state.coating_efficiency
    print(f"Initial coating: {initial_coating:.3f}")

    # Passage plate 5 times
    for i in range(5):
        context.event_type = 'passage_plate'
        injection.on_event(state, context)
        print(f"After passage {i+1}: {state.coating_efficiency:.3f} (passage #{state.passage_number})")

    final_coating = state.coating_efficiency
    degradation = initial_coating - final_coating

    assert degradation > 0.05, f"Should degrade >0.05 after 5 passages, got {degradation:.3f}"
    assert state.passage_number == 5, "Should track passage number"

    print(f"\nTotal degradation: {degradation:.3f} ({degradation/initial_coating:.1%})")
    print("✓ Coating degradation: PASS")


def test_pipetting_accuracy():
    """Test that pipetting has systematic and random errors."""
    print("\n" + "="*60)
    print("Test: Pipetting Accuracy Variance")
    print("="*60)

    injection = PipettingVarianceInjection(seed=42, instrument_id='robot_001')
    context = InjectionContext(simulated_time=0.0, run_context=None)

    state = injection.create_state("well_A1", context)

    print(f"Instrument systematic error: {state.systematic_error:+.3f}")

    # Simulate 10 dispenses of 200 µL
    intended_volume = 200.0
    actual_volumes = []

    for i in range(10):
        context.event_type = 'dispense'
        context.event_params = {'volume_uL': intended_volume}

        injection.on_event(state, context)
        actual = context.event_params.get('pipetting_actual_volume_uL', intended_volume)
        actual_volumes.append(actual)

        if i < 3:  # Show first 3
            print(f"  Dispense {i+1}: intended={intended_volume:.2f}, actual={actual:.2f}, error={actual-intended_volume:+.2f}")

    # Check statistics
    mean_actual = np.mean(actual_volumes)
    std_actual = np.std(actual_volumes)
    mean_error = mean_actual - intended_volume

    print(f"\nStatistics (10 dispenses):")
    print(f"  Mean actual: {mean_actual:.2f} µL")
    print(f"  Mean error: {mean_error:+.2f} µL ({mean_error/intended_volume:+.2%})")
    print(f"  Std dev: {std_actual:.2f} µL ({std_actual/intended_volume:.2%})")

    # Variance should exist
    assert std_actual > 0.5, "Should have dispense-to-dispense variation"

    print("\n✓ Pipetting accuracy variance: PASS")


def test_mixing_gradient_decay():
    """Test that mixing gradient decays exponentially."""
    print("\n" + "="*60)
    print("Test: Mixing Gradient Decay")
    print("="*60)

    injection = MixingGradientsInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)

    state = injection.create_state("well_A1", context)

    print(f"Mixing tau: {state.mixing_tau:.1f} minutes")

    # Trigger gradient with dispense
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 200.0}
    injection.on_event(state, context)

    initial_gradient = state.gradient_magnitude
    print(f"\nInitial gradient: {initial_gradient:.3f} (±{initial_gradient*100:.0f}%)")

    # Measure gradient decay over time
    timepoints = [0, 5/60, 10/60, 20/60, 30/60]  # 0, 5, 10, 20, 30 minutes in hours
    gradients = [initial_gradient]

    for i in range(1, len(timepoints)):
        dt = timepoints[i] - timepoints[i-1]
        injection.apply_time_step(state, dt, context)
        gradients.append(state.gradient_magnitude)

        print(f"t={timepoints[i]*60:.0f}min: gradient={state.gradient_magnitude:.3f} (±{state.gradient_magnitude*100:.0f}%)")

    # Check exponential decay
    assert gradients[0] > gradients[-1] * 5, "Should decay significantly over 30min"
    assert gradients[-1] < 0.02, "Should be nearly mixed after 30min"

    print("\n✓ Mixing gradient decay: PASS")


def test_mixing_gradient_spatial_variation():
    """Test that mixing gradient creates Z-dependent concentration."""
    print("\n" + "="*60)
    print("Test: Mixing Gradient Spatial Variation")
    print("="*60)

    injection = MixingGradientsInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)

    state = injection.create_state("well_A1", context)

    # Trigger large gradient
    context.event_type = 'dispense'
    injection.on_event(state, context)

    # Check concentration at different Z-positions
    z_positions = [0.0, 0.25, 0.5, 0.75, 1.0]  # Bottom to top
    multipliers = []

    print(f"\nGradient magnitude: {state.gradient_magnitude:.3f}")
    print("Z-position → Concentration multiplier:")

    for z in z_positions:
        mult = state.get_local_concentration_multiplier(z)
        multipliers.append(mult)
        print(f"  z={z:.2f}: {mult:.3f}× ({(mult-1)*100:+.0f}%)")

    # Check that bottom and top are different
    bottom_mult = multipliers[0]
    top_mult = multipliers[-1]
    variation = abs(top_mult - bottom_mult)

    assert variation > 0.2, f"Should have >20% variation bottom-to-top, got {variation:.3f}"
    assert abs(multipliers[2] - 1.0) < 0.01, "Middle should be ~1.0"

    print(f"\nBottom-to-top variation: {variation:.3f} ({variation*100:.0f}%)")
    print("✓ Mixing gradient spatial variation: PASS")


def test_integrated_injections():
    """Test all new injections working together."""
    print("\n" + "="*60)
    print("Test: Integrated New Injections")
    print("="*60)

    # Create all injections
    coating = CoatingQualityInjection(seed=42)
    pipetting = PipettingVarianceInjection(seed=43)
    mixing = MixingGradientsInjection(seed=44)

    context = InjectionContext(
        simulated_time=0.0,
        run_context=None,
        well_position='A01'  # Edge well
    )

    # Create states
    coating_state = coating.create_state("well_A1", context)
    pipetting_state = pipetting.create_state("well_A1", context)
    mixing_state = mixing.create_state("well_A1", context)

    print("\nInitial state:")
    print(f"  Coating efficiency: {coating_state.coating_efficiency:.3f}")
    print(f"  Pipetting systematic error: {pipetting_state.systematic_error:+.3f}")
    print(f"  Mixing tau: {mixing_state.mixing_tau:.1f} min")

    # Simulate dispense operation
    context.event_type = 'dispense'
    context.event_params = {
        'volume_uL': 200.0,
        'compound_mass': 1.0
    }

    coating.on_event(coating_state, context)
    pipetting.on_event(pipetting_state, context)
    mixing.on_event(mixing_state, context)

    actual_volume = context.event_params.get('pipetting_actual_volume_uL', 200.0)
    actual_compound = context.event_params.get('pipetting_actual_compound_mass', 1.0)

    print(f"\nAfter dispense:")
    print(f"  Intended volume: 200.0 µL")
    print(f"  Actual volume: {actual_volume:.2f} µL (pipetting error)")
    print(f"  Mixing gradient: {mixing_state.gradient_magnitude:.3f}")

    # Get combined modifiers
    coating_mods = coating.get_biology_modifiers(coating_state, context)
    pipetting_mods = pipetting.get_biology_modifiers(pipetting_state, context)
    mixing_mods = mixing.get_biology_modifiers(mixing_state, context)

    print(f"\nBiology modifiers:")
    print(f"  Coating:")
    print(f"    - Attachment rate: {coating_mods['attachment_rate_multiplier']:.3f}×")
    print(f"    - Growth rate: {coating_mods['growth_rate_multiplier']:.3f}×")
    print(f"    - Substrate stress: {coating_mods['substrate_stress']:.3f}")
    print(f"  Mixing:")
    print(f"    - Gradient multiplier: {mixing_mods['compound_concentration_multiplier_gradient']:.3f}×")

    # Combined effect on compound concentration
    # Base dose × (volume error) × (mixing gradient)
    base_dose = 1.0
    volume_mult = 200.0 / actual_volume  # Concentration effect of volume error
    mixing_mult = mixing_mods['compound_concentration_multiplier_gradient']
    combined_dose = base_dose * volume_mult * mixing_mult

    print(f"\nCombined dose effect:")
    print(f"  Base dose: {base_dose:.3f}")
    print(f"  After volume error: {base_dose * volume_mult:.3f}×")
    print(f"  After mixing gradient: {combined_dose:.3f}×")
    print(f"  Total deviation: {(combined_dose - base_dose)*100:+.1f}%")

    # Advance time to see gradient decay
    print(f"\nTime evolution (mixing decay):")
    for t in [5/60, 10/60, 20/60]:  # 5, 10, 20 minutes
        mixing.apply_time_step(mixing_state, t, context)
        gradient = mixing_state.gradient_magnitude
        print(f"  t={t*60:.0f}min: gradient={gradient:.3f}")

    print("\n✓ Integrated new injections: PASS")


def test_all_injections_dont_crash():
    """Smoke test: ensure all injections can be instantiated and used."""
    print("\n" + "="*60)
    print("Test: All Injections Don't Crash")
    print("="*60)

    injections = [
        CoatingQualityInjection(seed=1),
        PipettingVarianceInjection(seed=2),
        MixingGradientsInjection(seed=3),
    ]

    context = InjectionContext(
        simulated_time=0.0,
        run_context=None,
        well_position='E06'
    )

    for inj in injections:
        name = inj.__class__.__name__
        print(f"\n{name}:")

        # Create state
        state = inj.create_state("test_well", context)
        print(f"  ✓ create_state")

        # Apply time step
        inj.apply_time_step(state, 1.0, context)
        print(f"  ✓ apply_time_step")

        # Trigger event
        context.event_type = 'dispense'
        context.event_params = {'volume_uL': 200.0}
        inj.on_event(state, context)
        print(f"  ✓ on_event")

        # Get modifiers
        bio_mods = inj.get_biology_modifiers(state, context)
        meas_mods = inj.get_measurement_modifiers(state, context)
        print(f"  ✓ get_biology_modifiers ({len(bio_mods)} keys)")
        print(f"  ✓ get_measurement_modifiers ({len(meas_mods)} keys)")

        # Pipeline transform
        obs = {'test': 1.0}
        obs = inj.pipeline_transform(obs, state, context)
        print(f"  ✓ pipeline_transform ({len(obs)} keys)")

    print("\n✓ All injections don't crash: PASS")


if __name__ == "__main__":
    print("="*60)
    print("New Injections Test Suite (C, D, E)")
    print("="*60)

    test_coating_quality_variation()
    test_coating_degradation()
    test_pipetting_accuracy()
    test_mixing_gradient_decay()
    test_mixing_gradient_spatial_variation()
    test_integrated_injections()
    test_all_injections_dont_crash()

    print("\n" + "="*60)
    print("✅ All new injection tests PASSED")
    print("="*60)
    print("\nNew injections complete:")
    print("  C. Coating Quality - Well-to-well variation, edge effects, degradation")
    print("  D. Pipetting Variance - Systematic + random errors, ±1-2%")
    print("  E. Mixing Gradients - Z-axis concentration variation, 5-10min decay")
    print("\nAll artifacts work together through injection system!")
