#!/usr/bin/env python3
"""
Double Dosing Accounting Test

Verify that death accounting doesn't drift with multiple treatment events.

Tests the invariant: death_compound <= 1 - viability
(i.e., tracked compound death can't exceed actual total death)
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

def run_double_dosing(call_painting: bool, seed: int = 42) -> dict:
    """
    Run simulation with two dosing events.

    Args:
        call_painting: If True, call cell_painting_assay every 12h
        seed: Random seed for reproducibility

    Returns:
        Dict with final viability, death_compound, death_mode
    """
    np.random.seed(seed)
    hardware = BiologicalVirtualMachine(seed=seed)

    # Disable noise for deterministic test
    for cell_line in hardware.cell_line_params:
        hardware.cell_line_params[cell_line]['biological_cv'] = 0.0

    vessel_id = "TEST_WELL"
    cell_line = "iPSC_NGN2"
    compound = "nocodazole"
    dose_uM = 2.0  # Dose at IC50 threshold

    # Seed cells with perfect viability (no seeding stress, for clean accounting)
    hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6, initial_viability=1.0)

    # Incubate for attachment (4h)
    hardware.advance_time(4.0)

    # First dose at t=4h
    hardware.treat_with_compound(vessel_id, compound, dose_uM)

    # Advance 48h (with optional painting)
    for step in range(4):  # 4 × 12h = 48h
        hardware.advance_time(12.0)
        if call_painting:
            hardware.cell_painting_assay(
                vessel_id,
                plate_id='P1',
                day=1,
                operator='Test',
                well_position='A1'
            )

    # Second dose at t=52h
    hardware.treat_with_compound(vessel_id, compound, dose_uM)

    # Advance to 96h (another 44h)
    remaining = [12.0, 12.0, 12.0, 8.0]  # 44h total
    for dt in remaining:
        hardware.advance_time(dt)
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
        'death_compound': vessel.death_compound,
        'death_confluence': vessel.death_confluence,
        'death_mode': vessel.death_mode,
        'cell_count': vessel.cell_count
    }


print("=" * 100)
print("DOUBLE DOSING ACCOUNTING TEST")
print("=" * 100)
print()
print("Protocol:")
print("  t=4h:  First dose (2.0 µM nocodazole)")
print("  t=52h: Second dose (2.0 µM nocodazole)")
print("  t=96h: Final measurement")
print()
print("Tests:")
print("  1. Observer independence (A vs B)")
print("  2. Accounting invariant: death_compound <= 1 - viability")
print("  3. Death mode labeled correctly")
print()
print("-" * 100)

# Run both conditions
result_no_painting = run_double_dosing(call_painting=False, seed=42)
result_with_painting = run_double_dosing(call_painting=True, seed=42)

print(f"{'Metric':<25} {'No Painting (A)':<20} {'With Painting (B)':<20} {'Match?':<10}")
print("-" * 100)

# Compare viability
viability_a = result_no_painting['viability']
viability_b = result_with_painting['viability']
viability_match = viability_a == viability_b
print(f"{'Viability':<25} {viability_a:>6.1%}{'':<13} {viability_b:>6.1%}{'':<13} {'✓' if viability_match else '✗ FAIL':<10}")

# Compare death compound
death_compound_a = result_no_painting['death_compound']
death_compound_b = result_with_painting['death_compound']
death_compound_match = death_compound_a == death_compound_b
print(f"{'Death compound':<25} {death_compound_a:>6.1%}{'':<13} {death_compound_b:>6.1%}{'':<13} {'✓' if death_compound_match else '✗ FAIL':<10}")

# Compare death mode
death_mode_a = result_no_painting['death_mode']
death_mode_b = result_with_painting['death_mode']
death_mode_match = death_mode_a == death_mode_b
print(f"{'Death mode':<25} {str(death_mode_a):<20} {str(death_mode_b):<20} {'✓' if death_mode_match else '✗ FAIL':<10}")

print()
print("=" * 100)
print("ACCOUNTING INVARIANT CHECK")
print("=" * 100)

# Check invariant for both runs
for name, result in [("No Painting (A)", result_no_painting), ("With Painting (B)", result_with_painting)]:
    viability = result['viability']
    death_compound = result['death_compound']
    death_confluence = result['death_confluence']

    total_dead = 1.0 - viability
    total_tracked = death_compound + death_confluence

    # Invariant: tracked death should equal total death (if accounting is correct)
    # With perfect initial viability, we expect tight accounting (0.1% tolerance)
    eps = 0.001  # 0.1% tolerance
    invariant_satisfied = abs(total_tracked - total_dead) < eps

    print(f"\n{name}:")
    print(f"  Viability: {viability:.6f}")
    print(f"  Total dead: {total_dead:.6f} (1 - viability)")
    print(f"  Death compound: {death_compound:.6f}")
    print(f"  Death confluence: {death_confluence:.6f}")
    print(f"  Total tracked: {total_tracked:.6f}")
    print(f"  Untracked death: {total_dead - total_tracked:.6f}")
    print(f"  Invariant: death_compound + death_confluence ≈ 1 - viability (±0.1%)")
    print(f"  Status: {'✓ PASS' if invariant_satisfied else '✗ FAIL'}")

print()
print("=" * 100)

# Final verdict
all_match = viability_match and death_compound_match and death_mode_match

# Check invariant satisfaction (with 0.1% tolerance for perfect seeding)
eps = 0.001
invariant_a = abs((result_no_painting['death_compound'] + result_no_painting['death_confluence']) - (1.0 - result_no_painting['viability'])) < eps
invariant_b = abs((result_with_painting['death_compound'] + result_with_painting['death_confluence']) - (1.0 - result_with_painting['viability'])) < eps

if all_match and invariant_a and invariant_b:
    print("✅ ALL TESTS PASS")
    print("  - Observer independence: ✓")
    print("  - Accounting invariant: ✓")
    print("  - Multiple treatments handled correctly: ✓")
else:
    print("❌ TEST FAILED")
    if not all_match:
        print("  - Observer independence: ✗ (A ≠ B)")
    if not (invariant_a and invariant_b):
        print("  - Accounting invariant: ✗ (death fractions don't partition total death)")

print("=" * 100)
