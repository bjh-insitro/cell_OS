"""
Test Measurement Back-Action Injection (Injection F)

Tests:
1. Imaging stress accumulation (photobleaching + phototoxicity)
2. Photobleaching is permanent signal loss
3. Handling stress from liquid operations
4. scRNA destructive sampling (cells removed)
5. Stress recovery over time (24h tau)
6. Wash trajectory reset (15% stress relief)
7. Integration with other injections
"""

import numpy as np
from cell_os.hardware.injections import (
    MeasurementBackActionInjection,
    InjectionContext
)


def test_imaging_stress_accumulation():
    """Test that imaging stress accumulates with each measurement."""
    print("\n" + "="*60)
    print("Test: Imaging Stress Accumulation")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial state:")
    print(f"  Imaging stress: {state.cumulative_imaging_stress:.3f}")
    print(f"  Photobleaching factor: {state.photobleaching_factor:.3f}")

    # Perform 5 imaging sessions
    for i in range(5):
        context.event_type = 'measure_imaging'
        injection.on_event(state, context)

        print(f"\nAfter imaging {i+1}:")
        print(f"  Imaging stress: {state.cumulative_imaging_stress:.3f}")
        print(f"  Photobleaching factor: {state.photobleaching_factor:.3f}")
        print(f"  Total stress: {state.get_total_measurement_stress():.3f}")

    # Check accumulation
    assert state.n_imaging_events == 5, "Should track 5 imaging events"
    assert state.cumulative_imaging_stress > 0.2, "Should accumulate >20% stress after 5 images"
    assert state.photobleaching_factor < 0.9, "Should have signal loss from photobleaching"

    # Get biology modifiers
    bio_mods = injection.get_biology_modifiers(state, context)
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\nBiology modifiers:")
    print(f"  Measurement stress: {bio_mods['measurement_stress']:.3f}")
    print(f"\nMeasurement modifiers:")
    print(f"  Photobleaching signal: {meas_mods['photobleaching_signal_multiplier']:.3f}×")
    print(f"  Noise multiplier: {meas_mods['measurement_noise_multiplier']:.3f}×")

    print("\n✓ Imaging stress accumulation: PASS")


def test_photobleaching_is_permanent():
    """Test that photobleaching doesn't recover (permanent signal loss)."""
    print("\n" + "="*60)
    print("Test: Photobleaching is Permanent")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply 3 imaging sessions
    for i in range(3):
        context.event_type = 'measure_imaging'
        injection.on_event(state, context)

    photobleach_after_imaging = state.photobleaching_factor
    print(f"Photobleaching after 3 images: {photobleach_after_imaging:.3f}")

    # Wait 48 hours (2× recovery tau)
    injection.apply_time_step(state, 48.0, context)

    photobleach_after_recovery = state.photobleaching_factor
    print(f"Photobleaching after 48h recovery: {photobleach_after_recovery:.3f}")

    # Photobleaching should NOT recover
    assert abs(photobleach_after_imaging - photobleach_after_recovery) < 0.001, \
        "Photobleaching should be permanent (no recovery)"

    # But imaging stress should recover
    print(f"Imaging stress after recovery: {state.cumulative_imaging_stress:.3f}")
    assert state.cumulative_imaging_stress < 0.05, "Imaging stress should recover"

    print("\n✓ Photobleaching is permanent: PASS")


def test_handling_stress_from_operations():
    """Test that liquid handling operations cause mechanical stress."""
    print("\n" + "="*60)
    print("Test: Handling Stress from Operations")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial handling stress: {state.cumulative_handling_stress:.3f}")

    # Perform liquid handling operations
    operations = [
        ('aspirate', 'Remove 100 µL'),
        ('dispense', 'Add 200 µL compound'),
        ('aspirate', 'Remove 150 µL'),
        ('dispense', 'Add 100 µL media'),
    ]

    for op_type, description in operations:
        context.event_type = op_type
        injection.on_event(state, context)
        print(f"After {description}: stress={state.cumulative_handling_stress:.3f}")

    assert state.n_handling_events == 4, "Should track 4 handling events"
    assert state.cumulative_handling_stress > 0.05, "Should accumulate handling stress"

    print(f"\nTotal handling stress: {state.cumulative_handling_stress:.3f}")
    print(f"Total measurement stress: {state.get_total_measurement_stress():.3f}")

    print("\n✓ Handling stress from operations: PASS")


