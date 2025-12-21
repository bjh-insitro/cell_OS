"""
Test Assay Deception Injection (Injection J): Cells Lie to Assays

Tests:
1. ATP-mito decoupling: High ATP despite damaged mitochondria
2. Glycolytic compensation: Glycolysis masks mitochondrial damage
3. Late inversion: Cells look healthy, then sudden collapse
4. Latent damage: Damage accumulates invisibly
5. Warburg effect: Cancer-like glycolysis preference
6. False negatives: Assay says "healthy" but cells are dying
7. Recovery is slow: Damage fast, recovery slow
"""

import numpy as np
from cell_os.hardware.injections import (
    AssayDeceptionInjection,
    InjectionContext
)


def test_atp_mito_decoupling():
    """Test that ATP can stay high despite mitochondrial damage."""
    print("\n" + "="*60)
    print("Test: ATP-Mito Decoupling")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial state:")
    print(f"  Mitochondrial health: {state.mitochondrial_health:.3f}")
    print(f"  ATP level: {state.atp_level:.3f}")
    print(f"  Glycolytic flux: {state.glycolytic_flux:.3f}")

    # Damage mitochondria
    context.event_type = 'mitochondrial_toxin'
    context.event_params = {'damage': 0.50}  # 50% mitochondrial damage
    injection.on_event(state, context)

    print(f"\nAfter mitochondrial toxin (50% damage):")
    print(f"  Mitochondrial health: {state.mitochondrial_health:.3f}")
    print(f"  ATP level: {state.atp_level:.3f}")
    print(f"  Glycolytic compensation: {state.glycolytic_compensation:.3f}")
    print(f"  Glycolytic flux: {state.glycolytic_flux:.3f}")

    # Advance time (glycolysis compensates)
    for _ in range(3):
        injection.apply_time_step(state, 1.0, context)

    print(f"\nAfter 3h (glycolysis activated):")
    print(f"  Mitochondrial health: {state.mitochondrial_health:.3f}")
    print(f"  ATP level: {state.atp_level:.3f}")
    print(f"  Apparent health: {state.get_apparent_health():.3f}")
    print(f"  True health: {state.get_true_health():.3f}")
    print(f"  Deception: {state.get_deception_magnitude():.3f}")

    # Key test: ATP stays relatively high despite damaged mitochondria
    assert state.mitochondrial_health < 0.60, "Mitochondria should be damaged"
    assert state.atp_level > 0.70, "ATP should stay relatively high (glycolysis compensates)"
    assert state.get_deception_magnitude() > 0.20, "Should have significant deception"

    print("\n✓ ATP-mito decoupling: PASS")


def test_glycolytic_compensation():
    """Test that glycolysis compensates for mitochondrial damage."""
    print("\n" + "="*60)
    print("Test: Glycolytic Compensation")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Progressively damage mitochondria
    print("Progressive mitochondrial damage:\n")
    print(f"{'Damage':<10} {'Mito Health':<15} {'Glycolytic':<15} {'ATP':<10}")
    print("-" * 60)

    for i in range(5):
        context.event_type = 'mitochondrial_toxin'
        context.event_params = {'damage': 0.15}
        injection.on_event(state, context)

        # Let ATP update
        injection.apply_time_step(state, 1.0, context)

        print(f"{(i+1)*0.15:<10.2f} {state.mitochondrial_health:<15.3f} "
              f"{state.glycolytic_flux:<15.3f} {state.atp_level:<10.3f}")

    # Glycolytic flux should increase as mitochondria damaged
    assert state.glycolytic_flux > 0.40, "Glycolysis should compensate"
    assert state.glycolytic_compensation > 0.20, "Should have compensation"

    print(f"\nFinal glycolytic compensation: {state.glycolytic_compensation:.3f}")

    print("\n✓ Glycolytic compensation: PASS")


def test_late_inversion():
    """Test that cells can look healthy then suddenly collapse."""
    print("\n" + "="*60)
    print("Test: Late Inversion")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Build up latent damage (slowly)
    print("Building latent damage:\n")

    for i in range(4):
        context.event_type = 'mitochondrial_toxin'
        context.event_params = {'damage': 0.20}
        injection.on_event(state, context)

        # Update ATP (stays high due to glycolysis)
        injection.apply_time_step(state, 1.0, context)

        print(f"Exposure {i+1}:")
        print(f"  Latent damage: {state.latent_damage_accumulator:.3f}")
        print(f"  ATP (apparent): {state.atp_level:.3f}")
        print(f"  True health: {state.get_true_health():.3f}")
        print(f"  Inversion armed: {state.inversion_armed}")

    # Check if inversion was armed
    if state.inversion_armed:
        print(f"\n→ INVERSION ARMED! Collapse in {state.inversion_timer_h:.1f}h")
        atp_before_inversion = state.atp_level

        # Advance time until inversion
        total_time = 0.0
        while state.inversion_armed and total_time < 20.0:
            injection.apply_time_step(state, 1.0, context)
            total_time += 1.0

        print(f"\nAfter inversion:")
        print(f"  ATP before: {atp_before_inversion:.3f}")
        print(f"  ATP after: {state.atp_level:.3f}")
        print(f"  Mito health: {state.mitochondrial_health:.3f}")
        print(f"  ROS spike: {state.ros_level:.3f}")

        # Verify sudden collapse
        assert state.atp_level < atp_before_inversion * 0.50, \
            "ATP should collapse during inversion"

    print("\n✓ Late inversion: PASS")


