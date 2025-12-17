#!/usr/bin/env python3
"""
Debug Agent Viability

Check what's happening to viability during agent execution at different timepoints.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

print("=" * 100)
print("AGENT VIABILITY DEBUG: 0.3 µM Nocodazole")
print("=" * 100)
print()

for timepoint in [12.0, 24.0, 48.0, 72.0, 96.0]:
    print(f"Timepoint: {timepoint}h")
    print("-" * 100)

    np.random.seed(42)
    agent = CellThalamusAgent(phase=0)

    well = WellAssignment(
        well_id='TEST',
        cell_line='iPSC_NGN2',
        compound='nocodazole',
        dose_uM=0.3,
        timepoint_h=timepoint,
        plate_id='P1',
        day=1,
        operator='Test',
        is_sentinel=False
    )

    # Get vessel ID
    vessel_id = f"{well.plate_id}_{well.well_id}"

    # Execute well
    result = agent._execute_well(well)

    # Get vessel state after execution
    vessel_state = agent.hardware.get_vessel_state(vessel_id)

    if vessel_state:
        print(f"  Cell count: {vessel_state['cell_count']:.2e}")
        print(f"  Viability: {vessel_state['viability']:.1%}")
        print(f"  Compounds: {vessel_state['compounds']}")

    # Get result data
    if 'atp_signal' in result:
        print(f"  LDH signal: {result['atp_signal']:.1f}")

        # Calculate viability from LDH (inverse)
        baseline_ldh = 70000.0  # iPSC_NGN2 baseline
        # viability = 1.0 - (ldh / baseline)
        ldh_derived_viability = 1.0 - (result['atp_signal'] / baseline_ldh)
        ldh_derived_viability = max(0.0, min(1.0, ldh_derived_viability))
        print(f"  Viability (from LDH): {ldh_derived_viability:.1%}")

    if 'morphology' in result:
        morph = result['morphology']
        print(f"  Morphology - Actin: {morph.get('actin', 0):.1f}, Mito: {morph.get('mito', 0):.1f}")

    print()

print("=" * 100)
print("EXPECTED: Viability should stay ~95-98% at all timepoints (dose << IC50)")
print("=" * 100)
