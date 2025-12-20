"""
Keeper of Honesty Tests: Volume + Evaporation Injection

Guards against:
1. Position effects being fake (edge must drift)
2. Mass teleporting during operations
3. Negative volume under extreme conditions
4. Concentration dishonesty (derived vs independent)
"""

import sys
import numpy as np
from src.cell_os.hardware.injections.volume_evaporation import (
    VolumeEvaporationInjection,
    VolumeEvaporationState,
    VolumeEvaporationError,
    MIN_VOLUME_uL
)
from src.cell_os.hardware.injections.base import InjectionContext


def test_edge_vs_center_concentration_drift():
    """
    Test 1: Edge wells must show higher concentration than center after time.

    Same initial conditions, run 48h with no ops. Edge wells evaporate faster,
    so compound concentration must increase more.
    """
    print("Test: Edge vs center concentration drift")
    print("-" * 70)

    injection = VolumeEvaporationInjection()

    # Create mock RunContext with neutral humidity
    class MockRunContext:
        incubator_humidity = 1.0

    context = InjectionContext(
        simulated_time=0.0,
        run_context=MockRunContext(),
        plate_id="P1"
    )

    # Center well (D6)
    context_center = InjectionContext(
        simulated_time=0.0,
        run_context=MockRunContext(),
        plate_id="P1",
        well_position="D06"
    )

    state_center = injection.create_state("center_well", context_center)
    state_center.compound_mass = 1.0  # Baseline compound

    # Edge well (A01)
    context_edge = InjectionContext(
        simulated_time=0.0,
        run_context=MockRunContext(),
        plate_id="P1",
        well_position="A01"
    )

    state_edge = injection.create_state("edge_well", context_edge)
    state_edge.compound_mass = 1.0  # Same initial compound

    print(f"Initial state:")
    print(f"  Center (D06): vol={state_center.vol_uL:.1f} uL, compound_mass={state_center.compound_mass:.3f}")
    print(f"  Edge (A01): vol={state_edge.vol_uL:.1f} uL, compound_mass={state_edge.compound_mass:.3f}")

    # Run 48 hours
    for step in range(48):
        context_center.simulated_time = float(step + 1)
        context_edge.simulated_time = float(step + 1)

        injection.apply_time_step(state_center, 1.0, context_center)
        injection.apply_time_step(state_edge, 1.0, context_edge)

    print(f"\nAfter 48h:")
    print(f"  Center: vol={state_center.vol_uL:.1f} uL, conc_mult={state_center.get_compound_concentration_multiplier():.3f}")
    print(f"  Edge: vol={state_edge.vol_uL:.1f} uL, conc_mult={state_edge.get_compound_concentration_multiplier():.3f}")

    # Edge must have higher concentration multiplier (more evaporation)
    # Edge gets 3× evap rate, so should be noticeably higher (at least 1.5× the effect)
    center_effect = state_center.get_compound_concentration_multiplier() - 1.0  # Effect above baseline
    edge_effect = state_edge.get_compound_concentration_multiplier() - 1.0

    if edge_effect > center_effect * 1.5:
        print(f"✓ PASS: Edge effect {edge_effect:.3f} > 1.5× center effect {center_effect:.3f}")
        return True
    else:
        print(f"❌ FAIL: Edge effect {edge_effect:.3f} not > 1.5× center effect {center_effect:.3f}")
        return False


def test_mass_conservation_through_operations():
    """
    Test 2: Mass conservation through liquid handling.

    Aspirate 50% then dispense 50% fresh media:
    - Compound mass halves
    - Volume returns to baseline
    - Concentration halves (not stays same!)
    """
    print("\nTest: Mass conservation through operations")
    print("-" * 70)

    injection = VolumeEvaporationInjection()

    context = InjectionContext(
        simulated_time=0.0,
        run_context=None,
        plate_id="P1",
        well_position="D06"
    )

    state = injection.create_state("test_well", context)
    state.compound_mass = 2.0  # 2× baseline
    state.baseline_compound_mass = 2.0  # Set baseline for concentration computation

    print(f"Initial state:")
    print(f"  vol={state.vol_uL:.1f} uL, compound_mass={state.compound_mass:.3f}")
    print(f"  compound_conc_mult={state.get_compound_concentration_multiplier():.3f}")

    # Aspirate 50%
    context.event_type = 'aspirate'
    context.event_params = {'fraction': 0.5}
    injection.on_event(state, context)

    print(f"\nAfter aspirate 50%:")
    print(f"  vol={state.vol_uL:.1f} uL, compound_mass={state.compound_mass:.3f}")
    print(f"  compound_conc_mult={state.get_compound_concentration_multiplier():.3f}")

    vol_after_aspirate = state.vol_uL
    mass_after_aspirate = state.compound_mass

    # Dispense 100 uL fresh media (no compound)
    context.event_type = 'dispense'
    context.event_params = {'volume_uL': 100.0, 'compound_mass': 0.0, 'nutrient_mass': 0.5}
    injection.on_event(state, context)

    print(f"\nAfter dispense 100 uL fresh:")
    print(f"  vol={state.vol_uL:.1f} uL, compound_mass={state.compound_mass:.3f}")
    print(f"  compound_conc_mult={state.get_compound_concentration_multiplier():.3f}")

    # Check expectations
    expected_mass = 1.0  # 2.0 * 0.5 = 1.0
    expected_vol = 200.0  # 100 (after aspirate) + 100 (dispense) = 200

    mass_ok = abs(state.compound_mass - expected_mass) < 0.01
    vol_ok = abs(state.vol_uL - expected_vol) < 1.0

    # Concentration should be 0.5× baseline (mass halved, volume returned)
    conc_mult = state.get_compound_concentration_multiplier()
    conc_ok = abs(conc_mult - 0.5) < 0.1  # Should be ~0.5 (mass=1.0, vol=200)

    # CRITICAL: Concentration derives from mass/vol, not independent
    # multiplier = (mass / baseline_mass) * (baseline_vol / vol)
    derived_conc = (state.compound_mass / 2.0) * (200.0 / state.vol_uL)
    derived_ok = abs(state.get_compound_concentration_multiplier() - derived_conc) < 0.01

    if mass_ok and vol_ok and conc_ok and derived_ok:
        print(f"✓ PASS: Mass conserved, volume correct, concentration derived honestly")
        return True
    else:
        print(f"❌ FAIL: mass_ok={mass_ok}, vol_ok={vol_ok}, conc_ok={conc_ok}, derived_ok={derived_ok}")
        return False