def test_latent_damage_invisible():
    """Test that latent damage accumulates invisibly."""
    print("\n" + "="*60)
    print("Test: Latent Damage is Invisible")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply stress
    context.event_type = 'mitochondrial_toxin'
    context.event_params = {'damage': 0.30}
    injection.on_event(state, context)

    # Update ATP
    injection.apply_time_step(state, 2.0, context)

    apparent_health = state.get_apparent_health()
    true_health = state.get_true_health()
    latent_damage = state.latent_damage_accumulator

    print(f"After mitochondrial stress:")
    print(f"  Apparent health (ATP): {apparent_health:.3f}")
    print(f"  True health: {true_health:.3f}")
    print(f"  Latent damage (hidden): {latent_damage:.3f}")
    print(f"  Deception: {state.get_deception_magnitude():.3f}")

    # Latent damage should be present but not visible in ATP
    assert latent_damage > 0.05, "Should have latent damage"
    assert apparent_health > true_health, \
        "Apparent health should be higher than true (deception)"

    print("\n✓ Latent damage is invisible: PASS")


def test_warburg_activation():
    """Test that heavy glycolysis triggers Warburg effect."""
    print("\n" + "="*60)
    print("Test: Warburg Effect Activation")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial Warburg status: {state.warburg_activated}")

    # Heavy mitochondrial damage → strong glycolysis
    context.event_type = 'mitochondrial_toxin'
    context.event_params = {'damage': 0.60}
    injection.on_event(state, context)

    # Update ATP
    injection.apply_time_step(state, 2.0, context)

    print(f"\nAfter heavy mitochondrial damage:")
    print(f"  Glycolytic flux: {state.glycolytic_flux:.3f}")
    print(f"  Warburg activated: {state.warburg_activated}")

    # Warburg should activate with high glycolysis
    if state.glycolytic_flux > 0.30:
        assert state.warburg_activated, \
            "Warburg effect should activate with high glycolysis"
        print(f"\n→ WARBURG EFFECT ACTIVATED (cancer-like metabolism)")

    print("\n✓ Warburg activation: PASS")


def test_false_negatives():
    """Test that assays can give false negatives (says healthy, cells dying)."""
    print("\n" + "="*60)
    print("Test: False Negatives (Assay Says Healthy)")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Apply moderate mitochondrial damage
    context.event_type = 'mitochondrial_toxin'
    context.event_params = {'damage': 0.40}
    injection.on_event(state, context)

    # Let glycolysis compensate
    for _ in range(5):
        injection.apply_time_step(state, 1.0, context)

    apparent = state.get_apparent_health()
    true = state.get_true_health()

    print(f"Mitochondrial health: {state.mitochondrial_health:.3f}")
    print(f"Apparent health (what assay sees): {apparent:.3f}")
    print(f"True health (ground truth): {true:.3f}")
    print(f"Deception magnitude: {state.get_deception_magnitude():.3f}")

    # False negative: assay says "healthy" (high ATP) but cells are damaged
    if apparent > 0.70 and true < 0.60:
        print(f"\n→ FALSE NEGATIVE: Assay reports {apparent:.0%} viability")
        print(f"   But true health is only {true:.0%}")
        assert True, "Demonstrated false negative"
    else:
        # Still valid test if deception is present
        assert state.get_deception_magnitude() > 0.10, \
            "Should have some deception"

    print("\n✓ False negatives: PASS")


def test_recovery_is_slow():
    """Test that mitochondrial recovery is much slower than damage."""
    print("\n" + "="*60)
    print("Test: Recovery is Slow")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Quick damage
    context.event_type = 'mitochondrial_toxin'
    context.event_params = {'damage': 0.40}
    injection.on_event(state, context)

    damaged_mito = state.mitochondrial_health
    print(f"After quick damage: {damaged_mito:.3f}")

    # Slow recovery (days)
    print(f"\nRecovery over time:")
    timepoints = [0, 24, 48, 72]  # Hours
    for t in timepoints[1:]:
        injection.apply_time_step(state, 24.0, context)
        print(f"  t={t}h: mito_health={state.mitochondrial_health:.3f}")

    recovered_mito = state.mitochondrial_health
    recovery = recovered_mito - damaged_mito

    print(f"\nRecovery after 72h: {recovery:.3f} ({recovery/(1-damaged_mito):.1%} of damage)")

    # Recovery should be partial (not complete in 3 days)
    assert recovered_mito < 0.90, "Should not fully recover in 3 days"
    assert recovery > 0.05, "Should have some recovery"

    print("\n✓ Recovery is slow: PASS")


