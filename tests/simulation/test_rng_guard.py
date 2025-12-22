"""
Agent 1: RNG Guard Unit Tests

Test that ValidatedRNG enforces stream partitioning.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from src.cell_os.hardware.rng_guard import ValidatedRNG, RNGStreamViolation


def test_rng_guard_allows_authorized():
    """Test that authorized callers can use RNG."""
    rng = ValidatedRNG(
        np.random.default_rng(42),
        stream_name="test",
        allowed_patterns={"test_rng_guard"},  # This function matches
        enforce=True
    )

    # Should not crash
    value = rng.random()
    assert 0 <= value <= 1
    assert rng.call_count == 1

    print("✓ Authorized caller can use RNG")


def test_rng_guard_blocks_unauthorized():
    """Test that unauthorized callers are blocked."""
    rng = ValidatedRNG(
        np.random.default_rng(42),
        stream_name="test",
        allowed_patterns={"_never_matches_"},
        enforce=True
    )

    try:
        value = rng.random()
        assert False, "Expected RNGStreamViolation but none raised"
    except RNGStreamViolation as e:
        assert "test" in e.stream_name
        assert "test_rng_guard" in e.caller_function
        print(f"✓ Unauthorized caller blocked: {e.caller_function}")


def test_rng_call_counting():
    """Test that RNG calls are counted."""
    rng = ValidatedRNG(
        np.random.default_rng(42),
        stream_name="test",
        allowed_patterns={"test_rng"},
        enforce=True
    )

    assert rng.call_count == 0
    rng.random()
    assert rng.call_count == 1
    rng.normal()
    assert rng.call_count == 2
    rng.integers(0, 10)
    assert rng.call_count == 3

    count = rng.reset_call_count()
    assert count == 3
    assert rng.call_count == 0

    print("✓ Call counting works correctly")


def test_rng_guard_non_enforcing():
    """Test that enforcement can be disabled for debugging."""
    rng = ValidatedRNG(
        np.random.default_rng(42),
        stream_name="test",
        allowed_patterns={"_never_matches_"},
        enforce=False  # Disabled
    )

    # Should not crash even though pattern doesn't match
    value = rng.random()
    assert 0 <= value <= 1
    print("✓ Non-enforcing mode allows all calls")


if __name__ == "__main__":
    print("="*60)
    print("Agent 1: RNG Guard Unit Tests")
    print("="*60)
    print()

    test_rng_guard_allows_authorized()
    test_rng_guard_blocks_unauthorized()
    test_rng_call_counting()
    test_rng_guard_non_enforcing()

    print()
    print("="*60)
    print("ALL RNG GUARD TESTS PASSED")
    print("="*60)
    print()
    print("✅ ValidatedRNG successfully enforces stream partitioning")
    print("✅ Unauthorized RNG usage crashes loudly")
    print("✅ Call counting enables audit diagnostics")
