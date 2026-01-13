#!/usr/bin/env python3
"""
Typical Effects Sanity Check: Imaging Artifacts

Verifies that debris artifacts have reasonable magnitudes in typical scenarios.
This prevents shipping a beautifully-tested no-op.

Scenarios:
- Low debris (gentle wash): artifacts ~0.1-0.5% (noticeable but small)
- Moderate debris (standard wash): artifacts ~0.5-1.5% (measurable)
- High debris (rough wash): artifacts ~1-5% (significant)
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS/src')

from cell_os.biology.imaging_artifacts_core import (
    compute_background_multipliers_by_channel,
    compute_segmentation_failure_modes,
    compute_debris_field_modifiers,
)


def test_low_debris_typical_effects():
    """
    Low debris scenario (gentle wash, ~2% debris fraction).

    Expect: Small but nonzero effects.
    """
    initial_cells = 3000.0
    debris_cells = 60.0  # 2% debris
    adherent_cells = 5800.0
    confluence = 0.5

    # Background multipliers (per-channel)
    channel_weights = {'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
    bg = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=channel_weights
    )

    # Expect 0.1-0.5% inflation
    assert 1.000 <= bg['rna'] <= 1.005, f"RNA multiplier {bg['rna']} outside expected range"
    assert 1.000 <= bg['mito'] <= 1.005, f"Mito multiplier {bg['mito']} outside expected range"

    # Segmentation modes
    seg = compute_segmentation_failure_modes(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        confluence=confluence
    )

    # Expect small but nonzero probabilities (not 1e-8, not 0.3)
    assert 0.0001 <= seg['p_merge'] <= 0.01, f"p_merge {seg['p_merge']} outside expected range"
    assert 0.0001 <= seg['p_split'] <= 0.01, f"p_split {seg['p_split']} outside expected range"

    print(f"✓ Low debris effects:")
    print(f"  Background: RNA={bg['rna']:.4f}, Mito={bg['mito']:.4f}")
    print(f"  Segmentation: p_merge={seg['p_merge']:.4f}, p_split={seg['p_split']:.4f}")


def test_moderate_debris_typical_effects():
    """
    Moderate debris scenario (standard wash, ~4-6% debris fraction).

    Expect: Measurable effects (0.5-1.5%).
    """
    initial_cells = 3000.0
    debris_cells = 150.0  # 5% debris
    adherent_cells = 5500.0
    confluence = 0.5

    # Background multipliers (per-channel)
    channel_weights = {'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
    bg = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=channel_weights
    )

    # Expect 0.5-1.5% inflation
    assert 1.002 <= bg['rna'] <= 1.015, f"RNA multiplier {bg['rna']} outside expected range"
    assert 1.001 <= bg['mito'] <= 1.012, f"Mito multiplier {bg['mito']} outside expected range"

    # Segmentation modes
    seg = compute_segmentation_failure_modes(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        confluence=confluence
    )

    # Expect noticeable probabilities (0.05-0.5%)
    assert 0.0003 <= seg['p_merge'] <= 0.005, f"p_merge {seg['p_merge']} outside expected range"
    assert 0.0001 <= seg['p_split'] <= 0.005, f"p_split {seg['p_split']} outside expected range"

    print(f"✓ Moderate debris effects:")
    print(f"  Background: RNA={bg['rna']:.4f}, Mito={bg['mito']:.4f}")
    print(f"  Segmentation: p_merge={seg['p_merge']:.4f}, p_split={seg['p_split']:.4f}")


def test_high_debris_typical_effects():
    """
    High debris scenario (rough wash or trashed well, ~15-30% debris fraction).

    Expect: Significant effects (1-5%).
    """
    initial_cells = 3000.0
    debris_cells = 600.0  # 20% debris
    adherent_cells = 4000.0
    confluence = 0.5

    # Background multipliers (per-channel)
    channel_weights = {'rna': 1.5, 'actin': 1.3, 'nucleus': 1.0, 'er': 0.8, 'mito': 0.8}
    bg = compute_background_multipliers_by_channel(
        debris_cells=debris_cells,
        adherent_cells=initial_cells,
        channel_weights=channel_weights
    )

    # Expect 1-5% inflation
    assert 1.005 <= bg['rna'] <= 1.050, f"RNA multiplier {bg['rna']} outside expected range"
    assert 1.003 <= bg['mito'] <= 1.040, f"Mito multiplier {bg['mito']} outside expected range"

    # Segmentation modes
    seg = compute_segmentation_failure_modes(
        debris_cells=debris_cells,
        adherent_cell_count=adherent_cells,
        confluence=confluence
    )

    # Expect significant probabilities (0.2-2%)
    assert 0.001 <= seg['p_merge'] <= 0.02, f"p_merge {seg['p_merge']} outside expected range"
    assert 0.0005 <= seg['p_split'] <= 0.02, f"p_split {seg['p_split']} outside expected range"

    print(f"✓ High debris effects:")
    print(f"  Background: RNA={bg['rna']:.4f}, Mito={bg['mito']:.4f}")
    print(f"  Segmentation: p_merge={seg['p_merge']:.4f}, p_split={seg['p_split']:.4f}")


def test_spatial_field_texture_corruption():
    """
    Spatial field texture corruption should be noticeable but modest.

    Expect: 0-30% corruption depending on debris load.
    """
    initial_cells = 3000.0

    # Low debris
    result_low = compute_debris_field_modifiers(
        debris_cells=60.0,  # 2%
        adherent_cells=initial_cells,
        is_edge=False,
        well_id="B03",
        experiment_seed=42
    )

    # Moderate debris
    result_mod = compute_debris_field_modifiers(
        debris_cells=150.0,  # 5%
        adherent_cells=initial_cells,
        is_edge=False,
        well_id="B03",
        experiment_seed=42
    )

    # High debris
    result_high = compute_debris_field_modifiers(
        debris_cells=600.0,  # 20%
        adherent_cells=initial_cells,
        is_edge=True,
        well_id="A01",
        experiment_seed=42
    )

    # Texture corruption should scale with debris
    assert 0.0 <= result_low['texture_corruption'] <= 0.02, \
        f"Low debris texture corruption {result_low['texture_corruption']} outside expected"
    assert 0.01 <= result_mod['texture_corruption'] <= 0.05, \
        f"Moderate debris texture corruption {result_mod['texture_corruption']} outside expected"
    assert 0.05 <= result_high['texture_corruption'] <= 0.15, \
        f"High debris texture corruption {result_high['texture_corruption']} outside expected"

    # Edge amplification should be present for edge wells with debris
    assert result_high['edge_amplification'] > 1.0, \
        "Edge wells should have edge_amplification > 1.0"

    print(f"✓ Spatial field effects:")
    print(f"  Low debris: texture_corruption={result_low['texture_corruption']:.3f}")
    print(f"  Moderate debris: texture_corruption={result_mod['texture_corruption']:.3f}")
    print(f"  High debris: texture_corruption={result_high['texture_corruption']:.3f}, edge_amp={result_high['edge_amplification']:.2f}")


if __name__ == "__main__":
    print("=" * 70)
    print("Typical Effects Sanity Check")
    print("=" * 70)
    print()

    test_low_debris_typical_effects()
    print()
    test_moderate_debris_typical_effects()
    print()
    test_high_debris_typical_effects()
    print()
    test_spatial_field_texture_corruption()

    print("\n" + "=" * 70)
    print("ALL SANITY CHECKS PASSED")
    print("Effects are noticeable but reasonable (not a no-op)")
    print("=" * 70)
