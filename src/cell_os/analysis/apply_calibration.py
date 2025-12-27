#!/usr/bin/env python3
"""
Apply Calibration - Pure function to apply calibration corrections to observations.

Read-only transformation: raw observations -> calibrated observations
No state mutation, no config changes, no side effects.

CLI usage:
    python -m src.cell_os.analysis.apply_calibration \
        --obs results/cal_beads_dyes_seed42/observations.jsonl \
        --calibration results/cal_beads_dyes_seed42/calibration/calibration_report.json \
        --out results/cal_beads_dyes_seed42/observations_calibrated.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.cell_os.calibration.profile import CalibrationProfile


def apply_calibration_to_observation(
    obs: Dict[str, Any],
    profile: CalibrationProfile
) -> Dict[str, Any]:
    """
    Apply calibration corrections to a single observation.

    Creates derived fields:
      - morphology_corrected: Vignette-corrected morphology
      - calibration: Metadata block documenting applied corrections

    Original morphology remains unchanged (read-only).

    Args:
        obs: Raw observation dict
        profile: CalibrationProfile instance

    Returns:
        Observation with added calibrated fields
    """
    # Copy observation (non-destructive)
    obs_cal = obs.copy()

    # Extract raw morphology and well_id
    morphology_raw = obs.get("morphology", {})
    well_id = obs.get("well_id")

    if not morphology_raw or not well_id:
        # Cannot apply correction without morphology or well_id
        obs_cal["morphology_corrected"] = morphology_raw
        obs_cal["calibration"] = {
            "applied": False,
            "reason": "Missing morphology or well_id"
        }
        return obs_cal

    # Apply vignette correction
    morphology_corrected = profile.correct_morphology(morphology_raw, well_id)

    # Add corrected morphology as new field
    obs_cal["morphology_corrected"] = morphology_corrected

    # Stamp calibration metadata
    obs_cal["calibration"] = profile.calibration_metadata()
    obs_cal["calibration"]["applied"] = True

    # Add saturation warnings if near safe max
    warnings = []
    for ch, val in morphology_corrected.items():
        safe_max = profile.safe_max(ch)
        if safe_max is not None and val > safe_max * 0.9:
            confidence = profile.saturation_confidence(ch)
            warnings.append(
                f"{ch}: {val:.1f} AU near safe max {safe_max:.1f} AU (confidence: {confidence})"
            )

    if warnings:
        obs_cal["calibration"]["saturation_warnings"] = warnings

    # Add SNR warnings if signal is below noise floor threshold (Phase 4)
    # This prevents agent from learning from sub-noise signals
    snr_warnings = []
    snr_threshold_sigma = 5.0  # Conservative: require 5σ above floor

    if profile.floor_observable():
        for ch, val in morphology_corrected.items():
            is_above, reason = profile.is_above_noise_floor(val, ch, k=snr_threshold_sigma)
            if not is_above:
                snr_warnings.append(f"{ch}: {reason}")

    if snr_warnings:
        obs_cal["calibration"]["snr_warnings"] = snr_warnings
        obs_cal["calibration"]["snr_threshold_sigma"] = snr_threshold_sigma

    return obs_cal


def apply_calibration_to_jsonl(
    input_path: Path,
    calibration_path: Path,
    output_path: Path
) -> None:
    """
    Apply calibration to all observations in a JSONL file.

    Args:
        input_path: Path to input observations.jsonl
        calibration_path: Path to calibration_report.json
        output_path: Path to output observations_calibrated.jsonl
    """
    # Load calibration profile
    print(f"Loading calibration: {calibration_path}")
    profile = CalibrationProfile(calibration_path)
    print(f"  Schema: {profile.schema_version}")
    print(f"  Vignette observable: {profile._vignette.get('observable')}")
    print(f"  Saturation observable: {profile._saturation.get('observable')}")
    print(f"  Quantization observable: {profile._quantization.get('observable')}")
    print(f"  Floor observable: {profile.floor_observable()}")

    # Read input observations
    print(f"\nReading observations: {input_path}")
    observations = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            observations.append(json.loads(line))
    print(f"  Loaded {len(observations)} observations")

    # Apply calibration
    print(f"\nApplying calibration corrections...")
    calibrated_observations = []
    for i, obs in enumerate(observations):
        obs_cal = apply_calibration_to_observation(obs, profile)
        calibrated_observations.append(obs_cal)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(observations)} observations")

    # Write output
    print(f"\nWriting calibrated observations: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        for obs_cal in calibrated_observations:
            f.write(json.dumps(obs_cal) + '\n')

    print(f"✓ Done! {len(calibrated_observations)} observations calibrated")

    # Summary statistics
    vignette_applied = sum(1 for o in calibrated_observations if o.get("calibration", {}).get("vignette_applied"))
    with_warnings = sum(1 for o in calibrated_observations if "saturation_warnings" in o.get("calibration", {}))

    print(f"\nSummary:")
    print(f"  Vignette applied: {vignette_applied}/{len(calibrated_observations)}")
    print(f"  Saturation warnings: {with_warnings}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply calibration corrections to observations (read-only, creates derived fields)"
    )
    parser.add_argument("--obs", required=True, help="Path to input observations.jsonl")
    parser.add_argument("--calibration", required=True, help="Path to calibration_report.json")
    parser.add_argument("--out", required=True, help="Path to output observations_calibrated.jsonl")

    args = parser.parse_args()

    apply_calibration_to_jsonl(
        input_path=Path(args.obs),
        calibration_path=Path(args.calibration),
        output_path=Path(args.out),
    )


if __name__ == "__main__":
    main()
