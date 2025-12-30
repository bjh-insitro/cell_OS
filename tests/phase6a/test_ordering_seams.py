"""
Phase 6a: Ordering seam exploit detection.

Tests whether action timing relative to update order creates exploitable advantages.

The core question: Can an agent game the scheduler by timing actions to read
stale state or skip penalties?

If two policies deliver the same integrated exposure (AUC), they should produce
similar outcomes regardless of action timing. Violations indicate ordering exploits
that teach wrong lessons about intervention timing.

Target exploit: "pulse after growth reads" strategy that keeps growth seeing
low stress more often than steady dosing.
"""

import pytest
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_ordering_exploit_steady_vs_pulse_12h():
    """
    Test: Growth penalty should not be dodgeable by action timing (coarse dt).

    Two strategies with matched AUC (area under curve):
    A. Steady dose: Apply once and hold for entire period
    B. Pulse-lag: Apply after each growth read, washout before next read

    If B achieves materially higher growth than A, we have an ordering exploit
    where agents can arbitrage the scheduler.

    Uses dt=12h (coarse) where ordering matters most.
    """
    # Setup
    dose_uM = 1.5  # Moderate ER stress
    total_duration = 48.0  # 48h total
    dt_step = 12.0  # Coarse timestep (where ordering exploits are visible)

    # ===== Strategy A: Steady dose =====
    vm_steady = BiologicalVirtualMachine(seed=42)
    vm_steady.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    # Apply dose once at t=0 and hold
    vm_steady.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM)

    initial_count_steady = vm_steady.vessel_states["Plate1_A01"].cell_count

    # Run full duration with steady dose
    # Advance in dt_step chunks (simulate coarse action granularity)
    for _ in range(int(total_duration / dt_step)):
        vm_steady.advance_time(dt_step)

    final_count_steady = vm_steady.vessel_states["Plate1_A01"].cell_count
    final_stress_steady = vm_steady.vessel_states["Plate1_A01"].er_stress

    # ===== Strategy B: Pulse-lag (exploit attempt) =====
    # Goal: Apply dose AFTER growth reads in each step, washout before next step
    #
    # To match AUC over 12h step:
    # - Steady: 12h at dose D
    # - Pulse: 6h at dose 2D (second half of step only)
    #
    # This creates timing where growth reads happen when stress is low.

    vm_pulse = BiologicalVirtualMachine(seed=42)
    vm_pulse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    initial_count_pulse = vm_pulse.vessel_states["Plate1_A01"].cell_count

    # Manually step through, pulsing in second half of each interval
    num_steps = int(total_duration / dt_step)

    for step in range(num_steps):
        # First half: no compound (growth reads low stress)
        vm_pulse.advance_time(dt_step / 2)

        # Second half: apply 2× dose to match AUC
        vm_pulse.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM * 2.0)
        vm_pulse.advance_time(dt_step / 2)

        # Washout before next cycle (if not last step)
        if step < num_steps - 1:
            vm_pulse.washout_compound("Plate1_A01")

    final_count_pulse = vm_pulse.vessel_states["Plate1_A01"].cell_count
    final_stress_pulse = vm_pulse.vessel_states["Plate1_A01"].er_stress

    # ===== Analysis =====
    growth_ratio_steady = final_count_steady / initial_count_steady
    growth_ratio_pulse = final_count_pulse / initial_count_pulse

    print(f"\n=== Ordering Exploit Test (dt={dt_step}h) ===")
    print(f"Strategy A (Steady):")
    print(f"  Initial count: {initial_count_steady:.1e}")
    print(f"  Final count:   {final_count_steady:.1e}")
    print(f"  Growth ratio:  {growth_ratio_steady:.4f}")
    print(f"  Final stress:  {final_stress_steady:.4f}")
    print()
    print(f"Strategy B (Pulse-lag):")
    print(f"  Initial count: {initial_count_pulse:.1e}")
    print(f"  Final count:   {final_count_pulse:.1e}")
    print(f"  Growth ratio:  {growth_ratio_pulse:.4f}")
    print(f"  Final stress:  {final_stress_pulse:.4f}")
    print()

    # Calculate relative advantage
    advantage_ratio = growth_ratio_pulse / growth_ratio_steady
    advantage_pct = (advantage_ratio - 1.0) * 100

    print(f"Pulse advantage: {advantage_ratio:.4f}× ({advantage_pct:+.1f}%)")

    # ===== Assertions =====
    # Tolerance: Allow ±5% difference for numerical/stochastic effects
    # But pulse should NOT achieve >5% higher growth with same AUC
    tolerance = 0.05  # 5%

    if advantage_ratio > 1.0 + tolerance:
        pytest.fail(
            f"ORDERING EXPLOIT DETECTED: Pulse-lag strategy achieves {advantage_pct:+.1f}% "
            f"higher growth than steady dosing with same AUC. This indicates agents can "
            f"arbitrage the scheduler by timing actions relative to update order."
        )
    elif advantage_ratio < 1.0 - tolerance:
        # Pulse doing worse is fine (means steady is optimal, no exploit)
        print(f"✓ No exploit: Pulse strategy is worse than steady (advantage: {advantage_pct:+.1f}%)")
    else:
        # Within tolerance - no clear exploit
        print(f"✓ No exploit: Strategies perform similarly (advantage: {advantage_pct:+.1f}%)")

    # Final sanity: Both should show stress penalty relative to untreated
    # (This verifies the mechanism is working at all)
    assert growth_ratio_steady < 5.0, "Steady strategy should show stress penalty (growth < 5×)"
    assert growth_ratio_pulse < 5.0, "Pulse strategy should show stress penalty (growth < 5×)"


