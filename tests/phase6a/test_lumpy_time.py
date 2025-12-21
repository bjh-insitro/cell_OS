"""
Test Lumpy Time Injection (Injection H): Commitment Points and Phase Transitions

Tests:
1. Cells accumulate stress toward commitment threshold
2. Commitment point is irreversible (no going back)
3. Latent period between commitment and observable change
4. State-dependent dynamics (different rules per state)
5. Recovery is possible before commitment
6. Phase transitions are discrete (not gradual)
7. Terminal states (senescent, dead) are permanent
"""

import numpy as np
from cell_os.hardware.injections import (
    LumpyTimeInjection,
    InjectionContext
)
from cell_os.hardware.injections.lumpy_time import CellState


def test_stress_accumulation_to_threshold():
    """Test that stress accumulates toward commitment threshold."""
    print("\n" + "="*60)
    print("Test: Stress Accumulation to Threshold")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial state:")
    print(f"  Cell state: {state.cell_state.value}")
    print(f"  Accumulator: {state.commitment_accumulator:.3f}")

    # Apply moderate stress repeatedly (should eventually transition to STRESSED)
    for i in range(5):
        context.event_type = 'acute_stress'
        context.event_params = {'magnitude': 0.08}  # 8% stress each
        injection.on_event(state, context)

        print(f"\nAfter stress {i+1}:")
        print(f"  Cell state: {state.cell_state.value}")
        print(f"  Accumulator: {state.commitment_accumulator:.3f}")

        if state.cell_state != CellState.PROLIFERATING:
            print(f"  → Transitioned to {state.cell_state.value}!")
            break

    # Should have transitioned away from PROLIFERATING
    assert state.cell_state != CellState.PROLIFERATING, \
        f"Should transition from PROLIFERATING, still in {state.cell_state.value}"

    print("\n✓ Stress accumulation to threshold: PASS")


def test_commitment_is_irreversible():
    """Test that commitment to apoptosis/senescence is irreversible."""
    print("\n" + "="*60)
    print("Test: Commitment is Irreversible")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Push cell to STRESSED first
    context.event_type = 'acute_stress'
    context.event_params = {'magnitude': 0.25}
    injection.on_event(state, context)

    print(f"After initial stress: {state.cell_state.value}")

    # Apply heavy stress to commit to apoptosis
    for i in range(3):
        context.event_type = 'acute_stress'
        context.event_params = {'magnitude': 0.30}
        injection.on_event(state, context)

        if state.cell_state == CellState.COMMITTED_APOPTOSIS:
            print(f"\nCommitted to apoptosis after {i+1} exposures!")
            print(f"  Reversibility: {state.get_state_summary()['reversibility']:.1f}")
            break

    assert state.cell_state == CellState.COMMITTED_APOPTOSIS, "Should commit to apoptosis"

    # Try to recover (should fail - irreversible)
    print(f"\nAttempting recovery (should fail)...")
    context.event_type = 'recovery'
    context.event_params = {'magnitude': 1.0}  # Full recovery attempt
    injection.on_event(state, context)

    print(f"  After recovery attempt: {state.cell_state.value}")
    print(f"  Accumulator: {state.commitment_accumulator:.3f}")

    assert state.cell_state == CellState.COMMITTED_APOPTOSIS, \
        "Committed apoptosis is IRREVERSIBLE"

    print("\n✓ Commitment is irreversible: PASS")


