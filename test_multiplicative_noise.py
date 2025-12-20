"""
Test that multiplicative noise preserves positivity.

Invariant: For any strictly-positive quantity x (counts, concentrations, intensities),
noise must preserve positivity.
"""

import sys
import numpy as np


def test_normal_multiplier_can_go_negative():
    """
    Prove that x * N(1.0, cv) can go negative for large cv.

    This is the BUG we're fixing.
    """
    x = 100.0  # Positive baseline
    cv = 0.3   # 30% coefficient of variation

    # Monte Carlo: sample 100k times
    n_samples = 100_000
    rng = np.random.default_rng(seed=42)

    samples = []
    for _ in range(n_samples):
        noise_factor = rng.normal(1.0, cv)
        x_noisy = x * noise_factor
        samples.append(x_noisy)

    min_val = min(samples)
    neg_count = sum(1 for s in samples if s < 0)

    print(f"Baseline: {x}")
    print(f"CV: {cv}")
    print(f"Min sampled value: {min_val:.3f}")
    print(f"Negative samples: {neg_count}/{n_samples} ({100*neg_count/n_samples:.2f}%)")

    if min_val < 0:
        print("❌ FAIL: Multiplicative normal noise can produce negative values")
        return False
    else:
        print("✓ PASS: All samples positive")
        return True


def test_lognormal_preserves_positivity():
    """
    Prove that x * lognormal(μ=-0.5σ², σ) preserves positivity.

    This is the FIX.
    """
    x = 100.0
    cv = 0.3

    # For lognormal with E[X] = 1:
    # If X ~ lognormal(μ, σ), then E[X] = exp(μ + σ²/2)
    # Setting E[X] = 1 gives μ = -σ²/2
    sigma = cv  # Standard deviation of log(X)
    mu = -0.5 * sigma ** 2

    # Monte Carlo
    n_samples = 100_000
    rng = np.random.default_rng(seed=42)

    samples = []
    for _ in range(n_samples):
        noise_factor = rng.lognormal(mean=mu, sigma=sigma)
        x_noisy = x * noise_factor
        samples.append(x_noisy)

    min_val = min(samples)
    mean_val = np.mean(samples)
    neg_count = sum(1 for s in samples if s < 0)

    print(f"Baseline: {x}")
    print(f"CV: {cv}")
    print(f"Min sampled value: {min_val:.3f}")
    print(f"Mean: {mean_val:.3f} (should be ≈ {x})")
    print(f"Negative samples: {neg_count}/{n_samples}")

    if neg_count > 0:
        print("❌ FAIL: Lognormal produced negative values")
        return False
    elif mean_val < x * 0.95 or mean_val > x * 1.05:
        print(f"❌ FAIL: Mean drift (expected {x}, got {mean_val:.1f})")
        return False
    else:
        print("✓ PASS: All samples positive, mean preserved")
        return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Multiplicative Noise Positivity")
    print("=" * 70)
    print()

    tests = [
        ("Normal multiplier can go negative (BUG)", test_normal_multiplier_can_go_negative),
        ("Lognormal preserves positivity (FIX)", test_lognormal_preserves_positivity),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            results.append((name, False))
        print()

    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    print()
    print(f"Total: {passed}/{total} passed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)
