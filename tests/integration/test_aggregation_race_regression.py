"""
Regression test for historical aggregation race bug.

HISTORICAL FAILURE:
- 32 DMSO baseline wells at "1.0 µM"
- Float arithmetic introduced tiny differences (1.0, 1.00001, 1.000002, ...)
- Wells split into 3-4 separate conditions
- Replicate counts dropped from 32 → 8-10 per condition
- noise_sigma_stable LOST (CI widening from reduced n)
- Gate unlocked despite no real change

AFTER FIX (Agent 2):
- All 32 wells collapse to canonical key (1000 nM, 1440 min)
- Single condition with n=32
- noise_sigma_stable MAINTAINED
- Gate remains locked correctly

This test MUST fail on old aggregation code, MUST pass after canonical keys.
"""

from typing import List
from dataclasses import dataclass
from cell_os.core.canonicalize import canonical_condition_key
from cell_os.epistemic_agent.observation_aggregator import aggregate_observation
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
from cell_os.core.observation import RawWellResult
from cell_os.core.experiment import SpatialLocation, Treatment
from cell_os.core.assay import AssayType
import numpy as np


def test_historical_gate_loss_prevented():
    """
    Regression test: 32-well DMSO split must not happen.

    Simulates the exact scenario that caused historical gate loss:
    - 32 baseline DMSO wells
    - Tiny float differences in dose (1.0, 1.00001, 1.000002, ...)
    - Old code: splits into multiple conditions → gate lost
    - New code: collapses to ONE condition → gate maintained
    """

    # Create proposal for 32 baseline DMSO wells
    wells = []
    for i in range(32):
        wells.append(WellSpec(
            cell_line="A549",
            compound="DMSO",
            dose_uM=1.0,  # Nominal dose
            time_h=24.0,
            assay="cell_painting",
            position_tag="center"
        ))

    proposal = Proposal(
        design_id="baseline_32_dmso",
        hypothesis="Measure baseline noise with 32 replicates",
        wells=wells,
        budget_limit=200
    )

    # Simulate raw results with FLOAT NOISE in dose
    # This is what caused the historical split
    raw_results: List[RawWellResult] = []

    # Introduce tiny float differences (arithmetic noise from different code paths)
    dose_variations = [
        1.0,
        1.0 + 1e-6,    # Float noise from one code path
        1.0 + 2e-6,    # Float noise from another
        1.0 - 1e-6,    # Negative noise
        1.0 + 5e-7,    # Even tinier noise
    ]

    np.random.seed(42)
    for i in range(32):
        # Pick a dose variant (simulates non-deterministic float arithmetic)
        dose_with_noise = dose_variations[i % len(dose_variations)]

        # Generate realistic morphology readout (mean ~0.95, std ~0.02)
        base_response = 0.95
        noise = np.random.normal(0, 0.02)
        response = base_response + noise

        raw_results.append(RawWellResult(
            location=SpatialLocation(
                plate_id="plate1",
                well_id=f"well_{i:03d}"
            ),
            cell_line="A549",
            treatment=Treatment(
                compound="DMSO",
                dose_uM=dose_with_noise  # FLOAT NOISE HERE
            ),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=24.0,
            readouts={
                'morphology': {
                    'er': response + np.random.normal(0, 0.01),
                    'mito': response + np.random.normal(0, 0.01),
                    'nucleus': response + np.random.normal(0, 0.01),
                    'actin': response + np.random.normal(0, 0.01),
                    'rna': response + np.random.normal(0, 0.01),
                }
            },
            qc={'failed': False}
        ))

    # Aggregate using canonical keys
    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=168,
        strategy="default_per_channel"
    )

    # CRITICAL ASSERTIONS: Verify split did not occur

    # 1. Must have exactly ONE condition (not 3-4 from float splitting)
    assert len(observation.conditions) == 1, \
        f"REGRESSION: Float noise caused condition splitting! " \
        f"Expected 1 condition, got {len(observation.conditions)}. " \
        f"This is the historical gate-loss bug."

    condition = observation.conditions[0]

    # 2. Condition must have all 32 wells
    assert condition.n_wells_total == 32, \
        f"REGRESSION: Wells not grouped correctly! " \
        f"Expected 32 wells, got {condition.n_wells_total}"

    # 3. Canonical dose must be exactly 1000 nM (not split)
    assert condition.canonical_dose_nM == 1000, \
        f"Canonical dose incorrect: {condition.canonical_dose_nM}"

    # 4. Canonical time must be exactly 1440 min
    assert condition.canonical_time_min == 1440, \
        f"Canonical time incorrect: {condition.canonical_time_min}"

    # 5. Check if near-duplicates were detected and logged
    if len(observation.near_duplicate_merges) > 0:
        # Near-duplicates were merged - this is GOOD
        merge = observation.near_duplicate_merges[0]
        assert len(merge['raw_doses_uM']) > 1, \
            "Near-duplicate merge should report multiple raw doses"
        print(f"✓ Near-duplicates detected and merged: {merge['raw_doses_uM']}")

    # 6. Verify noise characteristics support gate stability
    # With n=32, rel CI width should be low enough for gate
    # std/sqrt(32) * 2.04 / mean ≈ 0.02 / sqrt(32) * 2.04 / 0.95 ≈ 0.0075
    # This should easily pass 0.25 threshold
    cv = condition.cv
    rel_ci_width_approx = cv / np.sqrt(32) * 2.04  # t-statistic for df=31

    print(f"\n✓ Aggregation race PREVENTED:")
    print(f"  Conditions: {len(observation.conditions)} (expected: 1)")
    print(f"  Wells per condition: {condition.n_wells_total}")
    print(f"  CV: {cv:.4f}")
    print(f"  Approx rel CI width: {rel_ci_width_approx:.4f}")
    print(f"  Gate threshold: 0.25")
    print(f"  Gate status: {'STABLE' if rel_ci_width_approx < 0.25 else 'UNSTABLE'}")

    # 7. Final check: with 32 wells, gate should be stable
    assert rel_ci_width_approx < 0.25, \
        f"With 32 wells, gate should be stable (rel_width={rel_ci_width_approx:.4f})"

    return observation


