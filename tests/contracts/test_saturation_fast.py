"""
Fast contract tests for detector saturation (dynamic range limits).

Tests verify:
1. Dormant default preserves behavior (golden-preserving)
2. Hard bounds enforced (0 <= y_sat <= ceiling)
3. Identity below knee (y_sat == y for y <= knee_start)
4. Compression is monotone and smooth
5. Interacts correctly with additive floor

Runtime: <0.1 seconds (pure function tests, no VM, deterministic)
"""

import pytest
from cell_os.hardware._impl import apply_saturation


def test_saturation_dormant_default_preserves_behavior():
    """Dormant mode (ceiling=0) is exact no-op (identity function).

    Pure function test: verifies ceiling=0 means no saturation applied.
    """
    # Test that ceiling=0 means "disabled" (identity function)
    test_inputs = [0.0, 50.0, 100.0, 500.0, 1000.0, 10000.0]

    for y in test_inputs:
        y_sat = apply_saturation(y, ceiling=0.0, knee_start_frac=0.85, tau_frac=0.08)
        assert y_sat == y, \
            f"Dormant mode violated: y={y:.1f} → y_sat={y_sat:.3f} (expected identity)"

    print("✓ Dormant mode (ceiling=0.0) preserves golden behavior")


def test_saturation_primitive_hard_bounds():
    """Saturation primitive enforces hard bounds [0, ceiling]."""
    ceiling = 100.0
    knee_frac = 0.85
    tau_frac = 0.08

    # Test inputs spanning full range
    test_cases = [
        (-10.0, "negative input (should clamp to 0)"),
        (0.0, "zero input"),
        (50.0, "below knee"),
        (85.0, "at knee"),
        (90.0, "above knee"),
        (150.0, "far above ceiling"),
        (1000.0, "extremely high")
    ]

    for y, description in test_cases:
        y_sat = apply_saturation(y, ceiling, knee_frac, tau_frac)

        # Hard bound: 0 <= y_sat <= ceiling
        assert 0.0 <= y_sat <= ceiling, \
            f"Failed bounds for {description}: y={y:.1f} → y_sat={y_sat:.3f}"

        # If y >= ceiling, should saturate at ceiling exactly
        if y >= ceiling:
            assert y_sat == ceiling, \
                f"Failed ceiling clamp for {description}: y={y:.1f} → y_sat={y_sat:.3f}, expected {ceiling}"

    print("✓ Hard bounds enforced: 0 <= y_sat <= ceiling")


def test_saturation_primitive_identity_below_knee():
    """Identity region: y_sat == y for y <= knee_start."""
    ceiling = 600.0
    knee_frac = 0.85
    tau_frac = 0.08

    knee_start = knee_frac * ceiling  # 510.0

    # Test inputs below knee (should be exact identity)
    test_inputs = [0.0, 50.0, 100.0, 200.0, 400.0, 510.0]  # All <= knee_start

    for y in test_inputs:
        y_sat = apply_saturation(y, ceiling, knee_frac, tau_frac)
        assert y_sat == y, \
            f"Identity violation at y={y:.1f}: y_sat={y_sat:.3f}, expected {y:.1f} (knee={knee_start:.1f})"

    print(f"✓ Identity preserved below knee: y_sat == y for y <= {knee_start:.1f}")


def test_saturation_primitive_monotone_compression():
    """Compression above knee is monotone and approaches ceiling asymptotically."""
    ceiling = 600.0
    knee_frac = 0.85
    tau_frac = 0.08

    knee_start = knee_frac * ceiling  # 510.0

    # Test inputs above knee (should compress toward ceiling)
    test_inputs = [520.0, 550.0, 600.0, 700.0, 1000.0]
    y_sat_prev = knee_start

    for y in test_inputs:
        y_sat = apply_saturation(y, ceiling, knee_frac, tau_frac)

        # Monotone: higher input → higher/equal output (preserves order)
        assert y_sat >= y_sat_prev, \
            f"Monotone violation: y={y:.1f} → y_sat={y_sat:.3f} < prev={y_sat_prev:.3f}"

        # Bounded: never exceed ceiling
        assert y_sat <= ceiling, \
            f"Ceiling violation: y={y:.1f} → y_sat={y_sat:.3f} > ceiling={ceiling}"

        # Above knee: output should be in compression zone [knee_start, ceiling]
        if y > knee_start:
            assert knee_start <= y_sat <= ceiling, \
                f"Compression zone violation: y={y:.1f} → y_sat={y_sat:.3f}, expected in [{knee_start:.1f}, {ceiling}]"

        y_sat_prev = y_sat

    # Check compression effect: large input → output near ceiling (not proportional growth)
    # If no compression, y=1000 would map to ~1000, but with compression it should be ~ceiling
    y_large = 1000.0
    y_sat_large = apply_saturation(y_large, ceiling, knee_frac, tau_frac)
    assert y_sat_large < y_large * 0.7, \
        f"Insufficient compression: y={y_large:.1f} → y_sat={y_sat_large:.3f} (should be much less than input)"

    # Far above ceiling should saturate at ceiling (asymptotic approach)
    y_extreme = 10000.0
    y_sat_extreme = apply_saturation(y_extreme, ceiling, knee_frac, tau_frac)
    assert abs(y_sat_extreme - ceiling) < 0.001, \
        f"Asymptotic failure: y={y_extreme:.1f} → y_sat={y_sat_extreme:.3f}, expected ~{ceiling}"

    print("✓ Compression is monotone, bounded, and approaches ceiling asymptotically")


def test_saturation_with_additive_floor_interaction():
    """Saturation correctly handles additive floor pushing into saturation regime.

    Pure function test: simulates additive floor + saturation composition without VM.
    """
    import numpy as np
    from cell_os.hardware._impl import additive_floor_noise

    ceiling = 200.0
    knee_frac = 0.85
    tau_frac = 0.08
    sigma = 50.0  # Large additive noise

    # Simulate baseline signal (before noise)
    baseline = 150.0

    # Create RNG for additive floor
    rng = np.random.default_rng(123)

    # Simulate composition: baseline + additive_floor → saturation
    measurements = []
    for _ in range(20):
        # Apply additive floor noise
        noise = additive_floor_noise(rng, sigma)
        y_noisy = baseline + noise

        # Apply saturation
        y_sat = apply_saturation(y_noisy, ceiling, knee_frac, tau_frac)
        measurements.append(y_sat)

    # All measurements should respect ceiling (even with additive noise)
    max_observed = max(measurements)
    assert max_observed <= ceiling, \
        f"Saturation failed: observed {max_observed:.1f} > ceiling {ceiling}"

    # Should have some variance (additive noise) but bounded
    variance = sum((x - sum(measurements)/len(measurements))**2 for x in measurements) / len(measurements)
    assert variance > 0, "No variance observed (additive noise not working?)"

    print(f"✓ Additive floor + saturation: all measurements <= ceiling (max={max_observed:.1f})")


def test_saturation_deterministic_no_rng():
    """Saturation is deterministic (no RNG, pure function)."""
    ceiling = 600.0
    knee_frac = 0.85
    tau_frac = 0.08

    # Call primitive multiple times with same inputs
    test_inputs = [100.0, 300.0, 500.0, 700.0, 1000.0]

    for y in test_inputs:
        results = [apply_saturation(y, ceiling, knee_frac, tau_frac) for _ in range(10)]

        # All results should be identical (deterministic)
        assert len(set(results)) == 1, \
            f"Non-deterministic behavior at y={y:.1f}: results={results}"

    print("✓ Saturation is deterministic (no RNG)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
