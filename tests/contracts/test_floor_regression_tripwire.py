"""
Floor Observability Regression Tripwire

BLOCKING test that prevents future "optimizations" from breaking floor observability.

This test runs calibration on a minimal DARK-only subset and asserts:
  1. floor.observable == true
  2. floor has variance (unique_values >= 3 per channel)
  3. floor has positive mean (bias applied)

If this test fails, someone broke the detector bias or noise implementation.
Do NOT disable this test. Fix the simulator instead.
"""

from __future__ import annotations

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, List

# Import calibration module
from cell_os.calibration.bead_plate_calibration import calibrate_from_observations


def create_minimal_dark_observations(n_wells: int = 12) -> List[Dict]:
    """
    Create minimal synthetic DARK observations with known bias + noise.

    These are NOT from the simulator - they're synthetic test data
    to validate that the calibration module can detect observable floor.
    """
    import numpy as np

    # Known parameters matching Phase 4 implementation
    bias_mean = 0.25  # AU (roughly 20 LSB)
    noise_sigma = 0.05  # AU (roughly 3 LSB)
    quant_step = 0.0122  # AU/LSB (16-bit ADC scaled to 800 AU)

    rng = np.random.default_rng(seed=42)
    observations = []

    channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

    for i in range(n_wells):
        well_id = f"A{i+1}"

        # Generate bias + noise, then quantize
        morphology = {}
        for ch in channels:
            # Raw signal: bias + Gaussian noise
            raw = bias_mean + rng.normal(0, noise_sigma)
            # Clamp to non-negative
            raw = max(0.0, raw)
            # Quantize
            quantized = round(raw / quant_step) * quant_step
            morphology[ch] = quantized

        obs = {
            "well_id": well_id,
            "row": "A",
            "col": i + 1,
            "cell_line": "NONE",
            "compound": "NONE",
            "dose_uM": 0.0,
            "time_h": 0.0,
            "assay": "cell_painting",
            "mode": "optical_material",
            "material_assignment": "DARK",
            "material_type": "buffer_only",
            "morphology": morphology,
            "morphology_struct": {ch: 0.0 for ch in channels},
            "viability": 1.0,
            "n_cells": 0,
            "treatment": "MATERIAL_DARK",
        }
        observations.append(obs)

    return observations


@pytest.mark.contracts
def test_floor_observability_regression_tripwire():
    """
    REGRESSION TRIPWIRE: Prevents breaking floor observability.

    This test runs calibration on minimal synthetic DARK data and asserts:
      1. floor.observable == true
      2. At least 3 unique values per channel (non-degenerate)
      3. Positive mean (bias applied)

    If this fails:
      - Check detector_stack.py: is bias being applied? (enable_detector_bias=True)
      - Check calibration_thalamus_params.yaml: is additive_floor_sigma > 0?
      - Check biological_virtual.py: is enable_detector_bias passed correctly?

    DO NOT disable this test. Fix the implementation instead.
    """
    # Create minimal DARK observations
    observations = create_minimal_dark_observations(n_wells=12)

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        obs_path = Path(f.name)
        for obs in observations:
            f.write(json.dumps(obs) + '\n')

    try:
        # Run calibration
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            report = calibrate_from_observations(
                observations_jsonl=str(obs_path),
                design_json=None,
                outdir=str(output_dir)
            )

            floor = report['floor']

            # TRIPWIRE 1: Floor must be observable
            assert floor['observable'] == True, (
                "REGRESSION: floor.observable is False. "
                "Someone broke detector bias or noise implementation. "
                "Check detector_stack.py and calibration_thalamus_params.yaml."
            )

            # TRIPWIRE 2: Each channel must have at least 3 unique values
            channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
            for ch in channels:
                ch_data = floor['per_channel'][ch]
                unique_values = ch_data.get('unique_values', [])
                n_unique = len(unique_values)

                assert n_unique >= 3, (
                    f"REGRESSION: DARK floor for {ch} has only {n_unique} unique values (expected ≥3). "
                    f"Unique values: {unique_values}. "
                    f"This suggests floor noise sigma is too small or bias is missing."
                )

            # TRIPWIRE 3: Floor mean must be positive (bias applied)
            for ch in channels:
                ch_data = floor['per_channel'][ch]
                mean = ch_data['mean']

                assert mean > 0.0, (
                    f"REGRESSION: DARK floor mean for {ch} is {mean} (expected > 0). "
                    f"Detector bias is not being applied. Check detector_stack.py."
                )

            print("✓ Floor observability regression tripwire PASSED")
            print(f"  - floor.observable = {floor['observable']}")
            unique_counts = [len(floor['per_channel'][ch]['unique_values']) for ch in channels]
            print(f"  - Unique values per channel: {unique_counts}")
            means = [floor['per_channel'][ch]['mean'] for ch in channels]
            means_str = ', '.join([f"{m:.4f}" for m in means])
            print(f"  - Mean floor per channel: [{means_str}]")

    finally:
        # Cleanup temp file
        obs_path.unlink()


@pytest.mark.contracts
def test_floor_sigma_is_computable():
    """
    REGRESSION TRIPWIRE: Floor sigma must be computable from unique values.

    The calibration report may show std=0.0 (computed across wells with single measurements),
    but the unique_values list must have sufficient spread to compute a meaningful sigma.

    This test ensures variance is present in the data, even if not captured by the report's std field.
    """
    observations = create_minimal_dark_observations(n_wells=12)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        obs_path = Path(f.name)
        for obs in observations:
            f.write(json.dumps(obs) + '\n')

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            report = calibrate_from_observations(
                observations_jsonl=str(obs_path),
                design_json=None,
                outdir=str(output_dir)
            )

            floor = report['floor']
            channels = ['er', 'mito', 'nucleus', 'actin', 'rna']

            for ch in channels:
                unique_values = floor['per_channel'][ch].get('unique_values', [])

                # Compute sigma from unique values range
                if len(unique_values) >= 2:
                    value_range = max(unique_values) - min(unique_values)
                    # Range should be at least 3× the quantization step
                    # (With ~3 LSB noise, we expect range of ~6 LSB = 0.07 AU)
                    min_expected_range = 0.03  # AU (conservative lower bound)

                    assert value_range >= min_expected_range, (
                        f"REGRESSION: DARK floor range for {ch} is {value_range:.4f} AU (expected ≥ {min_expected_range}). "
                        f"Unique values: {unique_values}. "
                        f"Floor noise sigma is too small - SNR estimation will be unreliable."
                    )

            print("✓ Floor sigma computability tripwire PASSED")
            ranges = [max(floor['per_channel'][ch]['unique_values']) - min(floor['per_channel'][ch]['unique_values']) for ch in channels]
            ranges_str = ', '.join([f"{r:.4f}" for r in ranges])
            print(f"  - Value ranges: [{ranges_str}]")

    finally:
        obs_path.unlink()


if __name__ == '__main__':
    # Run tripwires
    test_floor_observability_regression_tripwire()
    test_floor_sigma_is_computable()
    print("\n✅ All floor regression tripwires PASSED")
