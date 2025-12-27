"""
DARK Floor Observability Contracts

Tests that enforce DARK wells have observable variance (non-degenerate)
and remain dark (not accidentally brightened by bias fix).

These are BLOCKING contracts for Phase 4 calibration.
"""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from typing import Dict, List


def load_bead_plate_observations(obs_path: Path) -> List[Dict]:
    """Load observations from JSONL file."""
    observations = []
    with open(obs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            observations.append(json.loads(line))
    return observations


def get_dark_wells(observations: List[Dict]) -> List[Dict]:
    """Extract DARK wells from observations."""
    return [obs for obs in observations if obs.get('material_assignment') == 'DARK']


def get_dye_low_wells(observations: List[Dict]) -> List[Dict]:
    """Extract dye_low wells from observations."""
    return [obs for obs in observations if obs.get('material_assignment') == 'FLATFIELD_DYE_LOW']


@pytest.mark.contracts
def test_dark_non_degeneracy():
    """
    Contract: DARK wells must have observable variance.

    Requirement: Across the plate, per channel, at least 3 unique values observed.
    This ensures DARK floor is non-degenerate (not all exactly 0.0).

    Fails if:
      - DARK wells all have identical values (degenerate distribution)
      - Fewer than 3 unique quantized values per channel
    """
    obs_path = Path("results/cal_beads_dyes_seed42_darkfix/observations.jsonl")
    if not obs_path.exists():
        pytest.skip("Bead plate observations not found; run calibration first")

    observations = load_bead_plate_observations(obs_path)
    dark_wells = get_dark_wells(observations)

    if not dark_wells:
        pytest.fail("No DARK wells found in observations")

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        # Extract all DARK values for this channel
        dark_values = [obs['morphology'][ch] for obs in dark_wells]

        # Count unique values
        unique_values = set(dark_values)
        n_unique = len(unique_values)

        # Contract: at least 3 unique values
        assert n_unique >= 3, (
            f"DARK non-degeneracy FAILED for {ch}: "
            f"only {n_unique} unique values observed (expected ≥3). "
            f"Unique values: {sorted(unique_values)[:10]} (showing first 10). "
            f"This suggests DARK floor noise sigma is too small or bias is missing."
        )

        print(f"✓ {ch}: DARK has {n_unique} unique values (non-degenerate)")


@pytest.mark.contracts
def test_dark_stays_dark():
    """
    Contract: DARK must remain dark (not accidentally brightened).

    Requirement: mean(DARK) < 0.01 * mean(dye_low) per channel.
    This ensures detector bias fix didn't make DARK unrealistically bright.

    Fails if:
      - DARK mean is more than 1% of dye_low mean
      - This would indicate bias is too large or applied incorrectly
    """
    obs_path = Path("results/cal_beads_dyes_seed42_darkfix/observations.jsonl")
    if not obs_path.exists():
        pytest.skip("Bead plate observations not found; run calibration first")

    observations = load_bead_plate_observations(obs_path)
    dark_wells = get_dark_wells(observations)
    dye_low_wells = get_dye_low_wells(observations)

    if not dark_wells:
        pytest.fail("No DARK wells found in observations")
    if not dye_low_wells:
        pytest.fail("No FLATFIELD_DYE_LOW wells found in observations")

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        # Compute mean DARK
        dark_values = [obs['morphology'][ch] for obs in dark_wells]
        mean_dark = sum(dark_values) / len(dark_values)

        # Compute mean dye_low
        dye_low_values = [obs['morphology'][ch] for obs in dye_low_wells]
        mean_dye_low = sum(dye_low_values) / len(dye_low_values)

        # Contract: DARK < 1% of dye_low
        threshold = 0.01 * mean_dye_low
        assert mean_dark < threshold, (
            f"DARK stays dark FAILED for {ch}: "
            f"mean_dark={mean_dark:.2f} AU ≥ 1% of mean_dye_low={mean_dye_low:.2f} AU. "
            f"Threshold: {threshold:.2f} AU. "
            f"This suggests detector bias is too large or applied incorrectly."
        )

        ratio = mean_dark / mean_dye_low
        print(f"✓ {ch}: DARK mean={mean_dark:.2f} AU ({ratio*100:.3f}% of dye_low={mean_dye_low:.1f} AU)")


@pytest.mark.contracts
def test_dark_has_positive_mean():
    """
    Contract: DARK must have positive mean (bias is applied).

    Requirement: mean(DARK) > 0 per channel.
    This ensures detector bias is actually being applied.

    Fails if:
      - DARK mean is ≤ 0 (bias not applied or clamp removed positive values)
    """
    obs_path = Path("results/cal_beads_dyes_seed42_darkfix/observations.jsonl")
    if not obs_path.exists():
        pytest.skip("Bead plate observations not found; run calibration first")

    observations = load_bead_plate_observations(obs_path)
    dark_wells = get_dark_wells(observations)

    if not dark_wells:
        pytest.fail("No DARK wells found in observations")

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        # Extract all DARK values for this channel
        dark_values = [obs['morphology'][ch] for obs in dark_wells]
        mean_dark = sum(dark_values) / len(dark_values)

        # Contract: mean > 0
        assert mean_dark > 0, (
            f"DARK positive mean FAILED for {ch}: "
            f"mean_dark={mean_dark:.4f} ≤ 0. "
            f"This suggests detector bias is not being applied or clamp is wrong."
        )

        print(f"✓ {ch}: DARK mean={mean_dark:.3f} AU (positive baseline)")


@pytest.mark.contracts
def test_dark_has_positive_std():
    """
    Contract: DARK must have positive standard deviation (noise is applied).

    Requirement: std(DARK) > 0 per channel.
    This ensures additive floor noise is actually being applied.

    Fails if:
      - DARK std is ≤ 0 (no variance, noise not applied or too small)
    """
    obs_path = Path("results/cal_beads_dyes_seed42_darkfix/observations.jsonl")
    if not obs_path.exists():
        pytest.skip("Bead plate observations not found; run calibration first")

    observations = load_bead_plate_observations(obs_path)
    dark_wells = get_dark_wells(observations)

    if not dark_wells:
        pytest.fail("No DARK wells found in observations")

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for ch in channels:
        # Extract all DARK values for this channel
        dark_values = [obs['morphology'][ch] for obs in dark_wells]

        # Compute std
        mean_dark = sum(dark_values) / len(dark_values)
        variance = sum((x - mean_dark) ** 2 for x in dark_values) / len(dark_values)
        std_dark = variance ** 0.5

        # Contract: std > 0
        assert std_dark > 0, (
            f"DARK positive std FAILED for {ch}: "
            f"std_dark={std_dark:.6f} ≤ 0. "
            f"This suggests additive floor noise sigma is 0 or too small."
        )

        print(f"✓ {ch}: DARK std={std_dark:.3f} AU (observable noise)")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
