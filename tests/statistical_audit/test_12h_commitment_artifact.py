"""
Minimal test proving the 12h commitment threshold exists.

This is the smallest possible demonstration of the artifact.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.sim.biology_core import compute_attrition_rate


def test_12h_threshold_exists():
    """Prove attrition rate is exactly zero before 12h, non-zero after."""

    # Parameters matching typical treatment
    dose_uM = 10.0  # High dose
    ic50_uM = 1.0
    viability = 0.3  # Well below threshold
    stress_axis = "er_stress"
    hill_slope = 1.5
    transport_dysfunction = 0.0

    # Test at 11.9h (just before threshold)
    rate_before = compute_attrition_rate(
        compound="tunicamycin",
        dose_uM=dose_uM,
        ic50_uM=ic50_uM,
        stress_axis=stress_axis,
        cell_line="A549",
        hill_slope=hill_slope,
        transport_dysfunction=transport_dysfunction,
        time_since_treatment_h=11.9,  # Just before
        current_viability=viability
    )

    # Test at 12.1h (just after threshold)
    rate_after = compute_attrition_rate(
        compound="tunicamycin",
        dose_uM=dose_uM,
        ic50_uM=ic50_uM,
        stress_axis=stress_axis,
        cell_line="A549",
        hill_slope=hill_slope,
        transport_dysfunction=transport_dysfunction,
        time_since_treatment_h=12.1,  # Just after
        current_viability=viability
    )

    print(f"\n=== 12H COMMITMENT THRESHOLD ARTIFACT ===")
    print(f"Attrition rate at 11.9h: {rate_before:.6f} per hour")
    print(f"Attrition rate at 12.1h: {rate_after:.6f} per hour")
    print(f"Jump magnitude: {rate_after / max(rate_before, 1e-9):.1f}×")

    # The artifact: attrition is exactly zero before 12h
    assert rate_before == 0.0, "Attrition should be exactly zero before 12h"
    assert rate_after > 0.0, "Attrition should be non-zero after 12h"

    print("\n✓ PROOF: Hard 12h threshold exists in biology_core.py:439")
    print("  Real biology: Commitment time should be dose-dependent and stochastic")
    print("  This simulator: All cells commit at exactly 12h (synchronization artifact)")


if __name__ == "__main__":
    test_12h_threshold_exists()
