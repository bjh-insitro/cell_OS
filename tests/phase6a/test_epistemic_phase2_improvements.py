"""
Test Phase 2 epistemic improvements: time-weighted provisional penalties and sandbagging detection.
"""

import numpy as np

from cell_os.epistemic_control import EpistemicController, EntropySource
from cell_os.epistemic_provisional import ProvisionalPenaltyTracker
from cell_os.epistemic_sandbagging import SandbaggingDetector, detect_sandbagging


def test_time_weighted_provisional_penalties():
    """
    Test that provisional penalties settle based on real time, not episode count.

    This prevents agents from spamming cheap fast actions to age out penalties.
    """
    tracker = ProvisionalPenaltyTracker()

    # Add provisional penalty with 12h settlement time
    tracker.add_provisional_penalty(
        action_id="widen_1",
        penalty_amount=0.5,
        prior_entropy=1.5,
        settlement_time_h=12.0
    )

    print("\n" + "="*60)
    print("Test: Time-Weighted Provisional Penalties")
    print("="*60)
    print(f"Initial penalty: 0.5, settlement time: 12h")

    # Scenario 1: Rapid actions (3× 5min imaging = 15min = 0.25h)
    print("\n--- Scenario 1: Rapid Actions (3× 5min imaging) ---")
    for i in range(3):
        finalized = tracker.step(current_entropy=2.0, time_increment_h=5.0/60)  # 5 minutes
        print(f"  Step {i+1}: time_elapsed={tracker.provisional_penalties['widen_1'].time_elapsed_h:.2f}h, finalized={finalized:.2f}")

    # Should NOT settle yet (only 0.25h < 12h)
    assert not tracker.provisional_penalties["widen_1"].settled, "Should not settle after rapid actions"
    print("  ✓ Penalty NOT settled (0.25h < 12h)")

    # Scenario 2: Slow action (1× 4h scRNA)
    print("\n--- Scenario 2: Slow Action (1× 4h scRNA) ---")
    finalized = tracker.step(current_entropy=2.0, time_increment_h=4.0)
    print(f"  Step 4: time_elapsed={tracker.provisional_penalties['widen_1'].time_elapsed_h:.2f}h, finalized={finalized:.2f}")

    assert not tracker.provisional_penalties["widen_1"].settled, "Should not settle yet (4.25h < 12h)"
    print("  ✓ Penalty NOT settled (4.25h < 12h)")

    # Scenario 3: More slow actions to cross threshold
    print("\n--- Scenario 3: More Slow Actions (2× 4h scRNA) ---")
    for i in range(2):
        finalized = tracker.step(current_entropy=2.0, time_increment_h=4.0)
        print(f"  Step {i+5}: time_elapsed={tracker.provisional_penalties['widen_1'].time_elapsed_h:.2f}h, finalized={finalized:.2f}")

    # Should settle now (12.25h >= 12h)
    assert tracker.provisional_penalties["widen_1"].settled, "Should settle after time threshold"
    print(f"  ✓ Penalty FINALIZED (12.25h >= 12h), finalized amount: {finalized:.2f}")

    print("\n✓ Time-weighted provisional penalties work correctly")
    print("  Rapid spam can't age out penalties, real time matters")


def test_sandbagging_detection():
    """
    Test that systematic underclaiming is detected and penalized.
    """
    detector = SandbaggingDetector(
        sandbagging_threshold=2.0,
        credit_discount=0.5
    )

    print("\n" + "="*60)
    print("Test: Sandbagging Detection")
    print("="*60)

    # Scenario 1: Well-calibrated agent
    print("\n--- Scenario 1: Well-Calibrated Agent ---")
    calibrated_claims = [0.3, 0.4, 0.5, 0.3, 0.4]
    calibrated_realized = [0.3, 0.4, 0.5, 0.3, 0.4]

    for claimed, realized in zip(calibrated_claims, calibrated_realized):
        detector.add_observation(claimed, realized)

    is_sandbagging = detector.is_sandbagging()
    mean_surprise = detector.compute_mean_surprise()

    print(f"  Claims: {calibrated_claims}")
    print(f"  Realized: {calibrated_realized}")
    print(f"  Mean surprise: {mean_surprise:.2f}")
    print(f"  Is sandbagging: {is_sandbagging}")

    assert not is_sandbagging, "Well-calibrated agent should not be flagged"
    print("  ✓ Well-calibrated agent not flagged")

    # Reset for next scenario
    detector.reset()

    # Scenario 2: Sandbagging agent
    print("\n--- Scenario 2: Sandbagging Agent ---")
    sandbagging_claims = [0.1, 0.1, 0.1, 0.1, 0.1]
    sandbagging_realized = [0.8, 0.7, 0.9, 0.6, 0.8]

    for claimed, realized in zip(sandbagging_claims, sandbagging_realized):
        detector.add_observation(claimed, realized)

    is_sandbagging = detector.is_sandbagging()
    mean_surprise = detector.compute_mean_surprise()

    print(f"  Claims: {sandbagging_claims}")
    print(f"  Realized: {sandbagging_realized}")
    print(f"  Mean surprise: {mean_surprise:.2f}")
    print(f"  Is sandbagging: {is_sandbagging}")

    assert is_sandbagging, "Sandbagging agent should be flagged"
    assert mean_surprise > 2.0, f"Mean surprise should be > 2.0, got {mean_surprise}"
    print("  ✓ Sandbagging agent correctly flagged")

    # Test credit discount
    print("\n--- Testing Credit Discount ---")
    claimed_next = 0.1
    realized_next = 0.9
    credited = detector.compute_credit_discount(claimed_next, realized_next)

    print(f"  New claim: {claimed_next}")
    print(f"  Realized: {realized_next}")
    print(f"  Credited: {credited:.2f} (50% discount on excess)")

    assert credited < realized_next, "Sandbagging should reduce credited gain"
    expected_credited = claimed_next + (realized_next - claimed_next) * 0.5
    assert abs(credited - expected_credited) < 0.01, f"Expected {expected_credited}, got {credited}"

    print(f"  ✓ Credit discount applied correctly")
    print(f"    Formula: claimed + (excess × discount) = {claimed_next} + ({realized_next - claimed_next} × 0.5) = {credited:.2f}")

    print("\n✓ Sandbagging detection works correctly")