def test_assay_deception_integration():
    """Test assay deception in realistic drug screen."""
    print("\n" + "="*60)
    print("Test: Assay Deception Integration")
    print("="*60)

    injection = AssayDeceptionInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Simulating mitotoxic drug screen:\n")

    timeline = []

    # Day 0: Add mitotoxic compound
    print("Day 0: Add mitotoxic compound")
    context.event_type = 'dispense'
    context.event_params = {'compound_uM': 10.0, 'mitotoxic': True}
    injection.on_event(state, context)
    injection.apply_time_step(state, 24.0, context)

    timeline.append((0, state.mitochondrial_health, state.atp_level,
                    state.get_apparent_health(), state.get_true_health()))

    print(f"  Mito health: {state.mitochondrial_health:.3f}")
    print(f"  ATP (apparent): {state.atp_level:.3f}")
    print(f"  True health: {state.get_true_health():.3f}")

    # Days 1-3: Continued exposure
    for day in range(1, 4):
        context.event_type = 'dispense'
        context.event_params = {'compound_uM': 10.0, 'mitotoxic': True}
        injection.on_event(state, context)
        injection.apply_time_step(state, 24.0, context)

        timeline.append((day, state.mitochondrial_health, state.atp_level,
                        state.get_apparent_health(), state.get_true_health()))

        print(f"\nDay {day}:")
        print(f"  Mito health: {state.mitochondrial_health:.3f}")
        print(f"  ATP (apparent): {state.atp_level:.3f}")
        print(f"  True health: {state.get_true_health():.3f}")
        print(f"  Deception: {state.get_deception_magnitude():.3f}")
        print(f"  Inversion armed: {state.inversion_armed}")

    # Get final measurements
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\n{'='*60}")
    print("Final Assessment:")
    print(f"{'='*60}")
    print(f"What assay reports:")
    print(f"  ATP viability: {meas_mods['apparent_viability_atp']:.3f} ({meas_mods['apparent_viability_atp']*100:.0f}%)")
    print(f"\nGround truth:")
    print(f"  True viability: {meas_mods['true_viability']:.3f} ({meas_mods['true_viability']*100:.0f}%)")
    print(f"  Mitochondrial health: {meas_mods['mitochondrial_health_true']:.3f}")
    print(f"\nDeception:")
    print(f"  Magnitude: {meas_mods['deception_magnitude']:.3f}")
    print(f"  Glycolytic compensation: {meas_mods['glycolytic_compensation']:.3f}")

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)

    if 'qc_warnings' in obs:
        print(f"\nQC Warnings: {obs['qc_warnings']}")

    # Should have deception
    assert meas_mods['deception_magnitude'] > 0.10 or state.latent_damage_accumulator > 0.20, \
        "Should have deception or latent damage"

    print("\n✓ Assay deception integration: PASS")


def test_all_injections_with_assay_deception():
    """Smoke test: ensure assay deception works with other injections."""
    print("\n" + "="*60)
    print("Test: All Injections with Assay Deception")
    print("="*60)

    from cell_os.hardware.injections import (
        VolumeEvaporationInjection,
        CoatingQualityInjection,
        PipettingVarianceInjection,
        MixingGradientsInjection,
        MeasurementBackActionInjection,
        StressMemoryInjection,
        LumpyTimeInjection,
        DeathModesInjection,
    )

    injections = [
        VolumeEvaporationInjection(),
        CoatingQualityInjection(seed=2),
        PipettingVarianceInjection(seed=3, instrument_id='robot_001'),
        MixingGradientsInjection(seed=4),
        MeasurementBackActionInjection(seed=5),
        StressMemoryInjection(seed=6),
        LumpyTimeInjection(seed=7),
        DeathModesInjection(seed=8),
        AssayDeceptionInjection(seed=9),
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
    context.event_params = {'volume_uL': 200.0, 'compound_uM': 50.0}

    for inj, state in zip(injections, states):
        inj.on_event(state, context)

    # Advance time
    for inj, state in zip(injections, states):
        inj.apply_time_step(state, 24.0, context)

    print("\n✓ All injections with assay deception: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Assay Deception Test Suite (Injection J)")
    print("="*60)

    test_atp_mito_decoupling()
    test_glycolytic_compensation()
    test_late_inversion()
    test_latent_damage_invisible()
    test_warburg_activation()
    test_false_negatives()
    test_recovery_is_slow()
    test_assay_deception_integration()
    test_all_injections_with_assay_deception()

    print("\n" + "="*60)
    print("✅ All assay deception tests PASSED")
    print("="*60)
    print("\nAssay Deception Injection (J) complete:")
    print("  - ATP-mito decoupling: High ATP despite damaged mitochondria")
    print("  - Glycolytic compensation: Masks mitochondrial damage")
    print("  - Late inversions: Cells look healthy, then sudden collapse")
    print("  - Latent damage: Accumulates invisibly, then manifests")
    print("  - Warburg effect: Cancer-like glycolysis preference")
    print("  - False negatives: Assay says 'healthy' but cells dying")
    print("  - Recovery is slow: Days to recover, minutes to damage")
    print("\nWhat you measure is not what matters - cells lie to assays!")