def test_scrna_destructive_sampling():
    """Test that scRNA removes cells from population (destructive)."""
    print("\n" + "="*60)
    print("Test: scRNA Destructive Sampling")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial cells removed: {state.cells_removed_fraction:.5f}")

    # Perform scRNA sampling (1000 cells from 1M population)
    population_size = 1e6
    n_cells_sampled = 1000

    context.event_type = 'measure_scrna'
    context.event_params = {
        'n_cells': n_cells_sampled,
        'population_size': population_size
    }
    injection.on_event(state, context)

    print(f"After scRNA (1000 cells from 1M):")
    print(f"  Cells removed fraction: {state.cells_removed_fraction:.5f}")
    print(f"  Population remaining: {state.get_population_fraction_remaining():.5f}")
    print(f"  N samples: {state.n_scrna_samples}")

    expected_fraction = n_cells_sampled / population_size
    assert abs(state.cells_removed_fraction - expected_fraction) < 1e-6, \
        f"Should remove {expected_fraction:.5f} fraction"

    # Perform 3 more scRNA samples
    for i in range(3):
        injection.on_event(state, context)

    print(f"\nAfter 4 total scRNA samples:")
    print(f"  Cells removed fraction: {state.cells_removed_fraction:.5f}")
    print(f"  Population remaining: {state.get_population_fraction_remaining():.5f}")

    assert state.n_scrna_samples == 4, "Should track 4 scRNA samples"
    assert state.cells_removed_fraction > 0.003, "Should have removed >0.3% after 4 samples"

    # Get biology modifiers
    bio_mods = injection.get_biology_modifiers(state, context)
    print(f"  Population multiplier: {bio_mods['population_multiplier']:.5f}×")

    print("\n✓ scRNA destructive sampling: PASS")


def test_stress_recovery_over_time():
    """Test that measurement stress recovers with 24h time constant."""
    print("\n" + "="*60)
    print("Test: Stress Recovery Over Time")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply heavy imaging stress
    for i in range(5):
        context.event_type = 'measure_imaging'
        injection.on_event(state, context)

    initial_stress = state.cumulative_imaging_stress
    print(f"Initial imaging stress (after 5 images): {initial_stress:.3f}")

    # Track recovery over time
    timepoints = [0, 6, 12, 24, 48, 72]  # Hours
    stresses = [initial_stress]

    for i in range(1, len(timepoints)):
        dt = timepoints[i] - timepoints[i-1]
        injection.apply_time_step(state, dt, context)
        stresses.append(state.cumulative_imaging_stress)
        print(f"t={timepoints[i]:2d}h: stress={state.cumulative_imaging_stress:.3f}")

    # Check exponential decay
    # After 24h (1 tau), should decay to ~37% (e^-1)
    stress_at_24h = stresses[3]
    expected_at_24h = initial_stress * np.exp(-1)

    print(f"\nStress at 24h: {stress_at_24h:.3f} (expected ~{expected_at_24h:.3f})")
    assert abs(stress_at_24h - expected_at_24h) < 0.05, \
        "Should follow exponential decay with 24h tau"

    # After 72h (3 tau), should be nearly recovered
    assert stresses[-1] < initial_stress * 0.1, "Should be <10% after 72h"

    print("\n✓ Stress recovery over time: PASS")


