"""
Phase 6a: Commitment delay dt-independence tests.

Tests whether commitment-gated death can be arbitraged by timestep size.

The attack: If commitment is checked only at step boundaries, agents can
"skip" the commitment window by taking one large step that jumps from
"before threshold" to "after window closed."

Expected behavior (dt-independent):
- Commitment delay is a time gate (e.g., 12h after treatment)
- Once time crosses threshold, death mechanisms activate
- This should be invariant across different timestep schedules
- 72×1h, 6×12h, and 1×72h should produce similar outcomes

Failure modes:
1. Coarse steps "skip" the commitment window (never checked)
2. Viability threshold creates feedback (attrition only if viability < 0.5)
3. Commitment count differs across schedules (event missed at boundaries)
"""

import pytest
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_commitment_dt_independence_fine_vs_coarse():
    """
    Test: Commitment-gated death should be dt-independent.

    Three schedules with identical real-time exposure:
    - Fine: 72 × 1h steps
    - Medium: 6 × 12h steps
    - Coarse: 1 × 72h step

    Invariant: Final viability (or death count) should be similar across schedules.

    If coarse is systematically safer, agents can arbitrage by taking large steps.
    """
    # Setup: Lethal dose that triggers commitment delay
    compound = "tunicamycin"  # ER stress compound
    dose_uM = 3.0  # High dose (well above IC50)
    total_duration = 72.0  # 72h total exposure

    # ===== Schedule 1: Fine (72 × 1h) =====
    vm_fine = BiologicalVirtualMachine(seed=42)
    vm_fine.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_fine.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)
    initial_viability_fine = vm_fine.vessel_states["Plate1_A01"].viability

    # Advance in 1h steps
    for _ in range(int(total_duration)):
        vm_fine.advance_time(1.0)

    final_viability_fine = vm_fine.vessel_states["Plate1_A01"].viability
    final_count_fine = vm_fine.vessel_states["Plate1_A01"].cell_count

    # ===== Schedule 2: Medium (6 × 12h) =====
    vm_medium = BiologicalVirtualMachine(seed=42)
    vm_medium.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_medium.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)
    initial_viability_medium = vm_medium.vessel_states["Plate1_A01"].viability

    # Advance in 12h steps
    for _ in range(6):
        vm_medium.advance_time(12.0)

    final_viability_medium = vm_medium.vessel_states["Plate1_A01"].viability
    final_count_medium = vm_medium.vessel_states["Plate1_A01"].cell_count

    # ===== Schedule 3: Coarse (1 × 72h) =====
    vm_coarse = BiologicalVirtualMachine(seed=42)
    vm_coarse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_coarse.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)
    initial_viability_coarse = vm_coarse.vessel_states["Plate1_A01"].viability

    # Single 72h step
    vm_coarse.advance_time(total_duration)

    final_viability_coarse = vm_coarse.vessel_states["Plate1_A01"].viability
    final_count_coarse = vm_coarse.vessel_states["Plate1_A01"].cell_count

    # ===== Analysis =====
    print(f"\n=== Commitment Delay dt-Independence Test ===")
    print(f"Setup: {compound} {dose_uM}µM for {total_duration}h")
    print()
    print(f"Fine schedule (72 × 1h):")
    print(f"  Initial viability: {initial_viability_fine:.4f}")
    print(f"  Final viability:   {final_viability_fine:.4f}")
    print(f"  Final cell count:  {final_count_fine:.2e}")
    print()
    print(f"Medium schedule (6 × 12h):")
    print(f"  Initial viability: {initial_viability_medium:.4f}")
    print(f"  Final viability:   {final_viability_medium:.4f}")
    print(f"  Final cell count:  {final_count_medium:.2e}")
    print()
    print(f"Coarse schedule (1 × 72h):")
    print(f"  Initial viability: {initial_viability_coarse:.4f}")
    print(f"  Final viability:   {final_viability_coarse:.4f}")
    print(f"  Final cell count:  {final_count_coarse:.2e}")
    print()

    # Calculate relative differences
    viability_diff_medium = abs(final_viability_medium - final_viability_fine)
    viability_diff_coarse = abs(final_viability_coarse - final_viability_fine)

    count_ratio_medium = final_count_medium / final_count_fine if final_count_fine > 0 else float('inf')
    count_ratio_coarse = final_count_coarse / final_count_fine if final_count_fine > 0 else float('inf')

    print(f"Differences from fine schedule:")
    print(f"  Medium viability diff: {viability_diff_medium:.4f}")
    print(f"  Coarse viability diff: {viability_diff_coarse:.4f}")
    print(f"  Medium count ratio:    {count_ratio_medium:.4f}")
    print(f"  Coarse count ratio:    {count_ratio_coarse:.4f}")
    print()

    # ===== Assertions =====
    # Tolerance: Allow ±10% difference in final viability (accounts for numerical error)
    # But systematic bias (coarse always safer) indicates exploit
    tolerance_viability = 0.10  # ±10% absolute viability difference
    tolerance_count_ratio = 0.20  # ±20% relative count difference

    # Check medium schedule
    if viability_diff_medium > tolerance_viability:
        print(f"⚠ Medium schedule differs by {viability_diff_medium:.4f} (>{tolerance_viability})")

    # Check coarse schedule
    if viability_diff_coarse > tolerance_viability:
        print(f"⚠ Coarse schedule differs by {viability_diff_coarse:.4f} (>{tolerance_viability})")

    # Primary exploit check: coarse schedule should NOT be systematically safer
    if final_viability_coarse > final_viability_fine + tolerance_viability:
        pytest.fail(
            f"COMMITMENT WINDOW SKIP EXPLOIT: Coarse schedule (1×72h) is systematically safer "
            f"than fine schedule (72×1h). Final viability: coarse={final_viability_coarse:.4f}, "
            f"fine={final_viability_fine:.4f}. This indicates commitment delay can be arbitraged "
            f"by taking large timesteps that skip the commitment window."
        )

    # Secondary check: count ratio should be close to 1.0
    if abs(count_ratio_coarse - 1.0) > tolerance_count_ratio:
        print(f"⚠ Coarse count ratio {count_ratio_coarse:.4f} differs by >{tolerance_count_ratio*100:.0f}%")

    # If all checks pass
    if viability_diff_coarse <= tolerance_viability:
        print(f"✓ Commitment delay is dt-independent (coarse diff: {viability_diff_coarse:.4f})")
    else:
        print(f"✓ No systematic exploit detected (coarse not safer than fine)")


