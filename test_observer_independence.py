#!/usr/bin/env python3
"""
Observer Independence Test (Option 2 Validation)

Verify that attrition is physics-based, not observation-dependent.
Cell fate must be identical whether you call cell_painting_assay or not.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

def run_simulation(call_painting: bool, seed: int = 42, deterministic: bool = True) -> dict:
    """
    Run simulation with or without calling cell_painting_assay.

    Args:
        call_painting: If True, call cell_painting_assay every 12h
        seed: Random seed for reproducibility
        deterministic: If True, disable all noise (pure physics test)

    Returns:
        Dict with final viability, death_mode, death_compound
    """
    np.random.seed(seed)
    hardware = BiologicalVirtualMachine(seed=seed)

    # Make test deterministic by disabling noise
    if deterministic:
        # Override noise parameters to zero
        for cell_line in hardware.cell_line_params:
            hardware.cell_line_params[cell_line]['biological_cv'] = 0.0
            hardware.cell_line_params[cell_line]['cell_count_cv'] = 0.0
            hardware.cell_line_params[cell_line]['viability_cv'] = 0.0

        # Disable technical noise if thalamus params loaded
        if hasattr(hardware, 'thalamus_params') and hardware.thalamus_params:
            hardware.thalamus_params['biological_noise']['cell_line_cv'] = 0.0
            hardware.thalamus_params['biological_noise']['stress_cv_multiplier'] = 1.0
            hardware.thalamus_params['technical_noise']['plate_cv'] = 0.0
            hardware.thalamus_params['technical_noise']['day_cv'] = 0.0
            hardware.thalamus_params['technical_noise']['operator_cv'] = 0.0
            hardware.thalamus_params['technical_noise']['well_cv'] = 0.0
            hardware.thalamus_params['technical_noise']['edge_effect'] = 0.0
            hardware.thalamus_params['technical_noise']['well_failure_rate'] = 0.0

    vessel_id = "TEST_WELL"
    cell_line = "iPSC_NGN2"
    compound = "nocodazole"
    dose_uM = 2.0  # Dose where attrition matters (IC50=1.93, so dose_ratio=1.04)
                   # Instant: ~50% viability, then attrition continues

    # Seed cells with perfect viability (no seeding stress, for clean accounting)
    hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6, initial_viability=1.0)

    # Incubate for attachment (4h)
    hardware.advance_time(4.0)

    # Apply compound
    hardware.treat_with_compound(vessel_id, compound, dose_uM)

    # Advance to 96h in 12h steps
    timepoints = [12.0, 24.0, 36.0, 48.0, 60.0, 72.0, 84.0, 96.0]
    for tp in timepoints:
        # Advance time to this timepoint (from last position)
        if tp == 12.0:
            dt = tp - 4.0  # From 4h (after treatment) to 12h
        else:
            prev_tp = timepoints[timepoints.index(tp) - 1]
            dt = tp - prev_tp

        hardware.advance_time(dt)

        # Optionally call cell_painting_assay
        if call_painting:
            hardware.cell_painting_assay(
                vessel_id,
                plate_id='P1',
                day=1,
                operator='Test',
                well_position='A1'
            )

    # Get final state
    vessel = hardware.vessel_states[vessel_id]

    return {
        'viability': vessel.viability,
        'death_mode': vessel.death_mode,
        'death_compound': vessel.death_compound,
        'cell_count': vessel.cell_count
    }


print("=" * 100)
print("OBSERVER INDEPENDENCE TEST (Option 2 Validation)")
print("=" * 100)
print()
print("Testing: iPSC_NGN2 neurons with 2.0 µM nocodazole @ 96h")
print("  Dose ratio: ~1.04× IC50 (attrition threshold)")
print("  Expected instant: ~50% viability, then attrition continues")
print()
print("Condition A: Only advance_time() calls (no cell_painting)")
print("Condition B: advance_time() + cell_painting() every 12h")
print()
print("-" * 100)

# Run both conditions with same seed
result_no_painting = run_simulation(call_painting=False, seed=42)
result_with_painting = run_simulation(call_painting=True, seed=42)

print(f"{'Metric':<25} {'No Painting (A)':<20} {'With Painting (B)':<20} {'Match?':<10}")
print("-" * 100)

# Compare viability (exact equality in deterministic mode)
viability_a = result_no_painting['viability']
viability_b = result_with_painting['viability']
viability_match = viability_a == viability_b  # Exact equality (deterministic test)
print(f"{'Viability':<25} {viability_a:>6.1%}{'':<13} {viability_b:>6.1%}{'':<13} {'✓' if viability_match else '✗ FAIL':<10}")

# Compare death mode
death_mode_a = result_no_painting['death_mode']
death_mode_b = result_with_painting['death_mode']
death_mode_match = death_mode_a == death_mode_b
print(f"{'Death mode':<25} {str(death_mode_a):<20} {str(death_mode_b):<20} {'✓' if death_mode_match else '✗ FAIL':<10}")

# Compare death compound
death_compound_a = result_no_painting['death_compound']
death_compound_b = result_with_painting['death_compound']
death_compound_match = abs(death_compound_a - death_compound_b) < 0.01
print(f"{'Death compound':<25} {death_compound_a:>6.1%}{'':<13} {death_compound_b:>6.1%}{'':<13} {'✓' if death_compound_match else '✗ FAIL':<10}")

# Compare cell count
cell_count_a = result_no_painting['cell_count']
cell_count_b = result_with_painting['cell_count']
cell_count_match = abs(cell_count_a - cell_count_b) / max(cell_count_a, cell_count_b) < 0.01  # 1% tolerance
print(f"{'Cell count':<25} {cell_count_a:>8.2e}{'':<11} {cell_count_b:>8.2e}{'':<11} {'✓' if cell_count_match else '✗ FAIL':<10}")

print()
print("=" * 100)

# Final verdict
all_match = viability_match and death_mode_match and death_compound_match and cell_count_match

if all_match:
    print("✅ PASS: Attrition is observer-independent (Option 2 working correctly)")
    print("Cell fate is identical whether you call cell_painting_assay or not.")
else:
    print("❌ FAIL: Attrition is observer-dependent (Option 1 behavior detected)")
    print("Cell fate differs based on whether cell_painting_assay was called.")
    print("This means dysfunction is cached from imaging, not computed from physics.")

print("=" * 100)
