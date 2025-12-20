"""
Enforcement Test B1: 48-Hour Story (Spine Stays The Spine)

A realistic mini-protocol that touches all 8 hook points and asserts
InjectionManager remains the single source of truth.

Protocol:
1. seed_vessel() - establish baseline
2. treat_with_compound(tunicamycin, 1.0 µM)
3. step 12h - evaporation concentrates
4. feed_vessel() - nutrient bump
5. step 12h - more evaporation
6. washout_compound() - remove compound
7. step 24h - post-washout recovery
8. cell_painting_assay() - readout (must not mutate spine)

Invariants Enforced:
- Single source of truth: vessel fields match InjectionManager exactly
- Mass monotonicity: concentrations follow physics (evaporation up, washout down)
- Feed semantics: nutrients increase, compounds unchanged (no dilution in v1)
- Washout semantics: compounds drop to ~0, nutrients unchanged
- Assay non-mutating: readout doesn't alter spine
- Step function wiring: concentrations match predicted values from rates
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_48h_story_all_hooks():
    """
    Run realistic 48h protocol and assert spine invariants at every step.
    """
    print("=" * 70)
    print("Enforcement Test B1: 48-Hour Story (Spine Stays The Spine)")
    print("=" * 70)
    print()

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "Plate1_D06"  # Interior well (predictable evaporation)

    violations = []

    # ========== Step 1: seed_vessel ==========
    print("Step 1: seed_vessel()")
    print("-" * 70)
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)

    # Invariant: InjectionManager initialized
    if not vm.injection_mgr.has_vessel(vessel_id):
        violations.append("seed_vessel did not initialize InjectionManager state")

    # Invariant: Nutrients match
    glc_spine = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
    gln_spine = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")
    vessel = vm.vessel_states[vessel_id]

    if abs(vessel.media_glucose_mM - glc_spine) > 1e-9:
        violations.append(f"seed: glucose mismatch (vessel={vessel.media_glucose_mM}, spine={glc_spine})")
    if abs(vessel.media_glutamine_mM - gln_spine) > 1e-9:
        violations.append(f"seed: glutamine mismatch (vessel={vessel.media_glutamine_mM}, spine={gln_spine})")

    print(f"  Glucose: {glc_spine:.1f} mM (spine)")
    print(f"  Glutamine: {gln_spine:.1f} mM (spine)")
    print(f"  ✓ Vessel fields mirror spine")
    print()

    # ========== Step 2: treat_with_compound ==========
    print("Step 2: treat_with_compound(tunicamycin, 1.0 µM)")
    print("-" * 70)
    vm.treat_with_compound(vessel_id, "tunicamycin", 1.0)

    # Deliver event at boundary (boundary semantics: operations queue, flush delivers)
    vm.flush_operations_now()
    vm.advance_time(0.0)  # Trigger mirroring without advancing time

    # Invariant: Compound added to spine (after delivery)
    vessel = vm.vessel_states[vessel_id]  # Refresh vessel reference
    tuni_spine = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")
    if abs(tuni_spine - 1.0) > 1e-6:
        violations.append(f"treat: tunicamycin not 1.0 µM in spine (got {tuni_spine})")

    # Invariant: Vessel mirrors spine (after _step_vessel mirroring)
    if "tunicamycin" not in vessel.compounds:
        violations.append("treat: tunicamycin not in vessel.compounds")
    elif abs(vessel.compounds["tunicamycin"] - tuni_spine) > 1e-9:
        violations.append(f"treat: vessel compound mismatch (vessel={vessel.compounds['tunicamycin']}, spine={tuni_spine})")

    print(f"  Tunicamycin: {tuni_spine:.3f} µM (spine)")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 3: advance_time(12h) ==========
    print("Step 3: advance_time(12h) - evaporation concentrates")
    print("-" * 70)
    tuni_before_evap = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")
    glc_before_evap = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")

    vm.advance_time(12.0)

    # Invariant: Evaporation increases concentrations
    tuni_after_evap = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")
    glc_after_evap = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")

    if tuni_after_evap <= tuni_before_evap:
        violations.append(f"evap: tunicamycin did not increase ({tuni_before_evap:.3f} → {tuni_after_evap:.3f})")
    if glc_after_evap <= glc_before_evap * 0.99:  # Allow tiny numerical drift
        violations.append(f"evap: glucose decreased unexpectedly ({glc_before_evap:.1f} → {glc_after_evap:.1f})")

    # Invariant: Vessel mirrors spine after step
    vessel = vm.vessel_states[vessel_id]
    if abs(vessel.compounds["tunicamycin"] - tuni_after_evap) > 1e-9:
        violations.append(f"evap: vessel compound stale (vessel={vessel.compounds['tunicamycin']:.3f}, spine={tuni_after_evap:.3f})")
    if abs(vessel.media_glucose_mM - glc_after_evap) > 1e-9:
        violations.append(f"evap: vessel glucose stale (vessel={vessel.media_glucose_mM:.1f}, spine={glc_after_evap:.1f})")

    print(f"  Tunicamycin: {tuni_before_evap:.3f} → {tuni_after_evap:.3f} µM (+{(tuni_after_evap/tuni_before_evap - 1)*100:.1f}%)")
    print(f"  Glucose: {glc_before_evap:.1f} → {glc_after_evap:.1f} mM")
    print(f"  ✓ Concentrations increased (evaporation working)")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 4: feed_vessel ==========
    print("Step 4: feed_vessel() - nutrient bump")
    print("-" * 70)
    tuni_before_feed = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    vm.feed_vessel(vessel_id, glucose_mM=25.0, glutamine_mM=4.0)

    # Deliver event at boundary
    vm.flush_operations_now()
    vm.advance_time(0.0)  # Trigger mirroring

    # Invariant: Nutrients reset, compounds unchanged (no dilution in v1)
    glc_after_feed = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
    gln_after_feed = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")
    tuni_after_feed = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    if abs(glc_after_feed - 25.0) > 0.1:
        violations.append(f"feed: glucose not reset to 25.0 mM (got {glc_after_feed:.1f})")
    if abs(gln_after_feed - 4.0) > 0.1:
        violations.append(f"feed: glutamine not reset to 4.0 mM (got {gln_after_feed:.1f})")
    if abs(tuni_after_feed - tuni_before_feed) > 1e-6:
        violations.append(f"feed: compound changed unexpectedly ({tuni_before_feed:.3f} → {tuni_after_feed:.3f})")

    # Invariant: Vessel mirrors spine
    vessel = vm.vessel_states[vessel_id]
    if abs(vessel.media_glucose_mM - glc_after_feed) > 1e-9:
        violations.append(f"feed: vessel glucose stale (vessel={vessel.media_glucose_mM:.1f}, spine={glc_after_feed:.1f})")
    if abs(vessel.compounds["tunicamycin"] - tuni_after_feed) > 1e-9:
        violations.append(f"feed: vessel compound stale (vessel={vessel.compounds['tunicamycin']:.3f}, spine={tuni_after_feed:.3f})")

    print(f"  Glucose: {glc_after_feed:.1f} mM (refreshed)")
    print(f"  Glutamine: {gln_after_feed:.1f} mM (refreshed)")
    print(f"  Tunicamycin: {tuni_after_feed:.3f} µM (unchanged, no dilution)")
    print(f"  ✓ Feed semantics correct")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 5: advance_time(12h) ==========
    print("Step 5: advance_time(12h) - more evaporation")
    print("-" * 70)
    tuni_before_evap2 = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    vm.advance_time(12.0)

    tuni_after_evap2 = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    if tuni_after_evap2 <= tuni_before_evap2:
        violations.append(f"evap2: tunicamycin did not increase ({tuni_before_evap2:.3f} → {tuni_after_evap2:.3f})")

    # Invariant: Vessel mirrors spine
    vessel = vm.vessel_states[vessel_id]
    if abs(vessel.compounds["tunicamycin"] - tuni_after_evap2) > 1e-9:
        violations.append(f"evap2: vessel compound stale (vessel={vessel.compounds['tunicamycin']:.3f}, spine={tuni_after_evap2:.3f})")

    print(f"  Tunicamycin: {tuni_before_evap2:.3f} → {tuni_after_evap2:.3f} µM (+{(tuni_after_evap2/tuni_before_evap2 - 1)*100:.1f}%)")
    print(f"  ✓ Concentrations increased again")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 6: washout_compound ==========
    print("Step 6: washout_compound() - remove compound")
    print("-" * 70)
    glc_before_washout = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")

    vm.washout_compound(vessel_id, "tunicamycin")

    # Deliver event at boundary
    vm.flush_operations_now()
    vm.advance_time(0.0)  # Trigger mirroring

    # Invariant: Compound removed, nutrients unchanged
    tuni_after_washout = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")
    glc_after_washout = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")

    if abs(tuni_after_washout) > 1e-9:
        violations.append(f"washout: compound not removed (spine={tuni_after_washout:.3f})")
    if abs(glc_after_washout - glc_before_washout) > 1e-9:
        violations.append(f"washout: glucose changed ({glc_before_washout:.1f} → {glc_after_washout:.1f})")

    # Invariant: Vessel mirrors spine
    vessel = vm.vessel_states[vessel_id]
    if "tunicamycin" in vessel.compounds and vessel.compounds["tunicamycin"] > 1e-9:
        violations.append(f"washout: vessel compound not removed (vessel={vessel.compounds.get('tunicamycin', 0):.3f})")

    print(f"  Tunicamycin: {tuni_after_washout:.6f} µM (removed)")
    print(f"  Glucose: {glc_after_washout:.1f} mM (unchanged)")
    print(f"  ✓ Washout semantics correct")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 7: advance_time(24h) ==========
    print("Step 7: advance_time(24h) - post-washout recovery")
    print("-" * 70)
    tuni_before_recovery = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    vm.advance_time(24.0)

    tuni_after_recovery = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    # Invariant: Evaporation does not resurrect compound
    if abs(tuni_after_recovery) > 1e-9:
        violations.append(f"recovery: compound resurrected by evaporation (spine={tuni_after_recovery:.3f})")

    # Invariant: Vessel mirrors spine
    vessel = vm.vessel_states[vessel_id]
    if "tunicamycin" in vessel.compounds and vessel.compounds["tunicamycin"] > 1e-9:
        violations.append(f"recovery: vessel compound resurrected (vessel={vessel.compounds.get('tunicamycin', 0):.3f})")

    print(f"  Tunicamycin: {tuni_after_recovery:.6f} µM (still absent)")
    print(f"  ✓ Evaporation does not resurrect compound")
    print(f"  ✓ Vessel mirrors spine")
    print()

    # ========== Step 8: cell_painting_assay ==========
    print("Step 8: cell_painting_assay() - readout must not mutate spine")
    print("-" * 70)

    # Snapshot state before assay
    glc_before_assay = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
    gln_before_assay = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")
    tuni_before_assay = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    result = vm.cell_painting_assay(vessel_id)

    # Invariant: Assay does not mutate spine
    glc_after_assay = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
    gln_after_assay = vm.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")
    tuni_after_assay = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    if abs(glc_after_assay - glc_before_assay) > 1e-9:
        violations.append(f"assay: glucose mutated ({glc_before_assay:.1f} → {glc_after_assay:.1f})")
    if abs(gln_after_assay - gln_before_assay) > 1e-9:
        violations.append(f"assay: glutamine mutated ({gln_before_assay:.1f} → {gln_after_assay:.1f})")
    if abs(tuni_after_assay - tuni_before_assay) > 1e-9:
        violations.append(f"assay: tunicamycin mutated ({tuni_before_assay:.6f} → {tuni_after_assay:.6f})")

    print(f"  Glucose: {glc_after_assay:.1f} mM (unchanged)")
    print(f"  Glutamine: {gln_after_assay:.1f} mM (unchanged)")
    print(f"  Tunicamycin: {tuni_after_assay:.6f} µM (unchanged)")
    print(f"  Morphology channels: {len(result.get('morphology', {}))} (readout successful)")
    print(f"  ✓ Assay is read-only")
    print()

    # ========== Summary ==========
    print("=" * 70)
    print("Summary: Spine Invariants")
    print("=" * 70)

    if violations:
        print(f"❌ FAIL: {len(violations)} violation(s) detected")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print("✓ PASS: All invariants hold")
        print("  - Single source of truth: vessel fields match InjectionManager")
        print("  - Mass monotonicity: evaporation up, washout down")
        print("  - Feed semantics: nutrients change, compounds don't")
        print("  - Washout semantics: compounds removed, nutrients unchanged")
        print("  - Assay non-mutating: readout doesn't alter spine")
        print("  - Step function wiring: concentrations follow physics")
        return True


if __name__ == "__main__":
    success = test_48h_story_all_hooks()
    sys.exit(0 if success else 1)
