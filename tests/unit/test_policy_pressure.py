"""
Phase 3: Policy pressure tests (pulse vs continuous tradeoffs).

These tests verify that the reward function creates real policy pressure:
- Continuous dosing kills more than pulse at matched mechanism engagement
- Pulse shows recovery after washout
- Identifiability holds under intervention policies

This is where "doing the locally good thing" causes later failure.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.reward import compute_microtubule_mechanism_reward


def test_pulse_vs_continuous_tradeoff():
    """
    Pulse dosing should beat continuous at matched mechanism engagement.

    Both policies:
    - Apply paclitaxel to hit actin structural target >1.4× at 12h
    - Measure death at 48h
    - Compare rewards

    Expected:
    - Both hit mechanism (reward_mechanism = 1.0)
    - Pulse has lower death (less mitotic hazard accumulation)
    - Pulse has higher ops cost (washout operation)
    - Pulse has HIGHER total reward (death penalty >> ops cost)

    This creates policy pressure: "short pulse achieves effect with less death."
    """
    print("\n=== Pulse vs Continuous Tradeoff ===")

    # Policy 1: Continuous exposure (48h)
    vm_continuous = BiologicalVirtualMachine(seed=42)
    vm_continuous.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Measure baseline
    baseline_result = vm_continuous.cell_painting_assay("test")
    baseline_actin = baseline_result['morphology_struct']['actin']

    # Apply compound and run continuous
    vm_continuous.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    vm_continuous.advance_time(12.0)

    # Measure mechanism engagement at 12h
    result_12h_continuous = vm_continuous.cell_painting_assay("test")
    actin_12h_continuous = result_12h_continuous['morphology_struct']['actin']

    # Continue to 48h (no washout)
    vm_continuous.advance_time(36.0)
    vessel_continuous = vm_continuous.vessel_states["test"]
    viability_48h_continuous = vessel_continuous.viability

    # Compute reward for continuous
    receipt_continuous = compute_microtubule_mechanism_reward(
        actin_struct_12h=actin_12h_continuous,
        baseline_actin=baseline_actin,
        viability_48h=viability_48h_continuous,
        washout_count=0,
        feed_count=0
    )

    print(f"\nContinuous policy (48h exposure):")
    print(f"  Actin at 12h: {receipt_continuous.actin_fold_12h:.2f}× baseline")
    print(f"  Mechanism hit: {receipt_continuous.mechanism_hit}")
    print(f"  Death at 48h: {receipt_continuous.total_dead_48h:.1%}")
    print(f"  Ops cost: {receipt_continuous.ops_cost:.2f}")
    print(f"  Reward: {receipt_continuous.reward_total:.2f}")

    # Policy 2: Pulse exposure (12h drug, washout, 36h recovery)
    vm_pulse = BiologicalVirtualMachine(seed=42)
    vm_pulse.seed_vessel("test", "A549", 1e6, capacity=1e7, initial_viability=0.98)

    # Apply compound
    vm_pulse.treat_with_compound("test", "paclitaxel", dose_uM=0.005)
    vm_pulse.advance_time(12.0)

    # Measure mechanism engagement at 12h (before washout)
    result_12h_pulse = vm_pulse.cell_painting_assay("test")
    actin_12h_pulse = result_12h_pulse['morphology_struct']['actin']

    # Washout at 12h
    washout_result = vm_pulse.washout_compound("test")

    # Recovery phase (36h)
    vm_pulse.advance_time(36.0)
    vessel_pulse = vm_pulse.vessel_states["test"]
    viability_48h_pulse = vessel_pulse.viability

    # Compute reward for pulse
    receipt_pulse = compute_microtubule_mechanism_reward(
        actin_struct_12h=actin_12h_pulse,
        baseline_actin=baseline_actin,
        viability_48h=viability_48h_pulse,
        washout_count=1,
        feed_count=0
    )

    print(f"\nPulse policy (12h exposure, washout, 36h recovery):")
    print(f"  Actin at 12h: {receipt_pulse.actin_fold_12h:.2f}× baseline")
    print(f"  Mechanism hit: {receipt_pulse.mechanism_hit}")
    print(f"  Death at 48h: {receipt_pulse.total_dead_48h:.1%}")
    print(f"  Ops cost: {receipt_pulse.ops_cost:.2f}")
    print(f"  Reward: {receipt_pulse.reward_total:.2f}")

    # Comparison
    print(f"\n=== Policy Comparison ===")
    print(f"Death reduction: {(receipt_continuous.total_dead_48h - receipt_pulse.total_dead_48h) / receipt_continuous.total_dead_48h:+.1%}")
    print(f"Ops cost increase: {receipt_pulse.ops_cost - receipt_continuous.ops_cost:+.2f}")
    print(f"Reward improvement: {receipt_pulse.reward_total - receipt_continuous.reward_total:+.2f}")

    # Assertions
    # 1. Both should hit mechanism
    assert receipt_continuous.mechanism_hit, (
        f"Continuous should hit mechanism: actin={receipt_continuous.actin_fold_12h:.2f}× (threshold=1.4×)"
    )
    assert receipt_pulse.mechanism_hit, (
        f"Pulse should hit mechanism: actin={receipt_pulse.actin_fold_12h:.2f}× (threshold=1.4×)"
    )

    # 2. Actin at 12h should be similar (both measure before/at washout)
    actin_ratio = receipt_pulse.actin_fold_12h / receipt_continuous.actin_fold_12h
    assert 0.9 < actin_ratio < 1.1, (
        f"Actin at 12h should be similar: continuous={receipt_continuous.actin_fold_12h:.2f}×, "
        f"pulse={receipt_pulse.actin_fold_12h:.2f}× (ratio={actin_ratio:.2f})"
    )

    # 3. Pulse should have less death
    assert receipt_pulse.total_dead_48h < receipt_continuous.total_dead_48h, (
        f"Pulse should have less death: continuous={receipt_continuous.total_dead_48h:.1%}, "
        f"pulse={receipt_pulse.total_dead_48h:.1%}"
    )

    # Death reduction should be substantial (>20%)
    death_reduction = (receipt_continuous.total_dead_48h - receipt_pulse.total_dead_48h) / receipt_continuous.total_dead_48h
    assert death_reduction > 0.20, (
        f"Death reduction should be >20%: {death_reduction:.1%}"
    )

    # 4. Pulse should have higher ops cost (washout operation)
    assert receipt_pulse.ops_cost > receipt_continuous.ops_cost, (
        f"Pulse should have higher ops cost: continuous={receipt_continuous.ops_cost:.2f}, "
        f"pulse={receipt_pulse.ops_cost:.2f}"
    )

    # 5. Pulse should have HIGHER total reward (death penalty >> ops cost)
    assert receipt_pulse.reward_total > receipt_continuous.reward_total, (
        f"Pulse should have higher reward: continuous={receipt_continuous.reward_total:.2f}, "
        f"pulse={receipt_pulse.reward_total:.2f}"
    )

    reward_improvement = receipt_pulse.reward_total - receipt_continuous.reward_total
    assert reward_improvement > 0.1, (
        f"Reward improvement should be substantial: {reward_improvement:.2f}"
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"✓ PASSED: Pulse beats continuous at matched mechanism")
    print(f"{'='*60}")
    print(f"\nKey tradeoffs:")
    print(f"  Mechanism engagement: MATCHED ({receipt_continuous.actin_fold_12h:.1f}× vs {receipt_pulse.actin_fold_12h:.1f}×)")
    print(f"  Death: Pulse WINS ({receipt_pulse.total_dead_48h:.0%} vs {receipt_continuous.total_dead_48h:.0%}, {death_reduction:+.0%})")
    print(f"  Ops cost: Pulse LOSES ({receipt_pulse.ops_cost:.2f} vs {receipt_continuous.ops_cost:.2f}, +{receipt_pulse.ops_cost - receipt_continuous.ops_cost:.2f})")
    print(f"  Total reward: Pulse WINS ({receipt_pulse.reward_total:.2f} vs {receipt_continuous.reward_total:.2f}, +{reward_improvement:.2f})")
    print(f"\nPolicy pressure verified: Death penalty >> ops cost makes pulse dominant strategy.")


if __name__ == "__main__":
    test_pulse_vs_continuous_tradeoff()
    print("\n=== Phase 3 Policy Pressure: First Test Complete ===")
