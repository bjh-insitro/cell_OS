"""
Fast contract tests for optical materials (pure functions).

Tests verify core optical properties WITHOUT constructing VM or vessels:
1. Determinism (same inputs → same outputs)
2. Vignette is monotonic (center brighter than edge)
3. Buffer is true zero (no variance)
4. Dye variance is N-independent
5. Bead variance scales as 1/sqrt(N)
6. Spatial vignette is deterministic

Runtime: <0.5 seconds (pure functions, no VM loops)
"""

import pytest
import numpy as np
from cell_os.hardware.optical_materials import (
    generate_material_base_signal,
    compute_radial_vignette
)
from cell_os.hardware.material_state import MATERIAL_NOMINAL_INTENSITIES


def test_vignette_is_deterministic():
    """Vignette is deterministic (same well → same value)."""
    well = "H12"  # Center well

    v1 = compute_radial_vignette(well, plate_format=384)
    v2 = compute_radial_vignette(well, plate_format=384)

    assert v1 == v2, "Vignette must be deterministic"
    print(f"✓ Vignette deterministic: {well} → {v1:.4f}")


def test_vignette_is_monotonic_radial():
    """Center wells brighter than edge wells (monotonic radial falloff)."""
    center = compute_radial_vignette("H12", plate_format=384)  # Center
    mid = compute_radial_vignette("H6", plate_format=384)      # Mid-radius
    edge = compute_radial_vignette("A1", plate_format=384)     # Corner

    assert center > mid > edge, \
        f"Vignette not monotonic: center={center:.3f}, mid={mid:.3f}, edge={edge:.3f}"

    # Center should be near 1.0, edge should be ~0.85
    assert 0.98 < center <= 1.0, f"Center should be ~1.0, got {center:.3f}"
    assert 0.84 < edge < 0.90, f"Edge should be ~0.85, got {edge:.3f}"

    print(f"✓ Vignette monotonic: center={center:.3f} > mid={mid:.3f} > edge={edge:.3f}")


def test_buffer_is_true_zero():
    """Buffer generates true zero signal (no variance, no vignette without enabling)."""
    base = MATERIAL_NOMINAL_INTENSITIES['DARK']
    rng = np.random.default_rng(42)

    # Generate signal (with RNG, but buffer should ignore it)
    signal = generate_material_base_signal(
        material_type="buffer_only",
        base_intensities=base,
        well_position="H12",
        enable_vignette=False,  # Disable vignette for this test
        rng=rng
    )

    # All channels should be exactly 0.0
    for ch, val in signal.items():
        assert val == 0.0, f"Buffer channel {ch} should be 0.0, got {val}"

    print("✓ Buffer is true zero (no variance)")


def test_dye_variance_is_n_independent():
    """Dye variance does not scale with N (no averaging)."""
    base = MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW']
    rng = np.random.default_rng(42)

    # Generate 100 measurements
    measurements = []
    for _ in range(100):
        signal = generate_material_base_signal(
            material_type="fluorescent_dye_solution",
            base_intensities=base,
            well_position="H12",
            enable_vignette=False,  # Disable vignette for variance test
            rng=rng
        )
        measurements.append(signal['er'])

    # CV should be ~3% (mixing variance, not N-dependent)
    mean = np.mean(measurements)
    std = np.std(measurements)
    cv = std / mean

    assert 0.02 < cv < 0.05, \
        f"Dye CV should be ~3% (N-independent), got {cv*100:.1f}%"

    print(f"✓ Dye variance N-independent: CV={cv*100:.1f}%")


def test_bead_variance_scales_with_sqrt_n():
    """Bead variance scales as 1/sqrt(N) (averaging effect)."""
    base = MATERIAL_NOMINAL_INTENSITIES['MULTICOLOR_BEADS_SPARSE']

    # Sparse beads (N=10)
    rng_sparse = np.random.default_rng(42)
    measurements_sparse = []
    for _ in range(100):
        signal = generate_material_base_signal(
            material_type="fluorescent_beads",
            base_intensities=base,
            spatial_pattern='sparse',
            bead_count=10,
            well_position="H12",
            enable_vignette=False,
            rng=rng_sparse
        )
        measurements_sparse.append(signal['er'])

    # Dense beads (N=100)
    rng_dense = np.random.default_rng(43)
    measurements_dense = []
    for _ in range(100):
        signal = generate_material_base_signal(
            material_type="fluorescent_beads",
            base_intensities=base,
            spatial_pattern='dense',
            bead_count=100,
            well_position="H12",
            enable_vignette=False,
            rng=rng_dense
        )
        measurements_dense.append(signal['er'])

    # Compute CVs
    cv_sparse = np.std(measurements_sparse) / np.mean(measurements_sparse)
    cv_dense = np.std(measurements_dense) / np.mean(measurements_dense)

    # Ratio should be sqrt(100/10) = sqrt(10) ≈ 3.16
    ratio = cv_sparse / cv_dense
    assert 2.8 < ratio < 3.5, \
        f"CV ratio should be ~sqrt(10)≈3.16 (pure averaging), got {ratio:.2f}"

    print(f"✓ Bead variance scales 1/sqrt(N): CV_10={cv_sparse*100:.1f}%, CV_100={cv_dense*100:.1f}%, ratio={ratio:.2f}")


def test_vignette_affects_all_channels_equally():
    """Vignette is achromatic (same multiplier for all channels)."""
    base = MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW']

    # Measure at center
    signal_center = generate_material_base_signal(
        material_type="fluorescent_dye_solution",
        base_intensities=base,
        well_position="H12",  # Center
        enable_vignette=True,
        rng=None  # No material variance
    )

    # Measure at edge
    signal_edge = generate_material_base_signal(
        material_type="fluorescent_dye_solution",
        base_intensities=base,
        well_position="A1",  # Corner
        enable_vignette=True,
        rng=None
    )

    # Compute vignette ratio for each channel
    ratios = {}
    for ch in signal_center.keys():
        if signal_center[ch] > 0:  # Avoid division by zero
            ratios[ch] = signal_edge[ch] / signal_center[ch]

    # All ratios should be identical (achromatic vignette)
    ratio_vals = list(ratios.values())
    ratio_spread = max(ratio_vals) - min(ratio_vals)

    assert ratio_spread < 0.001, \
        f"Vignette should be achromatic (same ratio for all channels), spread={ratio_spread:.4f}"

    print(f"✓ Vignette achromatic: ratio={ratio_vals[0]:.4f} (identical for all channels)")


def test_signal_generation_is_deterministic():
    """Same inputs → same outputs (deterministic, not stochastic)."""
    base = MATERIAL_NOMINAL_INTENSITIES['FLATFIELD_DYE_LOW']
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)  # Same seed

    signal1 = generate_material_base_signal(
        material_type="fluorescent_dye_solution",
        base_intensities=base,
        well_position="H12",
        enable_vignette=True,
        rng=rng1
    )

    signal2 = generate_material_base_signal(
        material_type="fluorescent_dye_solution",
        base_intensities=base,
        well_position="H12",
        enable_vignette=True,
        rng=rng2
    )

    # Signals should be identical
    for ch in signal1.keys():
        assert signal1[ch] == signal2[ch], \
            f"Signal not deterministic: {ch} {signal1[ch]:.6f} != {signal2[ch]:.6f}"

    print("✓ Signal generation deterministic (same seed → same output)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
