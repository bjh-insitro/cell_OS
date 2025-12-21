"""
Test Death Modes Injection (Injection I): Death Has Shape

Tests:
1. Different death modes have different assay signatures
2. Viability is assay-dependent (ATP ≠ LDH ≠ caspase)
3. Silent dropouts are invisible to most assays
4. Apoptosis: caspase+, low LDH
5. Necrosis: LDH+, low caspase
6. Mixed death modes create assay discrepancies
7. Death markers decay over time
"""

import numpy as np
from cell_os.hardware.injections import (
    DeathModesInjection,
    InjectionContext
)
from cell_os.hardware.injections.death_modes import DeathMode


def test_apoptosis_signature():
    """Test that apoptosis has characteristic markers."""
    print("\n" + "="*60)
    print("Test: Apoptosis Signature")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Initial state:")
    print(f"  Caspase activity: {state.caspase_activity:.3f}")
    print(f"  LDH release: {state.membrane_permeability:.3f}")

    # Trigger apoptosis (10% of cells)
    context.event_type = 'trigger_apoptosis'
    context.event_params = {'fraction': 0.10}
    injection.on_event(state, context)

    print(f"\nAfter 10% apoptosis:")
    print(f"  Caspase activity: {state.caspase_activity:.3f}")
    print(f"  LDH release: {state.membrane_permeability:.3f}")
    print(f"  Annexin-V: {state.ps_externalization:.3f}")

    # Get assay readouts
    caspase_signal = state.get_assay_readout('caspase_activity')
    ldh_signal = state.get_assay_readout('ldh_release')
    annexin_signal = state.get_assay_readout('annexin_v')

    print(f"\nAssay readouts:")
    print(f"  Caspase assay: {caspase_signal:.3f}")
    print(f"  LDH assay: {ldh_signal:.3f}")
    print(f"  Annexin-V assay: {annexin_signal:.3f}")

    # Apoptosis should be caspase+ annexin+ but LDH- (early)
    assert caspase_signal > 0.05, "Apoptosis should be caspase+"
    assert annexin_signal > 0.05, "Apoptosis should be annexin+"
    assert ldh_signal < caspase_signal, "Apoptosis LDH should be lower than caspase"

    print("\n✓ Apoptosis signature: PASS")


def test_necrosis_signature():
    """Test that necrosis has characteristic markers."""
    print("\n" + "="*60)
    print("Test: Necrosis Signature")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Trigger necrosis (10% of cells)
    context.event_type = 'trigger_necrosis'
    context.event_params = {'fraction': 0.10}
    injection.on_event(state, context)

    print(f"After 10% necrosis:")
    print(f"  Membrane permeability: {state.membrane_permeability:.3f}")
    print(f"  Caspase activity: {state.caspase_activity:.3f}")

    # Get assay readouts
    ldh_signal = state.get_assay_readout('ldh_release')
    caspase_signal = state.get_assay_readout('caspase_activity')
    pi_signal = state.get_assay_readout('pi_staining')

    print(f"\nAssay readouts:")
    print(f"  LDH assay: {ldh_signal:.3f}")
    print(f"  Caspase assay: {caspase_signal:.3f}")
    print(f"  PI staining: {pi_signal:.3f}")

    # Necrosis should be LDH+ PI+ but caspase-
    assert ldh_signal > 0.05, "Necrosis should be LDH+"
    assert pi_signal > 0.05, "Necrosis should be PI+"
    assert caspase_signal < ldh_signal, "Necrosis caspase should be lower than LDH"

    print("\n✓ Necrosis signature: PASS")


def test_silent_dropout_invisible():
    """Test that silent dropouts are invisible to assays."""
    print("\n" + "="*60)
    print("Test: Silent Dropout is Invisible")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Trigger silent dropout (15% of cells)
    context.event_type = 'trigger_dropout'
    context.event_params = {'fraction': 0.15}
    injection.on_event(state, context)

    print(f"After 15% dropout:")
    print(f"  Silent dropouts: {state.silent_dropouts_fraction:.3f}")
    print(f"  Total death: {state.total_death_fraction:.3f}")

    # Get assay readouts
    caspase_signal = state.get_assay_readout('caspase_activity')
    ldh_signal = state.get_assay_readout('ldh_release')
    annexin_signal = state.get_assay_readout('annexin_v')
    cell_count_signal = state.get_assay_readout('cell_count')

    print(f"\nAssay readouts:")
    print(f"  Caspase: {caspase_signal:.3f}")
    print(f"  LDH: {ldh_signal:.3f}")
    print(f"  Annexin-V: {annexin_signal:.3f}")
    print(f"  Cell count readout: {cell_count_signal:.3f}")

    # Silent dropouts should be invisible to molecular assays
    assert caspase_signal == 0.0, "Dropout should not trigger caspase"
    assert ldh_signal == 0.0, "Dropout should not release LDH (cells are gone)"
    assert annexin_signal == 0.0, "Dropout should not show annexin (cells are gone)"

    # But visible in cell count (0 = all counted, lower = fewer counted)
    assert cell_count_signal < 0.1, "Dropout should reduce cell count"

    print("\n✓ Silent dropout is invisible: PASS")


