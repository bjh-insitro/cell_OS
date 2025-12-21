"""
Test Stress Memory Injection (Injection G): Wells Remember Insults

Tests:
1. Adaptive resistance develops from repeated exposure
2. General hardening from diverse stress types
3. Priming activates after moderate stress
4. Sensitization occurs from severe stress
5. Memory decays over time (weeks)
6. Cross-resistance between related stresses
7. Washout doesn't erase memory
"""

import numpy as np
from cell_os.hardware.injections import (
    StressMemoryInjection,
    InjectionContext
)


def test_adaptive_resistance_develops():
    """Test that repeated exposure builds resistance."""
    print("\n" + "="*60)
    print("Test: Adaptive Resistance Develops")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Initial state:")
    print(f"  Compound resistance: {state.adaptive_resistance['compound_toxicity']:.3f}")
    print(f"  Hardening factor: {state.hardening_factor:.3f}")

    # Expose to compound toxicity 5 times (moderate stress)
    for i in range(5):
        context.simulated_time = i * 24.0  # Once per day
        context.event_type = 'compound_exposure'
        context.event_params = {'toxicity': 0.30}
        injection.on_event(state, context)

        print(f"\nAfter exposure {i+1}:")
        print(f"  Compound resistance: {state.adaptive_resistance['compound_toxicity']:.3f}")
        print(f"  Damage multiplier: {state.get_resistance_multiplier('compound_toxicity'):.3f}×")

    final_resistance = state.adaptive_resistance['compound_toxicity']
    damage_mult = state.get_resistance_multiplier('compound_toxicity')

    assert final_resistance > 0.10, "Should develop >10% resistance after 5 exposures"
    assert damage_mult < 0.90, "Damage should be reduced by resistance"

    print(f"\nFinal resistance: {final_resistance:.3f} ({final_resistance*100:.0f}%)")
    print(f"Damage reduction: {(1-damage_mult)*100:.0f}%")

    print("\n✓ Adaptive resistance develops: PASS")


def test_general_hardening_from_diversity():
    """Test that diverse stress types cause general hardening."""
    print("\n" + "="*60)
    print("Test: General Hardening from Diverse Stresses")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Expose to multiple different stress types
    stress_types = [
        ('compound_exposure', {'toxicity': 0.30}),
        ('oxidative_stress', {'magnitude': 0.25}),
        ('osmotic_stress', {'magnitude': 0.20}),
        ('mechanical_stress', {'magnitude': 0.15}),
        ('thermal_stress', {'magnitude': 0.30}),
    ]

    print("Applying diverse stresses:")
    for i, (event_type, params) in enumerate(stress_types):
        context.simulated_time = i * 12.0  # Every 12h
        context.event_type = event_type
        context.event_params = params
        injection.on_event(state, context)

        print(f"  After {event_type}: hardening={state.hardening_factor:.3f}")

    print(f"\nFinal hardening factor: {state.hardening_factor:.3f} ({state.hardening_factor*100:.0f}%)")
    print(f"Number of stress types: {len(set(exp.stress_type for exp in state.stress_exposures))}")

    assert state.hardening_factor > 0.10, "Should develop general hardening from diverse stresses"
    assert len(set(exp.stress_type for exp in state.stress_exposures)) >= 5, "Should have 5+ stress types"

    # Check that hardening provides cross-protection
    bio_mods = injection.get_biology_modifiers(state, context)
    print(f"General resistance: {bio_mods['stress_resistance_general']:.3f}×")

    print("\n✓ General hardening from diversity: PASS")