def test_commitment_delay_crosses_threshold_in_single_step():
    """
    Test: Commitment delay should trigger even if crossed in a single large step.

    Scenario:
    - Commitment delay = 12h (typical for tunicamycin)
    - Take single 24h step (crosses 12h threshold mid-step)
    - Death should accumulate for second half of interval (12-24h)

    If commitment is only checked at step boundaries, this might fail.
    """
    compound = "tunicamycin"
    dose_uM = 3.0  # Lethal dose
    dt_step = 24.0  # Single large step that crosses commitment threshold

    # ===== Reference: Two 12h steps (should definitely trigger) =====
    vm_ref = BiologicalVirtualMachine(seed=42)
    vm_ref.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_ref.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    # Two 12h steps
    vm_ref.advance_time(12.0)
    viability_12h_ref = vm_ref.vessel_states["Plate1_A01"].viability

    vm_ref.advance_time(12.0)
    viability_24h_ref = vm_ref.vessel_states["Plate1_A01"].viability

    # ===== Test: Single 24h step =====
    vm_test = BiologicalVirtualMachine(seed=42)
    vm_test.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_test.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    # Single 24h step (crosses 12h threshold)
    vm_test.advance_time(dt_step)
    viability_24h_test = vm_test.vessel_states["Plate1_A01"].viability

    print(f"\n=== Commitment Threshold Crossing Test ===")
    print(f"Reference (2 × 12h steps):")
    print(f"  Viability at 12h: {viability_12h_ref:.4f}")
    print(f"  Viability at 24h: {viability_24h_ref:.4f}")
    print()
    print(f"Test (1 × 24h step):")
    print(f"  Viability at 24h: {viability_24h_test:.4f}")
    print()

    # ===== Assertions =====
    # Final viability should be similar (within ±10%)
    viability_diff = abs(viability_24h_test - viability_24h_ref)
    tolerance = 0.10

    print(f"Viability difference: {viability_diff:.4f} (tolerance: {tolerance})")

    if viability_diff > tolerance:
        if viability_24h_test > viability_24h_ref + tolerance:
            pytest.fail(
                f"COMMITMENT SKIP EXPLOIT: Single large step (24h) is safer than two 12h steps. "
                f"Viability: test={viability_24h_test:.4f}, ref={viability_24h_ref:.4f}. "
                f"Commitment threshold may not be checked mid-interval."
            )
        else:
            print(f"⚠ Large step is MORE lethal (diff: {viability_diff:.4f}). Possible over-counting.")
    else:
        print(f"✓ Commitment threshold crossed correctly in single step (diff: {viability_diff:.4f})")