def test_viability_assay_dependent():
    """Test that different assays report different viabilities."""
    print("\n" + "="*60)
    print("Test: Viability is Assay-Dependent")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Mixed death: 10% apoptosis, 10% necrosis, 10% dropout
    context.event_type = 'trigger_apoptosis'
    context.event_params = {'fraction': 0.10}
    injection.on_event(state, context)

    context.event_type = 'trigger_necrosis'
    context.event_params = {'fraction': 0.10}
    injection.on_event(state, context)

    context.event_type = 'trigger_dropout'
    context.event_params = {'fraction': 0.10}
    injection.on_event(state, context)

    # True viability: 70% (30% dead total)
    true_viability = state.get_true_viability()
    print(f"True viability: {true_viability:.3f} ({true_viability*100:.0f}%)")

    # Different assays see different things
    viability_atp = state.get_apparent_viability('atp_content')
    viability_ldh = state.get_apparent_viability('ldh_release')
    viability_caspase = state.get_apparent_viability('caspase_activity')
    viability_count = state.get_apparent_viability('cell_count')

    print(f"\nAssay-dependent viability:")
    print(f"  ATP assay: {viability_atp:.3f} ({viability_atp*100:.0f}%)")
    print(f"  LDH assay: {viability_ldh:.3f} ({viability_ldh*100:.0f}%)")
    print(f"  Caspase assay: {viability_caspase:.3f} ({viability_caspase*100:.0f}%)")
    print(f"  Cell count: {viability_count:.3f} ({viability_count*100:.0f}%)")

    # All should differ from true viability
    print(f"\nDiscrepancies from true viability:")
    print(f"  ATP: {abs(viability_atp - true_viability):.3f}")
    print(f"  LDH: {abs(viability_ldh - true_viability):.3f}")
    print(f"  Caspase: {abs(viability_caspase - true_viability):.3f}")
    print(f"  Count: {abs(viability_count - true_viability):.3f}")

    # Assays should disagree (death mode confounding)
    assert viability_atp != viability_ldh or viability_ldh != viability_caspase, \
        "Assays should give different viability estimates"

    print("\n✓ Viability is assay-dependent: PASS")


def test_mixed_death_modes():
    """Test that different stresses produce different death mode distributions."""
    print("\n" + "="*60)
    print("Test: Mixed Death Modes from Different Stresses")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)

    # Test oxidative stress (mostly apoptosis)
    state_ox = injection.create_state("well_oxidative", context)
    context.event_type = 'stress_induced_death'
    context.event_params = {'stress_type': 'oxidative', 'fraction': 0.20}
    injection.on_event(state_ox, context)

    # Test mechanical stress (necrosis + dropout)
    state_mech = injection.create_state("well_mechanical", context)
    context.event_params = {'stress_type': 'mechanical', 'fraction': 0.20}
    injection.on_event(state_mech, context)

    # Test detachment stress (dropout + apoptosis)
    state_detach = injection.create_state("well_detachment", context)
    context.event_params = {'stress_type': 'detachment', 'fraction': 0.20}
    injection.on_event(state_detach, context)

    print("Death mode distribution by stress type:\n")
    print(f"{'Stress Type':<15} {'Apoptosis':<12} {'Necrosis':<12} {'Dropout':<12}")
    print("-" * 60)

    for label, state in [('Oxidative', state_ox), ('Mechanical', state_mech), ('Detachment', state_detach)]:
        apop = state.death_mode_fractions[DeathMode.APOPTOSIS]
        necr = state.death_mode_fractions[DeathMode.NECROSIS]
        drop = state.death_mode_fractions[DeathMode.SILENT_DROPOUT]

        print(f"{label:<15} {apop:<12.3f} {necr:<12.3f} {drop:<12.3f}")

    # Oxidative stress should favor apoptosis
    assert state_ox.death_mode_fractions[DeathMode.APOPTOSIS] > \
           state_ox.death_mode_fractions[DeathMode.NECROSIS], \
           "Oxidative stress should favor apoptosis"

    # Mechanical stress should have necrosis + dropout
    assert state_mech.death_mode_fractions[DeathMode.NECROSIS] > \
           state_mech.death_mode_fractions[DeathMode.APOPTOSIS], \
           "Mechanical stress should favor necrosis"

    # Detachment should have high dropout
    assert state_detach.death_mode_fractions[DeathMode.SILENT_DROPOUT] > \
           state_detach.death_mode_fractions[DeathMode.NECROSIS], \
           "Detachment should favor dropout"

    print("\n✓ Mixed death modes: PASS")