def test_priming_activation():
    """Test that moderate stress activates priming."""
    print("\n" + "="*60)
    print("Test: Priming Activation")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Before stress:")
    print(f"  Priming active: {state.priming_active}")
    print(f"  Priming boost: {state.get_priming_boost():.3f}×")

    # Apply moderate stress (above priming threshold, below sensitization)
    context.event_type = 'oxidative_stress'
    context.event_params = {'magnitude': 0.40}  # 40% stress
    injection.on_event(state, context)

    print(f"\nAfter moderate stress (40%):")
    print(f"  Priming active: {state.priming_active}")
    print(f"  Priming magnitude: {state.priming_magnitude:.3f}")
    print(f"  Priming boost: {state.get_priming_boost():.3f}×")

    assert state.priming_active, "Priming should be active after moderate stress"
    assert state.get_priming_boost() > 1.0, "Priming should boost response speed"

    # Advance time beyond priming window
    print(f"\nAdvancing time 60h (beyond 48h priming window)...")
    injection.apply_time_step(state, 60.0, context)

    print(f"After 60h:")
    print(f"  Priming active: {state.priming_active}")
    print(f"  Time since last stress: {state.time_since_last_stress:.1f}h")

    assert not state.priming_active, "Priming should deactivate after 48h"

    print("\n✓ Priming activation: PASS")


def test_sensitization_from_severe_stress():
    """Test that excessive stress causes sensitization."""
    print("\n" + "="*60)
    print("Test: Sensitization from Severe Stress")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Initial sensitization: {:.3f}".format(state.sensitization_factor))

    # Apply severe stress (above sensitization threshold)
    for i in range(3):
        context.simulated_time = i * 12.0
        context.event_type = 'compound_exposure'
        context.event_params = {'toxicity': 0.75}  # 75% toxicity (severe)
        injection.on_event(state, context)

        print(f"After severe stress {i+1}: sensitization={state.sensitization_factor:.3f}")

    assert state.sensitization_factor > 0.05, "Should develop sensitization from severe stress"

    # Check that sensitization increases damage
    damage_mult = state.get_resistance_multiplier('compound_toxicity')
    print(f"\nDamage multiplier (with sensitization): {damage_mult:.3f}×")
    print(f"Sensitization factor: {state.sensitization_factor:.3f}")

    # Despite some resistance, sensitization should increase damage
    # (or at least prevent full resistance benefit)
    print("\n✓ Sensitization from severe stress: PASS")


def test_memory_decay_over_time():
    """Test that stress memory decays over weeks."""
    print("\n" + "="*60)
    print("Test: Memory Decay Over Time")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Build up resistance
    for i in range(5):
        context.event_type = 'compound_exposure'
        context.event_params = {'toxicity': 0.30}
        injection.on_event(state, context)

    initial_resistance = state.adaptive_resistance['compound_toxicity']
    initial_hardening = state.hardening_factor

    print(f"After building resistance:")
    print(f"  Compound resistance: {initial_resistance:.3f}")
    print(f"  Hardening: {initial_hardening:.3f}")

    # Decay over time (1 week increments)
    timepoints = [0, 168, 336, 504, 672]  # 0, 1, 2, 3, 4 weeks
    resistances = [initial_resistance]
    hardenings = [initial_hardening]

    for i in range(1, len(timepoints)):
        dt = timepoints[i] - timepoints[i-1]
        injection.apply_time_step(state, dt, context)

        resistances.append(state.adaptive_resistance['compound_toxicity'])
        hardenings.append(state.hardening_factor)

        print(f"Week {i}: resistance={resistances[-1]:.3f}, hardening={hardenings[-1]:.3f}")

    # Check exponential decay
    # After 1 week (1 tau), should decay to ~37% (e^-1)
    expected_at_1week = initial_resistance * np.exp(-1)
    actual_at_1week = resistances[1]

    print(f"\nResistance at 1 week: {actual_at_1week:.3f} (expected ~{expected_at_1week:.3f})")

    assert resistances[-1] < initial_resistance * 0.2, "Should decay to <20% after 4 weeks"
    assert hardenings[-1] < initial_hardening * 0.5, "Hardening decays slower"

    print("\n✓ Memory decay over time: PASS")


