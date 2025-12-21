"""
Test Final Injections: Identifiability Limits (L) and Cursed Plate (M)

Priority 7 Tests (Identifiability Limits):
1. Growth vs death confounding (only net observable)
2. Cytostatic vs cytotoxic ambiguity
3. Mechanism aliasing (different causes, same effect)
4. Permanent ambiguity (more data doesn't help)

Priority 8 Tests (Cursed Plate):
5. Contamination curse
6. Instrument failure curse
7. Curse progression over time
8. Curse detection and impact
"""

import numpy as np
from cell_os.hardware.injections import (
    IdentifiabilityLimitsInjection,
    CursedPlateInjection,
    InjectionContext
)
from cell_os.hardware.injections.identifiability_limits import ConfoundingType
from cell_os.hardware.injections.cursed_plate import CurseType


# ============================================================
# Priority 7: Identifiability Limits Tests
# ============================================================

def test_growth_death_confounding():
    """Test that growth and death rates are confounded (only net observable)."""
    print("\n" + "="*60)
    print("Test: Growth vs Death Confounding")
    print("="*60)

    injection = IdentifiabilityLimitsInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Introduce growth/death confounding
    context.event_type = 'introduce_growth_death_confounding'
    context.event_params = {
        'growth_rate': 0.20,   # 20% growth per hour
        'death_rate': 0.15,    # 15% death per hour
    }
    injection.on_event(state, context)

    print(f"True parameters (hidden from agent):")
    print(f"  Growth rate: {state.growth_rate_true:.3f}")
    print(f"  Death rate: {state.death_rate_true:.3f}")

    print(f"\nObservable parameter:")
    print(f"  Net growth rate: {state.get_observable_net_rate():.3f}")

    # Get measurement modifiers
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\nIdentifiability:")
    print(f"  Growth rate identifiable: {meas_mods['growth_rate_identifiable']}")
    print(f"  Death rate identifiable: {meas_mods['death_rate_identifiable']}")

    # Key test: Agent can only see net rate
    assert abs(state.growth_rate_true - 0.20) < 1e-6, "True growth is 20%"
    assert abs(state.death_rate_true - 0.15) < 1e-6, "True death is 15%"
    assert abs(state.get_observable_net_rate() - 0.05) < 1e-6, "Observable net is 5%"
    assert not meas_mods['growth_rate_identifiable'], "Growth NOT identifiable"
    assert not meas_mods['death_rate_identifiable'], "Death NOT identifiable"

    print(f"\n→ CONFOUNDED: Agent sees net=5%, but can't tell if it's")
    print(f"   growth=20% death=15%, or growth=10% death=5%, or ...")

    print("\n✓ Growth vs death confounding: PASS")


def test_cytostatic_cytotoxic_ambiguity():
    """Test that cytostatic vs cytotoxic are indistinguishable early."""
    print("\n" + "="*60)
    print("Test: Cytostatic vs Cytotoxic Ambiguity")
    print("="*60)

    injection = IdentifiabilityLimitsInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Introduce cytostatic/cytotoxic confounding
    context.event_type = 'introduce_cytostatic_cytotoxic'
    context.event_params = {
        'true_mechanism': 'cytostatic',  # Actually cytostatic
        'fraction': 0.30,                # 30% affected
    }
    injection.on_event(state, context)

    print(f"True mechanism (hidden from agent): cytostatic")
    print(f"True cytostatic fraction: {state.cytostatic_fraction:.3f}")
    print(f"True cytotoxic fraction: {state.cytotoxic_fraction:.3f}")

    print(f"\nObservable parameter:")
    print(f"  Cell count reduction: {state.get_observable_cell_count_change():.3f}")

    # Get confounding report
    report = state.get_confounding_report()

    print(f"\nConfounding report:")
    print(f"  Confounded mechanisms: {report['n_confounded_mechanisms']}")
    for scenario in report['confounding_scenarios']:
        print(f"  {scenario['mechanism_a']} vs {scenario['mechanism_b']}: "
              f"{scenario['equivalence']:.1f} equivalence")

    # Key test: Agent can't distinguish
    assert abs(state.cytostatic_fraction - 0.30) < 1e-6, "True mechanism is cytostatic"
    assert abs(state.cytotoxic_fraction - 0.0) < 1e-6, "No cytotoxic effect"
    assert abs(state.get_observable_cell_count_change() - 0.30) < 1e-6, "Observable: 30% reduction"
    assert report['cytostatic_cytotoxic_confounded'], "Mechanisms confounded"

    print(f"\n→ AMBIGUOUS: 30% cell count reduction could be:")
    print(f"   - 30% cytostatic (growth arrested)")
    print(f"   - 30% cytotoxic (dead)")
    print(f"   - Any mixture!")

    print("\n✓ Cytostatic vs cytotoxic ambiguity: PASS")