def test_no_negative_volume():
    """
    Test 3: Volume hits floor (MIN_VOLUME_uL) under extreme evaporation.

    Should not go negative, should trigger dry well failure mode.
    """
    print("\nTest: No negative volume under extreme evaporation")
    print("-" * 70)

    injection = VolumeEvaporationInjection()

    # Create aggressive evaporation context
    class MockRunContext:
        incubator_humidity = 0.5  # Very dry (2× evap multiplier)

    context = InjectionContext(
        simulated_time=0.0,
        run_context=MockRunContext(),
        plate_id="P1",
        well_position="A01"  # Edge well (3× multiplier)
    )

    state = injection.create_state("edge_well", context)
    state.vol_uL = 50.0  # Start low

    print(f"Initial state: vol={state.vol_uL:.1f} uL")
    print(f"Running 200 hours with aggressive evaporation...")

    # Run until dry (should hit floor, not go negative)
    for step in range(200):
        context.simulated_time = float(step + 1)
        injection.apply_time_step(state, 1.0, context)

        if state.vol_uL <= MIN_VOLUME_uL:
            print(f"  Hit minimum at t={step+1}h: vol={state.vol_uL:.1f} uL")
            break

    print(f"\nFinal state: vol={state.vol_uL:.1f} uL")

    # Check non-negativity and floor
    if state.vol_uL >= 0 and state.vol_uL <= MIN_VOLUME_uL * 1.01:
        print(f"✓ PASS: Volume hit floor (MIN_VOLUME_uL={MIN_VOLUME_uL}) without going negative")
        return True
    else:
        print(f"❌ FAIL: Volume = {state.vol_uL:.1f}, expected near {MIN_VOLUME_uL}")
        return False


def test_osmolality_stress_at_high_concentration():
    """
    Test 4: Osmolality stress kicks in at high concentrations.

    High compound + low volume → hyperosmotic stress.
    """
    print("\nTest: Osmolality stress at high concentration")
    print("-" * 70)

    injection = VolumeEvaporationInjection()

    context = InjectionContext(
        simulated_time=0.0,
        run_context=None,
        plate_id="P1",
        well_position="D06"
    )

    state = injection.create_state("test_well", context)

    # Normal state: no stress
    stress_normal = state.get_osmolality_stress()
    print(f"Normal state: vol={state.vol_uL:.1f} uL, osmolality_stress={stress_normal:.3f}")

    # High concentration state: reduce volume, increase solutes
    state.vol_uL = 80.0  # 40% of baseline
    state.compound_mass = 2.0  # 2× compound
    state.waste_mass = 1.0  # Some waste

    stress_high = state.get_osmolality_stress()
    print(f"High concentration: vol={state.vol_uL:.1f} uL, osmolality_stress={stress_high:.3f}")

    if stress_high > 0.3 and stress_high > stress_normal + 0.2:
        print(f"✓ PASS: Osmolality stress {stress_high:.3f} > {stress_normal:.3f} at high concentration")
        return True
    else:
        print(f"❌ FAIL: Osmolality stress not elevated enough ({stress_high:.3f})")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Volume + Evaporation Injection (Keeper of Honesty)")
    print("=" * 70)
    print()

    tests = [
        ("Edge vs center concentration drift", test_edge_vs_center_concentration_drift),
        ("Mass conservation through operations", test_mass_conservation_through_operations),
        ("No negative volume", test_no_negative_volume),
        ("Osmolality stress at high concentration", test_osmolality_stress_at_high_concentration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
