"""
Enforcement Test B2: Spine Tampering Is Ignored

The "petty and necessary" test.

Proves that biology reads InjectionManager, not legacy concentration fields,
by deliberately corrupting legacy fields and asserting results are unchanged.

This prevents future "helpful" refactors from accidentally reintroducing shadow state.

Test Strategy:
1. Run protocol twice with same seed
2. In run #2, monkeypatch vessel.compounds to nonsense mid-protocol
3. Assert final state is identical (biology ignored the tampering)
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def run_protocol(vm, vessel_id, tamper=False):
    """
    Run mini-protocol and optionally tamper with legacy fields.

    Returns: (final_viability, final_death_compound, final_concentration)
    """
    # seed
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=1.0)

    # treat
    vm.treat_with_compound(vessel_id, "tunicamycin", 1.5)

    # step 24h (accumulate some attrition)
    vm.advance_time(24.0)

    # TAMPERING: Corrupt vessel.compounds to nonsense
    if tamper:
        vessel = vm.vessel_states[vessel_id]
        # Store true value from spine
        true_conc = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")
        # Corrupt vessel field to 10× wrong value
        vessel.compounds["tunicamycin"] = 15.0  # Should be ~1.54 µM, now nonsense
        print(f"  ⚠ TAMPERED: vessel.compounds['tunicamycin'] = 15.0 µM (spine={true_conc:.3f} µM)")

    # step another 24h (if biology reads corrupted field, death will differ)
    vm.advance_time(24.0)

    vessel = vm.vessel_states[vessel_id]
    final_viability = vessel.viability
    final_death_compound = vessel.death_compound
    final_conc_spine = vm.injection_mgr.get_compound_concentration_uM(vessel_id, "tunicamycin")

    return final_viability, final_death_compound, final_conc_spine


def test_spine_tampering_ignored():
    """
    Run protocol twice (same seed), tamper with legacy fields in run #2,
    assert final state is identical.
    """
    print("=" * 70)
    print("Enforcement Test B2: Spine Tampering Is Ignored")
    print("=" * 70)
    print()

    vessel_id = "Plate1_D06"
    seed = 123

    # ========== Run 1: Clean (no tampering) ==========
    print("Run 1: Clean (no tampering)")
    print("-" * 70)
    vm1 = BiologicalVirtualMachine(seed=seed)
    via1, death1, conc1 = run_protocol(vm1, vessel_id, tamper=False)
    print(f"  Final viability: {via1:.6f}")
    print(f"  Final death_compound: {death1:.6f}")
    print(f"  Final concentration (spine): {conc1:.3f} µM")
    print()

    # ========== Run 2: Tampered (corrupt vessel.compounds mid-protocol) ==========
    print("Run 2: Tampered (corrupt vessel.compounds mid-protocol)")
    print("-" * 70)
    vm2 = BiologicalVirtualMachine(seed=seed)
    via2, death2, conc2 = run_protocol(vm2, vessel_id, tamper=True)
    print(f"  Final viability: {via2:.6f}")
    print(f"  Final death_compound: {death2:.6f}")
    print(f"  Final concentration (spine): {conc2:.3f} µM")
    print()

    # ========== Assertions ==========
    print("=" * 70)
    print("Assertion: Tampering Had No Effect")
    print("=" * 70)

    violations = []

    # Viability should match exactly (same seed, same physics)
    if abs(via1 - via2) > 1e-9:
        violations.append(f"Viability differs: clean={via1:.6f}, tampered={via2:.6f}")

    # Death accounting should match exactly
    if abs(death1 - death2) > 1e-9:
        violations.append(f"Death differs: clean={death1:.6f}, tampered={death2:.6f}")

    # Concentrations should match exactly (spine is authoritative)
    if abs(conc1 - conc2) > 1e-9:
        violations.append(f"Concentration differs: clean={conc1:.3f}, tampered={conc2:.3f}")

    if violations:
        print("❌ FAIL: Tampering affected results (biology reads legacy fields!)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("This means biology is reading vessel.compounds instead of InjectionManager.")
        print("Shadow state detected. The spine is decoration, not constitution.")
        return False
    else:
        print("✓ PASS: Tampering had no effect")
        print("  Biology reads InjectionManager, ignores corrupted vessel.compounds")
        print("  The spine is the constitution.")
        return True


if __name__ == "__main__":
    success = test_spine_tampering_ignored()
    sys.exit(0 if success else 1)