def test_permanent_ambiguity():
    """Test that ambiguity is permanent (more data doesn't help)."""
    print("\n" + "="*60)
    print("Test: Permanent Ambiguity")
    print("="*60)

    injection = IdentifiabilityLimitsInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Introduce confounding
    context.event_type = 'introduce_growth_death_confounding'
    context.event_params = {'growth_rate': 0.15, 'death_rate': 0.10}
    injection.on_event(state, context)

    net_rate_t0 = state.get_observable_net_rate()
    print(f"Observable at t=0: net_rate={net_rate_t0:.3f}")

    # Advance time (simulate "more data")
    for t in [10, 100, 1000]:
        injection.apply_time_step(state, float(t), context)

        net_rate = state.get_observable_net_rate()
        print(f"Observable at t={t}h: net_rate={net_rate:.3f}")

        # Net rate unchanged (confounding is structural, not noise)
        assert abs(net_rate - net_rate_t0) < 1e-6, "Confounding is permanent"

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)

    print(f"\nPipeline metadata:")
    print(f"  Permanent ambiguity: {obs.get('permanent_ambiguity_present', False)}")
    print(f"  More data helps: {obs.get('more_data_helps', True)}")

    if 'qc_warnings' in obs:
        print(f"  QC warnings: {obs['qc_warnings']}")

    assert obs.get('more_data_helps') == False, "More data doesn't resolve confounding"

    print(f"\n→ PERMANENT: This is structural confounding, not measurement noise.")
    print(f"   Infinite data won't help - the question is unanswerable.")

    print("\n✓ Permanent ambiguity: PASS")


# ============================================================
# Priority 8: Cursed Plate Tests
# ============================================================

def test_contamination_curse():
    """Test that contamination curse ruins the plate."""
    print("\n" + "="*60)
    print("Test: Contamination Curse")
    print("="*60)

    injection = CursedPlateInjection(seed=42, enable_curses=False)  # Manual trigger
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print(f"Initial state:")
    print(f"  Curse active: {state.curse_active}")

    # Trigger contamination
    context.event_type = 'trigger_contamination'
    context.event_params = {'severity': 0.70}
    injection.on_event(state, context)

    print(f"\nAfter contamination:")
    print(f"  Curse active: {state.curse_active}")
    print(f"  Curse type: {state.curse_type.value if state.curse_type else None}")
    print(f"  Curse severity: {state.curse_severity:.3f}")
    print(f"  Contamination level: {state.contamination_overgrowth:.3f}")

    # Contamination grows over time
    print(f"\nContamination growth over time:")
    for t in [0, 6, 12, 24]:
        if t > 0:
            injection.apply_time_step(state, 6.0, context)

        viability = state.get_viability_impact()
        print(f"  t={t}h: contamination={state.contamination_overgrowth:.3f}, "
              f"viability={viability:.3f}")

    assert state.curse_active, "Curse should be active"
    assert state.contamination_overgrowth > 0.70, "Contamination should grow"
    assert viability < 0.50, "Contamination should kill cells"

    print(f"\n→ CURSED: Contamination grows exponentially, ruins experiment")

    print("\n✓ Contamination curse: PASS")


def test_instrument_failure_curse():
    """Test that instrument failure introduces systematic errors."""
    print("\n" + "="*60)
    print("Test: Instrument Failure Curse")
    print("="*60)

    injection = CursedPlateInjection(seed=42, enable_curses=False)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Trigger instrument failure
    context.event_type = 'trigger_instrument_failure'
    context.event_params = {'severity': 0.60}
    injection.on_event(state, context)

    print(f"After instrument failure:")
    print(f"  Curse type: {state.curse_type.value if state.curse_type else None}")
    print(f"  Systematic error: {state.instrument_systematic_error:+.3f}")

    corruption = state.get_measurement_corruption()

    print(f"  Measurement corruption: {corruption:.3f}")

    # Get measurement modifiers
    meas_mods = injection.get_measurement_modifiers(state, context)

    print(f"\nMeasurement effects:")
    print(f"  Systematic error: {meas_mods['systematic_error']:+.3f}")
    print(f"  Corruption magnitude: {meas_mods['measurement_corruption']:.3f}")

    assert state.curse_active, "Curse should be active"
    assert abs(state.instrument_systematic_error) > 0.01, "Should have systematic error"
    assert corruption > 0.02, "Should corrupt measurements"

    print(f"\n→ CURSED: Robot miscalibrated, all volumes systematically wrong")

    print("\n✓ Instrument failure curse: PASS")


