"""
Agent 3: Mechanism Posterior Calibration Tests (ECE)

Tests that prove:
1. Overconfidence is detectable
2. Underconfidence is detectable
3. Well-calibrated posteriors have low ECE
4. Small samples are marked as unstable

Philosophy:
- These tests prove DETECTION, not CORRECTION
- No policy coupling
- Pure instrumentation
"""

from cell_os.hardware.mechanism_posterior_v2 import (
    CalibrationEvent,
    MechanismCalibrationTracker,
    compute_ece,
    Mechanism
)


def test_calibration_event_validation():
    """Test that CalibrationEvent validates bounds."""
    # Valid events
    event = CalibrationEvent(confidence=0.9, correct=True)
    assert event.confidence == 0.9
    assert event.correct is True

    # Invalid confidence (out of bounds)
    try:
        CalibrationEvent(confidence=1.5, correct=True)
        assert False, "Should have raised assertion"
    except AssertionError:
        pass

    try:
        CalibrationEvent(confidence=-0.1, correct=False)
        assert False, "Should have raised assertion"
    except AssertionError:
        pass

    # Invalid correct type
    try:
        CalibrationEvent(confidence=0.5, correct="yes")
        assert False, "Should have raised assertion"
    except AssertionError:
        pass


def test_overconfidence_detection():
    """
    Test 1: Overconfidence Detection

    Scenario:
    - Agent says "95% confident"
    - But is only right 60% of the time
    - ECE should be HIGH (> 0.25)

    This is catastrophic miscalibration.
    """
    # Create 100 events: confidence ~0.95, accuracy ~0.60
    events = []
    for i in range(100):
        confidence = 0.95
        correct = (i < 60)  # 60% correct
        events.append(CalibrationEvent(confidence, correct))

    # Compute ECE
    ece = compute_ece(events, n_bins=10)

    # Overconfidence: gap = |0.95 - 0.60| = 0.35
    # Since all events are in same bin, ECE ≈ 0.35
    print(f"Overconfidence test: ECE = {ece:.3f}")
    assert ece > 0.25, f"ECE should be high for overconfidence, got {ece:.3f}"


def test_underconfidence_detection():
    """
    Test 2: Underconfidence Detection

    Scenario:
    - Agent says "55% confident"
    - But is actually right 90% of the time
    - ECE should be HIGH (> 0.25)

    This is also miscalibration (conservative bias).
    """
    # Create 100 events: confidence ~0.55, accuracy ~0.90
    events = []
    for i in range(100):
        confidence = 0.55
        correct = (i < 90)  # 90% correct
        events.append(CalibrationEvent(confidence, correct))

    # Compute ECE
    ece = compute_ece(events, n_bins=10)

    # Underconfidence: gap = |0.55 - 0.90| = 0.35
    print(f"Underconfidence test: ECE = {ece:.3f}")
    assert ece > 0.25, f"ECE should be high for underconfidence, got {ece:.3f}"


def test_well_calibrated_case():
    """
    Test 3: Well-Calibrated Case

    Scenario:
    - Agent says "90% confident" → right 90% of time
    - Agent says "70% confident" → right 70% of time
    - Agent says "50% confident" → right 50% of time
    - ECE should be LOW (< 0.10)

    This is ideal calibration.
    """
    events = []

    # 90% bin: 90% correct
    for i in range(100):
        events.append(CalibrationEvent(0.90, correct=(i < 90)))

    # 70% bin: 70% correct
    for i in range(100):
        events.append(CalibrationEvent(0.70, correct=(i < 70)))

    # 50% bin: 50% correct
    for i in range(100):
        events.append(CalibrationEvent(0.50, correct=(i < 50)))

    # Compute ECE
    ece = compute_ece(events, n_bins=10)

    # Well-calibrated: each bin has near-zero gap
    print(f"Well-calibrated test: ECE = {ece:.3f}")
    assert ece < 0.10, f"ECE should be low for well-calibrated, got {ece:.3f}"


def test_small_sample_warning():
    """
    Test 4: Small Sample Warning

    Scenario:
    - Only 10 events (< 30 minimum)
    - Even if ECE is high, mark as UNSTABLE
    - No alert should be emitted

    This prevents false alarms during warmup.
    """
    tracker = MechanismCalibrationTracker(min_samples_for_stability=30)

    # Add 10 events (overconfident)
    for i in range(10):
        tracker.events.append(CalibrationEvent(0.95, correct=(i < 6)))

    # Compute ECE
    ece, is_stable = tracker.compute_ece()

    print(f"Small sample test: n={len(tracker.events)}, ECE={ece:.3f}, stable={is_stable}")

    # ECE might be high, but should be marked unstable
    assert not is_stable, "Small samples should be marked as unstable"
    assert len(tracker.events) < tracker.min_samples_for_stability


