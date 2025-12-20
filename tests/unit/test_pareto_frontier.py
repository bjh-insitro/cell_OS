"""
Phase 4 Option 1: Pareto frontier test (continuous control landscape).

This test verifies that the decision problem has a non-trivial landscape:
- Multiple policies are evaluated
- A Pareto frontier emerges (tradeoff between mechanism engagement and death)
- Best policies are non-degenerate (not "do nothing", not "washout spam")

This is where the sandbox becomes a decision problem with structure, not two hardcoded points.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path

from cell_os.hardware.episode import EpisodeRunner, Policy, Action


def test_policy_enumeration():
    """
    Enumerate policies and verify landscape structure.

    Expected:
    - Top policies beat continuous and control
    - Pulse-like policies (1 washout) dominate
    - Double-pulse (2 washouts) may win if dose is tuned
    - Control (no treatment) is worst
    - "Do nothing" is NOT the best policy
    """
    print("\n=== Policy Enumeration Test ===")

    runner = EpisodeRunner(
        compound="paclitaxel",
        reference_dose_uM=0.005,
        cell_line="A549",
        horizon_h=48.0,
        step_h=6.0,
        seed=42
    )

    # Enumerate all policies up to 2 washouts
    results = runner.enumerate_policies(max_washouts=2)

    print(f"\n{'='*90}")
    print(f"{'Policy':<30} {'Mechanism':<12} {'Death':<10} {'Ops':<8} {'Reward':<10}")
    print(f"{'='*90}")

    for policy, receipt, trajectory in results[:15]:  # Top 15
        print(f"{policy.name:<30} "
              f"{'HIT' if receipt.mechanism_hit else 'MISS':<12} "
              f"{receipt.total_dead_48h:>8.1%} "
              f"{receipt.washout_count + receipt.feed_count:>8d} "
              f"{receipt.reward_total:>10.3f}")

    # Get top policy
    best_policy, best_receipt, best_trajectory = results[0]
    worst_policy, worst_receipt, worst_trajectory = results[-1]

    print(f"\n{'='*90}")
    print(f"Best policy: {best_policy.name}")
    print(f"  Mechanism: {'HIT' if best_receipt.mechanism_hit else 'MISS'} (actin {best_receipt.actin_fold_12h:.2f}×)")
    print(f"  Death: {best_receipt.total_dead_48h:.1%}")
    print(f"  Ops: {best_receipt.washout_count + best_receipt.feed_count}")
    print(f"  Reward: {best_receipt.reward_total:.3f}")

    print(f"\nWorst policy: {worst_policy.name}")
    print(f"  Mechanism: {'HIT' if worst_receipt.mechanism_hit else 'MISS'} (actin {worst_receipt.actin_fold_12h:.2f}×)")
    print(f"  Death: {worst_receipt.total_dead_48h:.1%}")
    print(f"  Ops: {worst_receipt.washout_count + worst_receipt.feed_count}")
    print(f"  Reward: {worst_receipt.reward_total:.3f}")

    # Find control policy
    control_result = [r for r in results if r[0].name == "control"]
    if control_result:
        control_policy, control_receipt, control_trajectory = control_result[0]
        print(f"\nControl policy (no treatment):")
        print(f"  Mechanism: {'HIT' if control_receipt.mechanism_hit else 'MISS'} (actin {control_receipt.actin_fold_12h:.2f}×)")
        print(f"  Death: {control_receipt.total_dead_48h:.1%}")
        print(f"  Reward: {control_receipt.reward_total:.3f}")

    # Assertions

    # 1. Best policy should hit mechanism
    assert best_receipt.mechanism_hit, (
        f"Best policy should hit mechanism: {best_policy.name} (actin {best_receipt.actin_fold_12h:.2f}×)"
    )

    # 2. Best policy should NOT be control (doing nothing)
    assert best_policy.name != "control", (
        f"Best policy should not be 'do nothing': {best_policy.name}"
    )

    # 3. Best policy should NOT be continuous (should be pulse-like)
    # Pulse should beat continuous due to lower death
    continuous_results = [r for r in results if "continuous" in r[0].name]
    if continuous_results:
        best_continuous = continuous_results[0]
        best_continuous_reward = best_continuous[1].reward_total
        assert best_receipt.reward_total > best_continuous_reward, (
            f"Best policy should beat best continuous: "
            f"{best_policy.name} ({best_receipt.reward_total:.3f}) vs "
            f"{best_continuous[0].name} ({best_continuous_reward:.3f})"
        )

    # 4. Best policy should have 1-2 washouts (pulse-like)
    assert 1 <= best_receipt.washout_count <= 2, (
        f"Best policy should have 1-2 washouts (pulse-like): {best_receipt.washout_count}"
    )

    # 5. Control should be worse than best (verify non-trivial landscape)
    if control_result:
        assert best_receipt.reward_total > control_receipt.reward_total, (
            f"Best policy should beat control: "
            f"{best_receipt.reward_total:.3f} vs {control_receipt.reward_total:.3f}"
        )

    # 6. Multiple policies should hit mechanism (non-degenerate)
    mechanism_hit_count = sum(1 for _, receipt, _ in results if receipt.mechanism_hit)
    print(f"\nPolicies hitting mechanism: {mechanism_hit_count}/{len(results)}")
    assert mechanism_hit_count >= 3, (
        f"At least 3 policies should hit mechanism: {mechanism_hit_count}"
    )

    print(f"\n✓ PASSED: Policy enumeration produces non-degenerate landscape")


def test_pareto_frontier():
    """
    Verify Pareto frontier emergence via existence proof (not exhaustive search).

    Existence proof assertions:
    1. At least 3 non-dominated policies exist (non-trivial frontier)
    2. Trivial policies (control, continuous high-dose) are dominated
    3. Pulse-like policies appear in top-5 by reward

    This keeps CI sane by avoiding exhaustive enumeration.
    """
    print("\n=== Pareto Frontier Existence Proof ===")

    runner = EpisodeRunner(
        compound="paclitaxel",
        reference_dose_uM=0.005,
        cell_line="A549",
        horizon_h=48.0,
        step_h=6.0,
        seed=42
    )

    # Enumerate policies (cache makes this fast on repeated runs)
    results = runner.enumerate_policies(max_washouts=2)

    # Extract data for plotting
    mechanism_scores = [r[1].actin_fold_12h for r in results]
    deaths = [r[1].total_dead_48h for r in results]
    ops_counts = [r[1].washout_count + r[1].feed_count for r in results]
    rewards = [r[1].reward_total for r in results]
    names = [r[0].name for r in results]

    # Find Pareto frontier (non-dominated points)
    # A point dominates another if it has higher mechanism AND lower death
    pareto_indices = []
    for i in range(len(results)):
        dominated = False
        for j in range(len(results)):
            if i == j:
                continue
            # j dominates i if: mechanism_j >= mechanism_i AND death_j < death_i
            if mechanism_scores[j] >= mechanism_scores[i] and deaths[j] < deaths[i]:
                dominated = True
                break
        if not dominated:
            pareto_indices.append(i)

    print(f"\nPareto frontier has {len(pareto_indices)} points out of {len(results)} policies")

    # Plot frontier
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left plot: Mechanism vs Death (Pareto frontier)
    scatter = ax1.scatter(mechanism_scores, deaths, c=ops_counts, s=100, alpha=0.6, cmap='viridis')
    ax1.scatter([mechanism_scores[i] for i in pareto_indices],
                [deaths[i] for i in pareto_indices],
                s=200, facecolors='none', edgecolors='red', linewidths=2,
                label='Pareto frontier')

    # Annotate top 5 policies
    for i in range(min(5, len(results))):
        ax1.annotate(names[i], (mechanism_scores[i], deaths[i]),
                     xytext=(5, 5), textcoords='offset points', fontsize=8)

    ax1.set_xlabel('Mechanism Score (actin fold-change at 12h)', fontsize=12)
    ax1.set_ylabel('Death at 48h', fontsize=12)
    ax1.set_title('Pareto Frontier: Mechanism vs Death', fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax1)
    cbar.set_label('Ops Count', fontsize=10)

    # Right plot: Mechanism vs Reward
    scatter2 = ax2.scatter(mechanism_scores, rewards, c=ops_counts, s=100, alpha=0.6, cmap='viridis')
    for i in range(min(5, len(results))):
        ax2.annotate(names[i], (mechanism_scores[i], rewards[i]),
                     xytext=(5, 5), textcoords='offset points', fontsize=8)

    ax2.set_xlabel('Mechanism Score (actin fold-change at 12h)', fontsize=12)
    ax2.set_ylabel('Total Reward', fontsize=12)
    ax2.set_title('Reward Landscape', fontsize=14)
    ax2.grid(True, alpha=0.3)
    cbar2 = plt.colorbar(scatter2, ax=ax2)
    cbar2.set_label('Ops Count', fontsize=10)

    plt.tight_layout()

    # Save plot
    output_dir = Path("/Users/bjh/cell_OS/tests/unit/figures")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "pareto_frontier.png"
    plt.savefig(output_path, dpi=150)
    print(f"\nPareto frontier plot saved to: {output_path}")

    # Print Pareto frontier policies
    print(f"\n{'='*90}")
    print(f"Pareto Frontier Policies:")
    print(f"{'='*90}")
    print(f"{'Policy':<30} {'Mechanism':<12} {'Death':<10} {'Ops':<8} {'Reward':<10}")
    print(f"{'-'*90}")

    pareto_results = [results[i] for i in sorted(pareto_indices, key=lambda i: -rewards[i])]
    for policy, receipt, trajectory in pareto_results:
        print(f"{policy.name:<30} "
              f"{receipt.actin_fold_12h:>10.2f}× "
              f"{receipt.total_dead_48h:>9.1%} "
              f"{receipt.washout_count + receipt.feed_count:>8d} "
              f"{receipt.reward_total:>10.3f}")

    # Existence Proof Assertions

    # 1. At least 3 non-dominated policies exist (non-trivial frontier)
    print(f"\n=== Assertion 1: Non-trivial frontier ===")
    print(f"Pareto frontier has {len(pareto_indices)} non-dominated policies")
    assert len(pareto_indices) >= 3, (
        f"Expected ≥3 non-dominated policies, got {len(pareto_indices)}"
    )
    print("✓ PASS: Frontier has ≥3 policies")

    # 2. Trivial policies are dominated
    print(f"\n=== Assertion 2: Trivial policies dominated ===")

    # Control (do nothing) should be dominated
    control_results = [r for r in results if r[0].name == "control"]
    if control_results:
        control_idx = results.index(control_results[0])
        control_dominated = control_idx not in pareto_indices
        print(f"Control policy dominated: {control_dominated}")
        assert control_dominated, "Control (do nothing) should be dominated"

    # Continuous 1.0× (high dose, no washout) should be dominated
    continuous_1x = [r for r in results if r[0].name == "continuous_1.00×"]
    if continuous_1x:
        continuous_idx = results.index(continuous_1x[0])
        continuous_dominated = continuous_idx not in pareto_indices
        print(f"Continuous 1.0× dominated: {continuous_dominated}")
        assert continuous_dominated, "Continuous 1.0× should be dominated by pulse"

    print("✓ PASS: Trivial policies are dominated")

    # 3. Pulse-like policies appear in top-5 reward
    print(f"\n=== Assertion 3: Pulse-like in top-5 ===")
    top5_names = [results[i][0].name for i in range(min(5, len(results)))]
    pulse_in_top5 = any("pulse" in name for name in top5_names)
    print(f"Top 5 policies: {top5_names}")
    print(f"Pulse in top-5: {pulse_in_top5}")
    assert pulse_in_top5, f"Expected pulse-like policy in top-5, got: {top5_names}"
    print("✓ PASS: Pulse-like appears in top-5")

    print(f"\n✓ PASSED: Pareto frontier existence proof complete")


if __name__ == "__main__":
    test_policy_enumeration()
    test_pareto_frontier()
    print("\n=== Phase 4 Option 1: Pareto Frontier Tests Complete ===")
