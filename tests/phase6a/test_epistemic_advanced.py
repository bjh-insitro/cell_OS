"""
Test: Advanced epistemic features (global inflation, volatility, stability).

Tests the loophole-closing improvements:
1. Global inflation prevents "debt farming" with cheap assays
2. Volatility detection penalizes thrashing
3. Calibration stability penalizes erratic agents
"""

import numpy as np

from cell_os.epistemic_agent import EpistemicController, EntropySource
from cell_os.epistemic_agent import EntropyVolatilityTracker, CalibrationStabilityTracker


def test_global_inflation_prevents_debt_farming():
    """
    Test that ALL actions face inflation, not just expensive ones.

    This prevents agents from "farming debt" by spamming cheap assays
    to grind down debt without learning.
    """
    controller = EpistemicController()

    # Accumulate debt
    controller.claim_action("scrna_001", "scrna_seq", 1.0)
    controller.resolve_action("scrna_001", 0.0)  # Massive overclaim → 1.0 bit debt

    # Check inflation on cheap assay
    cheap_cost = 20.0  # Imaging
    inflated_cheap = controller.get_inflated_cost(cheap_cost)

    # Should have SOME inflation (global component)
    global_inflation = inflated_cheap - cheap_cost
    assert global_inflation > 0, f"Cheap assay should face global inflation, got ${inflated_cheap:.2f}"

    # Check inflation on expensive assay
    expensive_cost = 200.0  # scRNA
    inflated_expensive = controller.get_inflated_cost(expensive_cost)

    # Should have MORE inflation (global + specific)
    expensive_inflation = inflated_expensive - expensive_cost
    assert expensive_inflation > global_inflation * 5, (
        f"Expensive assay should face more inflation than cheap\n"
        f"  Cheap: ${global_inflation:.2f}\n"
        f"  Expensive: ${expensive_inflation:.2f}"
    )

    print("✓ Global inflation prevents debt farming")
    print(f"  Debt: 1.0 bits")
    print(f"  Cheap assay ($20): ${inflated_cheap:.2f} ({global_inflation/cheap_cost:.1%} increase)")
    print(f"  Expensive assay ($200): ${inflated_expensive:.2f} ({expensive_inflation/expensive_cost:.1%} increase)")


def test_volatility_detects_thrashing():
    """
    Test that volatility tracker detects epistemic thrashing.

    Thrashing = entropy oscillates wildly without making progress.
    """
    tracker = EntropyVolatilityTracker(
        window_size=10,
        volatility_threshold=0.25,
        penalty_weight=0.5
    )

    # Stable entropy trajectory (good)
    stable_trajectory = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    for h in stable_trajectory:
        tracker.add(h)

    volatility_stable = tracker.compute_volatility()
    is_thrashing_stable = tracker.is_thrashing()

    print(f"\nStable trajectory: {stable_trajectory}")
    print(f"  Volatility: {volatility_stable:.3f}")
    print(f"  Is thrashing: {is_thrashing_stable}")
    assert not is_thrashing_stable, "Stable trajectory should not be flagged as thrashing"

    # Reset and try thrashing trajectory
    tracker.reset()

    # Thrashing trajectory (bad)
    thrashing_trajectory = [2.0, 2.3, 1.9, 2.4, 2.0, 2.5, 1.8, 2.6]
    for h in thrashing_trajectory:
        tracker.add(h)

    volatility_thrashing = tracker.compute_volatility()
    is_thrashing_thrashing = tracker.is_thrashing()

    print(f"\nThrashing trajectory: {thrashing_trajectory}")
    print(f"  Volatility: {volatility_thrashing:.3f}")
    print(f"  Is thrashing: {is_thrashing_thrashing}")
    assert is_thrashing_thrashing, "Thrashing trajectory should be flagged"

    # Penalty should apply
    penalty = tracker.compute_penalty()
    assert penalty > 0, f"Thrashing should have penalty, got {penalty}"

    print(f"  Penalty: {penalty:.3f}")
    print("✓ Volatility detection works")