def test_ordering_exploit_steady_vs_pulse_1h():
    """
    Test: Same ordering exploit test but with fine timestep (dt=1h).

    This is the control condition: with fine timesteps, ordering effects should
    be negligible because updates happen frequently relative to dynamics.

    If this test passes while the 12h test fails, it confirms the exploit is
    timestep-dependent and not a fundamental issue.
    """
    # Setup (same as 12h test but finer timestep)
    dose_uM = 1.5
    total_duration = 48.0
    dt_step = 1.0  # Fine timestep

    # ===== Strategy A: Steady dose =====
    vm_steady = BiologicalVirtualMachine(seed=42)
    vm_steady.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_steady.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM)
    initial_count_steady = vm_steady.vessel_states["Plate1_A01"].cell_count

    # Advance in dt_step chunks
    for _ in range(int(total_duration / dt_step)):
        vm_steady.advance_time(dt_step)

    final_count_steady = vm_steady.vessel_states["Plate1_A01"].cell_count
    final_stress_steady = vm_steady.vessel_states["Plate1_A01"].er_stress

    # ===== Strategy B: Pulse-lag (same attempt) =====
    vm_pulse = BiologicalVirtualMachine(seed=42)
    vm_pulse.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    initial_count_pulse = vm_pulse.vessel_states["Plate1_A01"].cell_count

    # Match the 12h structure but scaled to 1h steps
    # Pulse in second half of each 1h step with 2× dose
    num_steps = int(total_duration / dt_step)

    for step in range(num_steps):
        vm_pulse.advance_time(dt_step / 2)
        vm_pulse.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM * 2.0)
        vm_pulse.advance_time(dt_step / 2)

        if step < num_steps - 1:
            vm_pulse.washout_compound("Plate1_A01")

    final_count_pulse = vm_pulse.vessel_states["Plate1_A01"].cell_count
    final_stress_pulse = vm_pulse.vessel_states["Plate1_A01"].er_stress

    # ===== Analysis =====
    growth_ratio_steady = final_count_steady / initial_count_steady
    growth_ratio_pulse = final_count_pulse / initial_count_pulse

    print(f"\n=== Ordering Exploit Test (dt={dt_step}h) - Control ===")
    print(f"Strategy A (Steady):")
    print(f"  Growth ratio:  {growth_ratio_steady:.4f}")
    print(f"  Final stress:  {final_stress_steady:.4f}")
    print()
    print(f"Strategy B (Pulse-lag):")
    print(f"  Growth ratio:  {growth_ratio_pulse:.4f}")
    print(f"  Final stress:  {final_stress_pulse:.4f}")
    print()

    advantage_ratio = growth_ratio_pulse / growth_ratio_steady
    advantage_pct = (advantage_ratio - 1.0) * 100

    print(f"Pulse advantage: {advantage_ratio:.4f}× ({advantage_pct:+.1f}%)")

    # ===== Assertions =====
    # With fine timestep, ordering should not matter
    tolerance = 0.05  # 5%

    if abs(advantage_ratio - 1.0) > tolerance:
        print(f"⚠ Even at dt={dt_step}h, pulse strategy differs by {advantage_pct:+.1f}%")
        print(f"  This may indicate dynamics are too fast relative to timestep")
    else:
        print(f"✓ No exploit at fine timestep (advantage: {advantage_pct:+.1f}%)")

    # Should pass at fine timestep (no exploit detectable)
    assert abs(advantage_ratio - 1.0) <= tolerance, \
        f"Pulse advantage {advantage_pct:+.1f}% exceeds tolerance at dt={dt_step}h"


