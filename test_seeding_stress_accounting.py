#!/usr/bin/env python3
"""
Seeding Stress Accounting Test

Verify that accounting correctly handles unknown death from seeding stress.

Tests the complete partition: death_compound + death_confluence + death_unknown = 1 - viability

This validates the philosophy:
- Unknown death is tracked honestly (not invented as "compound")
- After treatment, compound death adds on top of seeding stress
- Accounting doesn't rewrite history
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

def run_with_seeding_stress(seed: int = 42) -> dict:
    """
    Run simulation with realistic seeding stress (viability=0.98).

    Protocol:
    - Seed with 98% viability (2% seeding stress)
    - Wait 4h (no treatment)
    - Treat with nocodazole (2.0 µM)
    - Measure at 96h

    Expected accounting:
    - Before treatment: death_unknown ≈ 0.02, death_mode="unknown"
    - After treatment: death_compound adds on top, death_mode="compound"
    - Final: death_compound + death_unknown ≈ 1 - viability
    """
    np.random.seed(seed)
    hardware = BiologicalVirtualMachine(seed=seed)

    # Disable noise for deterministic test
    for cell_line in hardware.cell_line_params:
        hardware.cell_line_params[cell_line]['biological_cv'] = 0.0

    vessel_id = "TEST_WELL"
    cell_line = "iPSC_NGN2"
    compound = "nocodazole"
    dose_uM = 2.0

    # Seed with realistic stress (default viability=0.98)
    hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6)  # No initial_viability override

    # Incubate for attachment (4h) - no treatment yet
    hardware.advance_time(4.0)

    # Check accounting before treatment
    vessel = hardware.vessel_states[vessel_id]
    before_treatment = {
        'viability': vessel.viability,
        'death_compound': vessel.death_compound,
        'death_confluence': vessel.death_confluence,
        'death_unknown': vessel.death_unknown,
        'death_mode': vessel.death_mode
    }

    # Apply compound
    hardware.treat_with_compound(vessel_id, compound, dose_uM)

    # Advance to 96h
    remaining_time = 92.0  # 96h - 4h
    while remaining_time > 0:
        dt = min(12.0, remaining_time)
        hardware.advance_time(dt)
        remaining_time -= dt

    # Get final state
    vessel = hardware.vessel_states[vessel_id]

    return {
        'before_treatment': before_treatment,
        'after_treatment': {
            'viability': vessel.viability,
            'death_compound': vessel.death_compound,
            'death_confluence': vessel.death_confluence,
            'death_unknown': vessel.death_unknown,
            'death_mode': vessel.death_mode
        }
    }


print("=" * 100)
print("SEEDING STRESS ACCOUNTING TEST")
print("=" * 100)
print()
print("Protocol:")
print("  - Seed with 98% viability (2% seeding stress)")
print("  - Wait 4h (no treatment)")
print("  - Treat with 2.0 µM nocodazole")
print("  - Measure at 96h")
print()
print("Expected:")
print("  Before treatment: death_unknown ≈ 0.02, death_mode='unknown'")
print("  After treatment: death_compound + death_unknown ≈ 1 - viability")
print()
print("-" * 100)

result = run_with_seeding_stress(seed=42)

before = result['before_treatment']
after = result['after_treatment']

print()
print("BEFORE TREATMENT (4h):")
print(f"  Viability: {before['viability']:.1%}")
print(f"  Death compound: {before['death_compound']:.1%}")
print(f"  Death confluence: {before['death_confluence']:.1%}")
print(f"  Death unknown: {before['death_unknown']:.1%}")
print(f"  Death mode: {before['death_mode']}")
print()

# Check seeding stress accounting
seeding_stress_expected = 0.02  # 2% from viability=0.98
seeding_stress_actual = before['death_unknown']
seeding_stress_match = abs(seeding_stress_actual - seeding_stress_expected) < 0.001

print("  Seeding stress accounting:")
print(f"    Expected: {seeding_stress_expected:.1%}")
print(f"    Actual: {seeding_stress_actual:.1%}")
print(f"    Status: {'✓ PASS' if seeding_stress_match else '✗ FAIL'}")
print()

# Check death mode is "unknown" before treatment
death_mode_before_correct = before['death_mode'] == 'unknown'
print(f"  Death mode before treatment: {before['death_mode']} {'✓' if death_mode_before_correct else '✗ (expected unknown)'}")
print()

print("=" * 100)
print("AFTER TREATMENT (96h):")
print(f"  Viability: {after['viability']:.1%}")
print(f"  Death compound: {after['death_compound']:.1%}")
print(f"  Death confluence: {after['death_confluence']:.1%}")
print(f"  Death unknown: {after['death_unknown']:.1%}")
print(f"  Death mode: {after['death_mode']}")
print()

# Check complete partition
total_dead = 1.0 - after['viability']
total_tracked = after['death_compound'] + after['death_confluence'] + after['death_unknown']
partition_satisfied = abs(total_tracked - total_dead) < 0.001

print("  Complete accounting partition:")
print(f"    Total dead: {total_dead:.1%} (1 - viability)")
print(f"    Total tracked: {total_tracked:.1%} (compound + confluence + unknown)")
print(f"    Difference: {abs(total_tracked - total_dead):.4%}")
print(f"    Status: {'✓ PASS' if partition_satisfied else '✗ FAIL'}")
print()

# Check death mode is "compound" after treatment (compound >> unknown)
death_mode_after_correct = after['death_mode'] == 'compound'
print(f"  Death mode after treatment: {after['death_mode']} {'✓' if death_mode_after_correct else '✗ (expected compound)'}")
print()

# Check that seeding stress persists (doesn't get rewritten)
seeding_stress_persists = abs(after['death_unknown'] - seeding_stress_expected) < 0.01  # 1% tolerance
print(f"  Seeding stress persists: {after['death_unknown']:.1%} ≈ {seeding_stress_expected:.1%} {'✓' if seeding_stress_persists else '✗'}")
print()

# Check that compound death adds on top
compound_death_added = after['death_compound'] > 0.30  # Should be ~48% compound death
print(f"  Compound death added: {after['death_compound']:.1%} {'✓' if compound_death_added else '✗ (expected >30%)'}")
print()

print("=" * 100)

# Final verdict
all_pass = (
    seeding_stress_match and
    death_mode_before_correct and
    partition_satisfied and
    death_mode_after_correct and
    seeding_stress_persists and
    compound_death_added
)

if all_pass:
    print("✅ ALL TESTS PASS")
    print("  - Seeding stress tracked as unknown: ✓")
    print("  - Death mode before treatment: ✓")
    print("  - Complete partition maintained: ✓")
    print("  - Death mode after treatment: ✓")
    print("  - Seeding stress not rewritten: ✓")
    print("  - Compound death adds on top: ✓")
else:
    print("❌ TEST FAILED")
    if not seeding_stress_match:
        print("  - Seeding stress tracking: ✗")
    if not death_mode_before_correct:
        print("  - Death mode before treatment: ✗")
    if not partition_satisfied:
        print("  - Complete partition: ✗")
    if not death_mode_after_correct:
        print("  - Death mode after treatment: ✗")
    if not seeding_stress_persists:
        print("  - Seeding stress rewritten: ✗")
    if not compound_death_added:
        print("  - Compound death not added: ✗")

print("=" * 100)