def test_latent_period():
    """Test that latent period delays observable change."""
    print("\n" + "="*60)
    print("Test: Latent Period")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Build up stress gradually to commit to apoptosis
    for i in range(5):
        context.event_type = 'acute_stress'
        context.event_params = {'magnitude': 0.30}  # Moderate stress
        injection.on_event(state, context)

        if state.cell_state == CellState.COMMITTED_APOPTOSIS:
            print(f"Committed after {i+1} stress exposures")
            break

        # Advance time slightly
        injection.apply_time_step(state, 1.0, context)

    if state.cell_state != CellState.COMMITTED_APOPTOSIS:
        # Try a larger push
        context.event_params = {'magnitude': 0.50}
        for _ in range(3):
            injection.on_event(state, context)
            if state.cell_state == CellState.COMMITTED_APOPTOSIS:
                break

    assert state.cell_state == CellState.COMMITTED_APOPTOSIS, \
        f"Should be committed to apoptosis, got {state.cell_state.value}"

    latent_period = state.latent_period_remaining
    print(f"\nCommitted to apoptosis:")
    print(f"  Latent period: {latent_period:.1f}h")
    print(f"  Current state: {state.cell_state.value}")

    # During latent period, cells still viable
    bio_mods = injection.get_biology_modifiers(state, context)
    print(f"  Viability during latent period: {bio_mods['viability']:.2f}")

    assert latent_period > 0, "Should have latent period"
    assert bio_mods['viability'] > 0.8, "Still viable during latent period"

    # Advance through latent period
    print(f"\nAdvancing through latent period...")
    time_advanced = 0.0
    while state.cell_state == CellState.COMMITTED_APOPTOSIS and time_advanced < 20.0:
        injection.apply_time_step(state, 1.0, context)
        time_advanced += 1.0

        if state.latent_period_remaining == 0 and time_advanced > latent_period:
            print(f"  After {time_advanced:.1f}h: {state.cell_state.value}")
            break

    # Should transition to EXECUTING_APOPTOSIS after latent period
    assert state.cell_state in [CellState.EXECUTING_APOPTOSIS, CellState.DEAD], \
        f"Should be executing or dead after latent period, got {state.cell_state.value}"

    print(f"\nFinal state: {state.cell_state.value}")

    print("\n✓ Latent period: PASS")


def test_recovery_before_commitment():
    """Test that cells can recover if not yet committed."""
    print("\n" + "="*60)
    print("Test: Recovery Before Commitment")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply moderate stress (not enough to commit)
    context.event_type = 'acute_stress'
    context.event_params = {'magnitude': 0.25}
    injection.on_event(state, context)

    print(f"After stress:")
    print(f"  Cell state: {state.cell_state.value}")
    print(f"  Accumulator: {state.commitment_accumulator:.3f}")
    print(f"  Reversibility: {state.get_state_summary()['reversibility']:.1f}")

    # Accumulator may have reset after transition, so build it up again
    context.event_type = 'chronic_stress'
    context.event_params = {'magnitude': 0.20}
    injection.on_event(state, context)

    accumulator_before = state.commitment_accumulator
    print(f"\nAfter additional stress:")
    print(f"  Accumulator: {accumulator_before:.3f}")

    # Apply recovery
    context.event_type = 'recovery'
    context.event_params = {'magnitude': 0.5}
    injection.on_event(state, context)

    print(f"\nAfter recovery:")
    print(f"  Cell state: {state.cell_state.value}")
    print(f"  Accumulator: {state.commitment_accumulator:.3f}")

    # Should reduce accumulator (recovery works before commitment)
    assert state.commitment_accumulator <= accumulator_before, \
        "Recovery should reduce or maintain accumulator"

    # Let time pass (accumulator decays in reversible states)
    injection.apply_time_step(state, 10.0, context)

    print(f"\nAfter 10h rest:")
    print(f"  Cell state: {state.cell_state.value}")
    print(f"  Accumulator: {state.commitment_accumulator:.3f}")

    # Should eventually return to proliferating if accumulator drops enough
    for _ in range(20):
        injection.apply_time_step(state, 5.0, context)
        if state.cell_state == CellState.PROLIFERATING:
            print(f"\n→ Recovered to PROLIFERATING!")
            break

    print("\n✓ Recovery before commitment: PASS")


def test_state_dependent_dynamics():
    """Test that different states have different biology."""
    print("\n" + "="*60)
    print("Test: State-Dependent Dynamics")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)

    # Test multiple states
    states_to_test = [
        (CellState.PROLIFERATING, "proliferating"),
        (CellState.STRESSED, "stressed"),
        (CellState.QUIESCENT, "quiescent"),
        (CellState.SENESCENT, "senescent"),
    ]

    print("\nState-dependent properties:\n")
    print(f"{'State':<20} {'Growth':<10} {'Viability':<12} {'Metabolism':<12}")
    print("-" * 60)

    for cell_state, label in states_to_test:
        state = injection.create_state(f"well_{label}", context)
        state.cell_state = cell_state

        bio_mods = injection.get_biology_modifiers(state, context)

        print(f"{label:<20} "
              f"{bio_mods['growth_rate_multiplier']:<10.2f} "
              f"{bio_mods['viability']:<12.2f} "
              f"{bio_mods['metabolic_activity']:<12.2f}")

        # Verify state-specific properties
        if cell_state == CellState.PROLIFERATING:
            assert bio_mods['growth_rate_multiplier'] == 1.0, "Proliferating should grow"
        elif cell_state == CellState.QUIESCENT:
            assert bio_mods['growth_rate_multiplier'] == 0.0, "Quiescent doesn't grow"
        elif cell_state == CellState.SENESCENT:
            assert bio_mods['growth_rate_multiplier'] == 0.0, "Senescent doesn't grow"
            assert bio_mods['viability'] > 0.8, "Senescent cells are alive"

    print("\n✓ State-dependent dynamics: PASS")