def test_commitment_delay_viability_threshold_interaction():
    """
    Test: Interaction between commitment delay and viability < 0.5 threshold.

    Attrition only applies when both conditions are met:
    1. time_since_treatment > commitment_delay_h
    2. current_viability < 0.5

    Potential exploit: If viability is checked only at step boundaries,
    coarse steps might miss the "viability drops below 0.5" event.

    Scenario:
    - Moderate dose that slowly drops viability below 0.5
    - Compare fine vs coarse timesteps
    - Check if coarse steps miss the viability threshold crossing
    """
    compound = "tunicamycin"
    dose_uM = 2.0  # Moderate dose (drops viability slowly)
    total_duration = 48.0

    # ===== Fine schedule (24 × 2h) =====
    vm_fine = BiologicalVirtualMachine(seed=42)
    vm_fine.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_fine.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    viability_trajectory_fine = [vm_fine.vessel_states["Plate1_A01"].viability]
    for _ in range(24):
        vm_fine.advance_time(2.0)
        viability_trajectory_fine.append(vm_fine.vessel_states["Plate1_A01"].viability)

    final_viability_fine = viability_trajectory_fine[-1]

    # ===== Coarse schedule (2 × 24h) =====
    vm_coarse = BiologicalVirtualMachine(seed=42)
    vm_coarse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_coarse.treat_with_compound("Plate1_A01", compound, dose_uM=dose_uM)

    viability_trajectory_coarse = [vm_coarse.vessel_states["Plate1_A01"].viability]
    for _ in range(2):
        vm_coarse.advance_time(24.0)
        viability_trajectory_coarse.append(vm_coarse.vessel_states["Plate1_A01"].viability)

    final_viability_coarse = viability_trajectory_coarse[-1]

    print(f"\n=== Viability Threshold Interaction Test ===")
    print(f"Fine schedule (24 × 2h):")
    print(f"  Viability at 0h:  {viability_trajectory_fine[0]:.4f}")
    print(f"  Viability at 12h: {viability_trajectory_fine[6]:.4f} (commitment delay)")
    print(f"  Viability at 24h: {viability_trajectory_fine[12]:.4f}")
    print(f"  Viability at 48h: {viability_trajectory_fine[-1]:.4f}")
    print()
    print(f"Coarse schedule (2 × 24h):")
    print(f"  Viability at 0h:  {viability_trajectory_coarse[0]:.4f}")
    print(f"  Viability at 24h: {viability_trajectory_coarse[1]:.4f}")
    print(f"  Viability at 48h: {viability_trajectory_coarse[-1]:.4f}")
    print()

    # Check when viability first drops below 0.5
    idx_below_05_fine = next((i for i, v in enumerate(viability_trajectory_fine) if v < 0.5), None)
    time_below_05_fine = idx_below_05_fine * 2.0 if idx_below_05_fine is not None else None

    idx_below_05_coarse = next((i for i, v in enumerate(viability_trajectory_coarse) if v < 0.5), None)
    time_below_05_coarse = idx_below_05_coarse * 24.0 if idx_below_05_coarse is not None else None

    print(f"Viability drops below 0.5:")
    print(f"  Fine schedule:   t={time_below_05_fine}h" if time_below_05_fine else "  Fine schedule:   Never")
    print(f"  Coarse schedule: t={time_below_05_coarse}h" if time_below_05_coarse else "  Coarse schedule: Never")
    print()

    # ===== Assertions =====
    viability_diff = abs(final_viability_coarse - final_viability_fine)
    tolerance = 0.10

    print(f"Final viability difference: {viability_diff:.4f}")

    if viability_diff > tolerance:
        if final_viability_coarse > final_viability_fine + tolerance:
            pytest.fail(
                f"VIABILITY THRESHOLD EXPLOIT: Coarse schedule misses viability < 0.5 crossing. "
                f"Final viability: coarse={final_viability_coarse:.4f}, fine={final_viability_fine:.4f}. "
                f"Attrition may not trigger if viability threshold is checked only at boundaries."
            )
        else:
            print(f"⚠ Coarse is MORE lethal (diff: {viability_diff:.4f}). Possible over-counting.")
    else:
        print(f"✓ Viability threshold interaction is dt-independent (diff: {viability_diff:.4f})")