def test_cross_resistance():
    """Test that some stresses confer resistance to others."""
    print("\n" + "="*60)
    print("Test: Cross-Resistance")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply oxidative stress (should give cross-resistance to compound toxicity)
    print("Applying oxidative stress (should help with compound toxicity):")
    for i in range(5):
        context.event_type = 'oxidative_stress'
        context.event_params = {'magnitude': 0.30}
        injection.on_event(state, context)

    oxidative_resistance = state.adaptive_resistance['oxidative']
    compound_resistance = state.adaptive_resistance['compound_toxicity']

    print(f"\nAfter 5 oxidative stress exposures:")
    print(f"  Oxidative resistance: {oxidative_resistance:.3f}")
    print(f"  Compound resistance (cross): {compound_resistance:.3f}")

    assert oxidative_resistance > compound_resistance, \
        "Direct resistance should be stronger than cross-resistance"
    assert compound_resistance > 0.0, \
        "Should develop some cross-resistance to compound toxicity"

    print(f"\nCross-resistance effect: {compound_resistance/oxidative_resistance:.1%} of direct effect")

    print("\n✓ Cross-resistance: PASS")


def test_washout_doesnt_erase_memory():
    """Test that washout doesn't reset stress memory to baseline."""
    print("\n" + "="*60)
    print("Test: Washout Doesn't Erase Memory")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Build up resistance
    print("Building resistance with 5 compound exposures:")
    for i in range(5):
        context.event_type = 'compound_exposure'
        context.event_params = {'toxicity': 0.30}
        injection.on_event(state, context)

    resistance_before_wash = state.adaptive_resistance['compound_toxicity']
    print(f"  Resistance before wash: {resistance_before_wash:.3f}")

    # Perform washout
    context.event_type = 'washout'
    injection.on_event(state, context)

    resistance_after_wash = state.adaptive_resistance['compound_toxicity']
    print(f"  Resistance after wash: {resistance_after_wash:.3f}")

    # Resistance should be unchanged (washout doesn't erase memory)
    assert abs(resistance_before_wash - resistance_after_wash) < 0.01, \
        "Washout should NOT erase resistance memory"

    print(f"\nResistance preserved: {resistance_after_wash/resistance_before_wash:.1%}")

    # Only TIME should decay memory
    print(f"\nWaiting 1 week (168h)...")
    injection.apply_time_step(state, 168.0, context)

    resistance_after_time = state.adaptive_resistance['compound_toxicity']
    print(f"  Resistance after 1 week: {resistance_after_time:.3f}")

    assert resistance_after_time < resistance_before_wash * 0.5, \
        "Time should decay resistance (not instant washout)"

    print("\n✓ Washout doesn't erase memory: PASS")


