#!/usr/bin/env python3
"""
Stream Isolation Unit Test

Prove that calling cell_painting_assay() ONLY advances rng_assay state,
and does NOT perturb rng_growth or rng_treatment state.

This catches regressions like "I used rng_growth for a well-factor because
it was convenient" which would break observer independence.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

def snapshot_rng_states(hardware):
    """
    Capture bit_generator.state for each RNG stream.

    Returns:
        dict with keys: 'growth', 'treatment', 'assay'
    """
    return {
        'growth': hardware.rng_growth.bit_generator.state,
        'treatment': hardware.rng_treatment.bit_generator.state,
        'assay': hardware.rng_assay.bit_generator.state
    }

def states_equal(state1, state2):
    """
    Compare two bit_generator states.

    States are dicts with keys like {'bit_generator', 'state', ...}
    """
    # Extract the actual state tuple/dict
    s1 = state1['state']
    s2 = state2['state']

    # For PCG64, state is a dict with 'state' and 'inc' keys
    if isinstance(s1, dict) and isinstance(s2, dict):
        return s1['state'] == s2['state'] and s1['inc'] == s2['inc']

    # For other generators, might be tuple or other structure
    return s1 == s2


print("=" * 100)
print("STREAM ISOLATION UNIT TEST")
print("=" * 100)
print()
print("Goal: Prove that cell_painting_assay() ONLY advances rng_assay")
print("      and does NOT touch rng_growth or rng_treatment")
print()
print("-" * 100)

# Setup hardware
hardware = BiologicalVirtualMachine(seed=42)

# Disable noise so we're not just relying on CV=0 guards
for cell_line in hardware.cell_line_params:
    hardware.cell_line_params[cell_line]['biological_cv'] = 0.0

# Seed a vessel and treat
vessel_id = "TEST_WELL"
cell_line = "iPSC_NGN2"
hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6, initial_viability=1.0)
hardware.advance_time(4.0)
hardware.treat_with_compound(vessel_id, "nocodazole", 2.0)

# Snapshot RNG states BEFORE assay
print()
print("Step 1: Snapshot RNG states BEFORE cell_painting_assay()")
states_before = snapshot_rng_states(hardware)
print("  ✓ Captured growth state")
print("  ✓ Captured treatment state")
print("  ✓ Captured assay state")

# Call the assay (this should ONLY touch rng_assay)
print()
print("Step 2: Call cell_painting_assay()")
hardware.cell_painting_assay(
    vessel_id,
    plate_id='P1',
    day=1,
    operator='Test',
    well_position='A1'
)
print("  ✓ Assay completed")

# Snapshot RNG states AFTER assay
print()
print("Step 3: Snapshot RNG states AFTER cell_painting_assay()")
states_after = snapshot_rng_states(hardware)
print("  ✓ Captured growth state")
print("  ✓ Captured treatment state")
print("  ✓ Captured assay state")

# Check which streams changed
print()
print("=" * 100)
print("STREAM ISOLATION RESULTS")
print("=" * 100)

growth_unchanged = states_equal(states_before['growth'], states_after['growth'])
treatment_unchanged = states_equal(states_before['treatment'], states_after['treatment'])
assay_changed = not states_equal(states_before['assay'], states_after['assay'])

print()
print(f"rng_growth:    {'UNCHANGED ✓' if growth_unchanged else 'CHANGED ✗ (ISOLATION BROKEN!)'}")
print(f"rng_treatment: {'UNCHANGED ✓' if treatment_unchanged else 'CHANGED ✗ (ISOLATION BROKEN!)'}")
print(f"rng_assay:     {'CHANGED ✓' if assay_changed else 'UNCHANGED ✗ (NOT BEING USED!)'}")

print()
print("=" * 100)

# Final verdict
isolation_preserved = growth_unchanged and treatment_unchanged and assay_changed

if isolation_preserved:
    print("✅ PASS: Stream isolation preserved")
    print()
    print("  - cell_painting_assay() does NOT perturb physics RNG streams")
    print("  - Observer independence guaranteed at RNG level")
    print("  - Safe to call assays at any frequency without changing cell fate")
else:
    print("❌ FAIL: Stream isolation BROKEN")
    print()
    if not growth_unchanged:
        print("  - rng_growth was modified (physics coupling!)")
    if not treatment_unchanged:
        print("  - rng_treatment was modified (physics coupling!)")
    if not assay_changed:
        print("  - rng_assay was NOT used (assay not using dedicated stream!)")
    print()
    print("  This means observation CAN change cell fate. Observer independence is violated.")

print("=" * 100)
