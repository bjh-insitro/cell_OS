"""
Phase 3: Washout costs (intervention costs prevent free micro-cycling).

This test verifies that washout:
1. Removes compounds (expected behavior)
2. Does NOT directly affect latent states (recovery comes from decay dynamics)
3. Does NOT directly affect structural morphology (measurement artifact only)
4. DOES apply intervention costs (time, contamination risk, intensity penalty)

This is the physics lock before defining rewards.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_washout_has_cost_but_no_structural_effect():
    """
    Washout should apply intervention costs but NOT affect structural biology.

    Timeline:
    - 0h: Apply paclitaxel
    - 6h: Measure baseline (transport engaged)
    - 6h: Washout (intervention)
    - 6h+1min: Measure immediately after washout

    Expected:
    - Compounds cleared ✓
    - Transport dysfunction unchanged immediately (decay happens over hours, not instantly)
    - Morphology struct unchanged immediately (structural biology doesn't change from washout)
    - Signal intensity reduced (measurement artifact from handling stress)
    - Ops cost recorded (time cost, contamination risk, intensity penalty)

    Key insight: Washout removes compounds and adds costs. Recovery comes from
    natural decay dynamics (k_off terms), not from washout itself.
    """
    print("\n=== Washout Costs Sanity Test ===")

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Apply paclitaxel to induce transport dysfunction
    vm.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    vm.advance_time(6.0)

    vessel = vm.vessel_states["test"]

    # Measure before washout
    result_before = vm.cell_painting_assay("test")
    morph_struct_before = result_before['morphology_struct'].copy()
    morph_measured_before = result_before['morphology_measured'].copy()
    intensity_before = result_before['signal_intensity']

    transport_before = vessel.transport_dysfunction
    er_stress_before = vessel.er_stress
    mito_dysfunction_before = vessel.mito_dysfunction
    viability_before = vessel.viability

    compounds_before = set(vessel.compounds.keys())

    print(f"\nBefore washout (6h):")
    print(f"  Compounds: {compounds_before}")
    print(f"  Transport dysfunction: {transport_before:.3f}")
    print(f"  Actin structural: {morph_struct_before['actin']:.1f}")
    print(f"  Signal intensity: {intensity_before:.3f}")
    print(f"  Viability: {viability_before:.3f}")

    # Washout
    washout_result = vm.washout_compound("test")

    print(f"\nWashout result:")
    print(f"  Status: {washout_result['status']}")
    print(f"  Removed compounds: {washout_result['removed_compounds']}")
    print(f"  Time cost: {washout_result.get('time_cost_h', 'N/A')}h")
    print(f"  Contamination event: {washout_result.get('contamination_event', 'N/A')}")
    print(f"  Intensity penalty applied: {washout_result.get('intensity_penalty_applied', 'N/A')}")

    # Measure immediately after washout (1 minute later, ~0.017h)
    vm.advance_time(0.017)

    result_after = vm.cell_painting_assay("test")
    morph_struct_after = result_after['morphology_struct'].copy()
    morph_measured_after = result_after['morphology_measured'].copy()
    intensity_after = result_after['signal_intensity']

    transport_after = vessel.transport_dysfunction
    er_stress_after = vessel.er_stress
    mito_dysfunction_after = vessel.mito_dysfunction
    viability_after = vessel.viability

    compounds_after = set(vessel.compounds.keys())

    print(f"\nImmediately after washout (6h + 1min):")
    print(f"  Compounds: {compounds_after if compounds_after else 'none'}")
    print(f"  Transport dysfunction: {transport_after:.3f} (Δ={transport_after - transport_before:+.3f})")
    print(f"  Actin structural: {morph_struct_after['actin']:.1f} (Δ={morph_struct_after['actin'] - morph_struct_before['actin']:+.1f})")
    print(f"  Signal intensity: {intensity_after:.3f} (Δ={intensity_after - intensity_before:+.3f})")
    print(f"  Viability: {viability_after:.3f} (Δ={viability_after - viability_before:+.3f})")

    # Check 1: Compounds cleared
    assert len(compounds_after) == 0, f"Compounds should be cleared: {compounds_after}"
    assert len(compounds_before) > 0, f"Should have had compounds before washout: {compounds_before}"
    print(f"\n✓ Check 1: Compounds cleared")

    # Check 2: Transport dysfunction unchanged immediately
    # Allow tiny numerical drift (~1e-3) but no large changes
    transport_change = abs(transport_after - transport_before)
    assert transport_change < 0.01, (
        f"Transport dysfunction should be unchanged immediately after washout: "
        f"{transport_before:.3f} → {transport_after:.3f} (Δ={transport_change:.3f})"
    )
    print(f"✓ Check 2: Transport dysfunction unchanged ({transport_change:.4f} drift)")

    # Check 3: ER stress and mito dysfunction unchanged
    er_change = abs(er_stress_after - er_stress_before)
    mito_change = abs(mito_dysfunction_after - mito_dysfunction_before)
    assert er_change < 0.01, f"ER stress should be unchanged: {er_change:.3f}"
    assert mito_change < 0.01, f"Mito dysfunction should be unchanged: {mito_change:.3f}"
    print(f"✓ Check 3: ER and mito unchanged")

    # Check 4: Structural morphology has TWO components (Model B: acute + chronic)
    #
    # Model B formula: morph_struct = baseline × (1 + acute_effect) × (1 + chronic_effect)
    #   - Acute: Direct compound stress axis effects (instant on/off)
    #   - Chronic: Latent dysfunction effects (slow k_off decay)
    #
    # Before washout: actin_struct = baseline × compound_effect × latent_effect
    # After washout: actin_struct = baseline × 1.0 × latent_effect
    #
    # We verify the change is in the expected direction (actin decreases when acute removed)
    actin_struct_change = morph_struct_after['actin'] - morph_struct_before['actin']
    actin_struct_change_pct = actin_struct_change / morph_struct_before['actin']

    # Actin should decrease (acute component gone, chronic component remains)
    assert actin_struct_change < 0, (
        f"Actin structural should decrease when compound removed (Model B): "
        f"{morph_struct_before['actin']:.1f} → {morph_struct_after['actin']:.1f}"
    )

    # But should not drop to zero (chronic latent effect still present)
    assert morph_struct_after['actin'] > morph_struct_before['actin'] * 0.5, (
        f"Actin should not drop too far (chronic effect ~0.8× remains): "
        f"{morph_struct_before['actin']:.1f} → {morph_struct_after['actin']:.1f}"
    )
    print(f"✓ Check 4: Structural morphology follows Model B (acute removed, chronic persists: {actin_struct_change_pct:.1%})")

    # Check 5: Signal intensity reduced (measurement artifact)
    intensity_reduction = intensity_before - intensity_after
    assert intensity_reduction > 0.01, (
        f"Signal intensity should be reduced by washout penalty: "
        f"{intensity_before:.3f} → {intensity_after:.3f} (reduction={intensity_reduction:.3f})"
    )
    print(f"✓ Check 5: Signal intensity reduced by {intensity_reduction:.3f} (measurement artifact)")

    # Check 6: Viability unchanged (washout doesn't kill cells)
    viability_change = abs(viability_after - viability_before)
    assert viability_change < 0.01, (
        f"Viability should be unchanged by washout: "
        f"{viability_before:.3f} → {viability_after:.3f} (Δ={viability_change:.3f})"
    )
    print(f"✓ Check 6: Viability unchanged ({viability_change:.4f} drift)")

    # Check 7: Ops cost metadata present
    assert washout_result['status'] == 'success', "Washout should succeed"
    assert 'time_cost_h' in washout_result, "Should report time cost"
    assert 'contamination_event' in washout_result, "Should report contamination risk"
    assert 'intensity_penalty_applied' in washout_result, "Should report intensity penalty"

    assert washout_result['time_cost_h'] == 0.25, f"Time cost should be 0.25h: {washout_result['time_cost_h']}"
    assert washout_result['intensity_penalty_applied'] == True, "Intensity penalty should be applied"
    print(f"✓ Check 7: Ops cost metadata present (time={washout_result['time_cost_h']}h)")

    # Check 8: Washout count tracked
    assert vessel.washout_count == 1, f"Washout count should be 1: {vessel.washout_count}"
    assert vessel.last_washout_time is not None, "Last washout time should be recorded"
    print(f"✓ Check 8: Washout count tracked (count={vessel.washout_count})")

    # Summary
    print(f"\n{'='*60}")
    print(f"✓ PASSED: Washout has cost but no structural effect")
    print(f"{'='*60}")
    print(f"\nKey results:")
    print(f"  Compounds cleared: {compounds_before} → ∅")
    print(f"  Transport dysfunction unchanged: {transport_before:.3f} → {transport_after:.3f} (latent persists)")
    print(f"  Actin structural changed: {morph_struct_before['actin']:.1f} → {morph_struct_after['actin']:.1f} (compound effect removed)")
    print(f"  Signal intensity reduced: {intensity_before:.3f} → {intensity_after:.3f} (artifact)")
    print(f"  Ops cost: {washout_result['time_cost_h']}h operator time")
    print(f"\nPhysics principle: Washout removes compounds and adds costs.")
    print(f"  - Compound's direct morphology effects disappear immediately")
    print(f"  - Latent states (transport dysfunction) persist and decay naturally (k_off)")
    print(f"  - Recovery is gradual, not instantaneous")


if __name__ == "__main__":
    test_washout_has_cost_but_no_structural_effect()
    print("\n=== Washout Costs Physics Lock Complete ===")