def test_growth_reads_current_vs_lagged_stress():
    """
    Test: Does growth penalty use current stress (within-step) or lagged stress (start-of-step)?

    This directly probes the _step_vessel update order without relying on
    washout timing.

    Method:
    1. Start with clean cells
    2. Apply stress at t=0
    3. Advance one large timestep (12h)
    4. Check if growth penalty was immediate or delayed

    If growth reads lagged stress, the first step will show higher growth
    than it should given the stress present during the step.
    """
    # Setup
    dose_uM = 2.0  # Strong dose for clear signal
    dt_step = 12.0

    # ===== Reference: No stress (maximum growth) =====
    vm_control = BiologicalVirtualMachine(seed=42)
    vm_control.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    initial_count_control = vm_control.vessel_states["Plate1_A01"].cell_count
    vm_control.advance_time(dt_step)
    final_count_control = vm_control.vessel_states["Plate1_A01"].cell_count

    growth_rate_control = (final_count_control / initial_count_control) ** (1.0 / dt_step)

    # ===== Test: Stress applied at t=0 =====
    vm_test = BiologicalVirtualMachine(seed=42)
    vm_test.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    # Apply stress immediately
    vm_test.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM)

    initial_count_test = vm_test.vessel_states["Plate1_A01"].cell_count

    # Advance one step
    vm_test.advance_time(dt_step)

    final_count_test = vm_test.vessel_states["Plate1_A01"].cell_count
    final_stress_test = vm_test.vessel_states["Plate1_A01"].er_stress

    growth_rate_test = (final_count_test / initial_count_test) ** (1.0 / dt_step)

    # ===== Analysis =====
    penalty_ratio = growth_rate_test / growth_rate_control

    print(f"\n=== Growth Penalty Timing Test ===")
    print(f"Control (no stress):")
    print(f"  Growth rate: {growth_rate_control:.6f} /h")
    print()
    print(f"Test (stress at t=0):")
    print(f"  Growth rate: {growth_rate_test:.6f} /h")
    print(f"  Final stress: {final_stress_test:.4f}")
    print(f"  Penalty ratio: {penalty_ratio:.4f} (1.0 = no penalty)")
    print()

    # ===== Assertions =====
    # Growth should be penalized immediately (within first step)
    # If growth reads lagged stress, penalty_ratio will be close to 1.0
    # If growth reads current stress, penalty_ratio will be ~0.8-0.9

    # Expected penalty for ER stress ~0.5-1.0: roughly 10-30% growth reduction
    expected_penalty_min = 0.70  # At least 30% reduction
    expected_penalty_max = 0.95  # At most 5% reduction

    if penalty_ratio > expected_penalty_max:
        pytest.fail(
            f"Growth penalty appears delayed: penalty_ratio={penalty_ratio:.4f} (expected <{expected_penalty_max}). "
            f"This suggests growth reads lagged stress from previous step, creating timing exploit."
        )
    elif penalty_ratio < expected_penalty_min:
        # Penalty is strong (good, but verify it's not too extreme)
        print(f"✓ Strong immediate penalty: {(1 - penalty_ratio) * 100:.1f}% growth reduction")
    else:
        print(f"✓ Moderate immediate penalty: {(1 - penalty_ratio) * 100:.1f}% growth reduction")

    # Sanity: stress should be elevated after treatment
    assert final_stress_test > 0.3, f"Stress should be elevated after treatment (got {final_stress_test:.4f})"


