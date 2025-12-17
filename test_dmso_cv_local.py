#!/usr/bin/env python3
"""
Test DMSO CV for local codebase only (no multiprocessing)
"""
import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

# Initialize agent
np.random.seed(42)
agent = CellThalamusAgent(phase=0)

# Simulate 100 DMSO wells
print("Testing Local Codebase DMSO CV...")
print("=" * 60)

dmso_values = []
for i in range(100):
    well = WellAssignment(
        well_id=f'D{i:02d}',
        cell_line='A549',
        compound='DMSO',
        dose_uM=0.0,
        timepoint_h=12.0,
        plate_id='TestPlate1',
        day=1,
        operator='TestOp',
        is_sentinel=False
    )

    # Execute well
    result = agent._execute_well(well)
    if result:
        dmso_values.append(result['morphology']['er'])

mean = np.mean(dmso_values)
std = np.std(dmso_values)
cv = (std / mean) * 100

print(f"\nDMSO ER CV: {cv:.2f}%")
print(f"Mean: {mean:.3f}, Std: {std:.3f}")
print(f"Min: {min(dmso_values):.3f}, Max: {max(dmso_values):.3f}")
print(f"Expected: ~2-3% CV")
print(f"Status: {'✓ PASS' if 1.5 <= cv <= 5.0 else '✗ FAIL'}")

# Show distribution
import collections
bins = [round(v, 2) for v in dmso_values]
hist = collections.Counter(bins)
print("\nDistribution (top 10):")
for val in sorted(hist.keys())[:10]:
    print(f"  {val:.2f}: {'*' * hist[val]}")