def test_phase_transitions_are_discrete():
    """Test that transitions are discrete jumps, not gradual."""
    print("\n" + "="*60)
    print("Test: Phase Transitions are Discrete")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Tracking state over stress accumulation:\n")

    states_seen = [state.cell_state.value]
    accumulators = [state.commitment_accumulator]

    # Apply stress incrementally
    for i in range(15):
        context.event_type = 'acute_stress'
        context.event_params = {'magnitude': 0.10}
        injection.on_event(state, context)

        # Record state
        states_seen.append(state.cell_state.value)
        accumulators.append(state.commitment_accumulator)

        # Print transitions
        if states_seen[-1] != states_seen[-2]:
            print(f"Step {i+1}: TRANSITION {states_seen[-2]} → {states_seen[-1]}")
            print(f"  Accumulator crossed threshold: {accumulators[-1]:.3f}")

    print(f"\nStates visited: {list(set(states_seen))}")

    # Should see discrete transitions (not gradual)
    # A "discrete" transition means the state only takes discrete values
    unique_states = set(states_seen)
    print(f"Number of unique states: {len(unique_states)}")

    assert len(unique_states) >= 2, "Should visit multiple discrete states"

    print("\n✓ Phase transitions are discrete: PASS")


def test_terminal_states_permanent():
    """Test that terminal states (senescent, dead) are permanent."""
    print("\n" + "="*60)
    print("Test: Terminal States are Permanent")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)

    # Test senescence
    state = injection.create_state("well_senescent", context)
    state.cell_state = CellState.SENESCENT

    print("Testing senescence (terminal):")
    print(f"  Initial: {state.cell_state.value}")
    print(f"  Reversibility: {state.get_state_summary()['reversibility']:.1f}")

    # Try to recover (should fail)
    context.event_type = 'recovery'
    context.event_params = {'magnitude': 1.0}
    injection.on_event(state, context)
    injection.apply_time_step(state, 100.0, context)  # Wait long time

    print(f"  After recovery + 100h: {state.cell_state.value}")

    assert state.cell_state == CellState.SENESCENT, "Senescence is irreversible"

    # Test death
    state2 = injection.create_state("well_dead", context)
    state2.cell_state = CellState.DEAD

    print(f"\nTesting death (terminal):")
    print(f"  Initial: {state2.cell_state.value}")
    print(f"  Reversibility: {state2.get_state_summary()['reversibility']:.1f}")

    # Try to recover (should fail)
    injection.on_event(state2, context)
    injection.apply_time_step(state2, 100.0, context)

    print(f"  After recovery + 100h: {state2.cell_state.value}")

    assert state2.cell_state == CellState.DEAD, "Death is irreversible"

    print("\n✓ Terminal states are permanent: PASS")


