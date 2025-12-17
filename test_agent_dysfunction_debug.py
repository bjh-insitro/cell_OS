#!/usr/bin/env python3
"""
Debug Dysfunction Computation

Check if dysfunction is being computed correctly in the agent path.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

np.random.seed(42)
agent = CellThalamusAgent(phase=0)

well = WellAssignment(
    well_id='TEST',
    cell_line='iPSC_NGN2',
    compound='nocodazole',
    dose_uM=0.3,  # Low dose
    timepoint_h=48.0,
    plate_id='P1',
    day=1,
    operator='Test',
    is_sentinel=False
)

# Execute well
result = agent._execute_well(well)

print("=" * 100)
print("DYSFUNCTION DEBUG")
print("=" * 100)
print(f"Compound: {well.compound}")
print(f"Dose: {well.dose_uM} µM")
print(f"Cell line: {well.cell_line}")
print(f"Timepoint: {well.timepoint_h}h")
print()

print("RESULT:")
print(f"  Viability: {result.get('viability', 0.0):.1%}")
print(f"  Death mode: {result.get('death_mode')}")
print(f"  Death compound: {result.get('death_compound', 0.0):.1%}")
print()

print("MORPHOLOGY:")
morph = result.get('morphology', {})
morph_struct = result.get('morphology_struct', {})
for channel in ['actin', 'mito']:
    observed = morph.get(channel, 0)
    structural = morph_struct.get(channel, 0)
    print(f"  {channel.capitalize()}: observed={observed:.1f}, structural={structural:.1f}")
print()

print(f"DYSFUNCTION SCORE: {result.get('transport_dysfunction_score', 0.0):.3f}")
print()

print("=" * 100)
print("EXPECTED:")
print("  Dysfunction should be ~0.37 for nocodazole @ 0.3µM on iPSC_NGN2")
print("  Structural actin should be ~96 AU (40% disruption from baseline 160)")
print("  Structural mito should be ~147 AU (33% disruption from baseline 220)")
print("=" * 100)
