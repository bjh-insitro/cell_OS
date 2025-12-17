#!/usr/bin/env python3
"""
Trace Viability Changes

Instrument the code to see exactly when vessel.viability changes during execution.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.cell_thalamus.design_generator import WellAssignment
import numpy as np

# Patch BiologicalVirtualMachine to log viability changes
original_treat = BiologicalVirtualMachine.treat_with_compound
original_advance = BiologicalVirtualMachine.advance_time
original_update_growth = BiologicalVirtualMachine._update_vessel_growth

def logged_treat(self, vessel_id: str, compound: str, dose_uM: float, **kwargs):
    vessel = self.vessel_states.get(vessel_id)
    viability_before = vessel.viability if vessel else None

    result = original_treat(self, vessel_id, compound, dose_uM, **kwargs)

    vessel = self.vessel_states.get(vessel_id)
    viability_after = vessel.viability if vessel else None

    if viability_before != viability_after:
        print(f"  [treat_with_compound] Viability: {viability_before:.1%} → {viability_after:.1%}")
        print(f"    Compound: {compound}, Dose: {dose_uM} µM")

    return result

def logged_advance(self, hours: float):
    # Get viability before advance
    viabilities_before = {vid: v.viability for vid, v in self.vessel_states.items()}

    original_advance(self, hours)

    # Check if any viability changed
    for vid, v in self.vessel_states.items():
        viability_before = viabilities_before.get(vid)
        if viability_before != v.viability:
            print(f"  [advance_time] Viability changed: {viability_before:.1%} → {v.viability:.1%} after {hours:.1f}h")
            print(f"    Vessel: {vid}, Confluence: {v.confluence:.1%}")

def logged_update_growth(self, vessel, hours):
    viability_before = vessel.viability

    original_update_growth(self, vessel, hours)

    if viability_before != vessel.viability:
        print(f"    [_update_vessel_growth] Viability: {viability_before:.1%} → {vessel.viability:.1%}")
        print(f"      Cell count: {vessel.cell_count:.2e}, Confluence: {vessel.confluence:.1%}")

# Apply patches
BiologicalVirtualMachine.treat_with_compound = logged_treat
BiologicalVirtualMachine.advance_time = logged_advance
BiologicalVirtualMachine._update_vessel_growth = logged_update_growth

# Now run a test case
print("=" * 100)
print("VIABILITY TRACE: 96h timepoint, 0.3 µM nocodazole")
print("=" * 100)
print()

np.random.seed(42)
hardware = BiologicalVirtualMachine()

vessel_id = "TEST_WELL"
cell_line = "iPSC_NGN2"
compound = "nocodazole"
dose_uM = 0.3
timepoint_h = 96.0

print("1. Seed vessel")
hardware.seed_vessel(vessel_id, cell_line, 5e5, 2e6)
vessel = hardware.vessel_states[vessel_id]
print(f"   Viability: {vessel.viability:.1%}, Cell count: {vessel.cell_count:.2e}")
print()

print("2. Incubate for attachment (4h)")
hardware.advance_time(4.0)
vessel = hardware.vessel_states[vessel_id]
print(f"   Viability: {vessel.viability:.1%}, Cell count: {vessel.cell_count:.2e}")
print()

print("3. Apply compound")
hardware.treat_with_compound(vessel_id, compound, dose_uM)
vessel = hardware.vessel_states[vessel_id]
print(f"   Viability: {vessel.viability:.1%}, Cell count: {vessel.cell_count:.2e}")
print()

print(f"4. Incubate to timepoint ({timepoint_h - 4.0}h)")
hardware.advance_time(timepoint_h - 4.0)
vessel = hardware.vessel_states[vessel_id]
print(f"   Viability: {vessel.viability:.1%}, Cell count: {vessel.cell_count:.2e}")
print()

print("5. Measure LDH")
ldh_result = hardware.atp_viability_assay(vessel_id, well_position='A1')
print(f"   LDH signal: {ldh_result['ldh_signal']:.1f}")
print(f"   Viability (from result): {ldh_result['viability']:.1%}")
print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)
vessel = hardware.vessel_states[vessel_id]
print(f"Final viability: {vessel.viability:.1%}")
print(f"Final cell count: {vessel.cell_count:.2e}")
print(f"Final confluence: {vessel.confluence:.1%}")
print("=" * 100)
