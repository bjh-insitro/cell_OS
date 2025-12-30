"""
Phase 2 Bridge Test: Verify VM runs end-to-end without subpopulations.

This test is the canary that proves no hidden subpop code paths remain.
If this passes, the VM is functional for Attack 3.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def test_vm_runs_without_subpops():
    """
    Phase 2 bridge test: VM completes a run end-to-end.

    Tests:
    - Seed vessel
    - Apply compound
    - Step time (48h in 6h increments)
    - Measure viability + morphology
    - No exceptions, viability bounded, morphology finite
    """
    print("=" * 80)
    print("PHASE 2 BRIDGE TEST: VM End-to-End Without Subpopulations")
    print("=" * 80)

    # Create VM
    rc = RunContext.sample(seed=42)
    vm = BiologicalVirtualMachine(seed=42, run_context=rc)
    vm._load_cell_thalamus_params()

    print("\n1. Seeding vessel A1 with A549 cells...")
    vm.seed_vessel("A1", "A549", initial_count=2000, vessel_type="96-well")

    print("2. Applying tBHQ at 30 µM...")
    vm.treat_with_compound("A1", "tBHQ", 30.0)

    print("3. Stepping time (48h in 6h increments)...")
    for i in range(8):
        vm.advance_time(6.0)
        t = vm.simulated_time
        v = vm.vessel_states["A1"].viability
        print(f"   t={t:.1f}h: viability={v:.3f}")

    print("4. Measuring viability and morphology...")
    vessel = vm.vessel_states["A1"]
    obs = vm.cell_painting_assay("A1")

    # Assert sanity
    print("\n5. Assertions...")
    assert 0.0 <= vessel.viability <= 1.0, \
        f"❌ Bad viability: {vessel.viability}"
    print(f"   ✓ Viability bounded: {vessel.viability:.3f}")

    assert vessel.cell_count >= 0.0, \
        f"❌ Negative cell count: {vessel.cell_count}"
    print(f"   ✓ Cell count non-negative: {vessel.cell_count:.0f}")

    morph_values = list(obs['morphology'].values())
    assert all(np.isfinite(v) for v in morph_values), \
        f"❌ Non-finite morphology: {obs['morphology']}"
    print(f"   ✓ Morphology finite: {morph_values}")

    assert hasattr(vessel, '_hazards'), \
        "❌ Missing vessel._hazards field"
    print(f"   ✓ Vessel has _hazards field")

    assert hasattr(vessel, '_total_hazard'), \
        "❌ Missing vessel._total_hazard field"
    print(f"   ✓ Vessel has _total_hazard field: {vessel._total_hazard:.4f}")

    assert hasattr(vessel, 'er_stress'), \
        "❌ Missing vessel.er_stress field"
    print(f"   ✓ Vessel has er_stress field: {vessel.er_stress:.4f}")

    print("\n" + "=" * 80)
    print("✅ BRIDGE TEST PASSED")
    print("=" * 80)
    print(f"Final state: viability={vessel.viability:.3f}, cells={vessel.cell_count:.0f}")
    print("VM is functional. Ready for Attack 3.")


if __name__ == "__main__":
    test_vm_runs_without_subpops()