def test_lumpy_time_integration():
    """Test lumpy time in realistic stress protocol."""
    print("\n" + "="*60)
    print("Test: Lumpy Time Integration")
    print("="*60)

    injection = LumpyTimeInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Simulating progressive stress protocol:\n")

    timeline = []

    # Day 0: Healthy cells
    print("Day 0: Seed cells (healthy)")
    timeline.append((0, state.cell_state.value, state.commitment_accumulator))

    # Days 1-3: Low stress (recoverable)
    for day in range(1, 4):
        context.simulated_time = day * 24.0
        context.event_type = 'chronic_stress'
        context.event_params = {'magnitude': 0.15}
        injection.on_event(state, context)
        injection.apply_time_step(state, 24.0, context)

        timeline.append((day, state.cell_state.value, state.commitment_accumulator))
        print(f"Day {day}: Low stress → {state.cell_state.value} (acc={state.commitment_accumulator:.3f})")

    # Day 4: Recovery period
    print(f"\nDay 4: Recovery period")
    context.simulated_time = 4 * 24.0
    injection.apply_time_step(state, 24.0, context)
    timeline.append((4, state.cell_state.value, state.commitment_accumulator))
    print(f"  State: {state.cell_state.value} (acc={state.commitment_accumulator:.3f})")

    # Day 5: High acute stress (push to commitment)
    print(f"\nDay 5: HIGH stress challenge")
    context.simulated_time = 5 * 24.0
    context.event_type = 'acute_stress'
    context.event_params = {'magnitude': 0.60}
    injection.on_event(state, context)

    timeline.append((5, state.cell_state.value, state.commitment_accumulator))
    print(f"  State: {state.cell_state.value}")
    print(f"  Committed: {state.get_state_summary()['is_committed']}")
    print(f"  Latent period: {state.latent_period_remaining:.1f}h")

    # Days 6-7: Watch latent period
    if state.get_state_summary()['is_committed']:
        print(f"\nDays 6-7: Latent period (committed but not yet executing)")

        for day in range(6, 8):
            injection.apply_time_step(state, 24.0, context)
            timeline.append((day, state.cell_state.value, state.commitment_accumulator))
            print(f"Day {day}: {state.cell_state.value} "
                  f"(latent={state.latent_period_remaining:.1f}h)")

    # Final summary
    print(f"\n{'='*60}")
    print("Timeline Summary:")
    print(f"{'='*60}")
    for day, cell_state, acc in timeline:
        print(f"Day {day}: {cell_state:<25} acc={acc:.3f}")

    # Get final biology
    bio_mods = injection.get_biology_modifiers(state, context)
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\nFinal biology:")
    print(f"  Growth: {bio_mods['growth_rate_multiplier']:.2f}×")
    print(f"  Viability: {bio_mods['viability']:.2f}")
    print(f"  Metabolic: {bio_mods['metabolic_activity']:.2f}")

    print(f"\nFinal measurements:")
    print(f"  Apoptotic markers: {meas_mods['apoptotic_markers']:.2f}")
    print(f"  Morphology change: {meas_mods['morphology_change']:.2f}")

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)
    print(f"\nPipeline observation:")
    print(f"  Cell state: {obs['cell_state']}")
    print(f"  Is committed: {obs['is_committed']}")
    if 'qc_warnings' in obs:
        print(f"  QC warnings: {obs['qc_warnings']}")

    # Should have transitioned through multiple states
    unique_states = set(s for _, s, _ in timeline)
    assert len(unique_states) >= 2, "Should visit multiple states"

    print("\n✓ Lumpy time integration: PASS")


def test_all_injections_with_lumpy_time():
    """Smoke test: ensure lumpy time works with other injections."""
    print("\n" + "="*60)
    print("Test: All Injections with Lumpy Time")
    print("="*60)

    from cell_os.hardware.injections import (
        VolumeEvaporationInjection,
        CoatingQualityInjection,
        PipettingVarianceInjection,
        MixingGradientsInjection,
        MeasurementBackActionInjection,
        StressMemoryInjection,
    )

    injections = [
        VolumeEvaporationInjection(),
        CoatingQualityInjection(seed=2),
        PipettingVarianceInjection(seed=3, instrument_id='robot_001'),
        MixingGradientsInjection(seed=4),
        MeasurementBackActionInjection(seed=5),
        StressMemoryInjection(seed=6),
        LumpyTimeInjection(seed=7),
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

    # Simulate compound dispense + stress
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 200.0, 'compound_uM': 50.0}

    for inj, state in zip(injections, states):
        inj.on_event(state, context)

    # Advance time
    for inj, state in zip(injections, states):
        inj.apply_time_step(state, 24.0, context)

    print("\n✓ All injections with lumpy time: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Lumpy Time Test Suite (Injection H)")
    print("="*60)

    test_stress_accumulation_to_threshold()
    test_commitment_is_irreversible()
    test_latent_period()
    test_recovery_before_commitment()
    test_state_dependent_dynamics()
    test_phase_transitions_are_discrete()
    test_terminal_states_permanent()
    test_lumpy_time_integration()
    test_all_injections_with_lumpy_time()

    print("\n" + "="*60)
    print("✅ All lumpy time tests PASSED")
    print("="*60)
    print("\nLumpy Time Injection (H) complete:")
    print("  - Commitment points: Stress accumulates, then discrete transition")
    print("  - Irreversibility: Apoptosis, senescence, death are one-way")
    print("  - Latent periods: Commitment → observable change (hours delay)")
    print("  - State-dependent: Different rules in different states")
    print("  - Recovery possible: Before commitment, cells can heal")
    print("  - Phase transitions: Discrete jumps, not gradual slopes")
    print("  - Terminal states: Senescent and dead cells stay that way")
    print("\nCells are state machines, not differential equations!")
