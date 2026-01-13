"""
Trace internal simulator states to find where EC50 shift vs dose error diverge.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.biology import biology_core


def trace_conditions():
    """
    Compare internal states for EC50 shift vs dose error.
    """
    print("=" * 80)
    print("TRACE: EC50 Shift vs Dose Error Internal States")
    print("=" * 80)

    # Fixed seed for reproducibility
    seed = 42
    rc = RunContext.sample(seed=seed)

    # Condition A: EC50 × 2 (biology shift)
    vm_A = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm_A._load_cell_thalamus_params()

    # Create cell_line_sensitivity dict
    if 'cell_line_sensitivity' not in vm_A.thalamus_params:
        vm_A.thalamus_params['cell_line_sensitivity'] = {}
    if 'tBHQ' not in vm_A.thalamus_params['cell_line_sensitivity']:
        vm_A.thalamus_params['cell_line_sensitivity']['tBHQ'] = {}

    # EC50 × 2
    vm_A.thalamus_params['cell_line_sensitivity']['tBHQ']['A549'] = 2.0

    # Condition B: Dose × 0.5 (dose error)
    vm_B = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm_B._load_cell_thalamus_params()

    # Seed identical wells
    vm_A.seed_vessel("A1", "A549", initial_count=2000, capacity=1e7, vessel_type="96-well")
    vm_B.seed_vessel("A1", "A549", initial_count=2000, capacity=1e7, vessel_type="96-well")

    # Get nominal EC50 from thalamus params
    nominal_ec50 = vm_A.thalamus_params['compounds']['tBHQ']['ec50_uM']
    hill_slope = vm_A.thalamus_params['compounds']['tBHQ']['hill_slope']

    print(f"\nBase EC50: {nominal_ec50} µM")
    print(f"Hill slope: {hill_slope}")

    # Test dose: 1× nominal EC50
    nominal_dose = nominal_ec50

    print(f"\n--- Condition A: EC50 × 2, Dose = {nominal_dose} µM ---")
    print(f"  Effective EC50 = {nominal_ec50 * 2.0} µM")
    print(f"  Dose/EC50 ratio = {nominal_dose / (nominal_ec50 * 2.0):.3f}")

    print(f"\n--- Condition B: EC50 constant, Dose = {nominal_dose * 0.5} µM ---")
    print(f"  Effective EC50 = {nominal_ec50} µM")
    print(f"  Dose/EC50 ratio = {(nominal_dose * 0.5) / nominal_ec50:.3f}")

    print("\n→ Both should have Dose/EC50 = 0.5, so Hill effects should match")

    # Apply treatments
    vm_A.treat_with_compound("A1", "tBHQ", nominal_dose)
    vm_B.treat_with_compound("A1", "tBHQ", nominal_dose * 0.5)

    # Check instant viability effects
    print("\n--- Instant Viability Effects ---")
    viab_A_t0 = vm_A.vessel_states["A1"].viability
    viab_B_t0 = vm_B.vessel_states["A1"].viability
    print(f"  Condition A: {viab_A_t0:.4f}")
    print(f"  Condition B: {viab_B_t0:.4f}")
    print(f"  Difference: {abs(viab_A_t0 - viab_B_t0):.6f}")

    if abs(viab_A_t0 - viab_B_t0) > 0.01:
        print("  ⚠️  Instant effects differ (should be equal under Hill model)")
    else:
        print("  ✓ Instant effects match")

    # Trace over time
    print("\n--- Temporal Trace (12h intervals) ---")
    print(f"{'Time (h)':<10} {'Viab_A':<12} {'Viab_B':<12} {'Diff':<12}")
    print("-" * 48)

    for t in [0, 12, 24, 36, 48]:
        if t > 0:
            vm_A.advance_time(12)
            vm_B.advance_time(12)

        viab_A = vm_A.vessel_states["A1"].viability
        viab_B = vm_B.vessel_states["A1"].viability
        diff = viab_A - viab_B

        print(f"{t:<10} {viab_A:<12.4f} {viab_B:<12.4f} {diff:<12.6f}")

    # Check morphology at 24h
    vm_A_24 = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm_A_24._load_cell_thalamus_params()
    if 'cell_line_sensitivity' not in vm_A_24.thalamus_params:
        vm_A_24.thalamus_params['cell_line_sensitivity'] = {}
    if 'tBHQ' not in vm_A_24.thalamus_params['cell_line_sensitivity']:
        vm_A_24.thalamus_params['cell_line_sensitivity']['tBHQ'] = {}
    vm_A_24.thalamus_params['cell_line_sensitivity']['tBHQ']['A549'] = 2.0
    vm_A_24.seed_vessel("A1", "A549", initial_count=2000, capacity=1e7, vessel_type="96-well")
    vm_A_24.treat_with_compound("A1", "tBHQ", nominal_dose)
    vm_A_24.advance_time(24.0)

    vm_B_24 = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm_B_24._load_cell_thalamus_params()
    vm_B_24.seed_vessel("A1", "A549", initial_count=2000, capacity=1e7, vessel_type="96-well")
    vm_B_24.treat_with_compound("A1", "tBHQ", nominal_dose * 0.5)
    vm_B_24.advance_time(24.0)

    morph_A = vm_A_24.cell_painting_assay("A1")['morphology']
    morph_B = vm_B_24.cell_painting_assay("A1")['morphology']

    print("\n--- Morphology at 24h ---")
    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        val_A = morph_A[channel]
        val_B = morph_B[channel]
        diff = val_A - val_B
        print(f"  {channel:<10} A: {val_A:>8.4f}  B: {val_B:>8.4f}  Diff: {diff:>10.6f}")

    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)

    viab_diff_final = abs(vm_A.vessel_states["A1"].viability - vm_B.vessel_states["A1"].viability)

    if viab_diff_final < 0.01:
        print("✅ Viability trajectories match → Scale-invariant")
        print("   Any distinguishability must come from morphology or noise")
    else:
        print("❌ Viability trajectories DIVERGE → NOT scale-invariant")
        print("   Simulator has absolute-concentration dependencies")
        print("\n   Possible causes:")
        print("   - Attrition/hazard uses absolute C, not C/EC50")
        print("   - Stress accumulation has thresholds on absolute C")
        print("   - Time-to-commitment depends on absolute dose")
        print("   - Run context modifiers applied asymmetrically")


if __name__ == "__main__":
    trace_conditions()
