#!/usr/bin/env python3
"""
Test Continuous High Dose Attrition

Run a single continuous simulation (not restarting each timepoint)
to verify time-dependent attrition accumulates correctly.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

np.random.seed(42)
hardware = BiologicalVirtualMachine()

vessel_id = "TEST_WELL"
cell_line = "iPSC_NGN2"
compound = "nocodazole"
dose_uM = 10.0  # High dose

print("=" * 100)
print(f"CONTINUOUS HIGH DOSE TEST: {dose_uM} µM {compound} on {cell_line}")
print("=" * 100)
print()

# Seed cells
hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6)
print(f"0h: Seeded {5e5:.2e} cells")

# Incubate for attachment (4h)
hardware.advance_time(4.0)
vessel = hardware.vessel_states[vessel_id]
print(f"4h: After attachment - viability={vessel.viability:.1%}, count={vessel.cell_count:.2e}")

# Apply compound
result = hardware.treat_with_compound(vessel_id, compound, dose_uM)
vessel = hardware.vessel_states[vessel_id]
print(f"4h: After compound - viability={vessel.viability:.1%}, count={vessel.cell_count:.2e}")
print(f"    IC50={result['ic50_uM']:.2f}µM, stress_axis={result['stress_axis']}")
print()

# Track over time
print(f"{'Time (h)':<10} {'Viability':<12} {'Death Mode':<15} {'Death Compound':<15} {'Cell Count':<15}")
print("-" * 100)

timepoints = [12.0, 24.0, 48.0, 72.0, 96.0]
current_time = 4.0

for tp in timepoints:
    # Advance time
    dt = tp - current_time
    hardware.advance_time(dt)
    current_time = tp

    vessel = hardware.vessel_states[vessel_id]

    print(f"{tp:<10.0f} {vessel.viability:>6.1%}{'':<5} {str(vessel.death_mode):<15} {vessel.death_compound:>8.1%}{'':<6} {vessel.cell_count:>10.2e}{'':<4}")

print()
print("=" * 100)
print("EXPECTED:")
print("  Instant effect (~8% viability at 4h) from high dose (10µM >> IC50=2.5µM)")
print("  Time-dependent attrition should further reduce viability at 48h+ if dose_ratio >= 1.0")
print("  Death mode should be 'compound' (not None)")
print("=" * 100)
