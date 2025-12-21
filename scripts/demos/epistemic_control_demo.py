#!/usr/bin/env python3
"""
Demo: Epistemic control system with scRNA-seq.

Shows how epistemic debt and penalties enforce calibrated justification.

Scenarios:
1. Well-calibrated agent (claims match reality)
2. Overclaiming agent (promises more than delivers)
3. Agent that widens posterior (scRNA makes things worse)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.epistemic_control import EpistemicController
import numpy as np


def simulate_mechanism_posterior_entropy(certainty_level: str) -> float:
    """
    Simulate entropy for different certainty levels.

    High certainty: P = {0.9, 0.08, 0.02} → H ≈ 0.4 bits
    Medium: P = {0.6, 0.3, 0.1} → H ≈ 0.9 bits
    Low: P = {0.4, 0.35, 0.25} → H ≈ 1.1 bits
    """
    distributions = {
        "high": [0.9, 0.08, 0.02],
        "medium": [0.6, 0.3, 0.1],
        "low": [0.4, 0.35, 0.25],
    }

    probs = distributions.get(certainty_level, distributions["medium"])
    return -sum(p * np.log(p) for p in probs if p > 0)


def run_scenario(name: str, episodes: list, base_cost: float = 200.0):
    """
    Run a scenario with multiple scRNA episodes.

    Args:
        name: Scenario name
        episodes: List of (claimed_gain, realized_gain) tuples
        base_cost: Base scRNA cost
    """
    print("\n" + "=" * 70)
    print(f"Scenario: {name}")
    print("=" * 70)

    controller = EpistemicController()
    controller.set_baseline_entropy(0.9)  # Medium uncertainty baseline

    total_reward = 0.0

    for i, (claimed, realized) in enumerate(episodes, 1):
        print(f"\n[Episode {i}]")

        # Check cost before action
        cost = controller.get_inflated_cost(base_cost)
        print(f"  Cost: ${cost:.2f} (base: ${base_cost:.2f})")

        # Claim
        action_id = f"scrna_{i}"
        controller.claim_action(action_id, "scrna_seq", claimed)
        print(f"  Claimed info gain: {claimed:.2f} bits")

        # Simulate entropy change
        if realized > 0:
            prior_entropy = 0.9
            posterior_entropy = prior_entropy - realized
        else:
            # Widened
            prior_entropy = 0.9
            posterior_entropy = prior_entropy - realized  # Adds (since realized < 0)

        # Measure
        actual_gain = controller.measure_information_gain(prior_entropy, posterior_entropy)
        print(f"  Realized info gain: {actual_gain:.2f} bits")

        # Resolve
        debt_increment = controller.resolve_action(action_id, actual_gain, "scrna_seq")
        print(f"  Debt increment: {debt_increment:.2f} bits")
        print(f"  Total debt: {controller.get_total_debt():.2f} bits")

        # Compute penalty
        penalty = controller.compute_penalty()
        if penalty.did_widen:
            print(f"  ⚠️  WIDENED posterior!")
        print(f"  Entropy penalty: {penalty.entropy_penalty:.2f}")
        print(f"  Horizon multiplier: {penalty.horizon_multiplier:.2f}")

        # Simulate reward (base reward - cost - penalty)
        episode_reward = 10.0 - cost/20.0 - penalty.entropy_penalty  # Simplified
        total_reward += episode_reward
        print(f"  Episode reward: {episode_reward:.2f}")

    print(f"\n{'─' * 70}")
    print(f"Final Statistics:")
    stats = controller.get_statistics()
    print(f"  Total debt: {stats['total_debt']:.2f} bits")
    print(f"  Cost multiplier: {stats['cost_multiplier']:.2f}×")
    print(f"  Mean overclaim: {stats['mean_overclaim']:.2f} bits")
    print(f"  Overclaim rate: {stats['overclaim_rate']:.1%}")
    print(f"  Total reward: {total_reward:.2f}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("Epistemic Control System Demo")
    print("=" * 70)
    print("\nPhilosophy: Uncertainty is conserved unless you earn the reduction.")
    print("This system enforces that principle through:")
    print("  • Epistemic debt (overclaiming accumulates)")
    print("  • Cost inflation (debt makes future actions expensive)")
    print("  • Entropy penalties (widening hurts)")

    # Scenario 1: Well-calibrated agent
    # Claims match reality, no debt accumulation
    run_scenario(
        "Well-Calibrated Agent",
        episodes=[
            (0.3, 0.3),  # Perfect calibration
            (0.4, 0.4),  # Perfect calibration
            (0.2, 0.2),  # Perfect calibration
        ]
    )

    # Scenario 2: Overclaiming agent
    # Promises more than delivers, debt accumulates
    run_scenario(
        "Overclaiming Agent (Bad Justification)",
        episodes=[
            (0.8, 0.2),  # Overclaimed by 0.6
            (0.7, 0.1),  # Overclaimed by 0.6
            (0.5, 0.0),  # Overclaimed by 0.5
        ]
    )

    # Scenario 3: Agent that widens posterior
    # scRNA makes things WORSE (batch drift + cell cycle)
    run_scenario(
        "Agent That Widens Posterior (scRNA Backfires)",
        episodes=[
            (0.5, -0.3),  # Claimed gain, got widening!
            (0.4, -0.2),  # Another widening
            (0.3, 0.1),   # Finally some gain
        ]
    )

    print("\n" + "=" * 70)
    print("Key Takeaways")
    print("=" * 70)
    print("""
1. Well-calibrated agents:
   • No debt accumulation
   • Stable costs
   • High cumulative reward

2. Overclaiming agents:
   • Debt accumulates (1.7 bits after 3 episodes)
   • Costs inflate (19% by episode 3)
   • Lower cumulative reward

3. Agents that widen posteriors:
   • Massive debt (overclaim + widening)
   • Heavy entropy penalties
   • Severely reduced reward
   • Planning horizon shrinks

Conclusion: The system enforces honest, calibrated justifications.
             scRNA is not a ground truth oracle—it's a risk-bearing intervention.
""")


if __name__ == "__main__":
    main()