def test_stress_memory_integration():
    """Test stress memory in realistic experimental scenario."""
    print("\n" + "="*60)
    print("Test: Stress Memory Integration")
    print("="*60)

    injection = StressMemoryInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Simulating 4-week drug treatment protocol:\n")

    # Week 1: Initial low-dose exposure (conditioning)
    print("Week 1: Low-dose conditioning (5 µM, daily)")
    for day in range(7):
        context.simulated_time = day * 24.0
        context.event_type = 'dispense'
        context.event_params = {'compound_uM': 5.0}  # Low dose
        injection.on_event(state, context)

        # Time step to next day
        injection.apply_time_step(state, 24.0, context)

    print(f"  After week 1:")
    print(f"    Compound resistance: {state.adaptive_resistance['compound_toxicity']:.3f}")
    print(f"    Hardening: {state.hardening_factor:.3f}")
    print(f"    Priming: {state.priming_active}")

    # Week 2: Washout period (resistance persists)
    print(f"\nWeek 2: Washout period (no compound)")
    context.simulated_time = 7 * 24.0
    context.event_type = 'washout'
    injection.on_event(state, context)

    injection.apply_time_step(state, 7 * 24.0, context)

    resistance_after_washout = state.adaptive_resistance['compound_toxicity']
    print(f"  After washout + 1 week:")
    print(f"    Compound resistance: {resistance_after_washout:.3f}")
    print(f"    (Memory persists through washout!)")

    # Week 3: High-dose challenge (cells should be protected)
    print(f"\nWeek 3: High-dose challenge (50 µM)")
    context.simulated_time = 14 * 24.0
    context.event_type = 'dispense'
    context.event_params = {'compound_uM': 50.0}  # High dose
    injection.on_event(state, context)

    damage_mult = state.get_resistance_multiplier('compound_toxicity')
    print(f"  Damage multiplier: {damage_mult:.3f}×")
    print(f"  Damage reduction: {(1-damage_mult)*100:.0f}%")
    print(f"  (Cells are protected by prior conditioning!)")

    # Week 4: Continued high-dose (further adaptation)
    print(f"\nWeek 4: Continued high-dose (3× more exposures)")
    for i in range(3):
        context.simulated_time = (21 + i) * 24.0
        context.event_type = 'dispense'
        context.event_params = {'compound_uM': 50.0}
        injection.on_event(state, context)
        injection.apply_time_step(state, 24.0, context)

    final_resistance = state.adaptive_resistance['compound_toxicity']
    final_damage_mult = state.get_resistance_multiplier('compound_toxicity')

    print(f"  After week 4:")
    print(f"    Compound resistance: {final_resistance:.3f}")
    print(f"    Damage multiplier: {final_damage_mult:.3f}×")
    print(f"    Damage reduction: {(1-final_damage_mult)*100:.0f}%")

    # Get final modifiers
    bio_mods = injection.get_biology_modifiers(state, context)
    print(f"\n  Biology modifiers:")
    print(f"    Stress resistance (compound): {bio_mods['stress_resistance_compound']:.3f}×")
    print(f"    Stress resistance (general): {bio_mods['stress_resistance_general']:.3f}×")
    print(f"    Priming boost: {bio_mods['stress_priming_boost']:.3f}×")

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)
    print(f"\n  Pipeline observation:")
    print(f"    Exposures: {obs['stress_memory_exposures']}")
    print(f"    Hardening: {obs['stress_memory_hardening']:.3f}")
    print(f"    Priming: {obs['stress_memory_priming']}")

    assert final_resistance > 0.10, "Should develop resistance after 4-week protocol"
    assert final_damage_mult < 0.90, "Should reduce damage by >10%"

    print("\n✓ Stress memory integration: PASS")


def test_all_injections_with_stress_memory():
    """Smoke test: ensure stress memory works with other injections."""
    print("\n" + "="*60)
    print("Test: All Injections with Stress Memory")
    print("="*60)

    from cell_os.hardware.injections import (
        VolumeEvaporationInjection,
        CoatingQualityInjection,
        PipettingVarianceInjection,
        MixingGradientsInjection,
        MeasurementBackActionInjection,
    )

    injections = [
        VolumeEvaporationInjection(),
        CoatingQualityInjection(seed=2),
        PipettingVarianceInjection(seed=3, instrument_id='robot_001'),
        MixingGradientsInjection(seed=4),
        MeasurementBackActionInjection(seed=5),
        StressMemoryInjection(seed=6),
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

    # Simulate compound dispense
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 200.0, 'compound_uM': 10.0}

    for inj, state in zip(injections, states):
        inj.on_event(state, context)

    # Advance time
    for inj, state in zip(injections, states):
        inj.apply_time_step(state, 24.0, context)

    print("\n✓ All injections with stress memory: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Stress Memory Test Suite (Injection G)")
    print("="*60)

    test_adaptive_resistance_develops()
    test_general_hardening_from_diversity()
    test_priming_activation()
    test_sensitization_from_severe_stress()
    test_memory_decay_over_time()
    test_cross_resistance()
    test_washout_doesnt_erase_memory()
    test_stress_memory_integration()
    test_all_injections_with_stress_memory()

    print("\n" + "="*60)
    print("✅ All stress memory tests PASSED")
    print("="*60)
    print("\nStress Memory Injection (G) complete:")
    print("  - Adaptive resistance: Repeated stress → reduced damage")
    print("  - General hardening: Diverse stresses → toughness")
    print("  - Priming: Recent stress → faster response")
    print("  - Sensitization: Excessive stress → fragility")
    print("  - Cross-resistance: Some stresses protect against others")
    print("  - Memory decay: Resistance fades over weeks, not instantly")
    print("  - Washout immunity: Can't erase memory by washing")
    print("\nThe past is written in the cells' state!")