def test_death_marker_decay():
    """Test that death markers decay over time."""
    print("\n" + "="*60)
    print("Test: Death Marker Decay")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Trigger apoptosis and necrosis
    context.event_type = 'trigger_apoptosis'
    context.event_params = {'fraction': 0.20}
    injection.on_event(state, context)

    context.event_type = 'trigger_necrosis'
    context.event_params = {'fraction': 0.20}
    injection.on_event(state, context)

    initial_caspase = state.caspase_activity
    initial_membrane = state.membrane_permeability
    initial_bodies = state.apoptotic_bodies_fraction

    print(f"Initial markers:")
    print(f"  Caspase: {initial_caspase:.3f}")
    print(f"  Membrane perm: {initial_membrane:.3f}")
    print(f"  Apoptotic bodies: {initial_bodies:.3f}")

    # Advance time (markers decay)
    print(f"\nMarker decay over time:")
    timepoints = [0, 24, 48, 72]  # Hours
    for t in timepoints[1:]:
        injection.apply_time_step(state, 24.0, context)

        print(f"  t={t}h: caspase={state.caspase_activity:.3f}, "
              f"membrane={state.membrane_permeability:.3f}, "
              f"bodies={state.apoptotic_bodies_fraction:.3f}")

    # Markers should decay
    assert state.caspase_activity < initial_caspase * 0.5, \
        "Caspase should decay after 72h"
    assert state.apoptotic_bodies_fraction < initial_bodies * 0.8, \
        "Apoptotic bodies should be cleared"

    print("\n✓ Death marker decay: PASS")


def test_assay_discrepancy_warning():
    """Test that large assay discrepancies trigger warnings."""
    print("\n" + "="*60)
    print("Test: Assay Discrepancy Warning")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    # Create large discrepancy: autophagy (high ATP, low LDH)
    context.event_type = 'trigger_autophagy'
    context.event_params = {'fraction': 0.30}
    injection.on_event(state, context)

    # Also some necrosis (low ATP, high LDH)
    context.event_type = 'trigger_necrosis'
    context.event_params = {'fraction': 0.20}
    injection.on_event(state, context)

    viability_atp = state.get_apparent_viability('atp_content')
    viability_ldh = state.get_apparent_viability('ldh_release')
    discrepancy = abs(viability_atp - viability_ldh)

    print(f"Viability estimates:")
    print(f"  ATP assay: {viability_atp:.3f}")
    print(f"  LDH assay: {viability_ldh:.3f}")
    print(f"  Discrepancy: {discrepancy:.3f}")

    # Get pipeline observation
    obs = {}
    obs = injection.pipeline_transform(obs, state, context)

    print(f"\nPipeline observation:")
    print(f"  ATP viability: {obs['viability_atp']:.3f}")
    print(f"  LDH viability: {obs['viability_ldh']:.3f}")
    print(f"  True viability: {obs['viability_true']:.3f}")

    if 'qc_warnings' in obs:
        print(f"  QC warnings: {obs['qc_warnings']}")
        assert any('viability_assay_discrepancy' in w for w in obs['qc_warnings']), \
            "Should warn about assay discrepancy"
    else:
        # If discrepancy < 0.2, warning may not trigger
        assert discrepancy < 0.2, "Large discrepancy should trigger warning"

    print("\n✓ Assay discrepancy warning: PASS")