def test_wash_trajectory_reset():
    """Test that wash operations provide partial stress relief."""
    print("\n" + "="*60)
    print("Test: Wash Trajectory Reset")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Build up handling stress
    for i in range(10):
        context.event_type = 'dispense'
        injection.on_event(state, context)

    stress_before_wash = state.cumulative_handling_stress
    print(f"Handling stress before wash: {stress_before_wash:.3f}")

    # Perform wash (feed operation)
    context.event_type = 'feed'
    injection.on_event(state, context)

    stress_after_wash = state.cumulative_handling_stress
    stress_relief = stress_before_wash - stress_after_wash

    print(f"Handling stress after wash: {stress_after_wash:.3f}")
    print(f"Stress relief: {stress_relief:.3f} ({stress_relief/stress_before_wash:.1%})")

    # Should provide ~15% relief
    expected_relief = stress_before_wash * 0.15
    assert abs(stress_relief - expected_relief) < 0.02, \
        f"Should provide ~15% relief, got {stress_relief/stress_before_wash:.1%}"

    assert state.n_wash_events == 1, "Should track wash event"
    assert state.time_since_last_wash < 0.01, "Should reset wash timer"

    # Perform aggressive washout (should provide more relief)
    for i in range(5):
        context.event_type = 'dispense'
        injection.on_event(state, context)

    stress_before_washout = state.cumulative_handling_stress
    print(f"\nHandling stress before washout: {stress_before_washout:.3f}")

    context.event_type = 'washout'
    injection.on_event(state, context)

    stress_after_washout = state.cumulative_handling_stress
    washout_relief = stress_before_washout - stress_after_washout

    print(f"Handling stress after washout: {stress_after_washout:.3f}")
    print(f"Washout relief: {washout_relief:.3f} ({washout_relief/stress_before_washout:.1%})")

    assert state.n_wash_events == 2, "Should track 2 wash events"

    print("\n✓ Wash trajectory reset: PASS")


def test_measurement_backaction_integration():
    """Test measurement back-action with realistic experimental protocol."""
    print("\n" + "="*60)
    print("Test: Measurement Back-Action Integration")
    print("="*60)

    injection = MeasurementBackActionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Simulating 7-day drug screen protocol:\n")

    # Day 0: Seed cells
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 100.0}
    injection.on_event(state, context)
    print(f"Day 0: Seed cells")
    print(f"  Handling stress: {state.cumulative_handling_stress:.3f}")

    # Wait 24h for attachment
    injection.apply_time_step(state, 24.0, context)

    # Day 1: Add compound, image
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 100.0}
    injection.on_event(state, context)

    context.event_type = 'measure_imaging'
    injection.on_event(state, context)

    print(f"\nDay 1: Add compound + image")
    print(f"  Imaging stress: {state.cumulative_imaging_stress:.3f}")
    print(f"  Photobleaching: {state.photobleaching_factor:.3f}×")
    print(f"  Total stress: {state.get_total_measurement_stress():.3f}")

    # Days 2-6: Daily imaging
    for day in range(2, 7):
        injection.apply_time_step(state, 24.0, context)

        context.event_type = 'measure_imaging'
        injection.on_event(state, context)

        print(f"\nDay {day}: Image")
        print(f"  Imaging stress: {state.cumulative_imaging_stress:.3f}")
        print(f"  Photobleaching: {state.photobleaching_factor:.3f}×")
        print(f"  Total stress: {state.get_total_measurement_stress():.3f}")

    # Day 7: Final scRNA sampling
    injection.apply_time_step(state, 24.0, context)

    context.event_type = 'measure_scrna'
    context.event_params = {'n_cells': 1000, 'population_size': 1e6}
    injection.on_event(state, context)

    print(f"\nDay 7: scRNA sampling")
    print(f"  Cells removed: {state.cells_removed_fraction:.5f}")
    print(f"  Population remaining: {state.get_population_fraction_remaining():.5f}")

    # Final report
    print(f"\n{'='*60}")
    print("Final Protocol Impact:")
    print(f"{'='*60}")
    print(f"Total imaging events: {state.n_imaging_events}")
    print(f"Total handling events: {state.n_handling_events}")
    print(f"Total scRNA samples: {state.n_scrna_samples}")
    print(f"\nCumulative imaging stress: {state.cumulative_imaging_stress:.3f}")
    print(f"Cumulative handling stress: {state.cumulative_handling_stress:.3f}")
    print(f"Total measurement stress: {state.get_total_measurement_stress():.3f}")
    print(f"Photobleaching signal loss: {(1-state.photobleaching_factor)*100:.1f}%")
    print(f"Population loss from scRNA: {state.cells_removed_fraction*100:.3f}%")

    # Get final modifiers
    bio_mods = injection.get_biology_modifiers(state, context)
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\nFinal biology modifiers:")
    print(f"  Measurement stress: {bio_mods['measurement_stress']:.3f} (up to 30%)")
    print(f"  Population multiplier: {bio_mods['population_multiplier']:.5f}×")

    print(f"\nFinal measurement modifiers:")
    print(f"  Photobleaching signal: {meas_mods['photobleaching_signal_multiplier']:.3f}×")
    print(f"  Noise multiplier: {meas_mods['measurement_noise_multiplier']:.3f}×")

    # Validate reasonable ranges
    assert 0.0 <= state.get_total_measurement_stress() <= 1.0, "Total stress in range"
    assert 0.5 <= state.photobleaching_factor <= 1.0, "Photobleaching in range"
    assert 0.999 <= state.get_population_fraction_remaining() <= 1.0, "Population loss in range"

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)

    print(f"\nPipeline observation keys: {len(obs)}")
    if 'qc_warnings' in obs:
        print(f"QC warnings: {obs['qc_warnings']}")

    print("\n✓ Measurement back-action integration: PASS")


