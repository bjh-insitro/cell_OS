"""
Test RNG draw-count invariance: changing config should not change RNG stream order.

Critical covenant: setting a noise parameter to 0 should not change how many
RNG draws occur, which would cause downstream randomness to diverge under
the same seed.
"""

import numpy as np


def test_lognormal_multiplier_violates_draw_count_invariance():
    """
    EXPECTED TO FAIL: lognormal_multiplier conditionally skips RNG draw when cv=0.

    This test proves that the same seed produces different downstream randomness
    depending on whether cv=0 or cv>0, violating draw-count invariance.
    """
    from cell_os.hardware._impl import lognormal_multiplier

    seed = 42

    # Scenario A: cv > 0 (draws from RNG)
    rng_a = np.random.default_rng(seed)
    _ = lognormal_multiplier(rng_a, cv=0.04)  # Consumes RNG draw
    sentinel_a = rng_a.uniform()  # Next draw from RNG

    # Scenario B: cv = 0 (skips RNG draw)
    rng_b = np.random.default_rng(seed)
    _ = lognormal_multiplier(rng_b, cv=0.0)  # NO RNG draw consumed
    sentinel_b = rng_b.uniform()  # Should be same as sentinel_a if invariant

    # If draw-count invariance holds, sentinel values must match
    # If they differ, we've proven the violation
    assert sentinel_a != sentinel_b, (
        "Expected draw-count invariance to be violated, but sentinels matched. "
        "Either the violation was fixed, or test setup is wrong."
    )

    # Show the values for documentation
    print(f"Sentinel A (cv=0.04): {sentinel_a}")
    print(f"Sentinel B (cv=0.0):  {sentinel_b}")
    print(f"Difference: {abs(sentinel_a - sentinel_b)}")


def test_lognormal_multiplier_enforced_invariance():
    """
    This test documents the CORRECT behavior: draw-count invariance.

    Currently WILL FAIL because lognormal_multiplier does not enforce invariance.
    After fix, this should PASS.
    """
    from cell_os.hardware._impl import lognormal_multiplier

    seed = 42

    # Both scenarios should consume exactly one RNG draw
    rng_a = np.random.default_rng(seed)
    result_a = lognormal_multiplier(rng_a, cv=0.04)
    sentinel_a = rng_a.uniform()

    rng_b = np.random.default_rng(seed)
    result_b = lognormal_multiplier(rng_b, cv=0.0)
    sentinel_b = rng_b.uniform()

    # Sentinels must match (downstream RNG state is identical)
    assert sentinel_a == sentinel_b, (
        f"Draw-count invariance violated: "
        f"sentinel_a={sentinel_a}, sentinel_b={sentinel_b}. "
        f"Setting cv=0 changed downstream RNG state."
    )

    # result_b should be 1.0 (no noise), but RNG was still consumed
    assert result_b == 1.0, "cv=0 should return 1.0"
    assert result_a != 1.0, "cv>0 should return noisy value"


if __name__ == "__main__":
    print("=" * 70)
    print("TEST 1: Proving draw-count invariance violation")
    print("=" * 70)
    try:
        test_lognormal_multiplier_violates_draw_count_invariance()
        print("✅ PASS: Violation confirmed (as expected)")
    except AssertionError as e:
        print(f"❌ FAIL: {e}")

    print("\n" + "=" * 70)
    print("TEST 2: Enforced invariance (should fail until fixed)")
    print("=" * 70)
    try:
        test_lognormal_multiplier_enforced_invariance()
        print("✅ PASS: Draw-count invariance holds")
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