def test_tracker_record():
    """
    Test that MechanismCalibrationTracker.record() works correctly.
    """
    tracker = MechanismCalibrationTracker()

    # Simulate a classification
    posterior = {
        Mechanism.ER_STRESS: 0.72,
        Mechanism.MITOCHONDRIAL: 0.18,
        Mechanism.MICROTUBULE: 0.10,
    }
    predicted = Mechanism.ER_STRESS
    true_mechanism = Mechanism.ER_STRESS

    # Record event
    tracker.record(
        predicted=predicted,
        true_mechanism=true_mechanism,
        posterior=posterior
    )

    # Verify event was recorded
    assert len(tracker.events) == 1
    event = tracker.events[0]
    assert event.confidence == 0.72  # max posterior
    assert event.correct is True  # prediction was correct


def test_tracker_statistics():
    """
    Test that get_statistics() returns correct summary.
    """
    tracker = MechanismCalibrationTracker(min_samples_for_stability=30)

    # Add 50 events: confidence 0.8, accuracy 0.7
    for i in range(50):
        tracker.events.append(CalibrationEvent(0.80, correct=(i < 35)))

    stats = tracker.get_statistics()

    print(f"Statistics: {stats}")

    assert stats["n_samples"] == 50
    assert stats["is_stable"] is True  # >= 30 samples
    assert 0.79 < stats["mean_confidence"] < 0.81  # ~0.80
    assert 0.69 < stats["accuracy"] < 0.71  # ~0.70 (35/50)
    assert stats["ece"] > 0.05  # Should detect miscalibration


def test_edge_case_empty_tracker():
    """
    Test that empty tracker returns zeros gracefully.
    """
    tracker = MechanismCalibrationTracker()

    ece, is_stable = tracker.compute_ece()
    assert ece == 0.0
    assert is_stable is False

    stats = tracker.get_statistics()
    assert stats["n_samples"] == 0
    assert stats["ece"] == 0.0


def test_edge_case_perfect_confidence_one():
    """
    Test that confidence = 1.0 is handled correctly (edge bin).
    """
    events = [CalibrationEvent(1.0, True) for _ in range(10)]
    ece = compute_ece(events, n_bins=10)

    # All events in last bin, all correct → ECE = 0
    print(f"Perfect confidence test: ECE = {ece:.3f}")
    assert ece < 0.05


def test_determinism():
    """
    Test that ECE computation is deterministic.
    """
    events = [
        CalibrationEvent(0.9, True),
        CalibrationEvent(0.8, False),
        CalibrationEvent(0.7, True),
        CalibrationEvent(0.6, True),
        CalibrationEvent(0.5, False),
    ]

    ece1 = compute_ece(events, n_bins=10)
    ece2 = compute_ece(events, n_bins=10)

    assert ece1 == ece2, "ECE should be deterministic"


def test_mixed_confidence_bins():
    """
    Test that events across multiple bins are handled correctly.
    """
    events = []

    # High confidence bin (0.9): 80% correct
    for i in range(50):
        events.append(CalibrationEvent(0.90, correct=(i < 40)))

    # Medium confidence bin (0.6): 60% correct
    for i in range(50):
        events.append(CalibrationEvent(0.60, correct=(i < 30)))

    # Low confidence bin (0.3): 30% correct
    for i in range(50):
        events.append(CalibrationEvent(0.30, correct=(i < 15)))

    ece = compute_ece(events, n_bins=10)

    # Each bin is slightly miscalibrated:
    # High: |0.90 - 0.80| = 0.10
    # Med: |0.60 - 0.60| = 0.00
    # Low: |0.30 - 0.30| = 0.00
    # Weighted: (50/150)*0.10 + (50/150)*0.00 + (50/150)*0.00 ≈ 0.033

    print(f"Mixed bins test: ECE = {ece:.3f}")
    assert ece < 0.15, f"ECE should be low for mostly-calibrated, got {ece:.3f}"


if __name__ == "__main__":
    print("Running Agent 3: Mechanism Calibration Tests\n")

    print("=" * 60)
    print("Test 1: Overconfidence Detection")
    print("=" * 60)
    test_overconfidence_detection()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 2: Underconfidence Detection")
    print("=" * 60)
    test_underconfidence_detection()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 3: Well-Calibrated Case")
    print("=" * 60)
    test_well_calibrated_case()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 4: Small Sample Warning")
    print("=" * 60)
    test_small_sample_warning()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 5: Tracker Record")
    print("=" * 60)
    test_tracker_record()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 6: Tracker Statistics")
    print("=" * 60)
    test_tracker_statistics()
    print("✓ PASS\n")

    print("=" * 60)
    print("Test 7: Edge Cases")
    print("=" * 60)
    test_edge_case_empty_tracker()
    test_edge_case_perfect_confidence_one()
    test_determinism()
    test_mixed_confidence_bins()
    print("✓ PASS\n")

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print("\nAgent 3 Mission: Calibration tracking is INSTRUMENTED and TESTABLE")
    print("Overconfidence is now DETECTABLE in logs.")
