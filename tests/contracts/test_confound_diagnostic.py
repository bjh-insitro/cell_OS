"""
Diagnostic: Check if EC50 manipulation is actually working
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def test_ec50_manipulation():
    """
    Test whether modifying thalamus_params EC50 actually changes biology.
    """
    print("=" * 70)
    print("DIAGNOSTIC: EC50 Manipulation Check")
    print("=" * 70)

    # Create two VMs: one baseline, one with EC50 shifted
    rc = RunContext.sample(seed=42)

    vm_baseline = BiologicalVirtualMachine(seed=42, run_context=rc)
    vm_baseline._load_cell_thalamus_params()

    vm_shifted = BiologicalVirtualMachine(seed=42, run_context=rc)
    vm_shifted._load_cell_thalamus_params()

    # Print original thalamus params keys
    print("\n--- Thalamus Params Keys ---")
    print(f"Keys: {list(vm_baseline.thalamus_params.keys())}")

    # Try to modify EC50 (as test does)
    print("\n--- Attempting EC50 Modification ---")
    if 'compound_sensitivity' in vm_shifted.thalamus_params:
        print("✓ compound_sensitivity exists")
        if 'tBHQ' in vm_shifted.thalamus_params['compound_sensitivity']:
            print("✓ tBHQ exists in compound_sensitivity")
            original = vm_shifted.thalamus_params['compound_sensitivity']['tBHQ'].get('A549', 'NOT FOUND')
            print(f"  Original A549 sensitivity: {original}")
            vm_shifted.thalamus_params['compound_sensitivity']['tBHQ']['A549'] = original * 2.0
            print(f"  Modified A549 sensitivity: {vm_shifted.thalamus_params['compound_sensitivity']['tBHQ']['A549']}")
        else:
            print("✗ tBHQ NOT found in compound_sensitivity")
            print(f"  Available: {list(vm_shifted.thalamus_params.get('compound_sensitivity', {}).keys())}")
    else:
        print("✗ compound_sensitivity does NOT exist")

    # Check what key actually exists
    if 'cell_line_ic50_modifiers' in vm_baseline.thalamus_params:
        print("\n✓ cell_line_ic50_modifiers exists (YAML key)")
        print(f"  A549 tBHQ: {vm_baseline.thalamus_params['cell_line_ic50_modifiers'].get('A549', {}).get('tBHQ', 'NOT FOUND')}")

    if 'cell_line_sensitivity' in vm_baseline.thalamus_params:
        print("\n✓ cell_line_sensitivity exists (code expects this)")
    else:
        print("\n✗ cell_line_sensitivity does NOT exist (but code expects it!)")

    # Seed identical wells
    vm_baseline.seed_vessel("A1", "A549", 2000, "96-well")
    vm_shifted.seed_vessel("A1", "A549", 2000, "96-well")

    # Apply same dose
    dose_uM = 30.0  # Nominal EC50
    print(f"\n--- Treating with {dose_uM} µM tBHQ ---")

    vm_baseline.treat_with_compound("A1", "tBHQ", dose_uM)
    vm_shifted.treat_with_compound("A1", "tBHQ", dose_uM)

    # Advance time
    vm_baseline.advance_time(24.0)
    vm_shifted.advance_time(24.0)

    # Compare viabilities
    viab_baseline = vm_baseline.vessel_states["A1"].viability
    viab_shifted = vm_shifted.vessel_states["A1"].viability

    print(f"\nBaseline viability: {viab_baseline:.4f}")
    print(f"Shifted viability:  {viab_shifted:.4f}")
    print(f"Difference:         {abs(viab_baseline - viab_shifted):.4f}")

    if abs(viab_baseline - viab_shifted) < 0.001:
        print("\n❌ FAIL: EC50 modification had NO EFFECT")
        print("   The test's EC50 manipulation is broken!")
    else:
        print("\n✅ PASS: EC50 modification changed viability")
        print("   The manipulation is working correctly.")


if __name__ == "__main__":
    test_ec50_manipulation()