def test_one_step_lag_exploit():
    """
    Test: Growth penalty should apply in the SAME step as stress induction.

    Direct test for one-step lag exploit:
    - Compare growth over first step when stress applied at t=0
    - If growth penalty is delayed by one step, first-step growth will be too high

    This is cleaner than pulse tests because it avoids dose nonlinearity effects.
    """
    dose_uM = 2.0
    dt_step = 6.0  # 6h step (moderate granularity)

    # ===== Control: Two steps, no stress =====
    vm_control = BiologicalVirtualMachine(seed=42)
    vm_control.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    count_t0 = vm_control.vessel_states["Plate1_A01"].cell_count
    vm_control.advance_time(dt_step)
    count_t1_control = vm_control.vessel_states["Plate1_A01"].cell_count

    growth_step1_control = count_t1_control / count_t0

    # ===== Test: Stress at t=0, measure first step growth =====
    vm_test = BiologicalVirtualMachine(seed=42)
    vm_test.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    vm_test.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM)

    count_t0_test = vm_test.vessel_states["Plate1_A01"].cell_count
    stress_t0 = vm_test.vessel_states["Plate1_A01"].er_stress

    vm_test.advance_time(dt_step)

    count_t1_test = vm_test.vessel_states["Plate1_A01"].cell_count
    stress_t1 = vm_test.vessel_states["Plate1_A01"].er_stress

    growth_step1_test = count_t1_test / count_t0_test

    # ===== Advance to step 2 to see if penalty appears LATER =====
    vm_test.advance_time(dt_step)
    count_t2_test = vm_test.vessel_states["Plate1_A01"].cell_count
    growth_step2_test = count_t2_test / count_t1_test

    print(f"\n=== One-Step Lag Exploit Test ===")
    print(f"Control (no stress):")
    print(f"  Step 1 growth: {growth_step1_control:.4f}")
    print()
    print(f"Test (stress at t=0):")
    print(f"  Stress at t=0:  {stress_t0:.4f}")
    print(f"  Stress at t={dt_step}h: {stress_t1:.4f}")
    print(f"  Step 1 growth: {growth_step1_test:.4f} (should be < control)")
    print(f"  Step 2 growth: {growth_step2_test:.4f}")
    print()

    # Calculate first-step penalty ratio
    penalty_step1 = growth_step1_test / growth_step1_control

    print(f"First-step penalty ratio: {penalty_step1:.4f}")
    print(f"  (1.0 = no penalty, <0.9 = strong immediate penalty)")

    # ===== Assertions =====
    # With stress building to ~0.5-0.7 over first step, we expect growth penalty
    # If penalty ratio > 0.95, growth barely noticed the stress (LAG EXPLOIT)
    # If penalty ratio < 0.9, growth paid immediate cost (NO LAG)

    if penalty_step1 > 0.95:
        pytest.fail(
            f"ONE-STEP LAG EXPLOIT: First-step penalty ratio {penalty_step1:.4f} (>0.95). "
            f"Growth barely noticed stress building from {stress_t0:.2f} to {stress_t1:.2f}. "
            f"This indicates growth reads stress from PREVIOUS step (N-1), creating "
            f"arbitrage opportunity for agents to time actions relative to update order."
        )
    elif penalty_step1 > 0.90:
        print(f"⚠ Weak penalty: {penalty_step1:.4f} (between 0.90-0.95). Possible lag issue.")
    else:
        print(f"✓ Strong immediate penalty: {penalty_step1:.4f} (<0.90). No lag exploit.")

    # Sanity: stress should have built up significantly
    assert stress_t1 > 0.4, f"Stress should build up (got {stress_t1:.4f})"


@pytest.mark.xfail(reason="Expected to fail initially - ordering exploit likely present")
def test_ordering_invariant_auc_matched_trajectories():
    """
    Ordering invariant: Two policies with identical stress AUC should produce
    similar growth outcomes regardless of timing pattern.

    This is the general form of the ordering exploit test.

    If this fails, it means action timing relative to update order creates
    arbitrage opportunities that agents can exploit to game the scheduler.
    """
    dose_uM = 1.5
    total_duration = 48.0
    dt_step = 12.0

    # ===== Policy 1: Steady dose =====
    vm1 = BiologicalVirtualMachine(seed=42)
    vm1.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vm1.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM)

    initial_count1 = vm1.vessel_states["Plate1_A01"].cell_count
    # Advance in dt_step chunks
    for _ in range(int(total_duration / dt_step)):
        vm1.advance_time(dt_step)
    final_count1 = vm1.vessel_states["Plate1_A01"].cell_count

    # ===== Policy 2: Alternating (on/off with matched AUC) =====
    vm2 = BiologicalVirtualMachine(seed=42)
    vm2.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")

    initial_count2 = vm2.vessel_states["Plate1_A01"].cell_count

    # Alternate: 12h on, 12h off (double dose when on to match AUC)
    vm2.treat_with_compound("Plate1_A01", "tunicamycin", dose_uM=dose_uM * 2.0)
    for _ in range(int((total_duration / 2) / dt_step)):
        vm2.advance_time(dt_step)

    vm2.washout_compound("Plate1_A01")
    for _ in range(int((total_duration / 2) / dt_step)):
        vm2.advance_time(dt_step)

    final_count2 = vm2.vessel_states["Plate1_A01"].cell_count

    # ===== Comparison =====
    growth_ratio1 = final_count1 / initial_count1
    growth_ratio2 = final_count2 / initial_count2

    difference_pct = abs(growth_ratio1 - growth_ratio2) / growth_ratio1 * 100

    print(f"\n=== AUC-Matched Trajectory Test ===")
    print(f"Policy 1 (Steady):      Growth ratio = {growth_ratio1:.4f}")
    print(f"Policy 2 (Alternating): Growth ratio = {growth_ratio2:.4f}")
    print(f"Difference: {difference_pct:.1f}%")

    # Invariant: Should be within 10% (allowing for nonlinear dynamics)
    tolerance_pct = 10.0

    assert difference_pct <= tolerance_pct, \
        f"AUC-matched policies differ by {difference_pct:.1f}% (tolerance: {tolerance_pct}%)"