def test_all_injections_with_backaction():
    """Smoke test: ensure measurement back-action works with other injections."""
    print("\n" + "="*60)
    print("Test: All Injections with Back-Action")
    print("="*60)

    # This is a smoke test - just verify no crashes
    from cell_os.hardware.injections import (
        VolumeEvaporationInjection,
        CoatingQualityInjection,
        PipettingVarianceInjection,
        MixingGradientsInjection,
    )

    injections = [
        VolumeEvaporationInjection(),
        CoatingQualityInjection(seed=2),
        PipettingVarianceInjection(seed=3, instrument_id='robot_001'),
        MixingGradientsInjection(seed=4),
        MeasurementBackActionInjection(seed=5),
    ]

    context = InjectionContext(
        simulated_time=0.0,
        run_context=None,
        well_position='E06'
    )

    states = []
    for inj in injections:
        name = inj.__class__.__name__
        state = inj.create_state("test_well", context)
        states.append(state)
        print(f"  ✓ {name}")

    # Simulate compound dispense + imaging
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 200.0}

    for inj, state in zip(injections, states):
        inj.on_event(state, context)

    context.event_type = 'measure_imaging'
    for inj, state in zip(injections, states):
        inj.on_event(state, context)

    # Advance time
    for inj, state in zip(injections, states):
        inj.apply_time_step(state, 12.0, context)

    print("\n✓ All injections with back-action: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Measurement Back-Action Test Suite (Injection F)")
    print("="*60)

    test_imaging_stress_accumulation()
    test_photobleaching_is_permanent()
    test_handling_stress_from_operations()
    test_scrna_destructive_sampling()
    test_stress_recovery_over_time()
    test_wash_trajectory_reset()
    test_measurement_backaction_integration()
    test_all_injections_with_backaction()

    print("\n" + "="*60)
    print("✅ All measurement back-action tests PASSED")
    print("="*60)
    print("\nMeasurement Back-Action Injection (F) complete:")
    print("  - Imaging causes photobleaching (3% per session) + phototoxicity (5% stress)")
    print("  - Liquid handling causes mechanical stress (2% per operation)")
    print("  - scRNA is destructive (removes 0.1% of population per sample)")
    print("  - Wash operations provide partial stress relief (15% reset)")
    print("  - Stress recovers slowly (24h time constant)")
    print("  - Photobleaching is permanent (no recovery)")
    print("\nEvery observation changes the system!")
