#!/usr/bin/env python3
"""
Phase 2 Sanity Check: Minimal simulation to verify VM is functional after subpop removal.

Tests:
- One vessel, one compound, 24h simulation
- No AttributeErrors
- Viability stays in [0, 1]
- Cell count stays non-negative
- Death ledgers obey conservation law
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, DEATH_EPS

def main():
    print("=== Phase 2 Sanity Check ===\n")

    # Create VM
    print("1. Creating BiologicalVirtualMachine...")
    vm = BiologicalVirtualMachine(seed=42)
    print(f"   ✓ VM created (simulated_time={vm.simulated_time:.1f}h)")

    # Seed vessel
    print("\n2. Seeding vessel...")
    vm.seed_vessel("P1_A01", "A549", vessel_type="96-well")
    vessel = vm.vessel_states["P1_A01"]
    print(f"   ✓ Vessel seeded (count={vessel.cell_count:.0f}, viability={vessel.viability:.3f})")

    # Treat with compound
    print("\n3. Treating with compound (staurosporine 1.0 µM)...")
    result = vm.treat_with_compound("P1_A01", "staurosporine", 1.0)
    print(f"   ✓ Treatment applied (viability={vessel.viability:.3f})")

    # Run 24h simulation in 1h steps
    print("\n4. Running 24h simulation (1h steps)...")
    for hour in range(1, 25):
        vm.advance_time(1.0)

        # Assert invariants
        v = vessel.viability
        c = vessel.cell_count

        assert 0.0 <= v <= 1.0, f"Viability out of bounds at t={hour}h: {v}"
        assert c >= 0.0, f"Cell count negative at t={hour}h: {c}"

        # Check conservation
        total_dead = 1.0 - v
        tracked = (
            vessel.death_compound +
            vessel.death_starvation +
            vessel.death_mitotic_catastrophe +
            vessel.death_er_stress +
            vessel.death_mito_dysfunction +
            vessel.death_confluence +
            vessel.death_unknown
        )

        assert tracked <= total_dead + DEATH_EPS, \
            f"Conservation violation at t={hour}h: tracked={tracked:.6f} > total_dead={total_dead:.6f}"

        if hour % 6 == 0:
            print(f"   t={hour:2d}h: viability={v:.3f}, count={c:.0f}, death_compound={vessel.death_compound:.3f}")

    print(f"\n   ✓ Simulation completed (final viability={vessel.viability:.3f})")

    # Final checks
    print("\n5. Final invariant checks...")
    assert 0.0 <= vessel.viability <= 1.0, "Final viability out of bounds"
    assert vessel.cell_count >= 0.0, "Final cell count negative"

    total_dead = 1.0 - vessel.viability
    tracked = (
        vessel.death_compound +
        vessel.death_starvation +
        vessel.death_mitotic_catastrophe +
        vessel.death_er_stress +
        vessel.death_mito_dysfunction +
        vessel.death_confluence +
        vessel.death_unknown
    )
    unattributed = vessel.death_unattributed

    print(f"   Viability: {vessel.viability:.6f}")
    print(f"   Total dead: {total_dead:.6f}")
    print(f"   Tracked causes: {tracked:.6f}")
    print(f"   Unattributed: {unattributed:.6f}")
    print(f"   Conservation: {tracked + unattributed:.6f} ~= {total_dead:.6f}")

    assert tracked <= total_dead + DEATH_EPS, \
        f"Conservation violated: tracked={tracked:.6f} > total_dead={total_dead:.6f}"

    print("\n✅ ALL CHECKS PASSED - VM is functional after Phase 2!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ SANITY CHECK FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