def test_death_modes_integration():
    """Test death modes in realistic toxicity screen."""
    print("\n" + "="*60)
    print("Test: Death Modes Integration")
    print("="*60)

    injection = DeathModesInjection(seed=42)
    context = InjectionContext(simulated_time=0.0, run_context=None)
    state = injection.create_state("well_A1", context)

    print("Simulating dose-escalation toxicity screen:\n")

    # Low dose: some apoptosis
    print("Day 1: Low dose (mostly apoptosis)")
    context.event_type = 'stress_induced_death'
    context.event_params = {'stress_type': 'oxidative', 'fraction': 0.05}
    injection.on_event(state, context)

    print(f"  Apoptosis: {state.death_mode_fractions[DeathMode.APOPTOSIS]:.3f}")
    print(f"  Necrosis: {state.death_mode_fractions[DeathMode.NECROSIS]:.3f}")
    print(f"  Total death: {state.total_death_fraction:.3f}")

    # Medium dose: more death, mixed modes
    print(f"\nDay 2: Medium dose (mixed)")
    context.event_params = {'stress_type': 'toxic', 'fraction': 0.10}
    injection.on_event(state, context)
    injection.apply_time_step(state, 24.0, context)

    print(f"  Apoptosis: {state.death_mode_fractions[DeathMode.APOPTOSIS]:.3f}")
    print(f"  Necrosis: {state.death_mode_fractions[DeathMode.NECROSIS]:.3f}")
    print(f"  Total death: {state.total_death_fraction:.3f}")

    # High dose: mostly necrosis
    print(f"\nDay 3: High dose (mostly necrosis)")
    context.event_params = {'stress_type': 'toxic', 'fraction': 0.20}
    injection.on_event(state, context)
    injection.apply_time_step(state, 24.0, context)

    print(f"  Apoptosis: {state.death_mode_fractions[DeathMode.APOPTOSIS]:.3f}")
    print(f"  Necrosis: {state.death_mode_fractions[DeathMode.NECROSIS]:.3f}")
    print(f"  Total death: {state.total_death_fraction:.3f}")

    # Get final viability estimates
    print(f"\nFinal viability by assay:")
    meas_mods = injection.get_measurement_modifiers(state, context)
    print(f"  ATP: {meas_mods['viability_atp']:.3f}")
    print(f"  LDH: {meas_mods['viability_ldh']:.3f}")
    print(f"  Caspase: {meas_mods['viability_caspase']:.3f}")
    print(f"  True: {meas_mods['true_viability']:.3f}")

    # All viability estimates should be different
    viabilities = [
        meas_mods['viability_atp'],
        meas_mods['viability_ldh'],
        meas_mods['viability_caspase'],
    ]
    assert len(set(viabilities)) > 1, "Different assays should give different results"

    print("\n✓ Death modes integration: PASS")


def test_all_injections_with_death_modes():
    """Smoke test: ensure death modes work with other injections."""
    print("\n" + "="*60)
    print("Test: All Injections with Death Modes")
    print("="*60)

    from cell_os.hardware.injections import (
        VolumeEvaporationInjection,
        CoatingQualityInjection,
        PipettingVarianceInjection,
        MixingGradientsInjection,
        MeasurementBackActionInjection,
        StressMemoryInjection,
        LumpyTimeInjection,
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

    print("\n✓ All injections with death modes: PASS")


if __name__ == "__main__":
    print("="*60)
    print("Death Modes Test Suite (Injection I)")
    print("="*60)

    test_apoptosis_signature()
    test_necrosis_signature()
    test_silent_dropout_invisible()
    test_viability_assay_dependent()
    test_mixed_death_modes()
    test_death_marker_decay()
    test_assay_discrepancy_warning()
    test_death_modes_integration()
    test_all_injections_with_death_modes()

    print("\n" + "="*60)
    print("✅ All death modes tests PASSED")
    print("="*60)
    print("\nDeath Modes Injection (I) complete:")
    print("  - Apoptosis: caspase+, annexin+, low LDH (organized death)")
    print("  - Necrosis: LDH+, PI+, low caspase (membrane rupture)")
    print("  - Silent dropout: invisible to assays (cells gone)")
    print("  - Autophagy: high ATP, low markers (slow death)")
    print("  - Viability is assay-dependent: ATP ≠ LDH ≠ caspase ≠ truth")
    print("  - Mixed death modes create confounding")
    print("  - Death markers decay over time (bodies cleared)")
    print("\nDeath has shape - different modes, different signatures!")