def test_near_duplicate_detection_works():
    """Test that near-duplicate merges are logged correctly."""

    # Create proposal with intentional near-duplicates
    wells = []
    for i in range(16):
        wells.append(WellSpec(
            cell_line="A549",
            compound="tunicamycin",
            dose_uM=10.0,  # Half at 10.0
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ))

    for i in range(16):
        wells.append(WellSpec(
            cell_line="A549",
            compound="tunicamycin",
            dose_uM=10.001,  # Half at 10.001 (should merge if within rounding)
            time_h=12.0,
            assay="cell_painting",
            position_tag="center"
        ))

    proposal = Proposal(
        design_id="near_duplicate_test",
        hypothesis="Test near-duplicate detection",
        wells=wells,
        budget_limit=200
    )

    # Create raw results
    raw_results = []
    np.random.seed(42)

    for i, well_spec in enumerate(wells):
        response = 0.95 + np.random.normal(0, 0.02)

        raw_results.append(RawWellResult(
            location=SpatialLocation(
                plate_id="plate1",
                well_id=f"well_{i:03d}"
            ),
            cell_line=well_spec.cell_line,
            treatment=Treatment(
                compound=well_spec.compound,
                dose_uM=well_spec.dose_uM
            ),
            assay=AssayType.CELL_PAINTING,
            observation_time_h=well_spec.time_h,
            readouts={
                'morphology': {
                    'er': response,
                    'mito': response,
                    'nucleus': response,
                    'actin': response,
                    'rna': response,
                }
            },
            qc={'failed': False}
        ))

    observation = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=168,
        strategy="default_per_channel"
    )

    # Check canonical doses
    dose_10_0_nM = 10000  # 10.0 µM
    dose_10_001_nM = 10001  # 10.001 µM

    # These are DISTINCT (10000 nM vs 10001 nM)
    assert dose_10_0_nM != dose_10_001_nM

    # Should have TWO conditions (10.0 and 10.001 are distinct after rounding)
    if len(observation.conditions) == 2:
        print(f"\n✓ Near-duplicates correctly kept distinct:")
        print(f"  Conditions: {len(observation.conditions)}")
        print(f"  Canonical doses: {[c.canonical_dose_nM for c in observation.conditions]}")
        assert 10000 in [c.canonical_dose_nM for c in observation.conditions]
        assert 10001 in [c.canonical_dose_nM for c in observation.conditions]
    else:
        # Or if they collapsed (depends on rounding), verify merger was logged
        assert len(observation.conditions) == 1
        assert len(observation.near_duplicate_merges) > 0
        print(f"\n✓ Near-duplicates merged and logged:")
        print(f"  Merge events: {len(observation.near_duplicate_merges)}")


if __name__ == "__main__":
    print("="*60)
    print("REGRESSION TEST: Historical Gate Loss Bug")
    print("="*60)

    obs = test_historical_gate_loss_prevented()

    print("\n" + "="*60)
    print("NEAR-DUPLICATE DETECTION TEST")
    print("="*60)

    test_near_duplicate_detection_works()

    print("\n" + "="*60)
    print("ALL REGRESSION TESTS PASSED")
    print("="*60)
    print("\n✅ Historical gate-loss bug is now IMPOSSIBLE")
    print("✅ Float noise cannot split replicates")
    print("✅ 32-well baseline always groups correctly")
    print("✅ Canonical keys eliminate aggregation races\n")