def test_integrated_phase2_improvements():
    """
    Test both improvements integrated into EpistemicController.
    """
    controller = EpistemicController()
    controller.set_baseline_entropy(2.0)

    print("\n" + "="*60)
    print("Test: Integrated Phase 2 Improvements")
    print("="*60)

    # Simulate sandbagging agent
    print("\n--- Sandbagging Agent (5 episodes) ---")

    total_debt = 0.0
    total_credited = 0.0
    total_realized = 0.0

    for i in range(5):
        # Agent always claims low
        controller.claim_action(f"action_{i}", "scrna_seq", expected_gain_bits=0.2)

        # Measure (always high realized gain)
        prior = 2.0 - (i * 0.1)
        posterior = prior - 0.7  # 0.7 bits actual gain
        realized = controller.measure_information_gain(
            prior, posterior, EntropySource.MEASUREMENT_NARROWING
        )

        # Resolve (sandbagging discount should apply after 3rd observation)
        debt_increment = controller.resolve_action(f"action_{i}", realized, "scrna_seq")

        total_debt += debt_increment
        total_realized += realized

        # Get credited amount from ledger
        claim = controller.ledger.claims[i]
        credited = claim.realized_gain_bits
        total_credited += credited

        print(f"  Episode {i+1}: claimed=0.2, realized={realized:.2f}, credited={credited:.2f}, debt_inc={debt_increment:.2f}")

    # Get statistics
    stats = controller.get_statistics()

    print(f"\n--- Final Statistics ---")
    print(f"  Total claimed: {5 * 0.2:.2f} bits")
    print(f"  Total realized: {total_realized:.2f} bits")
    print(f"  Total credited: {total_credited:.2f} bits")
    print(f"  Total debt: {stats['total_debt']:.2f} bits")
    print(f"  Mean surprise: {stats['sandbagging_mean_surprise']:.2f}")
    print(f"  Is sandbagging: {stats['sandbagging_is_sandbagging']}")

    # Verify sandbagging was detected
    assert stats['sandbagging_is_sandbagging'], "Should detect sandbagging"
    assert stats['sandbagging_mean_surprise'] > 2.0, "Mean surprise should be high"

    # Verify credited < realized (discount applied)
    assert total_credited < total_realized, "Credited should be less than realized due to discount"

    print("\n✓ Integrated Phase 2 improvements work correctly")
    print("  Sandbagging detected and penalized via credit discount")


def test_convenience_function():
    """Test convenience function for sandbagging detection."""
    print("\n" + "="*60)
    print("Test: Convenience Function")
    print("="*60)

    # Test sandbagging
    claimed = [0.1, 0.1, 0.1, 0.1, 0.1]
    realized = [0.8, 0.7, 0.9, 0.6, 0.8]

    is_sandbagging = detect_sandbagging(claimed, realized, threshold=2.0)
    print(f"\nClaimed: {claimed}")
    print(f"Realized: {realized}")
    print(f"Is sandbagging: {is_sandbagging}")

    assert is_sandbagging, "Should detect sandbagging"
    print("✓ Convenience function works")


def test_backward_compatibility():
    """Test that episode-based settlement still works (backward compatibility)."""
    tracker = ProvisionalPenaltyTracker()

    tracker.add_provisional_penalty(
        action_id="test",
        penalty_amount=0.5,
        prior_entropy=1.5,
        settlement_horizon=3
    )

    print("\n" + "="*60)
    print("Test: Backward Compatibility (Episode-Based Settlement)")
    print("="*60)

    # Use episode-based settlement (time_increment_h=0)
    for i in range(3):
        finalized = tracker.step(current_entropy=2.0, time_increment_h=0)
        print(f"  Episode {i+1}: episodes_remaining={tracker.provisional_penalties['test'].episodes_remaining}, settled={tracker.provisional_penalties['test'].settled}")

    # Should settle after 3 episodes
    assert tracker.provisional_penalties["test"].settled, "Should settle after 3 episodes"
    print("\n✓ Backward compatibility maintained")


if __name__ == "__main__":
    print("="*60)
    print("Phase 2 Epistemic Improvements Tests")
    print("="*60)

    test_time_weighted_provisional_penalties()
    test_sandbagging_detection()
    test_integrated_phase2_improvements()
    test_convenience_function()
    test_backward_compatibility()

    print("\n" + "="*60)
    print("✓ All Phase 2 tests passed")
    print("="*60)
    print("\nLoopholes closed:")
    print("  1. Time exploitation: Rapid actions can't age out provisional penalties")
    print("  2. Sandbagging: Systematic underclaiming is detected and penalized")
    print("\nThe system is now even more robust against gaming strategies.")