def test_calibration_stability_penalizes_erratic_agents():
    """
    Test that calibration stability tracker penalizes erratic agents.

    Erratic = sometimes right, sometimes wildly wrong (high variance).
    Even if mean error is low, high variance indicates bad calibration.
    """
    tracker = CalibrationStabilityTracker(window_size=10)

    # Consistent agent (good)
    # Always overestimates by ~0.1 bits
    consistent_errors = [
        (0.6, 0.5),  # error = 0.1
        (0.7, 0.6),  # error = 0.1
        (0.5, 0.4),  # error = 0.1
        (0.8, 0.7),  # error = 0.1
        (0.4, 0.3),  # error = 0.1
    ]

    for claimed, realized in consistent_errors:
        tracker.add_error(claimed, realized)

    stability_consistent = tracker.compute_stability()
    penalty_consistent = tracker.compute_penalty()

    print(f"\nConsistent agent:")
    print(f"  Errors: {[c - r for c, r in consistent_errors]}")
    print(f"  Stability: {stability_consistent:.3f}")
    print(f"  Penalty: {penalty_consistent:.3f}")
    assert stability_consistent > 0.9, "Consistent agent should be stable"
    assert penalty_consistent < 0.05, "Consistent agent should have low penalty"

    # Reset and try erratic agent
    tracker.reset()

    # Erratic agent (bad)
    # Sometimes spot-on, sometimes wildly wrong
    erratic_errors = [
        (0.5, 0.5),  # error = 0.0 (lucky!)
        (0.9, 0.1),  # error = 0.8 (way off)
        (0.6, 0.6),  # error = 0.0 (lucky again)
        (0.8, 0.0),  # error = 0.8 (way off again)
        (0.4, 0.4),  # error = 0.0 (lucky)
        (0.9, 0.0),  # error = 0.9 (catastrophic)
        (0.5, 0.5),  # error = 0.0
    ]

    for claimed, realized in erratic_errors:
        tracker.add_error(claimed, realized)

    stability_erratic = tracker.compute_stability()
    penalty_erratic = tracker.compute_penalty()

    print(f"\nErratic agent:")
    print(f"  Errors: {[c - r for c, r in erratic_errors]}")
    print(f"  Stability: {stability_erratic:.3f}")
    print(f"  Penalty: {penalty_erratic:.3f}")
    assert stability_erratic < 0.5, "Erratic agent should be unstable"
    assert penalty_erratic > penalty_consistent * 3, "Erratic agent should have higher penalty"

    print("✓ Calibration stability tracking works")


def test_integrated_advanced_features():
    """
    Test all advanced features working together.

    Scenario: Agent that thrashes AND is erratic.
    """
    controller = EpistemicController()
    controller.set_baseline_entropy(1.5)

    print("\n" + "="*60)
    print("Integrated Test: Thrashing + Erratic Agent")
    print("="*60)

    # Simulate 8 episodes with thrashing entropy and erratic calibration
    episodes = [
        (2.0, 2.3, 0.8, 0.7),  # (prior, post, claimed, realized)
        (2.3, 1.9, 0.6, 0.1),  # Thrashing entropy, erratic calibration
        (1.9, 2.4, 0.7, 0.7),  # Sometimes right...
        (2.4, 2.0, 0.5, 0.0),  # Sometimes wrong...
        (2.0, 2.5, 0.6, 0.2),
        (2.5, 1.8, 0.8, 0.0),  # Wildly wrong
        (1.8, 2.3, 0.5, 0.5),  # Right again
        (2.3, 2.6, 0.4, 0.0),
    ]

    total_penalty = 0.0

    for i, (prior, post, claimed, realized) in enumerate(episodes, 1):
        # Claim
        controller.claim_action(f"action_{i}", "scrna_seq", claimed)

        # Measure
        controller.measure_information_gain(
            prior, post,
            EntropySource.MEASUREMENT_AMBIGUOUS
        )

        # Resolve
        controller.resolve_action(f"action_{i}", realized, "scrna_seq")

        # Penalty
        penalty = controller.compute_penalty("scrna_seq")
        total_penalty += penalty.entropy_penalty

        if i % 2 == 0:
            print(f"  Episode {i}: entropy={post:.2f}, penalty={penalty.entropy_penalty:.3f}")

    # Final stats
    stats = controller.get_statistics()

    print(f"\n{'─'*60}")
    print("Final Statistics:")
    print(f"  Total debt: {stats['total_debt']:.2f} bits")
    print(f"  Volatility: {stats['volatility_volatility']:.3f}")
    print(f"  Is thrashing: {stats['volatility_is_thrashing']}")
    print(f"  Stability: {stats['stability_stability']:.3f}")
    print(f"  Total penalty accumulated: {total_penalty:.2f}")

    # Verify features are working
    assert stats['volatility_is_thrashing'], "Should detect thrashing"
    assert stats['stability_stability'] < 0.7, "Should detect instability"
    assert total_penalty > 1.0, "Total penalty should be substantial"

    # Check cost inflation (both debt and instability)
    cost_mult = controller.get_cost_multiplier(base_cost=200.0)
    print(f"  Cost multiplier: {cost_mult:.2f}×")
    assert cost_mult > 1.1, "Cost should be inflated"

    print("✓ All advanced features working together")


if __name__ == "__main__":
    print("="*60)
    print("Advanced Epistemic Features Tests")
    print("="*60)

    test_global_inflation_prevents_debt_farming()
    test_volatility_detects_thrashing()
    test_calibration_stability_penalizes_erratic_agents()
    test_integrated_advanced_features()

    print("\n" + "="*60)
    print("✓ All advanced tests passed")
    print("="*60)
    print("\nLoopholes closed:")
    print("  1. Global inflation: Can't farm debt with cheap assays")
    print("  2. Volatility tracking: Thrashing is expensive")
    print("  3. Calibration stability: Erratic agents face cost penalties")
    print("\nThe system is now robust against sophisticated gaming strategies.")