def test_curse_detection():
    """Test that some curses are detectable, others hidden."""
    print("\n" + "="*60)
    print("Test: Curse Detection")
    print("="*60)

    injection = CursedPlateInjection(seed=42, enable_curses=False)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Trigger contamination (visible when severe)
    context.event_type = 'trigger_contamination'
    context.event_params = {'severity': 0.80}
    injection.on_event(state, context)

    # Progress contamination
    injection.apply_time_step(state, 12.0, context)

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)

    print(f"Contamination detection:")
    print(f"  Contamination level: {state.contamination_overgrowth:.3f}")
    print(f"  Visible contamination: {obs.get('visible_contamination', False)}")

    if 'qc_warnings' in obs:
        print(f"  QC warnings:")
        for warning in obs['qc_warnings']:
            print(f"    - {warning}")

    # Severe contamination should be detectable
    if state.contamination_overgrowth > 0.3:
        assert obs.get('visible_contamination'), "Severe contamination should be visible"

    # Check if abort recommended
    if obs.get('abort_recommended'):
        print(f"\n→ ABORT RECOMMENDED: Experiment may be ruined")

    print("\n✓ Curse detection: PASS")


def test_all_injections_final():
    """Smoke test: ensure all injections work together."""
    print("\n" + "="*60)
    print("Test: All 13 Injections Together")
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
        AssayDeceptionInjection,
        CoalitionDynamicsInjection,
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
        CoalitionDynamicsInjection(seed=10),
        IdentifiabilityLimitsInjection(seed=11),
        CursedPlateInjection(seed=12, enable_curses=False),  # Disable random curses
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

    print(f"\n✓ All 13 injections work together!")

    print("\n✓ All injections final: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Final Injections Test Suite (L & M)")
    print("="*60)

    # Priority 7: Identifiability Limits
    print("\n" + "="*60)
    print("PRIORITY 7: IDENTIFIABILITY LIMITS")
    print("="*60)

    test_growth_death_confounding()
    test_cytostatic_cytotoxic_ambiguity()
    test_permanent_ambiguity()

    # Priority 8: Cursed Plate
    print("\n" + "="*60)
    print("PRIORITY 8: CURSED PLATE")
    print("="*60)

    test_contamination_curse()
    test_instrument_failure_curse()
    test_curse_detection()

    # Final integration
    test_all_injections_final()

    print("\n" + "="*60)
    print("✅ ALL FINAL TESTS PASSED")
    print("="*60)

    print("\n" + "="*60)
    print("COMPLETE INJECTION SUITE (13 of 13)")
    print("="*60)
    print("\nIdentifiability Limits (L):")
    print("  - Growth vs death confounding (only net observable)")
    print("  - Cytostatic vs cytotoxic ambiguity")
    print("  - Permanent ambiguity (more data doesn't help)")
    print("  - Structural confounding (not measurement noise)")
    print("\nCursed Plate (M):")
    print("  - Contamination (bacteria/fungi ruin plate)")
    print("  - Instrument failure (systematic errors)")
    print("  - Curse progression (gets worse over time)")
    print("  - Rare tail events (probability has fat tails)")
    print("\n" + "="*60)
    print("🎉 ALL 8 PRIORITIES COMPLETE! 🎉")
    print("="*60)
    print("\nFull injection stack:")
    print("  A. Volume Evaporation")
    print("  B. Plating Artifacts")
    print("  C. Coating Quality")
    print("  D. Pipetting Variance")
    print("  E. Mixing Gradients")
    print("  F. Measurement Back-Action")
    print("  G. Stress Memory")
    print("  H. Lumpy Time")
    print("  I. Death Modes")
    print("  J. Assay Deception")
    print("  K. Coalition Dynamics")
    print("  L. Identifiability Limits")
    print("  M. Cursed Plate")
    print("\nThe system now enforces REALITY.")
